% ordenada(L): la lista de numeros L esta ordenada de forma creciente.
% Comparo pares consecutivos. Incluyo [] como ordenada.
ordenada([]).
ordenada([_]).
ordenada([X, Y|Resto]) :- X =< Y, ordenada([Y|Resto]).
