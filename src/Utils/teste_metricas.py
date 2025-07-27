#!/usr/bin/env python3
"""
Teste rápido das novas funções de métricas
"""

import sys
import os

# Adiciona o diretório atual ao path
sys.path.insert(0, os.getcwd())

try:
    from src.utils import obter_metricas_completas_banco
    
    print("🧪 Testando métricas do banco...")
    
    metricas = obter_metricas_completas_banco("omie.db")
    
    if metricas:
        print(f"✅ Total de registros: {metricas.get('total', 0):,}")
        print(f"✅ XMLs baixados: {metricas.get('baixados', 0):,}")
        print(f"✅ Pendentes: {metricas.get('pendentes', 0):,}")
        print(f"✅ Status: {metricas.get('status_processamento', 'N/A')}")
        print(f"✅ Período: {metricas.get('data_inicio', 'N/A')} até {metricas.get('data_fim', 'N/A')}")
        print(" Métricas obtidas com sucesso!")
    else:
        print("❌ Erro ao obter métricas")
        
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()
