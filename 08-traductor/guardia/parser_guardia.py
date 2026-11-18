"""Analizador sintáctico de guardia (ply.yacc) + controles semánticos.

El parser no genera JavaScript: arma un árbol con los roles y sus permisos (diccionarios de Python)
y verifica las reglas semánticas. La generación del código la hace después el agente (LLM),
recorriendo ese árbol, solo si no hubo ningún error.
"""
import ply.yacc as yacc
from lexer_guardia import LexerGuardia, tokens as _tokens_lexer

# SALTO es interno del lexer: el parser nunca lo recibe.
tokens = [t for t in _tokens_lexer if t != 'SALTO']

ACCIONES = ['ver', 'crear', 'editar', 'borrar']   # 'todo' equivale a las cuatro


class ErrorGuardia(Exception):
    """Error de traducción. tipo: 'léxico', 'sintáctico' o 'semántico'. errores: lista de (línea, mensaje)."""

    def __init__(self, tipo, errores):
        self.tipo, self.errores = tipo, errores
        detalle = '\n'.join(f'  línea {l}: {m}' for l, m in errores)
        super().__init__(f'Error {tipo}:\n{detalle}')


_errores_sintacticos = []
_errores_semanticos = []


def error_semantico(linea, mensaje):
    _errores_semanticos.append((linea, mensaje))


# ---------------------------------------------------------------- reglas de la GIC

def p_programa(p):
    'programa : PERMISOS CADENA NUEVA_LINEA INDENTA roles DESINDENTA'
    p[0] = {'aplicacion': p[2], 'roles': p[5]}
    verificar_roles(p[5])


def p_roles(p):
    '''roles : roles rol
             | rol'''
    p[0] = p[1] + [p[2]] if len(p) == 3 else [p[1]]


def p_rol(p):
    'rol : ROL CADENA herencia NUEVA_LINEA INDENTA permisos DESINDENTA'
    rol = {'nombre': p[2], 'hereda': p[3], 'permisos': p[6], 'linea': p.lineno(1)}
    # Un mismo permiso (o excepción) no puede repetirse dentro del rol.
    vistos, repetidos = {}, []
    for permiso in rol['permisos']:
        clave = (permiso['negado'], permiso['accion'], permiso['recurso'])
        if clave in vistos:
            error_semantico(permiso['linea'], f"\"{texto_permiso(permiso)}\" ya está en la línea "
                                              f"{vistos[clave]} del rol '{rol['nombre']}'")
            repetidos.append(permiso)
        else:
            vistos[clave] = permiso['linea']
    # Una excepción no puede contradecir un permiso del mismo rol.
    # Sí vale 'puede todo' + 'no puede <acción>': es "todo menos esa acción".
    for excepcion in (x for x in rol['permisos'] if x['negado'] and x not in repetidos):
        for permiso in (x for x in rol['permisos'] if not x['negado'] and x['recurso'] == excepcion['recurso']):
            if se_contradicen(permiso['accion'], excepcion['accion']):
                error_semantico(excepcion['linea'], f"Contradicción: el rol '{rol['nombre']}' tiene \"{texto_permiso(permiso)}\" "
                                                    f"(línea {permiso['linea']}) y \"{texto_permiso(excepcion)}\"")
    p[0] = rol


def p_herencia(p):
    'herencia : HEREDA CADENA'
    p[0] = p[2]


def p_herencia_vacia(p):
    'herencia : '
    p[0] = None


def p_permisos(p):
    '''permisos : permisos permiso
                | permiso'''
    p[0] = p[1] + [p[2]] if len(p) == 3 else [p[1]]


def p_permiso(p):
    'permiso : PUEDE accion CADENA NUEVA_LINEA'
    p[0] = {'negado': False, 'accion': p[2], 'recurso': p[3], 'linea': p.lineno(1)}


def p_permiso_negado(p):
    'permiso : NO PUEDE accion CADENA NUEVA_LINEA'
    p[0] = {'negado': True, 'accion': p[3], 'recurso': p[4], 'linea': p.lineno(1)}


def se_contradicen(permitida, negada):
    """'puede todo' + 'no puede borrar' es una excepción válida; cualquier otra superposición es contradicción."""
    if negada == 'todo':
        return True                       # no puede nada: choca con cualquier permiso del mismo recurso
    return permitida == negada            # puede ver + no puede ver


def texto_permiso(permiso):
    return f"{'no ' if permiso['negado'] else ''}puede {permiso['accion']} '{permiso['recurso']}'"


def p_accion(p):
    '''accion : VER
              | CREAR
              | EDITAR
              | BORRAR
              | TODO'''
    p[0] = p[1]


# ---------------------------------------------------------------- errores sintácticos

NOMBRES_TOKENS = {
    'NUEVA_LINEA': 'fin de línea', 'INDENTA': 'aumento de sangría',
    'DESINDENTA': 'fin de bloque (menos sangría)',
}


def describir(tok):
    if tok.type == 'CADENA':
        return f"el texto '{tok.value}'"
    return NOMBRES_TOKENS.get(tok.type, f"la palabra '{tok.value}'")


def p_error(tok):
    if tok is None:
        _errores_sintacticos.append((None, 'El programa terminó antes de tiempo (¿falta un rol o un permiso?)'))
    else:
        _errores_sintacticos.append((tok.lineno, f'No se esperaba {describir(tok)}'))
    raise _CortarAnalisis()


class _CortarAnalisis(Exception):
    pass


# ---------------------------------------------------------------- controles semánticos

def verificar_roles(roles):
    """Controles que necesitan conocer todos los roles: nombres repetidos, herencia y excepciones de más."""
    errores_antes = len(_errores_semanticos)
    por_nombre = {}
    for rol in roles:
        if rol['nombre'] in por_nombre:
            error_semantico(rol['linea'], f"El rol '{rol['nombre']}' ya se definió en la línea "
                                          f"{por_nombre[rol['nombre']]['linea']}")
        else:
            por_nombre[rol['nombre']] = rol

    for rol in roles:
        padre = rol['hereda']
        if padre is None:
            continue
        if padre == rol['nombre']:
            error_semantico(rol['linea'], f"El rol '{padre}' no puede heredar de sí mismo")
        elif padre not in por_nombre:
            error_semantico(rol['linea'], f"El rol '{rol['nombre']}' hereda de '{padre}', que no existe")

    # Herencia circular: siguiendo 'hereda' desde un rol se vuelve a ese mismo rol.
    informados = set()
    for rol in roles:
        cadena, actual = [rol['nombre']], rol['hereda']
        while actual in por_nombre and actual not in cadena:
            cadena.append(actual)
            actual = por_nombre[actual]['hereda']
        if actual == rol['nombre'] and len(cadena) > 1 and rol['nombre'] not in informados:
            informados.update(cadena)
            recorrido = ' → '.join(f"'{n}'" for n in cadena + [rol['nombre']])
            error_semantico(rol['linea'], f'Herencia circular: {recorrido}')

    # Excepciones de más: 'no puede' sobre algo que el rol igual no podría hacer.
    # Solo se controla si la herencia está bien (si no, no se puede recorrer la cadena).
    if len(_errores_semanticos) > errores_antes:
        return
    for rol in roles:
        for excepcion in (x for x in rol['permisos'] if x['negado']):
            acciones = ACCIONES if excepcion['accion'] == 'todo' else [excepcion['accion']]
            if not any(tendria_sin_excepcion(por_nombre, rol, a, excepcion['recurso']) for a in acciones):
                error_semantico(excepcion['linea'], f"La excepción \"{texto_permiso(excepcion)}\" no hace falta: "
                                                    f"el rol '{rol['nombre']}' no tiene ese permiso ni lo hereda")


def tendria_sin_excepcion(por_nombre, rol, accion, recurso):
    """¿El rol podría hacer la acción si se ignoraran sus propias excepciones?"""
    propios = [x['accion'] for x in rol['permisos'] if not x['negado'] and x['recurso'] == recurso]
    if accion in propios or 'todo' in propios:
        return True
    return rol['hereda'] is not None and decidir(por_nombre, rol['hereda'], accion, recurso)


# ---------------------------------------------------------------- tabla de permisos esperada

def recursos_de(arbol):
    """Todos los recursos nombrados en el programa, en el orden en que aparecen."""
    recursos = []
    for rol in arbol['roles']:
        for permiso in rol['permisos']:
            if permiso['recurso'] not in recursos:
                recursos.append(permiso['recurso'])
    return recursos


def decidir(por_nombre, nombre, accion, recurso):
    """Regla de guardia: se recorre la cadena de herencia desde el rol hacia arriba y decide el primer rol que
    diga algo sobre esa acción y ese recurso. Dentro de un rol, la excepción ('no puede') gana sobre el permiso."""
    while nombre is not None:
        rol = por_nombre.get(nombre)
        if rol is None:
            return False
        reglas = [x for x in rol['permisos'] if x['recurso'] == recurso and x['accion'] in (accion, 'todo')]
        if any(x['negado'] for x in reglas):
            return False
        if reglas:
            return True
        nombre = rol['hereda']
    return False


def tabla_esperada(arbol):
    """{rol: {recurso: conjunto de acciones permitidas}} con la herencia, 'todo' y las excepciones aplicadas.

    Es lo que el código JavaScript generado tiene que responder: el agente lo usa para verificarlo."""
    por_nombre = {r['nombre']: r for r in arbol['roles']}
    tabla = {}
    for rol in arbol['roles']:
        tabla[rol['nombre']] = {}
        for recurso in recursos_de(arbol):
            acciones = {a for a in ACCIONES if decidir(por_nombre, rol['nombre'], a, recurso)}
            if acciones:
                tabla[rol['nombre']][recurso] = acciones
    return tabla


# ---------------------------------------------------------------- punto de entrada

parser = yacc.yacc(debug=False, write_tables=False)
_lexer = LexerGuardia()


def analizar(texto):
    """Analiza un programa guardia. Devuelve el árbol de roles o lanza ErrorGuardia."""
    _errores_sintacticos.clear()
    _errores_semanticos.clear()
    arbol = None
    try:
        arbol = parser.parse(texto, lexer=_lexer)
    except _CortarAnalisis:
        pass
    # Se informa primero el error de la etapa más temprana.
    if _lexer.errores:
        raise ErrorGuardia('léxico', [(l, f'{m} (columna {c})') for l, c, m in _lexer.errores])
    if _errores_sintacticos:
        raise ErrorGuardia('sintáctico', list(_errores_sintacticos))
    if _errores_semanticos:
        raise ErrorGuardia('semántico', sorted(_errores_semanticos, key=lambda e: e[0]))
    return arbol
