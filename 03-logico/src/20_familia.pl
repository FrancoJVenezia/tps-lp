% Relaciones de parentesco a partir del hecho basico padre/2.
padre(alberto, juan).
padre(alberto, luis).
padre(leoncio, alberto).
padre(leoncio, geronimo).
padre(geronimo, luisa).

hijo(H, P) :- padre(P, H).

% Hermanos: comparten padre pero no son la misma persona.
hermano(A, B) :- padre(P, A), padre(P, B), A \== B.

nieto(N, A) :- padre(P, N), padre(A, P).
abuelo(A, N) :- nieto(N, A).

% Tio: hermano de alguno de los padres.
tio(T, S) :- padre(P, S), hermano(P, T).

% Primos: sus padres son hermanos entre si.
primo(A, B) :- padre(PA, A), padre(PB, B), hermano(PA, PB).

% Antepasado: padre, o padre de un antepasado (clausura transitiva).
antepasado(A, D) :- padre(A, D).
antepasado(A, D) :- padre(A, X), antepasado(X, D).
