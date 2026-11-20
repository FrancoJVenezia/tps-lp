"""Traductor permiso: programa fuente -> módulo JavaScript de permisos.

1. Análisis (lexer + parser + controles semánticos): arma el árbol o informa errores.
2. Generación: recorre el árbol y le pide al agente (LLM) el código de cada rol y de las funciones.
3. Armado y verificación final: une las partes y ejecuta el módulo completo con Node, comparando
   TODAS las combinaciones de rol, acción y recurso con la tabla que calculó el parser.
"""
import json
import re

import agente_permiso as agente
from parser_permiso import analizar, tabla_esperada, recursos_de, ACCIONES

SANGRIA = '  '


def traducir(texto, avisar=lambda mensaje: None, origen='programa'):
    """Traduce un programa en permiso a un módulo JavaScript. Lanza ErrorPermiso si el programa tiene errores."""
    arbol = analizar(texto)
    avisar(f"permisos '{arbol['aplicacion']}'")
    entradas = []
    for rol in arbol['roles']:
        excepciones = sum(p['negado'] for p in rol['permisos'])
        avisar(f"  rol '{rol['nombre']}'" + (f" (hereda de '{rol['hereda']}')" if rol['hereda'] else '')
               + (f" con {excepciones} {'excepciones' if excepciones > 1 else 'excepción'}" if excepciones else ''))
        entradas.append(agente.generar_rol(rol))
    avisar('  función contiene')
    contiene = agente.generar_contiene()
    avisar('  función puede')
    puede = agente.generar_puede()
    avisar('  middleware exigir')
    exigir = agente.generar_exigir()
    modulo = armar_modulo(arbol, origen, entradas, [contiene, puede, exigir])
    avisar('  verificación final con Node')
    problemas = verificar_modulo(modulo, arbol)
    if problemas:
        raise agente.ErrorAgente('El módulo generado no respeta la tabla de permisos: ' + '; '.join(problemas))
    return modulo


# ---------------------------------------------------------------- armado

def armar_modulo(arbol, origen, entradas, funciones):
    lineas = [f"// Permisos de '{arbol['aplicacion']}': generado por el traductor permiso a partir de {origen}.",
              '// Uso en Express: const { exigir } = require(\'./este-archivo\');',
              "//                 app.post('/ruta', exigir('crear', 'recurso'), manejador);",
              '',
              'const PERMISOS = {']
    lineas += [SANGRIA + formatear_entrada(e) for e in entradas]
    lineas.append('};')
    for funcion in funciones:
        lineas += ['', funcion.strip()]
    lineas += ['', 'module.exports = { PERMISOS, puede, exigir };']
    return '\n'.join(lineas) + '\n'


def formatear_entrada(entrada):
    """Espaciado uniforme en las llaves ({ a } en lugar de {a}, {} si está vacío) y una coma al final de cada entrada."""
    e = re.sub(r'\{\s*', '{ ', entrada.strip().rstrip(','))
    e = re.sub(r'\s*\}', ' }', e)
    e = e.replace('{  }', '{}').replace('{ }', '{}')   # objeto vacío
    return e + ','


# ---------------------------------------------------------------- verificación final

def combinaciones(arbol):
    """Todas las preguntas rol × acción × recurso, más un recurso y un rol que no existen."""
    roles = [r['nombre'] for r in arbol['roles']] + ['rol que no existe']
    recursos = recursos_de(arbol) + ['recurso que no existe']
    return [(r, a, x) for r in roles for a in ACCIONES for x in recursos]


def verificar_modulo(modulo, arbol):
    tabla = tabla_esperada(arbol)
    casos = combinaciones(arbol)
    prueba = (modulo.replace('module.exports', 'const _exportado') +
              f'\nconst casos = {json.dumps(casos, ensure_ascii=False)};\n'
              'process.stdout.write(JSON.stringify(casos.map(([r, a, x]) => _exportado.puede(r, a, x))));')
    ok, salida = agente.ejecutar_node(prueba)
    if not ok:
        return [f'el módulo da error al ejecutarlo: {salida}']
    problemas = []
    for (rol, accion, recurso), obtenido in zip(casos, json.loads(salida)):
        esperado = accion in tabla.get(rol, {}).get(recurso, set())
        if obtenido is not esperado:
            problemas.append(f"puede('{rol}', '{accion}', '{recurso}') da {json.dumps(obtenido)}, "
                             f'tenía que dar {json.dumps(esperado)}')
    return problemas
