% subconjunto(L1, L2): L2 es un subconjunto de L1.
% Para cada elemento de L1 hay dos opciones: incluirlo en L2 o descartarlo.
% Cuando L1 se agota, L2 tiene que estar cerrada en [].
subconjunto([], []).
subconjunto([X|L1], [X|L2]) :- subconjunto(L1, L2).
subconjunto([_|L1], L2) :- subconjunto(L1, L2).
