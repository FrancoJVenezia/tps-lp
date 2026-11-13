"""Analizador léxico de planilla (PLY).

Además de los tokens comunes, genera tres tokens que marcan la estructura por sangría:
  NUEVA_LINEA  al terminar cada línea con contenido
  INDENTA      cuando una línea tiene 2 espacios más que la anterior (se abre un nivel)
  DESINDENTA   por cada nivel que se cierra cuando la sangría vuelve atrás
"""
import ply.lex as lex

# ---------------------------------------------------------------- palabras reservadas
reservadas = {
    'formulario': 'FORMULARIO', 'seccion': 'SECCION', 'fila': 'FILA', 'boton': 'BOTON',
    'post': 'POST', 'get': 'GET',
    'tema': 'TEMA', 'claro': 'CLARO', 'oscuro': 'OSCURO', 'azul': 'AZUL',
    'texto': 'TEXTO', 'email': 'EMAIL', 'numero': 'NUMERO', 'fecha': 'FECHA',
    'area': 'AREA', 'clave': 'CLAVE', 'opciones': 'OPCIONES', 'casilla': 'CASILLA',
    'nombre': 'NOMBRE', 'placeholder': 'PLACEHOLDER', 'ayuda': 'AYUDA', 'mensaje': 'MENSAJE',
    'min': 'MIN', 'max': 'MAX', 'obligatorio': 'OBLIGATORIO',
}

tokens = [
    'CADENA', 'ENTERO', 'IGUAL', 'PAR_A', 'PAR_C', 'COMA',
    'NUEVA_LINEA', 'INDENTA', 'DESINDENTA',
] + list(reservadas.values())

ESPACIOS_POR_NIVEL = 2

# ---------------------------------------------------------------- reglas simples
t_IGUAL = r'='
t_PAR_A = r'\('
t_PAR_C = r'\)'
t_COMA = r','

# Dentro de una línea solo se ignoran espacios (los tabs son error).
t_ignore = ' '


# ---------------------------------------------------------------- reglas con acciones
# PLY prueba las funciones en el orden en que están escritas.

def t_SALTO(t):
    r'(\n[ ]*(\#[^\n]*)?)+'
    # Un salto de línea, junto con las líneas vacías o de solo comentario que lo siguen.
    # El valor que nos interesa es la sangría de la próxima línea con contenido:
    # la cantidad de espacios después del último '\n'.
    t.lexer.lineno += t.value.count('\n')
    ultima = t.value[t.value.rfind('\n') + 1:]
    t.value = len(ultima) - len(ultima.lstrip(' '))
    return t


def t_COMENTARIO(t):
    r'\#[^\n]*'
    pass  # se descarta


def t_CADENA(t):
    r"'[^'\n]*'"
    t.value = t.value[1:-1]  # sin las comillas
    return t


def t_CADENA_SIN_CERRAR(t):
    r"'[^'\n]*"
    t.lexer.errores.append((t.lineno, columna(t), f"Cadena sin cerrar: {t.value}"))


def t_ENTERO(t):
    r'[0-9]+'
    t.value = int(t.value)
    return t


def t_PALABRA(t):
    r'[A-Za-zÁÉÍÓÚáéíóúÑñÜü_][A-Za-zÁÉÍÓÚáéíóúÑñÜü_0-9]*'
    if t.value in reservadas:
        t.type = reservadas[t.value]
        return t
    t.lexer.errores.append((t.lineno, columna(t), f"Palabra desconocida: '{t.value}'"))


def t_error(t):
    c = t.value[0]
    if c == '\t':
        msg = "No se permiten tabulaciones: usá 2 espacios por nivel"
    else:
        msg = f"Carácter no reconocido: '{c}'"
    t.lexer.errores.append((t.lineno, columna(t), msg))
    t.lexer.skip(1)


def columna(t):
    inicio_linea = t.lexer.lexdata.rfind('\n', 0, t.lexpos) + 1
    return t.lexpos - inicio_linea + 1


# ---------------------------------------------------------------- sangría
def _nuevo(tipo, valor, linea):
    t = lex.LexToken()
    t.type, t.value, t.lineno, t.lexpos = tipo, valor, linea, -1
    return t


def _con_sangria(base):
    """Recorre los tokens de PLY y reemplaza cada SALTO por NUEVA_LINEA + INDENTA/DESINDENTA."""
    niveles = [0]                 # pila con la sangría de cada nivel abierto
    ultimo = 'NUEVA_LINEA'        # al empezar, "venimos" de una línea nueva
    while True:
        t = base.token()
        if t is None:
            break
        if t.type != 'SALTO':
            yield t
            ultimo = t.type
            continue

        sangria, linea = t.value, base.lineno
        if ultimo != 'NUEVA_LINEA':                 # cierra la línea anterior
            yield _nuevo('NUEVA_LINEA', None, linea - 1)
            ultimo = 'NUEVA_LINEA'
        if base.lexpos >= len(base.lexdata):
            break                                   # salto final del archivo: no hay más líneas

        actual = niveles[-1]
        if sangria % ESPACIOS_POR_NIVEL != 0:
            base.errores.append((linea, 1, f"Sangría de {sangria} espacios: debe ser múltiplo de {ESPACIOS_POR_NIVEL}"))
        elif sangria > actual:
            if sangria != actual + ESPACIOS_POR_NIVEL:
                base.errores.append((linea, 1, "La sangría sube más de un nivel de una línea a la siguiente"))
            niveles.append(sangria)
            yield _nuevo('INDENTA', None, linea)
        else:
            while sangria < niveles[-1]:
                niveles.pop()
                yield _nuevo('DESINDENTA', None, linea)
            if sangria != niveles[-1]:
                base.errores.append((linea, 1, "La sangría no coincide con ningún nivel anterior"))

    if ultimo != 'NUEVA_LINEA':
        yield _nuevo('NUEVA_LINEA', None, base.lineno)
    while len(niveles) > 1:                         # cierra los niveles abiertos al final
        niveles.pop()
        yield _nuevo('DESINDENTA', None, base.lineno)


class LexerPlanilla:
    """Lexer con la misma interfaz que usa ply.yacc (input/token), más la lista de errores."""

    def __init__(self):
        self.base = lex.lex()

    def input(self, texto):
        # Se agrega un '\n' adelante para que la primera línea también pase por la regla de sangría.
        self.base.input('\n' + texto)
        self.base.lineno = 0
        self.base.errores = []
        self._gen = _con_sangria(self.base)

    @property
    def errores(self):
        return self.base.errores

    def token(self):
        return next(self._gen, None)

    def __iter__(self):
        return iter(self.token, None)


tokens = tokens + ['SALTO']  # token interno: nunca llega al parser
lexer = LexerPlanilla()
