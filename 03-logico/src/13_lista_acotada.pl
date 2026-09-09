% lista_acotada(L): todo elemento de L es menor que la longitud de L.
% Calculo la longitud una sola vez y la paso como cota fija.
lista_acotada(L) :- length(L, N), menores_que(L, N).

menores_que([], _).
menores_que([X|Resto], N) :- X < N, menores_que(Resto, N).
