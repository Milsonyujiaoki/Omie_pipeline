#!/usr/bin/env python3
"""
Teste de imports na mesma ordem do main.py
"""

import sys
print("Testando imports na mesma ordem do main.py...")

try:
    print("1. Import coletivo...")
    from src import (
        atualizar_caminhos_arquivos,
        atualizar_query_params_ini,
        compactador_resultado,
        extrator_async,
        report_arquivos_vazios,
        verificador_xmls,
    )
    print("2. Import coletivo OK")
    
    print("3. Import src.utils...")
    from src.utils import (
        atualizar_campos_registros_pendentes,
    )
    print("4. Import src.utils OK")
    
    print("5. Todos os imports concluídos com sucesso!")
    
except Exception as e:
    print(f"ERRO: {e}")
    import traceback
    traceback.print_exc()

print("Teste finalizado")
