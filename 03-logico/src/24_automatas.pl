% AFD que reconoce el lenguaje a*(b | bb), es decir:
% {b, bb, ab, abb, aab, aabb, aaab, aaabb, ...}
%
%   q0 --a--> q0     (cualquier cantidad de aes, incluida ninguna)
%   q0 --b--> q1     (primera b: ya es aceptable)
%   q1 --b--> q2     (segunda b: tambien aceptable)
%
% q0 no es final porque la cadena vacia y "aaa" no pertenecen al lenguaje.
inicial(q0).

final(q1).
final(q2).

trans(q0, a, q0).
trans(q0, b, q1).
trans(q1, b, q2).

% acepta(L, Q): desde el estado Q, el automata acepta la cadena L.
% Consumida toda la entrada, hay que estar parado en un estado final.
acepta([], Q) :- final(Q).
acepta([Simbolo|Resto], Q) :-
    trans(Q, Simbolo, Q2),
    acepta(Resto, Q2).

% Punto de entrada: acepta desde el estado inicial.
acepta(L) :- inicial(Q0), acepta(L, Q0).
