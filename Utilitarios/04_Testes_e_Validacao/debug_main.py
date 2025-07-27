#!/usr/bin/env python3
"""
Teste específico do main.py
"""

import sys
print("Testando main.py...")

try:
    # Tenta importar apenas os imports básicos do main
    print("1. Testando imports básicos...")
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
    
    # Testa se consegue acessar as variáveis necessárias
    print("3. Testando constantes...")
    CONFIG_PATH = "configuracao.ini"
    print("4. Constantes OK")
    
    # Testa configuração básica de logging
    print("5. Testando logging básico...")
    logging.basicConfig(level=logging.INFO, force=True)
    logger = logging.getLogger(__name__)
    logger.info("Teste de logging")
    print("6. Logging básico OK")
    
    print("7. Teste do main.py básico concluído com sucesso")

except Exception as e:
    print(f"ERRO: {e}")
    import traceback
    traceback.print_exc()
