// Permisos de 'Campus virtual' (campus-virtual.js): generado por el traductor permiso a partir de 05_campus.permiso.
// Uso en Express: const { exigir } = require('./campus-virtual');
//                 app.post('/ruta', exigir('crear', 'recurso'), manejador);

const PERMISOS = {
  'alumno': { hereda: null, puede: { materias: ['ver'], notas: ['ver'], entregas: ['crear'] } },
  'ayudante': { hereda: 'alumno', puede: { entregas: ['ver'], notas: ['editar'] } },
  'profesor': { hereda: 'ayudante', puede: { materias: ['todo'], notas: ['todo'] }, noPuede: { notas: ['borrar'] } },
  administrativo: { hereda: null, puede: { materias: ['ver'], inscripciones: ['todo'] } },
  'suspendido': { hereda: 'alumno', puede: {}, noPuede: { entregas: ['crear'] } },
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
