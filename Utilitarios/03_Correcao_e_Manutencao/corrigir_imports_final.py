#!/usr/bin/env python3
"""
Correção final dos imports nos testes organizados
"""
import re
import os
from pathlib import Path

def corrigir_path_imports(diretorio_testes):
    """Corrige o sys.path.insert para apontar corretamente para o src"""
    contadores = {"corrigidos": 0, "sem_alteracoes": 0, "erros": 0}
    
    print("🔧 CORREÇÃO FINAL DOS IMPORTS")
    print("="*50)
    
    # Padrão antigo e novo para sys.path.insert
    pattern_path = re.compile(r'sys\.path\.insert\(0,\s*str\(Path\(__file__\)\.parent.*?\)\)')
    replacement_path = 'sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))'
    
    for root, dirs, files in os.walk(diretorio_testes):
        for file in files:
            if file.endswith('.py'):
                filepath = Path(root) / file
                relative_path = filepath.relative_to(Path(diretorio_testes).parent)
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    original_content = content
                    
                    # Corrigir sys.path.insert
                    content = pattern_path.sub(replacement_path, content)
                    
                    if content != original_content:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(content)
                        print(f"   ✅ {relative_path}")
                        contadores["corrigidos"] += 1
                    else:
                        print(f"   ⏭️  {relative_path} (sem alterações)")
                        contadores["sem_alteracoes"] += 1
                        
                except Exception as e:
                    print(f"   ❌ Erro em {relative_path}: {e}")
                    contadores["erros"] += 1
    
    print("\n📊 RESULTADO:")
    print(f"   ✅ Arquivos corrigidos: {contadores['corrigidos']}")
    print(f"   ⏭️  Sem alterações: {contadores['sem_alteracoes']}")
    print(f"   ❌ Erros: {contadores['erros']}")
    print("🎯 Correção final concluída!")

if __name__ == "__main__":
    diretorio_testes = Path("Utilitarios/05_Testes_Organizados")
    if diretorio_testes.exists():
        corrigir_path_imports(diretorio_testes)
    else:
        print("❌ Diretório de testes não encontrado!")
