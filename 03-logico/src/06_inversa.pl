% inversa(L1, L2): L2 es L1 con el orden invertido.
% Uso un acumulador: voy pasando la cabeza al frente del acumulador,
% asi la recursion es de cola y evito el append/3 cuadratico.
inversa(L1, L2) :- inversa_ac(L1, [], L2).

inversa_ac([], Ac, Ac).
inversa_ac([X|Resto], Ac, L2) :- inversa_ac(Resto, [X|Ac], L2).
