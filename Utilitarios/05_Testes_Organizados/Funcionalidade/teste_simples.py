#!/usr/bin/env python3
"""
Teste simples e direto do compactador
"""
import sys
from pathlib import Path

# Adiciona o diretório ao path
sys.path.insert(0, str(Path(__file__).parent))

print("🧪 Iniciando teste do compactador...")

try:
    from src.compactador_resultado import compactar_pasta_otimizada
    print("✅ Importação bem-sucedida!")
    
    # Testa com uma pasta pequena
    pasta_teste = Path(r"c:\milson\extrator_omie_v3\teste_pequeno")
    pasta_teste.mkdir(exist_ok=True)
    
    # Cria alguns arquivos de teste
    for i in range(3):
        arquivo = pasta_teste / f"teste_{i}.xml"
        arquivo.write_text(f"<xml>Conteúdo {i}</xml>")
    
    print(f"📁 Pasta de teste: {pasta_teste}")
    print(f"📄 Arquivos criados: 3")
    
    # Executa compactação
    resultado = compactar_pasta_otimizada(pasta_teste, limite=5)
    
    if resultado:
        print(f"✅ Compactação OK! Criados {len(resultado)} ZIPs")
        for arquivo in resultado:
            print(f"📦 {arquivo.name} ({arquivo.stat().st_size} bytes)")
    else:
        print("❌ Nenhum ZIP criado")
        
    # Limpeza
    import shutil
    shutil.rmtree(pasta_teste)
    print("🧹 Limpeza concluída")
    
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()
