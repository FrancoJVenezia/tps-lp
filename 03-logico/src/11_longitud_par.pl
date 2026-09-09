% longitud_par(L): la longitud de L es par.
% Dos predicados mutuamente recursivos: sacar un elemento cambia
% la paridad, asi que par delega en impar y viceversa.
% No uso length/2 para que sea puramente recursivo.
%
% Las clausulas son disjuntas ([] contra [_|_]) para que cada lista
% tenga UNA sola solucion y no haya respuestas repetidas.
longitud_par([]).
longitud_par([_|Resto]) :- longitud_impar(Resto).

longitud_impar([_|Resto]) :- longitud_par(Resto).
