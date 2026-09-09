# TP 03 — Programación Lógica

Resolución de los 24 ejercicios del TP en Prolog, usando `janus_swi`
para consultar SWI-Prolog desde el notebook.

- `TP-resuelto.ipynb` — la entrega, con las salidas ya ejecutadas
- `03-logico.ipynb` — enunciado original de la cátedra

## Cómo correrlo

```bash
python3 -m venv .venv
.venv/bin/pip install janus_swi jupyter
.venv/bin/jupyter notebook TP-resuelto.ipynb
```

Requiere SWI-Prolog instalado (`sudo apt install swi-prolog-nox`).

## Decisiones de implementación

Algunas cosas que resolví distinto de la forma más directa:

- **Fibonacci con acumulador.** La recursión ingenua recalcula los mismos
  términos y es exponencial. Arrastrando el par `(actual, siguiente)` queda
  lineal: `fibonacci(30, X)` responde al instante.
- **Inversa con acumulador**, en vez de `append/3` en cada paso, que sería
  cuadrática.
- **Rutas y caminos con lista de visitadas.** Los tramos son bidireccionales;
  sin llevar registro de las ciudades ya visitadas, ir y volver por el mismo
  tramo daría recursión infinita.
- **Cláusulas disjuntas en `longitud_par/1`.** Si `longitud_impar` acepta
  tanto `[_]` como `[_|R]`, la lista de un elemento tiene éxito por dos ramas
  y cada consulta devuelve soluciones repetidas. Separando los patrones
  (`[]` contra `[_|_]`) cada lista tiene exactamente una solución.
- **`valor/3` en lógica proposicional.** Además de reconocer fórmulas bien
  formadas con `expr/1`, agregué la evaluación bajo una asignación de valores,
  con las tablas de verdad como hechos.

## Verificación

El notebook corre de punta a punta sin errores. Cada predicado se probó con
casos que debe aceptar y casos que debe rechazar; el autómata contra 7 cadenas
del lenguaje y 7 que no pertenecen. Los predicados deterministas se auditaron
con `aggregate_all(count, ...)` para descartar soluciones duplicadas.
