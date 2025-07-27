#!/usr/bin/env python3
"""Script para debug do problema de duplicatas."""

import re
from pathlib import Path

def _esta_em_subpasta(caminho: str) -> bool:
    """Verifica se arquivo está em subpasta com padrão XX_pasta_Y."""
    padrao_subpasta = r'\\(\d+)_pasta_(\d+)\\'
    return re.search(padrao_subpasta, caminho) is not None

def _esta_na_pasta_dia(caminho: str) -> bool:
    """Verifica se arquivo está diretamente na pasta do dia."""
    padrao_pasta_dia = r'\\resultado\\(\d{4})\\(\d{2})\\(\d{2})\\[^\\]+\.xml$'
    return re.search(padrao_pasta_dia, caminho) is not None

def _e_duplicata_pasta_dia_vs_subpasta_debug(arquivos):
    """Debug da função de detecção de duplicatas."""
    if len(arquivos) != 2:
        print(f"DEBUG: Não são exatamente 2 arquivos: {len(arquivos)}")
        return False
    
    # Separar arquivos por tipo de localização
    arquivo_pasta_dia = None
    arquivo_subpasta = None
    
    for arquivo in arquivos:
        caminho_str = str(arquivo)
        print(f"DEBUG: Analisando caminho: {caminho_str}")
        
        # Verificar se está em subpasta (padrão: XX_pasta_Y)
        if _esta_em_subpasta(caminho_str):
            print(f"DEBUG: Arquivo em subpasta: {caminho_str}")
            arquivo_subpasta = arquivo
        else:
            # Verificar se está diretamente na pasta do dia
            if _esta_na_pasta_dia(caminho_str):
                print(f"DEBUG: Arquivo na pasta do dia: {caminho_str}")
                arquivo_pasta_dia = arquivo
            else:
                print(f"DEBUG: Arquivo não classificado: {caminho_str}")
    
    resultado = arquivo_pasta_dia is not None and arquivo_subpasta is not None
    print(f"DEBUG: Pasta dia encontrada: {arquivo_pasta_dia}")
    print(f"DEBUG: Subpasta encontrada: {arquivo_subpasta}")
    print(f"DEBUG: É duplicata resolvível: {resultado}")
    
    return resultado

if __name__ == "__main__":
    # Teste com caminhos reais
    caminhos_teste = [
        "c:\\milson\\extrator_omie_v3\\resultado\\2025\\07\\21\\arquivo.xml",
        "c:\\milson\\extrator_omie_v3\\resultado\\2025\\07\\21\\21_pasta_1\\arquivo.xml"
    ]
    
    print("=== TESTE COM CAMINHOS REAIS ===")
    resultado = _e_duplicata_pasta_dia_vs_subpasta_debug(caminhos_teste)
    print(f"Resultado final: {resultado}")
    
    print("\n=== TESTE INDIVIDUAL ===")
    for caminho in caminhos_teste:
        print(f"Caminho: {caminho}")
        print(f"  - Em subpasta: {_esta_em_subpasta(caminho)}")
        print(f"  - Na pasta dia: {_esta_na_pasta_dia(caminho)}")
        print()
