"""Analizador sintáctico de planilla (ply.yacc) + controles semánticos.

El parser no genera HTML: arma un árbol con los datos del formulario (diccionarios de Python)
y verifica las reglas semánticas. La generación del HTML la hace después el agente (LLM),
recorriendo ese árbol, solo si no hubo ningún error.
"""
import ply.yacc as yacc
from lexer_planilla import LexerPlanilla, tokens as _tokens_lexer

# SALTO es interno del lexer: el parser nunca lo recibe.
tokens = [t for t in _tokens_lexer if t != 'SALTO']

TIPOS_CON_MIN_MAX = {'numero'}
TIPOS_SIN_PLACEHOLDER = {'casilla', 'opciones', 'fecha'}


class ErrorPlanilla(Exception):
    """Error de traducción. tipo: 'léxico', 'sintáctico' o 'semántico'. errores: lista de (línea, mensaje)."""

    def __init__(self, tipo, errores):
        self.tipo, self.errores = tipo, errores
        detalle = '\n'.join(f'  línea {l}: {m}' for l, m in errores)
        super().__init__(f'Error {tipo}:\n{detalle}')


_errores_sintacticos = []
_errores_semanticos = []


def error_semantico(linea, mensaje):
    _errores_semanticos.append((linea, mensaje))


# ---------------------------------------------------------------- programa y encabezado

def p_programa(p):
    'programa : encabezado INDENTA cuerpo boton DESINDENTA'
    formulario = p[1]
    formulario['cuerpo'] = p[3]
    formulario['boton'] = p[4]
    # Los nombres de campo no pueden repetirse en todo el formulario.
    vistos = {}
    for campo in campos_de(formulario['cuerpo']):
        nombre = campo['atributos'].get('nombre')
        if nombre is None:
            continue
        if nombre in vistos:
            error_semantico(campo['linea'], f"El nombre '{nombre}' ya se usó en la línea {vistos[nombre]}")
        else:
            vistos[nombre] = campo['linea']
    p[0] = formulario


def p_encabezado(p):
    'encabezado : FORMULARIO CADENA metodo IGUAL CADENA tema NUEVA_LINEA'
    p[0] = {'titulo': p[2], 'metodo': p[3], 'ruta': p[5], 'tema': p[6]}


def p_metodo(p):
    '''metodo : POST
              | GET'''
    p[0] = p[1]


def p_tema(p):
    'tema : TEMA IGUAL color'
    p[0] = p[3]


def p_tema_vacio(p):
    'tema : '
    p[0] = 'claro'  # tema por defecto


def p_color(p):
    '''color : CLARO
             | OSCURO
             | AZUL'''
    p[0] = p[1]


# ---------------------------------------------------------------- cuerpo: secciones, filas y campos

def p_cuerpo(p):
    '''cuerpo : cuerpo bloque
              | bloque'''
    p[0] = p[1] + [p[2]] if len(p) == 3 else [p[1]]


def p_bloque(p):
    '''bloque : seccion
              | elemento'''
    p[0] = p[1]


def p_seccion(p):
    'seccion : SECCION CADENA NUEVA_LINEA INDENTA elementos DESINDENTA'
    p[0] = {'tipo': 'seccion', 'titulo': p[2], 'elementos': p[5], 'linea': p.lineno(1)}


def p_elementos(p):
    '''elementos : elementos elemento
                 | elemento'''
    p[0] = p[1] + [p[2]] if len(p) == 3 else [p[1]]


def p_elemento(p):
    '''elemento : campo
                | fila'''
    p[0] = p[1]


def p_fila(p):
    'fila : FILA NUEVA_LINEA INDENTA campos DESINDENTA'
    if len(p[4]) < 2:
        error_semantico(p.lineno(1), 'Una fila debe tener al menos 2 campos')
    p[0] = {'tipo': 'fila', 'campos': p[4], 'linea': p.lineno(1)}


def p_campos(p):
    '''campos : campos campo
              | campo'''
    p[0] = p[1] + [p[2]] if len(p) == 3 else [p[1]]


def p_campo(p):
    'campo : tipo atributos NUEVA_LINEA'
    control, linea = p[1]
    atributos = {}
    for clave, valor in p[2]:
        if clave in atributos:
            error_semantico(linea, f"El atributo '{clave}' está repetido")
        atributos[clave] = valor
    verificar_campo(control, atributos, linea)
    p[0] = {'tipo': 'campo', 'control': control, 'atributos': atributos, 'linea': linea}


def p_tipo(p):
    '''tipo : TEXTO
            | EMAIL
            | NUMERO
            | FECHA
            | AREA
            | CLAVE
            | OPCIONES
            | CASILLA'''
    p[0] = (p[1], p.lineno(1))


def p_atributos(p):
    'atributos : atributos atributo'
    p[0] = p[1] + [p[2]]


def p_atributos_vacio(p):
    'atributos : '
    p[0] = []


def p_atributo_cadena(p):
    '''atributo : NOMBRE IGUAL CADENA
                | PLACEHOLDER IGUAL CADENA
                | AYUDA IGUAL CADENA
                | MENSAJE IGUAL CADENA'''
    p[0] = (p[1], p[3])


def p_atributo_entero(p):
    '''atributo : MIN IGUAL ENTERO
                | MAX IGUAL ENTERO'''
    p[0] = (p[1], p[3])


def p_atributo_obligatorio(p):
    'atributo : OBLIGATORIO'
    p[0] = ('obligatorio', True)


def p_atributo_valores(p):
    'atributo : PAR_A valores PAR_C'
    p[0] = ('valores', p[2])


def p_valores(p):
    '''valores : valores COMA CADENA
               | CADENA'''
    p[0] = p[1] + [p[3]] if len(p) == 4 else [p[1]]


def p_boton(p):
    'boton : BOTON CADENA NUEVA_LINEA'
    p[0] = p[2]


# ---------------------------------------------------------------- errores sintácticos

NOMBRES_TOKENS = {
    'NUEVA_LINEA': 'fin de línea', 'INDENTA': 'aumento de sangría',
    'DESINDENTA': 'fin de bloque (menos sangría)', 'IGUAL': "'='",
    'PAR_A': "'('", 'PAR_C': "')'", 'COMA': "','",
}


def describir(tok):
    if tok.type == 'CADENA':
        return f"el texto '{tok.value}'"
    if tok.type == 'ENTERO':
        return f'el número {tok.value}'
    return NOMBRES_TOKENS.get(tok.type, f"la palabra '{tok.value}'")


def p_error(tok):
    if tok is None:
        _errores_sintacticos.append((None, 'El programa terminó antes de tiempo (¿falta el botón?)'))
    else:
        _errores_sintacticos.append((tok.lineno, f'No se esperaba {describir(tok)}'))
    raise _CortarAnalisis()


class _CortarAnalisis(Exception):
    pass


# ---------------------------------------------------------------- controles semánticos

def verificar_campo(control, atributos, linea):
    if 'nombre' not in atributos:
        error_semantico(linea, f"El campo '{control}' no tiene nombre")
    if ('min' in atributos or 'max' in atributos) and control not in TIPOS_CON_MIN_MAX:
        error_semantico(linea, f"'min' y 'max' solo valen en campos 'numero', no en '{control}'")
    if 'min' in atributos and 'max' in atributos and atributos['min'] > atributos['max']:
        error_semantico(linea, f"'min' ({atributos['min']}) es mayor que 'max' ({atributos['max']})")
    if control == 'opciones' and 'valores' not in atributos:
        error_semantico(linea, "Un campo 'opciones' necesita su lista de valores, por ejemplo ('A', 'B')")
    if control != 'opciones' and 'valores' in atributos:
        error_semantico(linea, f"La lista de valores solo vale en campos 'opciones', no en '{control}'")
    if 'placeholder' in atributos and control in TIPOS_SIN_PLACEHOLDER:
        error_semantico(linea, f"'placeholder' no vale en campos '{control}'")


def campos_de(bloques):
    """Devuelve todos los campos del formulario, estén sueltos, en secciones o en filas."""
    for b in bloques:
        if b['tipo'] == 'campo':
            yield b
        elif b['tipo'] == 'fila':
            yield from b['campos']
        else:
            yield from campos_de(b['elementos'])


# ---------------------------------------------------------------- punto de entrada

parser = yacc.yacc(debug=False, write_tables=False)
_lexer = LexerPlanilla()


def analizar(texto):
    """Analiza un programa planilla. Devuelve el árbol del formulario o lanza ErrorPlanilla."""
    _errores_sintacticos.clear()
    _errores_semanticos.clear()
    arbol = None
    try:
        arbol = parser.parse(texto, lexer=_lexer)
    except _CortarAnalisis:
        pass
    # Se informa primero el error de la etapa más temprana.
    if _lexer.errores:
        raise ErrorPlanilla('léxico', [(l, f'{m} (columna {c})') for l, c, m in _lexer.errores])
    if _errores_sintacticos:
        raise ErrorPlanilla('sintáctico', list(_errores_sintacticos))
    if _errores_semanticos:
        raise ErrorPlanilla('semántico', sorted(_errores_semanticos, key=lambda e: e[0]))
    return arbol
