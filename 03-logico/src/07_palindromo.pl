% palindromo(L): L se lee igual en ambos sentidos.
% Defino la inversion aca mismo (con nombre propio para no pisar
% la del ejercicio 6) para que el archivo sea autocontenido.
palindromo(L) :- invertir_ac(L, [], L).

invertir_ac([], Ac, Ac).
invertir_ac([X|Resto], Ac, Inv) :- invertir_ac(Resto, [X|Ac], Inv).
