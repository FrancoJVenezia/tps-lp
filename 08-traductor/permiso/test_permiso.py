"""TestSuite del lenguaje permiso (pytest).

- Programas válidos: se traducen con el LLM y se EJECUTA el módulo JavaScript generado con Node,
  verificando qué responde (no el texto exacto, porque la redacción del LLM puede variar).
- Middleware de Express: se simulan pedidos y se verifica que responda 401, 403 o deje pasar; y se levanta
  un servidor Express real con el módulo generado y se le hacen pedidos HTTP.
- Tabla esperada: el cálculo de permisos con herencia y excepciones que hace el parser.
- Errores léxicos, sintácticos y semánticos: se verifica el tipo de error y el mensaje.
- Programa completo por consola (main.py), como lo usaría un programador.
Ejecutar desde esta carpeta:  python -m pytest -v test_permiso.py
"""
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

CARPETA = Path(__file__).parent
sys.path.insert(0, str(CARPETA))
from parser_permiso import analizar, tabla_esperada, ErrorPermiso
from traductor_permiso import traducir
from agente_permiso import ejecutar_node

EJEMPLOS = CARPETA / 'ejemplos'


def leer(nombre):
    return (EJEMPLOS / nombre).read_text(encoding='utf-8')


def consultar(modulo, preguntas):
    """Ejecuta el módulo generado con Node y devuelve lo que responde puede() para cada (rol, acción, recurso)."""
    codigo = (modulo.replace('module.exports', 'const m') +
              f'\nprocess.stdout.write(JSON.stringify({json.dumps(preguntas, ensure_ascii=False)}'
              '.map(([r, a, x]) => m.puede(r, a, x))));')
    ok, salida = ejecutar_node(codigo)
    assert ok, salida
    return json.loads(salida)


def pedido_express(modulo, usuario, accion, recurso):
    """Simula un pedido a una ruta protegida con exigir(accion, recurso). Devuelve 'siguiente' o el estado HTTP."""
    req = json.dumps({'usuario': usuario} if usuario else {}, ensure_ascii=False)
    codigo = (modulo.replace('module.exports', 'const m') +
              f'\nlet r = null;\n'
              'const res = { status(n) { return { send() { r = n; } }; } };\n'
              f'm.exigir({json.dumps(accion)}, {json.dumps(recurso, ensure_ascii=False)})({req}, res, () => {{ r = "siguiente"; }});\n'
              'process.stdout.write(JSON.stringify(r));')
    ok, salida = ejecutar_node(codigo)
    assert ok, salida
    return json.loads(salida)


# ================================================================ programas válidos (con el LLM)

def test_minimo():
    m = traducir(leer('01_minimo.permiso'))
    assert consultar(m, [['lector', 'ver', 'articulos'], ['lector', 'editar', 'articulos'],
                         ['admin', 'ver', 'articulos']]) == [True, False, False]


def test_tienda_herencia_en_cadena_todo_y_excepciones():
    m = traducir(leer('02_tienda.permiso'))
    assert consultar(m, [
        ['invitado', 'ver', 'productos'],     # propio
        ['invitado', 'crear', 'pedidos'],     # no lo tiene
        ['cliente', 'ver', 'productos'],      # heredado de invitado
        ['admin', 'crear', 'pedidos'],        # heredado de cliente
        ['admin', 'editar', 'productos'],     # 'todo' incluye editar
        ['cliente', 'borrar', 'pedidos'],     # solo lo tiene admin
        ['pasante', 'editar', 'productos'],   # heredado de admin
        ['pasante', 'borrar', 'productos'],   # excepción: no puede, aunque admin sí
        ['pasante', 'borrar', 'pedidos'],     # excepción
    ]) == [True, False, True, True, True, False, True, False, False]


def test_hospital_recursos_con_espacios_y_tildes():
    m = traducir(leer('03_hospital.permiso'))
    assert consultar(m, [
        ['director', 'ver', 'historias clínicas'],   # director → médico → enfermero
        ['director', 'borrar', 'turnos'],            # ... → recepcionista: 'todo' sobre turnos
        ['enfermero', 'editar', 'historias clínicas'],
        ['paciente', 'editar', 'turnos'],
        ['residente', 'crear', 'recetas'],           # excepción sobre lo heredado de médico
        ['residente', 'editar', 'historias clínicas'],
        ['director', 'crear', 'recetas'],            # director hereda de médico, no de residente
    ]) == [True, True, False, False, False, True, True]


def test_foro_rol_sin_herencia():
    m = traducir(leer('04_foro.permiso'))
    assert consultar(m, [['bot', 'borrar', 'respuestas'], ['bot', 'ver', 'temas'],
                         ['moderador', 'ver', 'respuestas']]) == [True, False, True]


def test_campus_todo_menos_una_accion_en_el_mismo_rol():
    m = traducir(leer('05_campus.permiso'))
    assert consultar(m, [['profesor', 'editar', 'notas'], ['profesor', 'borrar', 'notas'],
                         ['profesor', 'borrar', 'materias'], ['suspendido', 'ver', 'notas'],
                         ['suspendido', 'crear', 'entregas']]) == [True, False, True, True, False]


@pytest.mark.parametrize('ejemplo', ['01_minimo', '02_tienda', '03_hospital', '04_foro', '05_campus'])
def test_todas_las_combinaciones_coinciden_con_la_tabla(ejemplo):
    texto = leer(f'{ejemplo}.permiso')
    tabla = tabla_esperada(analizar(texto))
    recursos = sorted({x for permisos in tabla.values() for x in permisos})
    preguntas = [[r, a, x] for r in tabla for a in ('ver', 'crear', 'editar', 'borrar') for x in recursos]
    esperado = [a in tabla[r].get(x, set()) for r, a, x in preguntas]
    assert consultar(traducir(texto), preguntas) == esperado


# ================================================================ middleware de Express

def test_middleware_401_403_y_siguiente():
    m = traducir(leer('02_tienda.permiso'))
    assert pedido_express(m, None, 'crear', 'pedidos') == 401
    assert pedido_express(m, {'rol': 'invitado'}, 'crear', 'pedidos') == 403
    assert pedido_express(m, {'rol': 'cliente'}, 'crear', 'pedidos') == 'siguiente'
    assert pedido_express(m, {'rol': 'admin'}, 'borrar', 'productos') == 'siguiente'


def test_modulo_formateado():
    m = traducir(leer('02_tienda.permiso'))
    assert m.startswith("// Permisos de 'Tienda'")
    assert 'const PERMISOS = {' in m and m.rstrip().endswith('module.exports = { PERMISOS, puede, exigir };')
    assert m.count('function contiene(') == 1 and m.count('function puede(') == 1 and m.count('function exigir(') == 1
    assert "noPuede" in m                                   # el pasante tiene excepciones


def servidor_disponible():
    ok, _ = ejecutar_node(f"require.resolve('express', {{ paths: [{json.dumps(str(CARPETA))}] }});")
    return ok


@pytest.mark.skipif(not servidor_disponible(), reason='Express no está instalado (npm install express)')
def test_servidor_express_real(tmp_path):
    modulo = tmp_path / 'tienda.permiso.js'
    modulo.write_text(traducir(leer('02_tienda.permiso')), encoding='utf-8')
    puerto = '3471'
    servidor = subprocess.Popen(['node', str(CARPETA / 'servidor_tienda.js'), str(modulo), puerto],
                                stdout=subprocess.PIPE, text=True, encoding='utf-8')
    try:
        assert 'escuchando' in servidor.stdout.readline()

        def estado(metodo, ruta, rol=None):
            pedido = urllib.request.Request(f'http://127.0.0.1:{puerto}{ruta}', method=metodo,
                                            headers={'X-Rol': rol} if rol else {})
            try:
                with urllib.request.urlopen(pedido) as r:
                    return r.status
            except urllib.error.HTTPError as e:
                return e.code

        assert estado('GET', '/productos') == 401
        assert estado('POST', '/pedidos', 'invitado') == 403
        assert estado('POST', '/pedidos', 'cliente') == 201
        assert estado('DELETE', '/productos/7', 'admin') == 200
        assert estado('DELETE', '/productos/7', 'pasante') == 403
        assert estado('PUT', '/productos/7', 'pasante') == 200
    finally:
        servidor.terminate()


# ================================================================ tabla esperada (parser, sin LLM)

def test_tabla_esperada_aplica_herencia_todo_y_excepciones():
    tabla = tabla_esperada(analizar(leer('02_tienda.permiso')))
    assert tabla['invitado'] == {'productos': {'ver'}}
    assert tabla['cliente'] == {'productos': {'ver'}, 'pedidos': {'crear', 'ver'}}
    assert tabla['admin'] == {'productos': {'ver', 'crear', 'editar', 'borrar'}, 'pedidos': {'crear', 'ver', 'borrar'}}
    assert tabla['pasante'] == {'productos': {'ver', 'crear', 'editar'}, 'pedidos': {'crear', 'ver'}}


def test_la_excepcion_se_hereda_y_lo_propio_gana():
    tabla = tabla_esperada(analizar(
        "permisos 'App'\n"
        "  rol 'a'\n    puede todo 'x'\n"
        "  rol 'b' hereda 'a'\n    no puede borrar 'x'\n"
        "  rol 'c' hereda 'b'\n    puede ver 'y'\n"            # hereda la excepción de b
        "  rol 'd' hereda 'b'\n    puede borrar 'x'\n"))        # lo propio de d le gana a la excepción de b
    assert tabla['c'] == {'x': {'ver', 'crear', 'editar'}, 'y': {'ver'}}
    assert tabla['d'] == {'x': {'ver', 'crear', 'editar', 'borrar'}}


# ================================================================ errores léxicos

E = "permisos 'App'\n  rol 'a'\n"


@pytest.mark.parametrize('programa, mensaje', [
    (E + "     puede ver 'x'\n", 'Sangría de 5 espacios'),
    (E + "    puede\tver 'x'\n", 'No se permiten tabulaciones'),
    (E + "    puede ver 'x\n", 'Cadena sin cerrar'),
    (E + "    puede leer 'x'\n", "Palabra desconocida: 'leer'"),
    (E + "    puede ver \"x\"\n", "Carácter no reconocido: '\"'"),
    ("permisos 'App'\n  rol 'a'\n      puede ver 'x'\n", 'sube más de un nivel'),
], ids=['sangria_impar', 'tabulacion', 'cadena_sin_cerrar', 'accion_desconocida', 'comillas_dobles', 'salto_de_nivel'])
def test_errores_lexicos(programa, mensaje):
    with pytest.raises(ErrorPermiso) as e:
        analizar(programa)
    assert e.value.tipo == 'léxico'
    assert any(mensaje in m for _, m in e.value.errores)


# ================================================================ errores sintácticos

@pytest.mark.parametrize('programa, linea', [
    (E, 3),                                                           # rol sin permisos
    ("permisos 'App'\n", None),                                       # programa sin roles
    (E + "    puede ver\n", 3),                                       # falta el recurso
    (E + "    puede 'x'\n", 3),                                       # falta la acción
    (E + "    puede ver 'x'\n    rol 'b'\n      puede ver 'x'\n", 4),  # rol dentro de un rol
    ("rol 'a'\n  puede ver 'x'\n", 1),                                # falta el encabezado permisos
    ("permisos 'App'\n  rol 'a' hereda\n    puede ver 'x'\n", 2),     # hereda sin el nombre del rol
    (E + "    no ver 'x'\n", 3),                                      # excepción sin 'puede'
    (E + "    puede no ver 'x'\n", 3),                                # 'no' en otro lugar
], ids=['rol_sin_permisos', 'sin_roles', 'falta_recurso', 'falta_accion', 'rol_dentro_de_rol', 'sin_encabezado',
        'hereda_sin_nombre', 'no_sin_puede', 'no_despues_de_puede'])
def test_errores_sintacticos(programa, linea):
    with pytest.raises(ErrorPermiso) as e:
        analizar(programa)
    assert e.value.tipo == 'sintáctico'
    assert e.value.errores[0][0] == linea


# ================================================================ errores semánticos

def rol(nombre, hereda=None, permiso="puede ver 'x'"):
    return f"  rol '{nombre}'" + (f" hereda '{hereda}'" if hereda else '') + f"\n    {permiso}\n"


@pytest.mark.parametrize('roles, mensaje', [
    (rol('a') + rol('a'), "El rol 'a' ya se definió en la línea 2"),
    (rol('a', 'z'), "hereda de 'z', que no existe"),
    (rol('a', 'a'), 'no puede heredar de sí mismo'),
    (rol('a', 'b') + rol('b', 'a'), "Herencia circular: 'a' → 'b' → 'a'"),
    (rol('a', 'c') + rol('b', 'a') + rol('c', 'b'), "Herencia circular: 'a' → 'c' → 'b' → 'a'"),
    ("  rol 'a'\n    puede ver 'x'\n    puede ver 'x'\n", 'ya está en la línea 3'),
    ("  rol 'a'\n    puede ver 'x'\n    no puede ver 'x'\n", 'Contradicción'),
    ("  rol 'a'\n    puede ver 'x'\n    no puede todo 'x'\n", 'Contradicción'),
    (rol('a', permiso="puede todo 'x'") + rol('b', 'a', "no puede ver 'y'"), 'no hace falta'),
    (rol('a') + rol('b', 'a', "no puede borrar 'x'"), 'no hace falta'),
], ids=['rol_repetido', 'hereda_inexistente', 'hereda_de_si_mismo', 'circular_directa', 'circular_indirecta',
        'permiso_repetido', 'contradiccion', 'contradiccion_con_todo', 'excepcion_sobre_otro_recurso',
        'excepcion_de_algo_no_heredado'])
def test_errores_semanticos(roles, mensaje):
    with pytest.raises(ErrorPermiso) as e:
        analizar("permisos 'App'\n" + roles)
    assert e.value.tipo == 'semántico'
    assert any(mensaje in m for _, m in e.value.errores)


def test_varios_errores_semanticos_se_informan_juntos():
    with pytest.raises(ErrorPermiso) as e:
        analizar(leer('08_error_semantico.permiso'))
    assert [l for l, _ in e.value.errores] == [2, 6, 10]


def test_casos_validos_que_no_son_error():
    # mismo recurso con acciones distintas
    assert len(analizar("permisos 'App'\n  rol 'a'\n    puede ver 'x'\n    puede crear 'x'\n")['roles'][0]['permisos']) == 2
    # 'todo' menos una acción, en el mismo rol
    analizar("permisos 'App'\n  rol 'a'\n    puede todo 'x'\n    no puede borrar 'x'\n")
    # 'no puede todo' sobre algo heredado: el rol pierde el recurso entero
    analizar("permisos 'App'\n  rol 'a'\n    puede ver 'x'\n  rol 'b' hereda 'a'\n    no puede todo 'x'\n")


# ================================================================ programa por consola (main.py)

def ejecutar_main(tmp_path, programa):
    fuente = tmp_path / 'prueba.permiso'
    fuente.write_text(programa, encoding='utf-8')
    r = subprocess.run([sys.executable, str(CARPETA / 'main.py'), str(fuente)],
                       capture_output=True, text=True, encoding='utf-8')
    return r, tmp_path / 'prueba.permiso.js'


def test_main_caso_feliz(tmp_path):
    r, salida = ejecutar_main(tmp_path, leer('01_minimo.permiso'))
    assert r.returncode == 0
    assert salida.exists()
    ok, _ = ejecutar_node(salida.read_text(encoding='utf-8'))   # el archivo generado se ejecuta sin errores
    assert ok


def test_main_caso_con_error(tmp_path):
    r, salida = ejecutar_main(tmp_path, leer('08_error_semantico.permiso'))
    assert r.returncode == 1
    assert 'Error semántico' in r.stdout and 'línea 2' in r.stdout and 'Herencia circular' in r.stdout
    assert not salida.exists()
