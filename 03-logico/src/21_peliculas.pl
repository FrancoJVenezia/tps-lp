% Un suertudo es quien actuo en una pelicula que gano el Oscar.
% Formalizacion: actuo(P, Peli) ^ ganoElOscar(Peli) -> suertudo(P)
actuo(leoDiCaprio, wolfOfWallStreet).
actuo(margotRobbie, wolfOfWallStreet).
actuo(jonahHill, wolfOfWallStreet).
actuo(leoDiCaprio, onceUponATimeInHollywood).
actuo(bradPitt, onceUponATimeInHollywood).
actuo(margotRobbie, onceUponATimeInHollywood).
actuo(joePesci, goodFellas).
actuo(robertDeNiro, goodFellas).
actuo(rayLiotta, goodFellas).
actuo(lorraineBracco, goodFellas).
actuo(leoDiCaprio, catchMeIfYouCan).
actuo(tomHanks, catchMeIfYouCan).
actuo(michaelKeaton, birdman).
actuo(emmaStone, birdman).

ganoElOscar(birdman).

suertudo(Persona) :- actuo(Persona, Pelicula), ganoElOscar(Pelicula).

% Companeros de reparto en alguna pelicula.
companeros(A, B) :- actuo(A, Peli), actuo(B, Peli), A \== B.
