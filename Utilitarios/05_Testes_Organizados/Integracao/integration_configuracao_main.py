#!/usr/bin/env python3
"""
Versão minimalista do main.py para testar o problema
"""

print("=== INICIO DO TESTE MAIN MINIMALISTA ===")

# Imports básicos
print("1. Fazendo imports básicos...")
import asyncio
import configparser
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, NamedTuple, Tuple
from dataclasses import dataclass
from contextlib import contextmanager
import sqlite3
import xml.etree.ElementTree as ET
import re
print("2. Imports básicos OK")

# Configuração básica de logging
print("3. Configurando logging básico...")
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)
logger.info("Logging configurado")
print("4. Logging básico OK")

# Constantes
print("5. Definindo constantes...")
CONFIG_PATH = "configuracao.ini"
print("6. Constantes OK")

# Imports do src
print("7. Fazendo imports do src...")
try:
    from src import (
        atualizar_caminhos_arquivos,
        atualizar_query_params_ini,
        compactador_resultado,
        extrator_async,
        report_arquivos_vazios,
        verificador_xmls,
    )
    print("8. Imports do src OK")
except Exception as e:
    print(f"8. ERRO nos imports do src: {e}")
    import traceback
    traceback.print_exc()

try:
    from src.utils import (
        atualizar_campos_registros_pendentes,
    )
    print("9. Import do src.utils OK")
except Exception as e:
    print(f"9. ERRO no import do src.utils: {e}")
    import traceback
    traceback.print_exc()

print("=== TESTE MAIN MINIMALISTA CONCLUÍDO ===")

def test_main():
    print("Função test_main executada com sucesso")

if __name__ == "__main__":
    test_main()
