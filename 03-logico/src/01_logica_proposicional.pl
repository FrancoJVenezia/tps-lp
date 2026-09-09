% Representacion de formulas de logica proposicional como listas.
%   negacion:  [neg, A]
%   binarias:  [A, Con, B]  con Con en {and, or, then}

conbi(and).
conbi(or).
conbi(then).

% Constantes logicas.
clog(v).
clog(f).

% Variables proposicionales.
vlog(p).
vlog(q).
vlog(r).
vlog(s).

% expr(E): E es una formula bien formada.
expr(X) :- clog(X).
expr(X) :- vlog(X).
expr([neg, A]) :- expr(A).
expr([A, Con, B]) :- expr(A), conbi(Con), expr(B).

% --- Evaluacion de una formula dada una asignacion de valores ---
% valor(E, Asignacion, V): la formula E vale V bajo Asignacion,
% una lista de pares Variable-Valor. Los valores son v (verdadero) y f (falso).

valor(v, _, v).
valor(f, _, f).
valor(X, Asig, V) :- vlog(X), memberchk(X-V, Asig).
valor([neg, A], Asig, V) :- valor(A, Asig, VA), negado(VA, V).
valor([A, Con, B], Asig, V) :-
    valor(A, Asig, VA),
    valor(B, Asig, VB),
    tabla(Con, VA, VB, V).

negado(v, f).
negado(f, v).

% Tablas de verdad de las conexiones binarias.
tabla(and,  v, v, v).
tabla(and,  v, f, f).
tabla(and,  f, v, f).
tabla(and,  f, f, f).
tabla(or,   v, v, v).
tabla(or,   v, f, v).
tabla(or,   f, v, v).
tabla(or,   f, f, f).
tabla(then, v, v, v).
tabla(then, v, f, f).
tabla(then, f, v, v).
tabla(then, f, f, v).
