#!/usr/bin/env python3
"""
Teste individual dos módulos do src
"""

import sys
print("Testando módulos do src individualmente...")

modulos_para_testar = [
    "atualizar_caminhos_arquivos",
    "atualizar_query_params_ini", 
    "compactador_resultado",
    "extrator_async",
    "report_arquivos_vazios",
    "verificador_xmls",
]

for modulo in modulos_para_testar:
    try:
        print(f"Testando src.{modulo}...")
        __import__(f"src.{modulo}")
        print(f"✓ src.{modulo} OK")
    except Exception as e:
        print(f"✗ ERRO em src.{modulo}: {e}")
        import traceback
        traceback.print_exc()
        print("---")

print("Teste concluído")
