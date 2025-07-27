#!/usr/bin/env python3
"""
Teste de imports mais detalhado
"""

import sys
print("Testando imports do main.py passo a passo...")

try:
    print("1. Imports básicos...")
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
    
    print("3. Testando imports específicos do src...")
    
    try:
        print("3.1. Import atualizar_caminhos_arquivos...")
        from src import atualizar_caminhos_arquivos
        print("3.2. atualizar_caminhos_arquivos OK")
    except Exception as e:
        print(f"3.2. ERRO: {e}")
        
    try:
        print("3.3. Import atualizar_query_params_ini...")
        from src import atualizar_query_params_ini
        print("3.4. atualizar_query_params_ini OK")
    except Exception as e:
        print(f"3.4. ERRO: {e}")
        
    try:
        print("3.5. Import compactador_resultado...")
        from src import compactador_resultado
        print("3.6. compactador_resultado OK")
    except Exception as e:
        print(f"3.6. ERRO: {e}")
        
    try:
        print("3.7. Import extrator_async...")
        from src import extrator_async
        print("3.8. extrator_async OK")
    except Exception as e:
        print(f"3.8. ERRO: {e}")
        
    try:
        print("3.9. Import report_arquivos_vazios...")
        from src import report_arquivos_vazios
        print("3.10. report_arquivos_vazios OK")
    except Exception as e:
        print(f"3.10. ERRO: {e}")
        
    try:
        print("3.11. Import verificador_xmls...")
        from src import verificador_xmls
        print("3.12. verificador_xmls OK")
    except Exception as e:
        print(f"3.12. ERRO: {e}")
        
    try:
        print("3.13. Import atualizar_campos_registros_pendentes...")
        from src.utils import atualizar_campos_registros_pendentes
        print("3.14. atualizar_campos_registros_pendentes OK")
    except Exception as e:
        print(f"3.14. ERRO: {e}")
    
    print("4. Teste de imports concluído")

except Exception as e:
    print(f"ERRO GERAL: {e}")
    import traceback
    traceback.print_exc()
