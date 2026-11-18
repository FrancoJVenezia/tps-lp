// Permisos de 'Hospital': generado por guardia a partir de 03_hospital.guardia.
// Uso en Express: const { exigir } = require('./este-archivo');
//                 app.post('/ruta', exigir('crear', 'recurso'), manejador);

const PERMISOS = {
  'paciente': { hereda: null, puede: { turnos: ['ver', 'crear', 'borrar'] } },
  'recepcionista': { hereda: null, puede: { turnos: ['todo'], pacientes: ['ver', 'crear'] } },
  enfermero: { hereda: 'recepcionista', puede: { 'historias clínicas': ['ver'] } },
  'médico': { hereda: 'enfermero', puede: { 'historias clínicas': ['crear', 'editar'], 'recetas': ['crear'] } },
  'residente': { hereda: 'médico', puede: {}, noPuede: { recetas: ['crear'] } },
  director: { hereda: 'médico', puede: { pacientes: ['todo'], estadísticas: ['ver'] } },
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
