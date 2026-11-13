"""Agente de planilla: le pide al LLM (ollama) el HTML y el CSS de cada parte del formulario.

Cada pedido describe en lenguaje natural el significado de la construcción (la especificación
semántica) y el elemento HTML que le corresponde según la grilla semántica. La respuesta se limpia
y se verifica; si tiene problemas, se le devuelve al LLM la lista de problemas para que la corrija.
"""
import re
import ollama
from bs4 import BeautifulSoup
from bs4.formatter import HTMLFormatter

MODELO = 'llama3.2'
OPCIONES = {'temperature': 0, 'seed': 7}   # sin azar: misma entrada, misma salida
INTENTOS = 3
MARCA = '{{CONTENIDO}}'                    # lugar donde después se insertan los elementos hijos

SISTEMA = ("Sos un generador de formularios web. Respondé ÚNICAMENTE con el código pedido: "
           "sin explicaciones, sin markdown, sin ``` y sin etiquetas <html>, <head> ni <body>. "
           "Usá exactamente los elementos, id, name, class y atributos indicados, sin agregar otros.")


class ErrorAgente(Exception):
    pass


# ---------------------------------------------------------------- comunicación con el LLM

def limpiar(respuesta, es_css=False):
    """Saca lo que el LLM agrega de más: bloques ``` y texto antes o después del código."""
    r = re.sub(r'```[a-zA-Z]*', '', respuesta).strip()
    if es_css:
        return re.sub(r'</?style[^>]*>', '', r).strip()
    inicio = r.find('<')
    if inicio == -1:
        return r
    fin = max(r.rfind('>') + 1, r.rfind(MARCA) + len(MARCA) if MARCA in r else 0)
    # BeautifulSoup cierra las etiquetas que el LLM haya dejado abiertas (por ejemplo </form>).
    return BeautifulSoup(r[inicio:fin], 'html.parser').decode(formatter=_SIN_ORDENAR)


class _FormatoSinOrdenar(HTMLFormatter):
    def attributes(self, tag):          # respeta el orden de los atributos que escribió el LLM
        return list(tag.attrs.items())


_SIN_ORDENAR = _FormatoSinOrdenar()


def atributos_de_mas(elemento, permitidos):
    sobran = sorted(set(elemento.attrs) - set(permitidos))
    return [f'el <{elemento.name}> tiene atributos que no se pidieron: {", ".join(sobran)}'] if sobran else []


_memoria = {}  # pedido -> respuesta ya verificada (evita repetir pedidos idénticos)


def pedir(pedido, verificar, es_css=False):
    """Hace el pedido, verifica la respuesta y, si hay problemas, pide la corrección."""
    if pedido not in _memoria:
        _memoria[pedido] = _pedir_al_llm(pedido, verificar, es_css)
    return _memoria[pedido]


def _pedir_al_llm(pedido, verificar, es_css):
    mensajes = [{'role': 'system', 'content': SISTEMA}, {'role': 'user', 'content': pedido}]
    problemas = []
    for _ in range(INTENTOS):
        respuesta = ollama.chat(model=MODELO, messages=mensajes, options=OPCIONES)['message']['content']
        codigo = limpiar(respuesta, es_css)
        problemas = verificar(codigo)
        if not problemas:
            return codigo
        mensajes += [
            {'role': 'assistant', 'content': respuesta},
            {'role': 'user', 'content': 'Tu respuesta tiene estos problemas:\n- ' + '\n- '.join(problemas)
                                        + '\nCorregilos y devolvé de nuevo el código COMPLETO (también lo que ya estaba bien), sin explicaciones.'},
        ]
    raise ErrorAgente(f'El LLM no generó código válido después de {INTENTOS} intentos: {"; ".join(problemas)}')


# ---------------------------------------------------------------- campos

# tipo de campo -> (significado en lenguaje natural, elemento HTML según la grilla semántica)
CONTROLES = {
    'texto':    ('un campo de texto de una sola línea', '<input type="text">'),
    'email':    ('un campo para escribir un correo electrónico (el navegador valida el formato)', '<input type="email">'),
    'numero':   ('un campo numérico', '<input type="number">'),
    'fecha':    ('un campo para elegir una fecha', '<input type="date">'),
    'area':     ('un campo de texto largo, de varias líneas', '<textarea>'),
    'clave':    ('un campo de contraseña (los caracteres se ocultan al escribir)', '<input type="password">'),
    'opciones': ('una lista desplegable para elegir una opción', '<select>'),
    'casilla':  ('una casilla de verificación', '<input type="checkbox">'),
}


def pedido_campo(campo, id_):
    control, at = campo['control'], campo['atributos']
    significado, elemento = CONTROLES[control]
    lineas = [f'Generá un campo de formulario envuelto en un <div class="campo">.',
              f'Es {significado}: usá el elemento {elemento} con id="{id_}" y name="{id_}".']
    if control == 'casilla':
        lineas.append(f'Poné primero la casilla y a su derecha un <label for="{id_}"> con el texto \'{at["nombre"]}\'.')
    else:
        lineas.append(f'Arriba del control, un <label for="{id_}"> con el texto \'{at["nombre"]}\'.')
    if at.get('obligatorio'):
        lineas.append('Es obligatorio' + (' marcarla' if control == 'casilla' else '') + ': agregale el atributo required.')
    if 'min' in at:
        lineas.append(f'El valor mínimo permitido es {at["min"]}: atributo min="{at["min"]}".')
    if 'max' in at:
        lineas.append(f'El valor máximo permitido es {at["max"]}: atributo max="{at["max"]}".')
    if 'placeholder' in at:
        lineas.append(f'Dentro del campo vacío se ve el texto de ejemplo \'{at["placeholder"]}\': atributo placeholder (no uses value).')
    if 'valores' in at:
        opciones = ', '.join(f"'{v}'" for v in at['valores'])
        lineas.append(f'Las opciones son {opciones}, en ese orden, cada una en un <option> cuyo value es igual a su texto.')
    if 'mensaje' in at:
        m = at['mensaje'].replace("'", "\\'")
        lineas.append(f'Si el valor no es válido, el navegador muestra el mensaje \'{at["mensaje"]}\': agregale al control '
                      f'exactamente oninvalid="this.setCustomValidity(\'{m}\')" oninput="this.setCustomValidity(\'\')".')
    if 'ayuda' in at:
        lineas.append(f'Debajo del control, un <small class="ayuda"> con el texto \'{at["ayuda"]}\'.')
    lineas.append('No agregues ningún otro elemento ni atributo.')
    return '\n'.join(lineas)


def verificar_campo(html, campo, id_):
    control, at = campo['control'], campo['atributos']
    sopa = BeautifulSoup(html, 'html.parser')
    p = []
    div = sopa.find('div', class_='campo')
    if div is None:
        return ['falta el <div class="campo"> que envuelve el campo']
    elemento = div.find(id=id_)
    tag_esperado = {'area': 'textarea', 'opciones': 'select'}.get(control, 'input')
    if elemento is None or elemento.name != tag_esperado:
        return [f'falta el elemento <{tag_esperado}> con id="{id_}"']
    if tag_esperado == 'input':
        tipo = CONTROLES[control][1].split('"')[1]
        if elemento.get('type') != tipo:
            p.append(f'el <input> debe tener type="{tipo}"')
    permitidos = {'id', 'name', 'type', 'required', 'min', 'max', 'placeholder', 'oninvalid', 'oninput'}
    p += atributos_de_mas(elemento, permitidos)
    if elemento.get('name') != id_:
        p.append(f'el control debe tener name="{id_}"')
    label = div.find('label', attrs={'for': id_})
    if label is None or label.get_text(strip=True) != at['nombre']:
        p.append(f'falta un <label for="{id_}"> con el texto exacto \'{at["nombre"]}\'')
    if bool(at.get('obligatorio')) != elemento.has_attr('required'):
        p.append('el control debe tener el atributo required' if at.get('obligatorio') else 'el control NO debe tener required')
    for clave in ('min', 'max'):
        if clave in at and elemento.get(clave) != str(at[clave]):
            p.append(f'el control debe tener {clave}="{at[clave]}"')
    if 'placeholder' in at and elemento.get('placeholder') != at['placeholder']:
        p.append(f'el control debe tener placeholder="{at["placeholder"]}"')
    if elemento.has_attr('value') and control not in ('casilla',):
        p.append('el control no debe tener el atributo value')
    if 'valores' in at:
        textos = [o.get_text(strip=True) for o in elemento.find_all('option')]
        if textos != at['valores']:
            p.append(f'el <select> debe tener exactamente estas opciones, en orden: {at["valores"]}')
    if 'mensaje' in at:
        oninvalid, oninput = elemento.get('oninvalid', ''), elemento.get('oninput', '')
        if 'setCustomValidity' not in oninvalid or at['mensaje'] not in oninvalid.replace("\\'", "'"):
            p.append(f'el control debe tener oninvalid="this.setCustomValidity(...)" con el mensaje \'{at["mensaje"]}\'')
        if oninput.replace(' ', '') != "this.setCustomValidity('')":
            p.append('el control debe tener exactamente oninput="this.setCustomValidity(\'\')"')
    if 'ayuda' in at:
        small = div.find('small', class_='ayuda')
        if small is None or small.get_text(strip=True) != at['ayuda']:
            p.append(f'falta un <small class="ayuda"> con el texto \'{at["ayuda"]}\'')
    return p


def generar_campo(campo, id_):
    return pedir(pedido_campo(campo, id_), lambda h: verificar_campo(h, campo, id_))


# ---------------------------------------------------------------- contenedores

def verificar_contenedor(html, tag, clase=None, textos=()):
    sopa = BeautifulSoup(html, 'html.parser')
    raiz = sopa.find(tag, class_=clase) if clase else sopa.find(tag)
    p = []
    if raiz is None:
        return [f'falta el elemento <{tag}{f" class={chr(34)}{clase}{chr(34)}" if clase else ""}>']
    for sub, texto in textos:
        e = raiz.find(sub)
        if e is None or e.get_text(strip=True) != texto:
            p.append(f'falta un <{sub}> con el texto exacto \'{texto}\'')
    if html.count(MARCA) != 1:
        p.append(f'el texto {MARCA} tiene que aparecer exactamente una vez, sin modificar')
    return p


def generar_seccion(titulo):
    pedido = (f"Generá una sección de formulario con el título '{titulo}': un <fieldset> que tenga adentro, "
              f"primero, un <legend> con el texto '{titulo}' y, después del legend, exactamente el texto {MARCA} sin modificarlo.")
    return pedir(pedido, lambda h: verificar_contenedor(h, 'fieldset', textos=[('legend', titulo)]))


def generar_fila():
    pedido = (f'Generá un contenedor que ubica campos de formulario uno al lado del otro: un <div class="fila"> '
              f'que tenga adentro solamente el texto {MARCA} sin modificarlo.')
    return pedir(pedido, lambda h: verificar_contenedor(h, 'div', clase='fila'))


def generar_boton(texto):
    pedido = f"Generá el botón que envía el formulario: un <button type=\"submit\"> con el texto '{texto}'."
    def verificar(h):
        b = BeautifulSoup(h, 'html.parser').find('button')
        if b is None or b.get('type') != 'submit' or b.get_text(strip=True) != texto:
            return [f"falta un <button type=\"submit\"> con el texto exacto '{texto}'"]
        return atributos_de_mas(b, {'type'})
    return pedir(pedido, verificar)


def generar_formulario(titulo, metodo, ruta, tema):
    pedido = (f"Generá un formulario web titulado '{titulo}' que se envía con el método {metodo.upper()} a la ruta '{ruta}': "
              f'un <form class="card tema-{tema}" method="{metodo}" action="{ruta}"> que tenga adentro, primero, '
              f"un <h2> con el texto '{titulo}' y, después del h2, exactamente el texto {MARCA} sin modificarlo.")
    def verificar(h):
        p = verificar_contenedor(h, 'form', textos=[('h2', titulo)])
        f = BeautifulSoup(h, 'html.parser').find('form')
        if f is not None:
            if f.get('method', '').lower() != metodo:
                p.append(f'el <form> debe tener method="{metodo}"')
            if f.get('action') != ruta:
                p.append(f'el <form> debe tener action="{ruta}"')
            if set(f.get('class', [])) != {'card', f'tema-{tema}'}:
                p.append(f'el <form> debe tener class="card tema-{tema}"')
            p += atributos_de_mas(f, {'class', 'method', 'action'})
        return p
    return pedir(pedido, verificar)


# ---------------------------------------------------------------- estilos (colores del tema)
# La estructura de la card (espaciado, anchos, filas) es fija y la escribe el traductor.
# El color de las letras y las líneas también es fijo según el tema, para garantizar que se lea.
# El LLM elige los FONDOS a partir de la descripción del tema, y se verifica que contrasten con esas letras.

LETRAS_Y_LINEAS = {
    #          texto      títulos    líneas     ayuda
    'claro':  ('#1f1f1f', '#111111', '#4a4a4a', '#555555'),
    'oscuro': ('#f2f2f2', '#ffffff', '#d9d9d9', '#c8c8c8'),
    'azul':   ('#1f2937', '#1d4ed8', '#3b82f6', '#4b5563'),
}
TEXTO_BOTON = '#ffffff'
TEMAS = {
    'claro':  'fondos claros: la página gris muy claro, la tarjeta blanca y los campos de un gris claro apenas distinto de la '
              'tarjeta; el botón gris oscuro',
    'oscuro': 'fondos oscuros: la página casi negra, la tarjeta gris oscuro y los campos de un gris oscuro un poco más claro '
              'que la tarjeta; el botón de un azul oscuro intenso',
    'azul':   'fondos claros con tono azul: la página celeste muy claro, la tarjeta blanca y los campos celeste muy suave; '
              'el botón azul intenso',
}
SELECTORES_CSS = ['body', '.card', '.campo input', '.campo select', '.campo textarea', 'button']
CONTRASTE_MINIMO = 4.5      # recomendación de accesibilidad (WCAG) para texto normal


def luminancia(color):
    """Luminancia relativa de un color #rrggbb (fórmula de WCAG): 0 = negro, 1 = blanco."""
    canales = []
    for i in (1, 3, 5):
        c = int(color[i:i + 2], 16) / 255
        canales.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = canales
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(color1, color2):
    """Relación de contraste entre dos colores: 1 (iguales) a 21 (negro sobre blanco)."""
    l1, l2 = sorted((luminancia(color1), luminancia(color2)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def fondos_de(css):
    """Lee el CSS del LLM: devuelve {selector: color de fondo} y el conjunto de propiedades no permitidas."""
    fondos, otras = {}, set()
    for sel, decl in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
        for d in decl.split(';'):
            if ':' not in d:
                continue
            prop, valor = (x.strip() for x in d.split(':', 1))
            if prop not in ('background-color', 'background'):
                otras.add(prop)
            elif re.fullmatch(r'#[0-9a-fA-F]{6}', valor):
                for s in sel.split(','):
                    fondos[' '.join(s.split())] = valor.lower()
    return fondos, otras


def generar_css(tema):
    texto = LETRAS_Y_LINEAS[tema][0]
    tono = 'oscuros' if tema == 'oscuro' else 'claros'
    pedido = (f'Generá solo el CSS (sin etiqueta <style>) con los COLORES DE FONDO de un formulario con tema {tema.upper()}: '
              f'{TEMAS[tema]}.\n'
              f'Las letras del formulario son de color {texto}, así que los fondos de la página, la tarjeta y los campos '
              f'tienen que ser {tono} para que se lean bien. El botón tiene letras blancas ({TEXTO_BOTON}), así que su fondo '
              'tiene que ser oscuro o de un color intenso. El fondo de los campos tiene que ser distinto del de la tarjeta.\n'
              f'Escribí una regla para cada uno de estos selectores: {", ".join(SELECTORES_CSS)}.\n'
              'Usá únicamente la propiedad background-color, con colores en formato #rrggbb. '
              'No agregues ninguna otra propiedad.')

    def verificar(css):
        p = []
        if '<' in css:
            p.append('devolvé solo CSS, sin etiquetas HTML')
        if css.count('{') != css.count('}') or css.count('{') == 0:
            p.append('las llaves { } no están balanceadas')
        fondos, otras = fondos_de(css)
        if otras:
            p.append('solo se permite background-color; sacá: ' + ', '.join(sorted(otras)))
        faltan = [s for s in SELECTORES_CSS if s not in fondos]
        if faltan:
            p.append('faltan reglas con background-color #rrggbb para: ' + ', '.join(faltan))
            return p
        for sel in SELECTORES_CSS:
            letra = TEXTO_BOTON if sel == 'button' else texto
            c = contraste(fondos[sel], letra)
            if c < CONTRASTE_MINIMO:
                cambio = 'más oscuro' if luminancia(letra) > 0.5 else 'más claro'
                p.append(f'el fondo de {sel} ({fondos[sel]}) casi no contrasta con sus letras {letra} '
                         f'(contraste {c:.1f}, mínimo {CONTRASTE_MINIMO}): elegí un fondo {cambio}')
        if fondos['.campo input'] == fondos['.card']:
            p.append('el fondo de los campos tiene que ser distinto del de .card')
        return p
    return pedir(pedido, verificar, es_css=True)
