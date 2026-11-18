"""Uso: python main.py <archivo.guardia>
Traduce el programa y escribe <archivo.guardia>.js. Si hay errores, los muestra y no genera el archivo."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parser_guardia import ErrorGuardia
from agente_guardia import ErrorAgente
from traductor_guardia import traducir

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')  # tildes y símbolos en la consola de Windows

if len(sys.argv) != 2:
    print(__doc__)
    sys.exit(2)

fuente = Path(sys.argv[1])
try:
    resultado = traducir(fuente.read_text(encoding='utf-8'), avisar=print, origen=fuente.name)
except ErrorGuardia as e:
    print(e)
    sys.exit(1)
except ErrorAgente as e:
    print(f'Error de generación: {e}')
    sys.exit(1)
except ConnectionError:
    print('No se pudo conectar con ollama: abrilo (y descargá el modelo con "ollama pull llama3.2") y volvé a intentar.')
    sys.exit(1)

destino = fuente.with_name(fuente.name + '.js')
destino.write_text(resultado, encoding='utf-8')
print(f'Generado: {destino}')
