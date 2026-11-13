"""TestSuite de planilla (pytest).

- Programas válidos: se traducen con el LLM y se verifica la ESTRUCTURA del HTML generado
  (elementos y atributos), no el texto exacto, porque la redacción del LLM puede variar.
- Errores léxicos, sintácticos y semánticos: se verifica el tipo de error y el mensaje.
- Programa completo por consola (main.py), como lo usaría un programador.
Ejecutar desde esta carpeta:  python -m pytest -v test_planilla.py
"""
import subprocess
import sys
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

CARPETA = Path(__file__).parent
sys.path.insert(0, str(CARPETA))
from parser_planilla import analizar, ErrorPlanilla
from traductor_planilla import traducir

EJEMPLOS = CARPETA / 'ejemplos'


def leer(nombre):
    return (EJEMPLOS / nombre).read_text(encoding='utf-8')


def html_de(programa):
    return BeautifulSoup(traducir(programa), 'html.parser')


# ================================================================ programas válidos

def test_minimo():
    s = html_de(leer('01_minimo.planilla'))
    form = s.find('form')
    assert form['method'] == 'post' and form['action'] == 'api/contacto'
    assert 'tema-claro' in form['class']
    assert form.find('h2').get_text(strip=True) == 'Contacto'
    entrada = s.find('input', id='comentario')
    assert entrada['type'] == 'text' and entrada['placeholder'] == 'Escribí tu comentario'
    assert s.find('label', attrs={'for': 'comentario'}).get_text(strip=True) == 'Comentario'
    assert s.find('button', type='submit').get_text(strip=True) == 'Enviar'


def test_registro_secciones_y_validaciones():
    s = html_de(leer('02_registro.planilla'))
    assert 'tema-oscuro' in s.find('form')['class']
    assert [l.get_text(strip=True) for l in s.find_all('legend')] == ['Datos personales', 'Cuenta']
    edad = s.find('input', id='edad')
    assert edad['type'] == 'number' and edad['min'] == '18' and edad['max'] == '99'
    assert 'Tenés que ser mayor de edad' in edad['oninvalid']
    assert s.find('input', id='nombre').has_attr('required')
    assert s.find('input', id='correo')['type'] == 'email'
    clave = s.find('input', id='contrasena')
    assert clave['type'] == 'password'
    assert clave.find_parent('div', class_='campo').find('small', class_='ayuda').get_text(strip=True) == 'Mínimo 8 caracteres'
    casilla = s.find('input', id='acepto_los_terminos')
    assert casilla['type'] == 'checkbox' and casilla.has_attr('required')


def test_turno_filas_y_opciones():
    s = html_de(leer('03_turno.planilla'))
    assert 'tema-azul' in s.find('form')['class']
    filas = s.find_all('div', class_='fila')
    assert len(filas) == 2
    assert [i['id'] for i in filas[0].find_all('input')] == ['nombre', 'apellido']
    opciones = [o.get_text(strip=True) for o in s.find('select', id='especialidad').find_all('option')]
    assert opciones == ['Clínica', 'Pediatría', 'Traumatología']
    assert s.find('textarea', id='motivo')['placeholder'] == 'Contanos brevemente'
    assert s.find('input', id='dia_preferido')['type'] == 'date'


def test_busqueda_get_sin_secciones():
    s = html_de(leer('04_busqueda.planilla'))
    form = s.find('form')
    assert form['method'] == 'get' and form['action'] == '/buscar'
    assert s.find('fieldset') is None
    assert len(s.find_all('div', class_='fila')) == 2
    assert s.find('input', id='precio_minimo')['min'] == '0'


def test_encuesta_campos_sueltos_y_secciones():
    s = html_de(leer('05_encuesta.planilla'))
    form = s.find('form')
    hijos = [h for h in form.find_all(recursive=False)]
    # orden: título, campo suelto, sección, campo suelto, botón
    assert [h.name for h in hijos] == ['h2', 'div', 'fieldset', 'div', 'button']
    assert s.find('input', id='quiero_recibir_novedades')['type'] == 'checkbox'


def test_html_formateado_y_estilos():
    html = traducir(leer('01_minimo.planilla'))
    lineas = html.splitlines()
    assert lineas[0] == '<!DOCTYPE html>'
    assert '      <h2>Contacto</h2>' in lineas            # un elemento por línea, con sangría
    assert all((len(l) - len(l.lstrip(' '))) % 2 == 0 for l in lineas if l.strip())
    assert '.card {' in html and 'colores del tema' in html


# ================================================================ errores léxicos

E = "formulario 'C' post='x'\n"


@pytest.mark.parametrize('programa, mensaje', [
    (E + "   texto nombre='A'\n  boton 'E'\n", 'Sangría de 3 espacios'),
    (E + "\ttexto nombre='A'\n  boton 'E'\n", 'No se permiten tabulaciones'),
    ("formulario 'C post='x'\n  boton 'E'\n", 'Cadena sin cerrar'),
    (E + "  sección 'Datos'\n    texto nombre='A'\n  boton 'E'\n", "Palabra desconocida: 'sección'"),
    (E + "  texto nombre='A' @\n  boton 'E'\n", "Carácter no reconocido: '@'"),
    (E + "    texto nombre='A'\n  boton 'E'\n", 'sube más de un nivel'),
], ids=['sangria_impar', 'tabulacion', 'cadena_sin_cerrar', 'palabra_desconocida', 'caracter_raro', 'salto_de_nivel'])
def test_errores_lexicos(programa, mensaje):
    with pytest.raises(ErrorPlanilla) as e:
        analizar(programa)
    assert e.value.tipo == 'léxico'
    assert any(mensaje in m for _, m in e.value.errores)


# ================================================================ errores sintácticos

@pytest.mark.parametrize('programa, linea', [
    (E + "  texto nombre='A'\n", 3),
    (E + "  seccion 'A'\n    seccion 'B'\n      texto nombre='X'\n  boton 'E'\n", 3),
    (E + "  texto nombre=\n  boton 'E'\n", 2),
    (E + "  seccion 'A'\n    texto nombre='X'\n    boton 'E'\n", 4),
    ("texto nombre='A'\n", 1),
    ("formulario 'C' post='x' tema=rojo\n  boton 'E'\n", 1),
], ids=['falta_boton', 'seccion_en_seccion', 'atributo_sin_valor', 'boton_en_seccion', 'sin_encabezado', 'tema_inexistente'])
def test_errores_sintacticos(programa, linea):
    with pytest.raises(ErrorPlanilla) as e:
        analizar(programa)
    assert e.value.tipo in ('sintáctico', 'léxico')
    if e.value.tipo == 'sintáctico':
        assert e.value.errores[0][0] == linea


# ================================================================ errores semánticos

@pytest.mark.parametrize('cuerpo, mensaje', [
    ("  texto placeholder='hola'\n", 'no tiene nombre'),
    ("  texto nombre='A' min=3\n", "solo valen en campos 'numero'"),
    ("  numero nombre='A' min=10 max=5\n", 'es mayor que'),
    ("  opciones nombre='A'\n", 'necesita su lista de valores'),
    ("  texto nombre='A' ('x', 'y')\n", "solo vale en campos 'opciones'"),
    ("  fecha nombre='A' placeholder='x'\n", "'placeholder' no vale"),
    ("  fila\n    texto nombre='A'\n", 'al menos 2 campos'),
    ("  texto nombre='A'\n  email nombre='A'\n", 'ya se usó en la línea 2'),
    ("  texto nombre='A' obligatorio obligatorio\n", 'está repetido'),
], ids=['sin_nombre', 'min_en_texto', 'min_mayor_que_max', 'opciones_sin_lista', 'lista_en_texto',
        'placeholder_en_fecha', 'fila_de_un_campo', 'nombre_repetido', 'atributo_repetido'])
def test_errores_semanticos(cuerpo, mensaje):
    with pytest.raises(ErrorPlanilla) as e:
        analizar(E + cuerpo + "  boton 'E'\n")
    assert e.value.tipo == 'semántico'
    assert any(mensaje in m for _, m in e.value.errores)


def test_varios_errores_semanticos_se_informan_juntos():
    with pytest.raises(ErrorPlanilla) as e:
        analizar(E + "  texto placeholder='x'\n  numero nombre='N' min=9 max=1\n  boton 'E'\n")
    assert [l for l, _ in e.value.errores] == [2, 3]


# ================================================================ programa por consola (main.py)

def ejecutar_main(tmp_path, programa):
    fuente = tmp_path / 'prueba.planilla'
    fuente.write_text(programa, encoding='utf-8')
    r = subprocess.run([sys.executable, str(CARPETA / 'main.py'), str(fuente)],
                       capture_output=True, text=True, encoding='utf-8')
    return r, tmp_path / 'prueba.planilla.html'


def test_main_caso_feliz(tmp_path):
    r, salida = ejecutar_main(tmp_path, leer('01_minimo.planilla'))
    assert r.returncode == 0
    assert salida.exists()
    assert BeautifulSoup(salida.read_text(encoding='utf-8'), 'html.parser').find('form') is not None


def test_main_caso_con_error(tmp_path):
    r, salida = ejecutar_main(tmp_path, E + "  numero nombre='A' min=10 max=5\n  boton 'E'\n")
    assert r.returncode == 1
    assert 'Error semántico' in r.stdout and 'línea 2' in r.stdout
    assert not salida.exists()
