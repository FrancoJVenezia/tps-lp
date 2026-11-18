// Permisos de 'Tienda': generado por guardia a partir de 02_tienda.guardia.
// Uso en Express: const { exigir } = require('./este-archivo');
//                 app.post('/ruta', exigir('crear', 'recurso'), manejador);

const PERMISOS = {
  'invitado': { hereda: null, puede: { productos: ['ver'] } },
  'cliente': { hereda: 'invitado', puede: { 'pedidos': ['crear', 'ver'] } },
  admin: { hereda: 'cliente', puede: { productos: ['todo'], pedidos: ['borrar'] } },
  'pasante': { hereda: 'admin', puede: {}, noPuede: { productos: ['borrar'], pedidos: ['borrar'] } },
};

function contiene(lista, accion) {
  if (lista === undefined || !Array.isArray(lista)) return false;
  if (lista.includes(accion)) return true;
  if (lista.includes('todo')) return true;
  return false;
}

function puede(rol, accion, recurso) {
  if (!PERMISOS[rol]) return false;
  if (PERMISOS[rol].noPuede && contiene(PERMISOS[rol].noPuede[recurso], accion)) return false;
  if (contiene(PERMISOS[rol].puede[recurso], accion)) return true;
  return puede(PERMISOS[rol].hereda, accion, recurso);
}

function exigir(accion, recurso) {
  return function(req, res, next) {
    if (!req.usuario) {
      return res.status(401).send('Falta iniciar sesión');
    }
    if (puede(req.usuario.rol, accion, recurso)) {
      return next();
    }
    return res.status(403).send('Sin permiso');
  };
}

module.exports = { PERMISOS, puede, exigir };
