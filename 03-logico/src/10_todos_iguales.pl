% todos_iguales(L): todos los elementos de L son iguales entre si.
% Comparo de a pares consecutivos: si los dos primeros unifican,
% sigo con la cola. La lista vacia y la unitaria son casos base.
todos_iguales([]).
todos_iguales([_]).
todos_iguales([X, X|Resto]) :- todos_iguales([X|Resto]).
