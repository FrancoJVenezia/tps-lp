% selecciona(X, L1, L2): L2 es L1 sin UNA ocurrencia de X.
% Caso base: X esta en la cabeza y lo salteo, la cola queda igual.
% Caso recursivo: conservo la cabeza Y y sigo buscando en el resto.
selecciona(X, [X|L], L).
selecciona(X, [Y|L1], [Y|L2]) :- selecciona(X, L1, L2).
