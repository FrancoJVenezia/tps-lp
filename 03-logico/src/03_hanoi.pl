% Torres de Hanoi: mover N aros del poste Origen al Destino usando Auxiliar.
% Estrategia clasica: mover N-1 aros al auxiliar, pasar el aro grande al
% destino, y mover los N-1 del auxiliar al destino.
hanoi(1, Origen, _, Destino) :-
    mostrar_movimiento(Origen, Destino).
hanoi(N, Origen, Auxiliar, Destino) :-
    N > 1,
    M is N - 1,
    hanoi(M, Origen, Destino, Auxiliar),
    mostrar_movimiento(Origen, Destino),
    hanoi(M, Auxiliar, Origen, Destino).

mostrar_movimiento(Origen, Destino) :-
    format("Mueve del ~w al ~w~n", [Origen, Destino]).

% cantidad_movimientos(N, Cant): 2^N - 1, la formula del enunciado.
cantidad_movimientos(N, Cant) :- Cant is 2**N - 1.
