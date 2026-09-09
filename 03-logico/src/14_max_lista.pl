% max_lista(L, X): X es el maximo de la lista de numeros L.
% Recorro con acumulador: comparo el candidato actual contra la cabeza.
max_lista([X|Resto], Max) :- max_ac(Resto, X, Max).

max_ac([], Max, Max).
max_ac([X|Resto], Parcial, Max) :-
    (   X > Parcial
    ->  max_ac(Resto, X, Max)
    ;   max_ac(Resto, Parcial, Max)
    ).
