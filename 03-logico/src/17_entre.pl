% entre(N1, N2, X): X es un entero tal que N1 =< X =< N2.
% Por backtracking genera todos los valores del intervalo, uno por solucion.
entre(N1, N2, N1) :- N1 =< N2.
entre(N1, N2, X) :-
    N1 < N2,
    Siguiente is N1 + 1,
    entre(Siguiente, N2, X).
