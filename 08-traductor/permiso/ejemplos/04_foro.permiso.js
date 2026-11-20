// Permisos de 'Foro': generado por el traductor permiso a partir de 04_foro.permiso.
// Uso en Express: const { exigir } = require('./este-archivo');
//                 app.post('/ruta', exigir('crear', 'recurso'), manejador);

const PERMISOS = {
  visitante: { hereda: null, puede: { temas: ['ver'], respuestas: ['ver'] } },
  miembro: { hereda: 'visitante', puede: { temas: ['crear'], respuestas: ['crear'] } },
  'moderador': { hereda: 'miembro', puede: { temas: ['editar', 'borrar'], respuestas: ['borrar'] } },
  bot: { hereda: null, puede: { respuestas: ['borrar'] } },
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
