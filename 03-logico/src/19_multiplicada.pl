% multiplicada(L1, N, L2): L2 repite N veces cada elemento de L1.
% Para cada elemento genero sus N copias y concateno con el resto.
multiplicada([], _, []).
multiplicada([X|Resto], N, L2) :-
    copias(X, N, Copias),
    multiplicada(Resto, N, RestoMult),
    append(Copias, RestoMult, L2).

copias(_, 0, []).
copias(X, N, [X|Resto]) :-
    N > 0,
    N1 is N - 1,
    copias(X, N1, Resto).
