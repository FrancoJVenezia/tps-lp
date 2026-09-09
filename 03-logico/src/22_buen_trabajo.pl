% Tiene un buen trabajo quien gana buen sueldo (> 800000)
% y ademas tiene tiempo libre (trabaja <= 8 horas).
sueldo(elektra, 850000).
sueldo(loki, 900000).
sueldo(thor, 750000).

trabaja(elektra, 6).
trabaja(thor, 5).
trabaja(loki, 8).

ganaBuenSueldo(Quien) :- sueldo(Quien, Monto), Monto > 800000.

tieneTiempoLibre(Quien) :- trabaja(Quien, Horas), Horas =< 8.

tieneUnBuenTrabajo(Quien) :- ganaBuenSueldo(Quien), tieneTiempoLibre(Quien).
