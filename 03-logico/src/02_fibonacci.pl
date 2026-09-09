% fibonacci(N, X): X es el N-esimo termino de la sucesion de Fibonacci.
% La version ingenua recalcula los mismos terminos y es exponencial,
% asi que uso un acumulador que arrastra el par (actual, siguiente):
% en cada paso avanza una posicion. Queda lineal en N.
fibonacci(N, X) :- fib_ac(N, 0, 1, X).

fib_ac(0, Actual, _, Actual).
fib_ac(N, Actual, Siguiente, X) :-
    N > 0,
    N1 is N - 1,
    Suma is Actual + Siguiente,
    fib_ac(N1, Siguiente, Suma, X).
