#!/usr/bin/env python3
"""
Teste do compactador real com as correções aplicadas
"""

import sys
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

from src.compactador_resultado import compactar_pasta_otimizada

def teste_compactador_real():
    """Testa o compactador real com as correções"""
    
    print("🧪 Testando compactar_pasta_otimizada com correções...")
    
    # Pasta de teste (dia 20)
    pasta_origem = Path(r"c:\milson\extrator_omie_v3\resultado\2025\07\20")
    
    if not pasta_origem.exists():
        print(f"❌ Pasta não encontrada: {pasta_origem}")
        return
    
    xml_files = list(pasta_origem.glob("*.xml"))
    if not xml_files:
        print(f"❌ Nenhum arquivo XML encontrado em: {pasta_origem}")
        return
    
    print(f"📊 Pasta: {pasta_origem}")
    print(f"📊 Arquivos XML encontrados: {len(xml_files)}")
    
    # Testa apenas uma compactação pequena (primeiros 10 arquivos)
    pasta_teste = Path(r"c:\milson\extrator_omie_v3\teste_compactacao")
    pasta_teste.mkdir(exist_ok=True)
    
    # Copia apenas alguns arquivos para teste
    import shutil
    for i, xml_file in enumerate(xml_files[:10]):
        shutil.copy2(xml_file, pasta_teste / xml_file.name)
    
    print(f"📁 Pasta de teste criada: {pasta_teste}")
    print(f"📊 Arquivos copiados: 10")
    
    # Executa compactação
    try:
        resultado = compactar_pasta_otimizada(
            origem=pasta_teste,
            limite=10  # Limite pequeno para teste
        )
        
        if resultado:
            print(f"✅ Compactação bem-sucedida!")
            print(f"📦 Arquivos criados: {len(resultado)}")
            
            for arquivo_zip in resultado:
                print(f"📦 Arquivo: {arquivo_zip}")
                print(f"📊 Tamanho: {arquivo_zip.stat().st_size / 1024:.1f} KB")
                
                # Verifica estrutura interna
                import zipfile
                print(f"🔍 Verificando estrutura interna de {arquivo_zip.name}:")
                with zipfile.ZipFile(arquivo_zip, 'r') as zipf:
                    for info in zipf.infolist()[:3]:  # Mostra apenas os primeiros 3
                        print(f"  📄 {info.filename}")
                    if len(zipf.infolist()) > 3:
                        print(f"  ... e mais {len(zipf.infolist()) - 3} arquivos")
        else:
            print(f"❌ Nenhum arquivo foi criado pela compactação")
            
    except Exception as e:
        print(f"❌ Erro durante teste: {e}")
        import traceback
        traceback.print_exc()
    
    # Limpeza
    try:
        shutil.rmtree(pasta_teste)
        print(f"\n🧹 Pasta de teste removida")
    except:
        pass

if __name__ == "__main__":
    teste_compactador_real()
