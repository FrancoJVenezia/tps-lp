% inserta(X, L1, L2): L2 es L1 con X insertado en alguna posicion.
% Es la relacion inversa de selecciona/3: insertar X en L1 dando L2
% equivale a sacar X de L2 dando L1. Redefino la extraccion aca
% para que el archivo funcione por si solo.
inserta(X, L1, L2) :- extraer(X, L2, L1).

extraer(X, [X|L], L).
extraer(X, [Y|L1], [Y|L2]) :- extraer(X, L1, L2).
