% lista(N, L): L es la lista de longitud N cuyos elementos son todos N.
% Uso un contador que baja de N a 0; N se mantiene fijo como valor a repetir.
lista(N, L) :- repetir(N, N, L).

repetir(_, 0, []).
repetir(N, Cont, [N|Resto]) :-
    Cont > 0,
    Cont1 is Cont - 1,
    repetir(N, Cont1, Resto).
