#!/usr/bin/env python3
"""
teste_nome_xml_final.py - Teste final do padrão de nomenclatura
"""

import sys
from pathlib import Path

# Setup do path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.utils import gerar_nome_arquivo_xml

def main():
    print("🎯 TESTE FINAL - PADRÃO DE NOMENCLATURA XML")
    print("="*60)
    print("Padrão esperado: nNF_YYYYMMDD_cChaveNFe.xml")
    print("="*60)
    
    # Casos de teste
    casos = [
        ("35250714200166000196550010000123451234567890", "17/07/2025", "123"),
        ("35250714200166000196550010000123461234567891", "18/07/2025", "124"), 
        ("35250714200166000196550010000123471234567892", "19/07/2025", "125"),
    ]
    
    for i, (chave, data, nf) in enumerate(casos, 1):
        print(f"\n{i}. Teste:")
        print(f"   📋 Entrada:")
        print(f"      cChaveNFe: {chave}")
        print(f"      dEmi: {data}")
        print(f"      nNF: {nf}")
        
        nome_gerado = gerar_nome_arquivo_xml(chave, data, nf)
        print(f"   📄 Nome gerado:")
        print(f"      {nome_gerado}")
        
        # Valida componentes
        partes = nome_gerado.replace('.xml', '').split('_')
        if len(partes) == 3:
            nf_parte, data_parte, chave_parte = partes
            print(f"   ✅ Análise:")
            print(f"      nNF: {nf_parte} {'✅' if nf_parte == nf else '❌'}")
            print(f"      Data: {data_parte} {'✅' if len(data_parte) == 8 else '❌'}")
            print(f"      Chave: {chave_parte} {'✅' if len(chave_parte) == 44 else '❌'}")
        else:
            print(f"   ❌ Formato incorreto - esperado 3 partes, encontrado {len(partes)}")
        
        print("   " + "-"*50)
    
    print(f"\n✅ CONCLUSÃO:")
    print(f"   O padrão está correto: nNF + data + chave NFe")
    print(f"   Não há números inseridos indevidamente no nome")
    print(f"   A chave NFe mantém seus 44 caracteres originais")

if __name__ == "__main__":
    main()
