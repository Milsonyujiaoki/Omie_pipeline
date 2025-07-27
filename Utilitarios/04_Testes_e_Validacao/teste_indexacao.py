#!/usr/bin/env python3
"""
Teste da função de indexação otimizada de XMLs.
"""

import sys
import time
from pathlib import Path
from src.utils import _indexar_xmls_por_chave

def main():
    print("=== TESTE DA INDEXAÇÃO OTIMIZADA DE XMLs ===")
    
    resultado_dir = "c:/milson/extrator_omie_v3/resultado"
    
    # Verifica se o diretório existe
    if not Path(resultado_dir).exists():
        print(f"ERRO: Diretório não encontrado: {resultado_dir}")
        return
    
    print(f"Testando indexação em: {resultado_dir}")
    print("Iniciando...")
    
    # Mede o tempo da indexação
    inicio = time.time()
    
    try:
        xml_index = _indexar_xmls_por_chave(resultado_dir)
        
        tempo_total = time.time() - inicio
        
        print(f"\n=== RESULTADOS ===")
        print(f"Tempo total: {tempo_total:.2f} segundos")
        print(f"Arquivos indexados: {len(xml_index)}")
        
        if xml_index:
            print(f"Taxa de indexação: {len(xml_index) / tempo_total:.0f} arquivos/segundo")
            
            # Mostra algumas chaves como exemplo
            print(f"\nPrimeiras 5 chaves indexadas:")
            for i, (chave, caminho) in enumerate(list(xml_index.items())[:5]):
                print(f"  {i+1}. {chave} -> {caminho.name}")
        
        print(f"\n=== TESTE CONCLUÍDO ===")
        
    except Exception as e:
        print(f"ERRO durante indexação: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
