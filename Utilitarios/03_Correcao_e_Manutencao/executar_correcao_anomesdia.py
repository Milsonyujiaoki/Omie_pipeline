
import sys
from pathlib import Path
# Adiciona o diretório raiz do projeto ao sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.utils import atualizar_anomesdia

if __name__ == "__main__":
    atualizar_anomesdia()