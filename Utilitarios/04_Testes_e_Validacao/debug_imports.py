#!/usr/bin/env python3
"""
Teste de debug para identificar problemas de importação no main.py
"""

import sys
print("1. Iniciando teste de debug...")

try:
    print("2. Importando bibliotecas básicas...")
    import os
    import time
    import logging
    import sqlite3
    print("3. Bibliotecas básicas OK")
    
    print("4. Testando configuração de logging...")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger(__name__)
    logger.info("Logging configurado com sucesso")
    print("5. Logging OK")
    
    print("6. Tentando importar módulos locais...")
    sys.path.insert(0, '.')
    
    try:
        print("6.1. Importando src.utils...")
        import src.utils
        print("6.2. src.utils OK")
    except Exception as e:
        print(f"6.2. ERRO em src.utils: {e}")
    
    try:
        print("6.3. Importando src.omie_client_async...")
        import src.omie_client_async
        print("6.4. src.omie_client_async OK")
    except Exception as e:
        print(f"6.4. ERRO em src.omie_client_async: {e}")
    
    try:
        print("6.5. Importando src.extrator_async...")
        import src.extrator_async
        print("6.6. src.extrator_async OK")
    except Exception as e:
        print(f"6.6. ERRO em src.extrator_async: {e}")
    
    print("7. Teste de importações locais concluído")
    
except Exception as e:
    print(f"ERRO GERAL: {e}")
    import traceback
    traceback.print_exc()

print("8. Teste de debug finalizado")
