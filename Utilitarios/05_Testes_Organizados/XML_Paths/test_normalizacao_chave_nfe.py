#!/usr/bin/env python3
"""
teste_normalizacao_chave.py - Teste da normalização de chave NFe
"""

import sys
from pathlib import Path

# Setup do path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.utils import gerar_nome_arquivo_xml, normalizar_chave_nfe

def main():
    print(" TESTE DE NORMALIZAÇÃO DE CHAVE NFE")
    print("="*50)
    
    # Chaves de teste problemáticas
    chaves_teste = [
        "35250714200166000196550010000123451234567890",  # 44 chars - parece OK
        "35250714200166000196550010000123461234567891",  # 44 chars
        "35250714200166000196550010000123471234567892",  # 44 chars
    ]
    
    print("📋 Analisando chaves de teste:")
    for i, chave in enumerate(chaves_teste, 1):
        print(f"\n{i}. Chave original:")
        print(f"   {chave}")
        print(f"   Comprimento: {len(chave)} caracteres")
        
        # Testa normalização
        chave_norm = normalizar_chave_nfe(chave)
        print(f"   Normalizada: {chave_norm}")
        print(f"   Comprimento: {len(chave_norm)} caracteres")
        
        # Testa geração de nome
        nome = gerar_nome_arquivo_xml(chave, "17/07/2025", "123")
        print(f"   Nome gerado: {nome}")
        
        # Analisa a estrutura da chave
        if len(chave) == 44:
            print(f"   ✅ Chave tem comprimento correto")
        else:
            print(f"   ❌ Chave com comprimento incorreto")
            
        # Mostra partes da chave
        if len(chave) >= 44:
            print(f"   📊 Estrutura da chave:")
            print(f"      UF + AAMM: {chave[:6]}")
            print(f"      CNPJ: {chave[6:20]}")
            print(f"      Modelo: {chave[20:22]}")
            print(f"      Série: {chave[22:25]}")
            print(f"      Número: {chave[25:34]}")
            print(f"      DV: {chave[43]}")
            if len(chave) > 44:
                print(f"      🚨 EXTRA: {chave[44:]} (SERÁ REMOVIDO)")
        
        print(f"   " + "-"*40)

if __name__ == "__main__":
    main()
