% elemento_en(K, L, X): X es el K-esimo elemento de L (numerando desde 1).
% Bajo K de a uno mientras descarto cabezas, hasta llegar a 1.
elemento_en(1, [X|_], X).
elemento_en(K, [_|Resto], X) :-
    K > 1,
    K1 is K - 1,
    elemento_en(K1, Resto, X).
