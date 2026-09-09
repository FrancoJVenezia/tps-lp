% Distancia en km entre ciudades, posiblemente pasando por escalas.
distancia(buenosAires, puertoMadryn, 1300).
distancia(puertoMadryn, puertoDeseado, 732).
distancia(puertoDeseado, rioGallegos, 736).
distancia(puertoDeseado, calafate, 979).
distancia(rioGallegos, calafate, 304).
distancia(calafate, chalten, 213).

% Los tramos son bidireccionales: se puede viajar en cualquier sentido.
tramo(A, B, Kms) :- distancia(A, B, Kms).
tramo(A, B, Kms) :- distancia(B, A, Kms).

% Llevo la lista de ciudades ya visitadas para no entrar en ciclos:
% sin eso, ir y volver por el mismo tramo daria recursion infinita.
viaje(Origen, Destino, Kms) :- viaje(Origen, Destino, [Origen], Kms).

viaje(Destino, Destino, _, 0).
viaje(Origen, Destino, Visitadas, Kms) :-
    tramo(Origen, Intermedia, KmsTramo),
    \+ memberchk(Intermedia, Visitadas),
    viaje(Intermedia, Destino, [Intermedia|Visitadas], KmsResto),
    Kms is KmsTramo + KmsResto.
