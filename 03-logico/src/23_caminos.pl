% Caminos entre ciudades. Hay camino si hay una ruta directa, o una ruta
% a una ciudad intermedia seguida de un camino desde alli.
ruta(ba, lp).
ruta(ba, jy).
ruta(mi, bb).
ruta(ba, mdq).
ruta(ba, mi).
ruta(mdq, mi).
ruta(lp, mi).

% Las rutas se pueden recorrer en ambos sentidos.
conectada(A, B) :- ruta(A, B).
conectada(A, B) :- ruta(B, A).

% Acumulo visitadas para cortar los ciclos que genera la simetria.
camino(Origen, Destino) :- camino(Origen, Destino, [Origen]).

camino(Origen, Destino, _) :- conectada(Origen, Destino).
camino(Origen, Destino, Visitadas) :-
    conectada(Origen, Intermedia),
    \+ memberchk(Intermedia, Visitadas),
    camino(Intermedia, Destino, [Intermedia|Visitadas]).
