// API de ejemplo de la tienda, protegida con el módulo de permisos que generó guardia.
// Uso: node servidor_tienda.js <módulo generado .js> [puerto]
const path = require('path');
const express = require('express');
const { exigir } = require(path.resolve(process.argv[2]));

const app = express();
const puerto = Number(process.argv[3] || 3457);

// Inicio de sesión simulado: el rol llega en el encabezado X-Rol.
// En una aplicación real, esto lo resuelve el login (por ejemplo, con una cookie de sesión o un token).
app.use((req, res, next) => {
  const rol = req.get('X-Rol');
  if (rol) req.usuario = { rol };
  next();
});

// Cada ruta exige un permiso: acción + recurso, como en el programa guardia.
app.get('/productos',       exigir('ver', 'productos'),    (req, res) => res.json(['mate', 'termo', 'yerba']));
app.post('/productos',      exigir('crear', 'productos'),  (req, res) => res.status(201).send('Producto creado'));
app.put('/productos/:id',   exigir('editar', 'productos'), (req, res) => res.send(`Producto ${req.params.id} editado`));
app.delete('/productos/:id', exigir('borrar', 'productos'), (req, res) => res.send(`Producto ${req.params.id} borrado`));
app.get('/pedidos',         exigir('ver', 'pedidos'),      (req, res) => res.json([{ id: 3, total: 4500 }]));
app.post('/pedidos',        exigir('crear', 'pedidos'),    (req, res) => res.status(201).send('Pedido creado'));
app.delete('/pedidos/:id',  exigir('borrar', 'pedidos'),   (req, res) => res.send(`Pedido ${req.params.id} borrado`));

// Solo escucha en esta computadora (127.0.0.1).
app.listen(puerto, '127.0.0.1', () => console.log(`Tienda escuchando en http://127.0.0.1:${puerto}`));
