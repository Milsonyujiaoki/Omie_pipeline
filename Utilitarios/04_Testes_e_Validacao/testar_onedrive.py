#!/usr/bin/env python3
"""
Script de teste para verificar o sistema de upload OneDrive
"""

import sys
import os
from pathlib import Path

# Adiciona o diretorio raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

from src.upload_onedrive import sincronizar_historico_uploads, validar_configuracao_onedrive

def main():
    print(" Testando sistema de upload OneDrive...")
    
    # Verifica configuracoo
    print("\n1. Verificando configuracoo...")
    if validar_configuracao_onedrive():
        print("✅ Configuracoo valida")
    else:
        print("❌ Configuracoo invalida")
        return
    
    # Sincroniza historico
    print("\n2. Sincronizando historico com OneDrive...")
    arquivos_encontrados = sincronizar_historico_uploads()
    print(f"✅ Encontrados {arquivos_encontrados} arquivos no OneDrive")
    
    # Verifica arquivo de historico
    print("\n3. Verificando arquivo de historico...")
    historico_path = Path("uploads_realizados.json")
    if historico_path.exists():
        import json
        try:
            with open(historico_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                uploads = data.get('uploads', [])
                print(f"✅ Historico carregado: {len(uploads)} entradas")
                
                # Mostra alguns exemplos
                if uploads:
                    print("\nExemplos de arquivos no historico:")
                    for i, upload in enumerate(uploads[:5]):
                        print(f"  {i+1}. {upload}")
                    if len(uploads) > 5:
                        print(f"  ... e mais {len(uploads) - 5} arquivos")
                        
        except Exception as e:
            print(f"❌ Erro ao ler historico: {e}")
    else:
        print("❌ Arquivo de historico noo encontrado")
    
    print("\n Teste concluido!")

if __name__ == "__main__":
    main()
