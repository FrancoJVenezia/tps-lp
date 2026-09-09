# TP 03 — Programación Lógica

Resolución de los 24 ejercicios del TP en Prolog.

## Estructura

- `src/` — un archivo `.pl` por ejercicio, autocontenido y ejecutable por separado
- `TP-resuelto.ipynb` — notebook de entrega, con las salidas ya ejecutadas
- `03-logico.ipynb` — enunciado original de la cátedra

## Cómo correrlo

Un ejercicio suelto, directo con SWI-Prolog:

```bash
swipl src/02_fibonacci.pl
?- fibonacci(9, X).
X = 34.
```

El notebook completo:

```bash
python3 -m venv .venv
.venv/bin/pip install janus_swi jupyter
.venv/bin/jupyter notebook TP-resuelto.ipynb
```

## Ejercicios

| # | Archivo | Predicado principal |
|---|---------|---------------------|
| 01 | `01_logica_proposicional.pl` | `expr/1`, `valor/3` |
| 02 | `02_fibonacci.pl` | `fibonacci/2` |
| 03 | `03_hanoi.pl` | `hanoi/4` |
| 04 | `04_rutas.pl` | `viaje/3` |
| 05 | `05_cons.pl` | `cons/3` |
| 06 | `06_inversa.pl` | `inversa/2` |
| 07 | `07_palindromo.pl` | `palindromo/1` |
| 08 | `08_selecciona.pl` | `selecciona/3` |
| 09 | `09_inserta.pl` | `inserta/3` |
| 10 | `10_todos_iguales.pl` | `todos_iguales/1` |
| 11 | `11_longitud_par.pl` | `longitud_par/1` |
| 12 | `12_subconjunto.pl` | `subconjunto/2` |
| 13 | `13_lista_acotada.pl` | `lista_acotada/1` |
| 14 | `14_max_lista.pl` | `max_lista/2` |
| 15 | `15_ordenada.pl` | `ordenada/1` |
| 16 | `16_lista.pl` | `lista/2` |
| 17 | `17_entre.pl` | `entre/3` |
| 18 | `18_elemento_en.pl` | `elemento_en/3` |
| 19 | `19_multiplicada.pl` | `multiplicada/3` |
| 20 | `20_familia.pl` | `hermano/2`, `tio/2`, `antepasado/2` |
| 21 | `21_peliculas.pl` | `suertudo/1` |
| 22 | `22_buen_trabajo.pl` | `tieneUnBuenTrabajo/1` |
| 23 | `23_caminos.pl` | `camino/2` |
| 24 | `24_automatas.pl` | `acepta/1`, `acepta/2` |

## Decisiones de implementación

Algunas cosas que resolví distinto de la forma más directa:

- **Fibonacci con acumulador.** La recursión ingenua recalcula los mismos
  términos y es exponencial. Arrastrando el par `(actual, siguiente)` queda
  lineal: `fibonacci(30, X)` responde al instante.
- **Inversa con acumulador**, en vez de `append/3` en cada paso, que sería
  cuadrática.
- **Rutas y caminos con lista de visitadas.** Los tramos son bidireccionales
  (`tramo/3` y `conectada/2` valen en ambos sentidos); sin llevar registro de
  las ciudades ya visitadas, ir y volver por el mismo tramo daría recursión
  infinita.
- **Cláusulas disjuntas en `longitud_par/1`.** Si `longitud_impar` acepta
  tanto `[_]` como `[_|R]`, la lista de un elemento tiene éxito por dos ramas
  y cada consulta devuelve soluciones repetidas. Separando los patrones
  (`[]` contra `[_|_]`) cada lista tiene exactamente una solución.
- **`valor/3` en lógica proposicional.** Además de reconocer fórmulas bien
  formadas con `expr/1`, agregué la evaluación bajo una asignación de valores,
  con las tablas de verdad como hechos.
- **Archivos autocontenidos.** `07_palindromo` y `09_inserta` redefinen los
  predicados auxiliares que necesitan en vez de importarlos: `ensure_loaded`
  con ruta relativa falla al cargar el texto vía `janus.consult`.

## Verificación

Los 24 archivos cargan sin warnings:

```bash
for f in src/*.pl; do swipl -q -g halt "$f"; done
```

Los predicados deterministas se comprobaron con `aggregate_all(count, ...)`
para asegurar que no devuelvan soluciones duplicadas, y el autómata se probó
contra 7 cadenas del lenguaje y 7 que no pertenecen.
