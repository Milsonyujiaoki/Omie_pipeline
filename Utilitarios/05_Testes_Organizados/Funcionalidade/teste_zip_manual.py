#!/usr/bin/env python3
"""
Teste manual para verificar a correção da estrutura do ZIP
"""

import zipfile
from pathlib import Path
import os

def teste_zip_estrutura():
    """Testa a criação de ZIP com estrutura correta"""
    
    # Caminho de teste
    pasta_origem = Path(r"c:\milson\extrator_omie_v3\resultado\2025\07\20")
    arquivo_zip = Path(r"c:\milson\extrator_omie_v3\teste_pasta_20.zip")
    
    print(f"📁 Testando ZIP da pasta: {pasta_origem}")
    print(f"📦 Arquivo ZIP será criado em: {arquivo_zip}")
    
    # Lista arquivos XML
    xml_files = list(pasta_origem.glob("*.xml"))
    if not xml_files:
        print("❌ Nenhum arquivo XML encontrado!")
        return
    
    print(f"📊 Encontrados {len(xml_files)} arquivos XML")
    
    # Cria ZIP com estrutura correta (sem pasta interna)
    with zipfile.ZipFile(arquivo_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for xml_file in xml_files[:5]:  # Testa apenas com 5 arquivos para não demorar
            # CORREÇÃO: usa apenas o nome do arquivo, não o caminho completo
            zipf.write(xml_file, xml_file.name)
            print(f"  ✅ Adicionado: {xml_file.name}")
    
    print(f"\n🎉 ZIP criado com sucesso!")
    print(f"📁 Tamanho: {arquivo_zip.stat().st_size / 1024:.1f} KB")
    
    # Verifica conteúdo do ZIP
    print("\n🔍 Verificando estrutura interna do ZIP:")
    with zipfile.ZipFile(arquivo_zip, 'r') as zipf:
        for info in zipf.infolist():
            print(f"  📄 {info.filename}")
    
    print(f"\n✅ Teste concluído! Arquivo criado: {arquivo_zip}")

if __name__ == "__main__":
    teste_zip_estrutura()
