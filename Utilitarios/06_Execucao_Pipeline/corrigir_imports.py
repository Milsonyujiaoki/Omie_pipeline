#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
corrigir_imports.py

Script para corrigir imports nos arquivos de teste organizados.
Ajusta os caminhos relativos para apontar corretamente para o módulo src.
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple

def corrigir_imports_arquivo(arquivo: Path) -> bool:
    """Corrige imports em um arquivo específico"""
    try:
        with open(arquivo, 'r', encoding='utf-8') as f:
            conteudo = f.read()
        
        conteudo_original = conteudo
        
        # Padrões de import para corrigir
        patterns = [
            # from src.utils import ... → from src.utils import ...
            (r'from src.utils import', 'from src.utils import'),
            # import src.utils as utils → import src.utils as utils
            (r'^import src.utils as utils$', 'import src.utils as utils'),
            # sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            (r'sys\.path\.insert\(0, str\(Path\(__file__\)\.parent / "src"\)\)', 
             'sys.path.insert(0, str(Path(__file__).parent.parent.parent))'),
            # sys.path.insert(0, "src")
            (r'sys\.path\.insert\(0, ["\']src["\']\)', 
             'sys.path.insert(0, str(Path(__file__).parent.parent.parent))'),
            # sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            (r'sys\.path\.insert\(0, str\(Path\(__file__\)\.parent\)\)', 
             'sys.path.insert(0, str(Path(__file__).parent.parent.parent))'),
        ]
        
        for pattern, replacement in patterns:
            conteudo = re.sub(pattern, replacement, conteudo, flags=re.MULTILINE)
        
        # Verificar se precisa adicionar import do Path
        if 'Path(__file__).parent.parent.parent' in conteudo and 'from pathlib import Path' not in conteudo:
            # Adicionar import do Path se não existir
            linhas = conteudo.split('\n')
            import_adicionado = False
            
            for i, linha in enumerate(linhas):
                if linha.startswith('import ') and not import_adicionado:
                    linhas.insert(i, 'from pathlib import Path')
                    import_adicionado = True
                    break
            
            if not import_adicionado:
                # Adicionar no início se não encontrou lugar melhor
                linhas.insert(0, 'from pathlib import Path')
            
            conteudo = '\n'.join(linhas)
        
        # Salvar apenas se houver mudanças
        if conteudo != conteudo_original:
            with open(arquivo, 'w', encoding='utf-8') as f:
                f.write(conteudo)
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ Erro ao processar {arquivo}: {e}")
        return False

def main():
    """Função principal"""
    print("🔧 CORREÇÃO DE IMPORTS - TESTES ORGANIZADOS")
    print("="*50)
    
    # Localizar pasta de testes organizados
    pasta_testes = Path("Utilitarios/05_Testes_Organizados")
    
    if not pasta_testes.exists():
        print("❌ Pasta de testes organizados não encontrada!")
        print("   Execute primeiro: python organizador_testes.py")
        sys.exit(1)
    
    # Encontrar todos os arquivos .py
    arquivos_python = list(pasta_testes.rglob("*.py"))
    
    # Filtrar apenas arquivos de teste (não READMEs convertidos)
    arquivos_teste = [arq for arq in arquivos_python if not arq.name.startswith('README')]
    
    print(f"📋 Encontrados {len(arquivos_teste)} arquivos para corrigir")
    
    corrigidos = 0
    erros = 0
    
    for arquivo in arquivos_teste:
        try:
            if corrigir_imports_arquivo(arquivo):
                print(f"   ✅ {arquivo.relative_to(pasta_testes)}")
                corrigidos += 1
            else:
                print(f"   ⏭️  {arquivo.relative_to(pasta_testes)} (sem alterações)")
        except Exception as e:
            print(f"   ❌ {arquivo.relative_to(pasta_testes)}: {e}")
            erros += 1
    
    print(f"\n📊 RESULTADO:")
    print(f"   ✅ Arquivos corrigidos: {corrigidos}")
    print(f"   ⏭️  Sem alterações: {len(arquivos_teste) - corrigidos - erros}")
    print(f"   ❌ Erros: {erros}")
    
    if erros == 0:
        print(f"\n Correção concluída com sucesso!")
    else:
        print(f"\n⚠️  Correção concluída com {erros} erros")

if __name__ == "__main__":
    main()
