"""Uso: python main.py <archivo.permiso>
Traduce el programa y escribe el módulo JavaScript en la misma carpeta, con el nombre de la aplicación
(permisos 'Tienda' -> tienda.js). Si hay errores, los muestra y no genera el archivo."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parser_permiso import ErrorPermiso, analizar
from agente_permiso import ErrorAgente
from traductor_permiso import traducir

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')  # tildes y símbolos en la consola de Windows

if len(sys.argv) != 2:
    print(__doc__)
    sys.exit(2)

fuente = Path(sys.argv[1])
texto = fuente.read_text(encoding='utf-8')
try:
    resultado = traducir(texto, avisar=print, origen=fuente.name)
except ErrorPermiso as e:
    print(e)
    sys.exit(1)
except ErrorAgente as e:
    print(f'Error de generación: {e}')
    sys.exit(1)
except ConnectionError:
    print('No se pudo conectar con ollama: abrilo (y descargá el modelo con "ollama pull llama3.2") y volvé a intentar.')
    sys.exit(1)

destino = fuente.with_name(analizar(texto)['archivo'])
destino.write_text(resultado, encoding='utf-8')
print(f'Generado: {destino}')
