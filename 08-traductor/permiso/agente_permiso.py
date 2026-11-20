"""Agente del lenguaje permiso: le pide al LLM (ollama) el código JavaScript de cada parte del módulo de permisos.

Cada pedido describe en lenguaje natural el significado de la construcción (la especificación
semántica) con los datos que armó el parser, nunca el programa fuente. La respuesta se limpia y se
verifica EJECUTÁNDOLA con Node; si tiene problemas, se le devuelve al LLM la lista de problemas para
que la corrija.
"""
import difflib
import json
import re
import shutil
import subprocess

import ollama

MODELO = 'llama3.2'
OPCIONES = {'temperature': 0, 'seed': 7}   # sin azar: misma entrada, misma salida
INTENTOS = 4                               # correcciones dentro de una misma conversación
RONDAS = 3                                 # conversaciones nuevas (con otra semilla) si se agotan los intentos

SISTEMA = ("Sos un programador JavaScript (Node.js). Respondé ÚNICAMENTE con el código pedido: "
           "sin explicaciones, sin comentarios, sin markdown y sin ```. "
           "No uses require, import ni console.log, y no agregues nada que no se haya pedido.")


class ErrorAgente(Exception):
    pass


# ---------------------------------------------------------------- Node

NODE = shutil.which('node')


def ejecutar_node(codigo):
    """Ejecuta código JavaScript con Node. Devuelve (salió bien, salida o mensaje de error)."""
    if NODE is None:
        raise ErrorAgente('No se encontró Node.js: instalalo desde https://nodejs.org')
    r = subprocess.run([NODE, '-'], input=codigo, capture_output=True, text=True, encoding='utf-8', timeout=20)
    if r.returncode != 0:
        lineas = [l for l in r.stderr.splitlines() if re.match(r'\w*Error\b', l.strip())]
        return False, lineas[0].strip() if lineas else r.stderr.strip()[-300:]
    return True, r.stdout


# ---------------------------------------------------------------- comunicación con el LLM

def error_de_ejecucion(salida, codigo):
    """Mensaje para el LLM cuando su código falla. Si usó un nombre que no existe, sugiere el más parecido."""
    mensaje = f'el código da error al ejecutarlo: {salida}'
    m = re.search(r'ReferenceError: (\w+) is not defined', salida)
    if m:
        nombres = set(re.findall(r'[A-Za-z_]\w*', codigo)) - {m.group(1)}
        parecido = difflib.get_close_matches(m.group(1), nombres, n=1)
        if parecido:
            mensaje += f" (usás '{m.group(1)}', que no existe: ¿quisiste escribir '{parecido[0]}'?)"
    return mensaje


def limpiar(respuesta):
    """Saca lo que el LLM agrega de más: bloques ```, texto antes del código y tabulaciones."""
    bloques = re.findall(r'```[a-zA-Z]*\n(.*?)```', respuesta, flags=re.S)
    codigo = bloques[0] if bloques else re.sub(r'```[a-zA-Z]*', '', respuesta)
    codigo = codigo.strip()
    if len(codigo) > 1 and codigo[0] == codigo[-1] == '"':   # a veces devuelve el código entre comillas, como texto
        codigo = codigo[1:-1]
    lineas = [l.rstrip().replace('\t', '  ') for l in codigo.strip().splitlines()]
    return '\n'.join(l for l in lineas if not l.strip().startswith(('console.log', 'module.exports')))


def extraer_funcion(codigo, nombre):
    """Se queda solo con la declaración 'function nombre(...) { ... }' (el LLM a veces agrega
    constantes o ejemplos de uso alrededor). Si no la encuentra, devuelve el código tal cual."""
    m = re.search(rf'function\s+{nombre}\s*\(', codigo)
    if m is None:
        return codigo
    profundidad, i = 0, codigo.find('{', m.end())
    while 0 <= i < len(codigo):
        profundidad += {'{': 1, '}': -1}.get(codigo[i], 0)
        if profundidad == 0:
            return codigo[m.start():i + 1]
        i += 1
    return codigo[m.start():]


_memoria = {}  # pedido -> respuesta ya verificada (evita repetir pedidos idénticos)


def pedir(pedido, verificar, funcion=None):
    """Hace el pedido, verifica la respuesta y, si hay problemas, pide la corrección.
    funcion: si se pidió una función, nombre de la función que hay que extraer de la respuesta."""
    if pedido not in _memoria:
        _memoria[pedido] = _pedir_al_llm(pedido, verificar, funcion)
    return _memoria[pedido]


def _pedir_al_llm(pedido, verificar, funcion):
    problemas = []
    for ronda in range(RONDAS):
        # Si una conversación se traba en el mismo error, se empieza otra desde cero con otra semilla.
        codigo, problemas = _conversacion(pedido, verificar, funcion, {**OPCIONES, 'seed': OPCIONES['seed'] + ronda})
        if not problemas:
            return codigo
    raise ErrorAgente(f'El LLM no generó código válido después de {RONDAS} rondas de {INTENTOS} intentos: '
                      f'{"; ".join(problemas)}')


def _conversacion(pedido, verificar, funcion, opciones):
    mensajes = [{'role': 'system', 'content': SISTEMA}, {'role': 'user', 'content': pedido}]
    for _ in range(INTENTOS):
        respuesta = ollama.chat(model=MODELO, messages=mensajes, options=opciones)['message']['content']
        codigo = limpiar(respuesta)
        if funcion:
            codigo = extraer_funcion(codigo, funcion)
        problemas = verificar(codigo)
        if not problemas:
            return codigo, []
        mensajes += [
            {'role': 'assistant', 'content': respuesta},
            {'role': 'user', 'content': 'Tu respuesta tiene estos problemas:\n- ' + '\n- '.join(problemas)
                                        + '\nCorregilos y devolvé de nuevo el código COMPLETO, sin explicaciones.'},
        ]
    return codigo, problemas


# ---------------------------------------------------------------- <Rol>: una entrada de la tabla PERMISOS

def texto_js(cadena):
    """Una cadena como literal de JavaScript con comillas simples: cliente -> 'cliente'."""
    return "'" + cadena.replace('\\', '\\\\').replace("'", "\\'") + "'"


def acciones_por_recurso(rol, negado=False):
    """Permisos propios del rol (o sus excepciones, si negado) agrupados por recurso, en el orden escrito."""
    agrupado = {}
    for permiso in rol['permisos']:
        if permiso['negado'] == negado:
            agrupado.setdefault(permiso['recurso'], []).append(permiso['accion'])
    return agrupado


def detalle(agrupado, verbo):
    return '\n'.join(f'- sobre el recurso {texto_js(r)} {verbo}: ' + ', '.join(texto_js(a) for a in acciones)
                     for r, acciones in agrupado.items())


def pedido_rol(rol):
    propios, excepciones = acciones_por_recurso(rol), acciones_por_recurso(rol, negado=True)
    herencia = (f'hereda los permisos del rol {texto_js(rol["hereda"])}: la propiedad hereda vale {texto_js(rol["hereda"])}'
                if rol['hereda'] else 'no hereda de ningún rol: la propiedad hereda vale null')
    lineas = [f'Generá UNA propiedad de un objeto JavaScript que describe los permisos del rol {texto_js(rol["nombre"])}.',
              f'La clave es el nombre del rol entre comillas simples: {texto_js(rol["nombre"])}.',
              'El valor es un objeto con exactamente ' + ('tres propiedades: hereda, puede y noPuede.' if excepciones
                                                          else 'dos propiedades: hereda y puede.'),
              f'- El rol {herencia}.',
              '- puede es un objeto: cada clave es un recurso (entre comillas simples) y su valor es un arreglo '
              'con los nombres de las acciones permitidas sobre ese recurso (entre comillas simples).'
              + (' Este rol NO tiene permisos propios: puede es un objeto vacío, puede: {}.' if not propios else '')]
    if excepciones:
        lineas.append('- noPuede tiene la misma forma que puede, pero con las acciones que el rol NO puede hacer '
                      'aunque las herede (excepciones).')
    if propios:
        lineas.append(f'Permisos propios del rol:\n{detalle(propios, "puede")}')
    if excepciones:
        lineas.append(f'Excepciones del rol (van en noPuede):\n{detalle(excepciones, "no puede")}')
    forma = (f'{texto_js(rol["nombre"])}: {{ hereda: ..., puede: ' + ('{ ... }' if propios else '{}')
             + (', noPuede: { ... }' if excepciones else '') + ' },')
    lineas.append(f'Forma de la respuesta (completá los ...): {forma}')
    lineas.append('Escribí solamente esa propiedad, en una sola línea, terminada en coma, sin encerrarla entre comillas. '
                  'No escribas const, ni el objeto que la contiene, ni llaves de más.')
    return '\n'.join(lineas)


def comparar_acciones(obtenido, esperado, propiedad):
    """Compara {recurso: [acciones]} del LLM con lo esperado (sin importar el orden de las acciones)."""
    if not isinstance(obtenido, dict) or not all(isinstance(a, list) for a in obtenido.values()):
        return [f'{propiedad} tiene que ser un objeto cuyos valores sean arreglos de acciones']
    obtenido = {r: sorted(a) for r, a in obtenido.items()}
    if not esperado and obtenido:
        return [f'{propiedad} tiene que ser exactamente {{}} (un objeto vacío): este rol no tiene nada propio ahí; '
                f'sacá {", ".join(texto_js(r) for r in obtenido)}']
    p = []
    for recurso, acciones in esperado.items():
        if obtenido.get(recurso) != sorted(acciones):
            p.append(f'en {propiedad}, el recurso {texto_js(recurso)} tiene que tener exactamente las acciones '
                     + '[' + ', '.join(texto_js(a) for a in acciones) + ']')
    for recurso in obtenido.keys() - esperado.keys():
        p.append(f'en {propiedad} sobra el recurso {texto_js(recurso)}: no se pidió')
    return p


def verificar_rol(codigo, rol):
    clave = texto_js(rol['nombre'])
    if '\n' in codigo.strip():
        return ['escribí la propiedad en UNA sola línea']
    if re.match(r'\s*(const|let|var)\b', codigo):
        return ['escribí solo la propiedad, sin const/let/var ni el objeto que la contiene']
    if re.match(r'\s*hereda\s*:', codigo):
        return [f'falta la clave del rol: la propiedad tiene que empezar con {clave}: y su valor es el objeto '
                f'{{ hereda: ..., puede: ... }}']
    ok, salida = ejecutar_node(f'const t = {{\n{codigo}\n}};\nprocess.stdout.write(JSON.stringify(t));')
    if not ok:
        return [f'no es una propiedad de objeto JavaScript válida ({salida})']
    tabla = json.loads(salida)
    nombre = rol['nombre']
    if list(tabla) != [nombre]:
        return [f'tiene que haber una sola propiedad, con la clave {texto_js(nombre)} (hay: {", ".join(tabla) or "ninguna"})']
    valor = tabla[nombre]
    excepciones = acciones_por_recurso(rol, negado=True)
    claves = {'hereda', 'puede', 'noPuede'} if excepciones else {'hereda', 'puede'}
    if not isinstance(valor, dict) or set(valor) != claves:
        return ['el valor tiene que ser un objeto con exactamente las propiedades ' + ', '.join(sorted(claves))]
    p = []
    if valor['hereda'] != rol['hereda']:
        p.append(f'hereda tiene que valer {texto_js(rol["hereda"]) if rol["hereda"] else "null"}')
    p += comparar_acciones(valor['puede'], acciones_por_recurso(rol), 'puede')
    if excepciones:
        p += comparar_acciones(valor['noPuede'], excepciones, 'noPuede')
    return p


def generar_rol(rol):
    return pedir(pedido_rol(rol), lambda c: verificar_rol(c, rol))


# ---------------------------------------------------------------- <Accion>: la función contiene

PEDIDO_CONTIENE = (
    'Escribí la función JavaScript contiene(lista, accion), que dice si una lista de acciones permite una acción.\n'
    'lista es un arreglo de textos (por ejemplo [\'ver\', \'crear\']) o puede ser undefined.\n'
    'Reglas:\n'
    '1. Si lista es undefined (o no es un arreglo), devuelve false.\n'
    '2. Si lista contiene la acción pedida (lista.includes(accion)), devuelve true.\n'
    "3. Si lista contiene el texto 'todo', devuelve true: 'todo' significa cualquier acción. "
    "'todo' es un valor guardado en el arreglo: se busca con lista.includes('todo').\n"
    '4. En cualquier otro caso devuelve false.\n'
    'La función devuelve siempre true o false. Escribí solo la función, con la palabra function.'
)

# (acciones, accion, resultado esperado); None representa undefined
CASOS_CONTIENE = [
    (['ver'], 'ver', True), (['ver', 'crear'], 'crear', True), (['ver'], 'borrar', False),
    (['todo'], 'editar', True), (['crear', 'todo'], 'ver', True), ([], 'ver', False), (None, 'ver', False),
]


def comparacion_con_todo(codigo):
    """Error típico del LLM: comparar el arreglo entero con el texto 'todo' (un arreglo nunca es igual a un texto)."""
    if re.search(r"(\]|lista)\s*===?\s*['\"]todo['\"]", codigo):
        return ["en tu código comparás un arreglo con 'todo' usando ===: eso siempre da false porque 'todo' está "
                "DENTRO del arreglo; usá .includes('todo')"]
    return []


def verificar_contiene(codigo):
    if not re.search(r'function\s+contiene\s*\(', codigo):
        return ['tiene que ser una función declarada como function contiene(lista, accion)']
    casos = [[a if a is not None else '__undefined__', x] for a, x, _ in CASOS_CONTIENE]
    prueba = (f'{codigo}\nconst casos = {json.dumps(casos)};\n'
              'process.stdout.write(JSON.stringify(casos.map(([a, x]) => contiene(a === "__undefined__" ? undefined : a, x))));')
    ok, salida = ejecutar_node(prueba)
    if not ok:
        return [error_de_ejecucion(salida, codigo)]
    p = comparacion_con_todo(codigo)
    for (acciones, accion, esperado), obtenido in zip(CASOS_CONTIENE, json.loads(salida)):
        if obtenido is not esperado:
            arg = 'undefined' if acciones is None else json.dumps(acciones).replace('"', "'")
            p.append(f"contiene({arg}, '{accion}') devolvió {json.dumps(obtenido)} y tenía que devolver {json.dumps(esperado)}")
    return p


def generar_contiene():
    return pedir(PEDIDO_CONTIENE, verificar_contiene, funcion='contiene')


# ---------------------------------------------------------------- <Herencia> y excepciones: la función puede

# Tabla de prueba con herencia en cadena, 'todo' y excepciones, para verificar la función con casos conocidos.
TABLA_PRUEBA = {
    'base':     {'hereda': None, 'puede': {'notas': ['ver']}},
    'medio':    {'hereda': 'base', 'puede': {'fotos': ['crear', 'borrar']}},
    'alto':     {'hereda': 'medio', 'puede': {'notas': ['todo']}},
    'limitado': {'hereda': 'alto', 'puede': {}, 'noPuede': {'notas': ['borrar'], 'fotos': ['todo']}},
    'nieto':    {'hereda': 'limitado', 'puede': {}},
    'casi':     {'hereda': 'base', 'puede': {'fotos': ['todo']}, 'noPuede': {'fotos': ['borrar']}},
}
CASOS_PRUEBA = [
    ('base', 'ver', 'notas', True), ('base', 'editar', 'notas', False), ('base', 'crear', 'fotos', False),
    ('medio', 'ver', 'notas', True), ('medio', 'crear', 'fotos', True), ('medio', 'editar', 'fotos', False),
    ('alto', 'editar', 'notas', True), ('alto', 'borrar', 'notas', True), ('alto', 'borrar', 'fotos', True),
    ('alto', 'ver', 'fotos', False), ('nadie', 'ver', 'notas', False), ('base', 'ver', 'otra', False),
    ('limitado', 'editar', 'notas', True), ('limitado', 'borrar', 'notas', False),
    ('limitado', 'crear', 'fotos', False), ('nieto', 'borrar', 'notas', False), ('nieto', 'ver', 'notas', True),
    ('casi', 'editar', 'fotos', True), ('casi', 'borrar', 'fotos', False), ('casi', 'ver', 'notas', True),
]

# contiene() correcta, para probar puede() aislada de los errores que pudiera tener la del LLM.
CONTIENE_REFERENCIA = ("function contiene(lista, accion) {\n"
                       "  return Array.isArray(lista) && (lista.includes(accion) || lista.includes('todo'));\n}")

PEDIDO_PUEDE = (
    'Escribí la función JavaScript puede(rol, accion, recurso), que decide si un rol tiene permiso.\n'
    'Usa la constante global PERMISOS, que YA ESTÁ DEFINIDA afuera de la función: no la declares ni la copies. '
    'Para cada rol, PERMISOS[rol].hereda es el nombre del rol del que hereda (o null); PERMISOS[rol].puede es un '
    'objeto que a cada recurso le asigna un arreglo con las acciones permitidas; y algunos roles tienen además '
    'PERMISOS[rol].noPuede, con la misma forma, que lista excepciones: acciones que el rol NO puede hacer aunque '
    'las herede. Los roles sin excepciones no tienen la propiedad noPuede.\n'
    'Para saber si un arreglo de acciones incluye la acción, usá la función contiene(lista, accion), que YA ESTÁ '
    'DEFINIDA (tiene en cuenta \'todo\' y devuelve false si el arreglo es undefined): no la escribas.\n'
    'Reglas, que se aplican primero al rol pedido:\n'
    '1. Si el rol no existe en PERMISOS, devuelve false.\n'
    '2. Si el rol tiene noPuede y contiene(PERMISOS[rol].noPuede[recurso], accion) es true, devuelve false: '
    'la excepción gana.\n'
    '3. Si contiene(PERMISOS[rol].puede[recurso], accion) es true, devuelve true.\n'
    '4. Si no, aplica las mismas reglas al rol indicado en PERMISOS[rol].hereda, y así sucesivamente.\n'
    '5. Si llega a un rol cuyo hereda es null sin decidir, devuelve false.\n'
    'La función devuelve siempre true o false, nunca undefined ni null.\n'
    'Escribí solo la función puede, con la palabra function.'
)


def explicar(tabla, rol, accion, recurso):
    """Explica con los datos de la tabla de prueba por qué puede(rol, accion, recurso) da lo que da."""
    if rol not in tabla:
        return f"el rol '{rol}' no existe en PERMISOS"
    pasos, actual = [], rol
    while actual is not None:
        negadas = tabla[actual].get('noPuede', {}).get(recurso)
        if negadas is not None and (accion in negadas or 'todo' in negadas):
            pasos.append(f"el arreglo noPuede de '{recurso}' del rol '{actual}' es {json.dumps(negadas)} (excepción)")
            return '; '.join(pasos)
        acciones = tabla[actual]['puede'].get(recurso)
        if acciones is None:
            pasos.append(f"el rol '{actual}' no tiene el recurso '{recurso}' en puede")
        else:
            pasos.append(f"el arreglo puede de '{recurso}' del rol '{actual}' es {json.dumps(acciones)}")
            if accion in acciones or 'todo' in acciones:
                return '; '.join(pasos)
        siguiente = tabla[actual]['hereda']
        pasos.append(f"hereda de '{siguiente}'" if siguiente else 'no hereda de nadie')
        actual = siguiente
    return '; '.join(pasos)


def verificar_puede(codigo, tabla=TABLA_PRUEBA, casos=CASOS_PRUEBA):
    if not re.search(r'function\s+puede\s*\(', codigo):
        return ['tiene que ser una función declarada como function puede(rol, accion, recurso)']
    if re.search(r'\bPERMISOS\s*=', codigo):
        return ['no declares PERMISOS adentro de la función: ya está definida afuera con los datos reales; usala tal cual']
    prueba = (f'const PERMISOS = {json.dumps(tabla)};\n{CONTIENE_REFERENCIA}\n{codigo}\n'
              f'const casos = {json.dumps(casos)};\n'
              'process.stdout.write(JSON.stringify(casos.map(([r, a, x]) => puede(r, a, x))));')
    ok, salida = ejecutar_node(prueba)
    if not ok:
        return [error_de_ejecucion(salida, codigo)]
    p = comparacion_con_todo(codigo)
    for (rol, accion, recurso, esperado), obtenido in zip(casos, json.loads(salida)):
        if obtenido is not esperado:
            p.append(f"puede('{rol}', '{accion}', '{recurso}') devolvió {json.dumps(obtenido)} y tenía que devolver "
                     f'{json.dumps(esperado)} porque {explicar(tabla, rol, accion, recurso)}')
    return p[:5]


def generar_puede():
    return pedir(PEDIDO_PUEDE, verificar_puede, funcion='puede')


# ---------------------------------------------------------------- middleware de Express: la función exigir

PEDIDO_EXIGIR = (
    'Escribí la función JavaScript exigir(accion, recurso) para usar como middleware de Express, '
    "por ejemplo: app.post('/pedidos', exigir('crear', 'pedidos'), crearPedido).\n"
    'exigir devuelve una función (req, res, next) que hace lo siguiente:\n'
    "1. Si req.usuario no existe, responde con estado 401 y el texto 'Falta iniciar sesión': "
    "return res.status(401).send('Falta iniciar sesión').\n"
    "2. Si puede(req.usuario.rol, accion, recurso) es true, llama a next() para que el pedido siga.\n"
    "3. Si no, responde con estado 403 y el texto 'Sin permiso': return res.status(403).send('Sin permiso').\n"
    'La función puede ya está definida: no la escribas. Escribí solo la función exigir, con la palabra function.'
)

# (usuario, permitido) -> resultado esperado del middleware
CASOS_EXIGIR = [
    (None, False, ['estado', 401, 'Falta iniciar sesión']),
    ({'rol': 'cliente'}, True, ['siguiente']),
    ({'rol': 'invitado'}, False, ['estado', 403, 'Sin permiso']),
]


def verificar_exigir(codigo):
    if not re.search(r'function\s+exigir\s*\(', codigo):
        return ['tiene que ser una función declarada como function exigir(accion, recurso)']
    if re.search(r'function\s+puede\s*\(', codigo):
        return ['no escribas la función puede: ya está definida']
    # Se simula Express: un req con o sin usuario, un res que anota lo que se responde y un next.
    prueba = (f"let permitido = false;\nfunction puede(rol, accion, recurso) {{ return permitido; }}\n{codigo}\n"
              f'const casos = {json.dumps(CASOS_EXIGIR)};\nconst resultados = [];\n'
              'for (const [usuario, ok] of casos) {\n'
              '  permitido = ok;\n'
              '  let r = null;\n'
              '  const res = { status(n) { return { send(t) { r = ["estado", n, t]; } }; } };\n'
              '  exigir("crear", "pedidos")(usuario ? { usuario } : {}, res, () => { r = ["siguiente"]; });\n'
              '  resultados.push(r);\n'
              '}\n'
              'process.stdout.write(JSON.stringify(resultados));')
    ok, salida = ejecutar_node(prueba)
    if not ok:
        return [error_de_ejecucion(salida, codigo)]
    p = []
    descripciones = ['sin usuario (req.usuario no existe)', 'con un usuario que tiene permiso',
                     'con un usuario que no tiene permiso']
    for desc, (_, _, esperado), obtenido in zip(descripciones, CASOS_EXIGIR, json.loads(salida)):
        if obtenido != esperado:
            quiere = 'llamar a next()' if esperado[0] == 'siguiente' else f"responder res.status({esperado[1]}).send('{esperado[2]}')"
            p.append(f'{desc} tiene que {quiere}')
    return p


def generar_exigir():
    return pedir(PEDIDO_EXIGIR, verificar_exigir, funcion='exigir')
