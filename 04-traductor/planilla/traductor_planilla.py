"""Traductor planilla: programa fuente -> documento HTML formateado.

1. Análisis (lexer + parser + controles semánticos): arma el árbol o informa errores.
2. Generación: recorre el árbol y le pide al agente (LLM) el HTML de cada parte y el CSS del tema.
3. Armado y formateo: une las partes y escribe el HTML con sangría prolija.
"""
import html
import re
import unicodedata
from bs4 import BeautifulSoup, NavigableString

import agente_planilla as agente
from parser_planilla import analizar, campos_de


# ---------------------------------------------------------------- identificadores de los campos

def a_identificador(texto):
    """'Fecha de nacimiento' -> 'fecha_de_nacimiento' (sin tildes ni símbolos)."""
    sin_tildes = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '_', sin_tildes.lower()).strip('_') or 'campo'


def asignar_ids(arbol):
    ids, usados = {}, set()
    for campo in campos_de(arbol['cuerpo']):
        base = a_identificador(campo['atributos']['nombre'])
        candidato, n = base, 2
        while candidato in usados:
            candidato, n = f'{base}_{n}', n + 1
        usados.add(candidato)
        ids[id(campo)] = candidato
    return ids


# ---------------------------------------------------------------- generación (recorre el árbol)

def generar_bloque(bloque, ids, avisar):
    if bloque['tipo'] == 'campo':
        avisar(f"  campo {bloque['control']} '{bloque['atributos']['nombre']}'")
        return agente.generar_campo(bloque, ids[id(bloque)])
    if bloque['tipo'] == 'fila':
        avisar('  fila')
        hijos = ''.join(generar_bloque(c, ids, avisar) for c in bloque['campos'])
        return agente.generar_fila().replace(agente.MARCA, hijos)
    avisar(f"  sección '{bloque['titulo']}'")
    hijos = ''.join(generar_bloque(e, ids, avisar) for e in bloque['elementos'])
    return agente.generar_seccion(bloque['titulo']).replace(agente.MARCA, hijos)


def traducir(texto, avisar=lambda mensaje: None):
    """Traduce un programa planilla a un documento HTML. Lanza ErrorPlanilla si el programa tiene errores."""
    arbol = analizar(texto)
    ids = asignar_ids(arbol)
    avisar(f"formulario '{arbol['titulo']}' (tema {arbol['tema']})")
    cuerpo = ''.join(generar_bloque(b, ids, avisar) for b in arbol['cuerpo'])
    avisar(f"  botón '{arbol['boton']}'")
    cuerpo += agente.generar_boton(arbol['boton'])
    form = agente.generar_formulario(arbol['titulo'], arbol['metodo'], arbol['ruta'], arbol['tema'])
    form = form.replace(agente.MARCA, cuerpo)
    avisar('  estilos')
    css = agente.generar_css(arbol['tema'])
    return armar_documento(arbol['titulo'], css, form)


# ---------------------------------------------------------------- armado y formateo

# Estructura fija del estilo card (la misma para todos los temas; los colores los genera el LLM).
CSS_BASE = '''
* { box-sizing: border-box; }
body { margin: 0; padding: 40px 16px; font-family: system-ui, Segoe UI, Arial, sans-serif; }
.card { max-width: 520px; margin: 0 auto; padding: 24px 28px; border-radius: 12px; box-shadow: 0 4px 18px rgba(0, 0, 0, 0.15); }
.card h2 { margin: 0 0 18px; }
fieldset { border: 1px solid; border-radius: 8px; padding: 10px 16px 2px; margin: 0 0 18px; }
legend { padding: 0 6px; font-weight: 600; }
.campo { display: flex; flex-direction: column; gap: 6px; margin-bottom: 14px; }
.campo input, .campo select, .campo textarea { width: 100%; padding: 8px 10px; border: 1px solid; border-radius: 6px; font: inherit; }
.campo textarea { min-height: 80px; resize: vertical; }
.campo:has(input[type="checkbox"]) { flex-direction: row; align-items: center; }
.campo input[type="checkbox"] { width: auto; margin: 0; }
.fila { display: flex; gap: 16px; }
.fila .campo { flex: 1; min-width: 0; }
.ayuda { font-size: 0.85em; opacity: 0.8; }
button { padding: 10px 22px; border: none; border-radius: 6px; font: inherit; font-weight: 600; cursor: pointer; }
'''

EN_UNA_LINEA = {'label', 'legend', 'option', 'button', 'h2', 'small', 'title'}
SIN_CIERRE = {'input', 'meta', 'br'}
SANGRIA = '  '


def _atributos(tag):
    partes = []
    for clave, valor in tag.attrs.items():
        if isinstance(valor, list):
            valor = ' '.join(valor)
        valor = valor.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;')
        partes.append(clave if valor == '' else f'{clave}="{valor}"')
    return (' ' + ' '.join(partes)) if partes else ''


def formatear_html(nodo, nivel=0):
    """Escribe cada elemento en su propia línea, con 2 espacios de sangría por nivel."""
    lineas, pre = [], SANGRIA * nivel
    for hijo in nodo.children:
        if isinstance(hijo, NavigableString):
            if hijo.strip():
                lineas.append(pre + html.escape(hijo.strip(), quote=False))
            continue
        apertura = f'<{hijo.name}{_atributos(hijo)}>'
        if hijo.name in SIN_CIERRE:
            lineas.append(pre + apertura)
        elif hijo.name in EN_UNA_LINEA or not any(not isinstance(c, NavigableString) for c in hijo.children):
            lineas.append(f'{pre}{apertura}{html.escape(hijo.get_text(" ", strip=True), quote=False)}</{hijo.name}>')
        else:
            lineas.append(pre + apertura)
            lineas.extend(formatear_html(hijo, nivel + 1))
            lineas.append(f'{pre}</{hijo.name}>')
    return lineas


def formatear_css(css, nivel):
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    pre, lineas = SANGRIA * nivel, []
    for selector, declaraciones in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
        lineas.append(f"{pre}{' '.join(selector.split())} {{")
        for d in declaraciones.split(';'):
            if d.strip():
                lineas.append(f"{pre}{SANGRIA}{' '.join(d.split())};")
        lineas.append(f'{pre}}}')
        lineas.append('')
    return lineas[:-1]


def armar_documento(titulo, css, form):
    lineas = ['<!DOCTYPE html>', '<html lang="es">', '  <head>', '    <meta charset="utf-8">',
              f'    <title>{html.escape(titulo)}</title>', '    <style>']
    lineas += formatear_css(CSS_BASE, 3) + [''] + ['      /* colores del tema (generados por el LLM) */'] + formatear_css(css, 3)
    lineas += ['    </style>', '  </head>', '  <body>']
    lineas += formatear_html(BeautifulSoup(form, 'html.parser'), 2)
    lineas += ['  </body>', '</html>']
    return '\n'.join(lineas) + '\n'
