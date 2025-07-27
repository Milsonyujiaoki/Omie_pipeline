#!/usr/bin/env python3
"""
Script para reorganizar a pasta DEV do projeto Extrator Omie V3.

Este script:
1. Cria estrutura organizada de pastas
2. Move arquivos para categorias apropriadas  
3. Remove redundâncias
4. Gera relatório da reorganização
5. Cria índice de navegação

Estrutura final:
├── 01_ANALISES/           # Análises técnicas e comparativas
├── 02_IMPLEMENTACOES/     # Implementações e integrações
├── 03_OTIMIZACOES/        # Otimizações e melhorias de performance
├── 04_RELATORIOS/         # Relatórios e documentação final
├── 05_INTEGRACOES/        # Integrações com APIs externas
├── 06_UTILS_TESTES/       # Utilitários e scripts de teste
├── 07_VERSOES_HISTORICAS/ # Versões antigas (PROD/)
└── _INDICE_NAVEGACAO.md   # Índice para navegação rápida
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# =============================================================================
# Configurações
# =============================================================================

DEV_PATH = Path(__file__).parent
BACKUP_PATH = DEV_PATH / "backup_reorganizacao"

# Mapeamento de arquivos para categorias
ESTRUTURA_ORGANIZACAO = {
    "01_ANALISES": {
        "descricao": "Análises técnicas e comparativas do sistema",
        "arquivos": [
            "ANALISE_COMPARATIVA_EXTRATORES.md",
            "ANALISE_MODULOS_RELATORIO.md", 
            "ANALISE_PROBLEMAS_PIPELINE.md",
            "ANALISE_UPLOAD_ONEDRIVE.md",
            "RELATORIO_ANALISE_FUNCOES_MODULOS.md",
            "RELATORIO_INVESTIGACAO_425.md",
            "verificar_compatibilidade.py"
        ]
    },
    "02_IMPLEMENTACOES": {
        "descricao": "Implementações e integrações realizadas",
        "arquivos": [
            "ADAPTACAO_MAIN_RESUMO.md",
            "IMPLEMENTACAO_PIPELINE_HIBRIDO_CONCLUIDA.md",
            "INTEGRACAO_ANOMESDIA_RELATORIO.md",
            "INTEGRACAO_MUDANCAS_MAIN.md",
            "COMO_USAR_PIPELINE_ADAPTATIVO.md",
            "README_PIPELINE_ADAPTATIVO.md"
        ]
    },
    "03_OTIMIZACOES": {
        "descricao": "Otimizações e melhorias de performance",
        "arquivos": [
            "OTIMIZACOES_ANALISE_COMPLETA_DB.md",
            "OTIMIZACOES_FASE9.md", 
            "OTIMIZACOES_VERIFICADOR_XMLS.md",
            "RELATORIO_OTIMIZACAO_INDEXACAO.md",
            "CORRECOES_ANALISE_COMPLETA_DB.md",
            "MELHORIAS_ERRO_425.md",
            "TIMEOUT_30_MINUTOS.md"
        ]
    },
    "04_RELATORIOS": {
        "descricao": "Relatórios finais e documentação consolidada",
        "arquivos": [
            "RELATORIO_COMPATIBILIDADE_FINAL.md",
            "RELATORIO_COMPLETO_ORGANIZACAO.md",
            "RELATORIO_DIVISAO_UTILS.md",
            "RELATORIO_LOGS_ESTRUTURADOS_ATUALIZAR_CAMINHOS.md",
            "RELATORIO_ORGANIZACAO_TESTES.md",
            "STATUS_EXECUCAO_PIPELINE.md",
            "relatorio_compatibilidade.txt",
            "relatorio_imports_20250723_012409.txt",
            "relatorio_organizacao_20250723_012229.txt"
        ]
    },
    "05_INTEGRACOES": {
        "descricao": "Integrações com APIs externas e serviços",
        "arquivos": [
            "Api_sharepoint/"  # Pasta inteira
        ]
    },
    "06_UTILS_TESTES": {
        "descricao": "Utilitários, scripts de teste e limpeza",
        "arquivos": [
            "LIMPEZA_PROJETO.md",
            "ARQUIVOS_REMOVIDOS.md"
        ]
    },
    "07_VERSOES_HISTORICAS": {
        "descricao": "Versões históricas e código legado",
        "arquivos": [
            "PROD/"  # Pasta inteira
        ]
    }
}

# =============================================================================
# Funções auxiliares
# =============================================================================

def criar_backup() -> None:
    """Cria backup da estrutura atual antes da reorganização."""
    print("[BACKUP] Criando backup da estrutura atual...")
    
    if BACKUP_PATH.exists():
        shutil.rmtree(BACKUP_PATH)
    
    BACKUP_PATH.mkdir()
    
    # Copia todos os arquivos e pastas para backup
    for item in DEV_PATH.iterdir():
        if item.name == "backup_reorganizacao" or item.name == "reorganizar_dev.py":
            continue
            
        if item.is_file():
            shutil.copy2(item, BACKUP_PATH / item.name)
        elif item.is_dir():
            shutil.copytree(item, BACKUP_PATH / item.name)
    
    print(f"[BACKUP] Backup criado em: {BACKUP_PATH}")

def criar_estrutura_pastas() -> None:
    """Cria a nova estrutura de pastas organizadas."""
    print("[ESTRUTURA] Criando nova estrutura de pastas...")
    
    for pasta, info in ESTRUTURA_ORGANIZACAO.items():
        pasta_path = DEV_PATH / pasta
        pasta_path.mkdir(exist_ok=True)
        
        # Cria README.md em cada pasta
        readme_path = pasta_path / "README.md"
        readme_content = f"""# {pasta.replace('_', ' ').title()}

{info['descricao']}

## Arquivos nesta categoria:
"""
        for arquivo in info['arquivos']:
            readme_content += f"- `{arquivo}`\n"
        
        readme_content += f"""
---
*Reorganizado automaticamente em {datetime.now().strftime('%d/%m/%Y às %H:%M')}*
"""
        
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        print(f"[ESTRUTURA] Criada pasta: {pasta}")

def mover_arquivos() -> Tuple[List[str], List[str]]:
    """Move arquivos para as categorias apropriadas."""
    print("[MOVIMENTACAO] Movendo arquivos para categorias...")
    
    movidos = []
    nao_encontrados = []
    
    for pasta, info in ESTRUTURA_ORGANIZACAO.items():
        pasta_destino = DEV_PATH / pasta
        
        for arquivo in info['arquivos']:
            origem = DEV_PATH / arquivo
            
            if origem.exists():
                destino = pasta_destino / arquivo
                
                try:
                    if origem.is_file():
                        shutil.move(str(origem), str(destino))
                    elif origem.is_dir():
                        if destino.exists():
                            shutil.rmtree(destino)
                        shutil.move(str(origem), str(destino))
                    
                    movidos.append(f"{arquivo} -> {pasta}")
                    print(f"[MOVIMENTACAO] {arquivo} -> {pasta}")
                    
                except Exception as e:
                    print(f"[ERRO] Erro ao mover {arquivo}: {e}")
                    nao_encontrados.append(f"{arquivo} (erro: {e})")
            else:
                nao_encontrados.append(arquivo)
                print(f"[AVISO] Arquivo não encontrado: {arquivo}")
    
    return movidos, nao_encontrados

def gerar_indice_navegacao(movidos: List[str], nao_encontrados: List[str]) -> None:
    """Gera índice de navegação da nova estrutura."""
    print("[INDICE] Gerando índice de navegação...")
    
    indice_content = f"""# 📁 Índice de Navegação - DEV Reorganizado

*Reorganizado automaticamente em {datetime.now().strftime('%d/%m/%Y às %H:%M')}*

## 🗂️ Estrutura Organizacional

"""
    
    for pasta, info in ESTRUTURA_ORGANIZACAO.items():
        pasta_nome = pasta.replace('_', ' ').title()
        indice_content += f"""### 📂 [{pasta_nome}](./{pasta}/)
**Descrição:** {info['descricao']}

**Arquivos:**
"""
        for arquivo in info['arquivos']:
            if arquivo.endswith('/'):
                indice_content += f"- 📁 `{arquivo[:-1]}/` (pasta)\n"
            else:
                indice_content += f"- 📄 `{arquivo}`\n"
        
        indice_content += "\n"
    
    # Seção de estatísticas
    indice_content += f"""## 📊 Estatísticas da Reorganização

- **Arquivos movidos:** {len(movidos)}
- **Arquivos não encontrados:** {len(nao_encontrados)}
- **Pastas criadas:** {len(ESTRUTURA_ORGANIZACAO)}

### ✅ Arquivos Movidos com Sucesso:
"""
    
    for movimento in movidos:
        indice_content += f"- {movimento}\n"
    
    if nao_encontrados:
        indice_content += f"""
### ⚠️ Arquivos Não Encontrados:
"""
        for arquivo in nao_encontrados:
            indice_content += f"- {arquivo}\n"
    
    indice_content += f"""
## 🔄 Recuperação

Se precisar desfazer a reorganização, use o backup criado em:
```
{BACKUP_PATH}
```

## 📝 Navegação Rápida

- Para **análises técnicas** → [`01_ANALISES/`](./01_ANALISES/)
- Para **implementações** → [`02_IMPLEMENTACOES/`](./02_IMPLEMENTACOES/)  
- Para **otimizações** → [`03_OTIMIZACOES/`](./03_OTIMIZACOES/)
- Para **relatórios finais** → [`04_RELATORIOS/`](./04_RELATORIOS/)
- Para **integrações** → [`05_INTEGRACOES/`](./05_INTEGRACOES/)
- Para **utils e testes** → [`06_UTILS_TESTES/`](./06_UTILS_TESTES/)
- Para **versões antigas** → [`07_VERSOES_HISTORICAS/`](./07_VERSOES_HISTORICAS/)

---
*Gerado por: reorganizar_dev.py*
"""
    
    indice_path = DEV_PATH / "_INDICE_NAVEGACAO.md"
    with open(indice_path, 'w', encoding='utf-8') as f:
        f.write(indice_content)
    
    print(f"[INDICE] Índice criado: {indice_path}")

def gerar_relatorio_final(movidos: List[str], nao_encontrados: List[str]) -> None:
    """Gera relatório final da reorganização."""
    print("[RELATORIO] Gerando relatório final...")
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    relatorio_path = DEV_PATH / f"_relatorio_reorganizacao_{timestamp}.log"
    
    relatorio_content = f"""RELATÓRIO DE REORGANIZAÇÃO - DEV FOLDER
Data: {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}
======================================================

ESTRUTURA CRIADA:
"""
    
    for pasta, info in ESTRUTURA_ORGANIZACAO.items():
        relatorio_content += f"\n{pasta}/\n  Descrição: {info['descricao']}\n  Arquivos: {len(info['arquivos'])}\n"
    
    relatorio_content += f"""
ESTATÍSTICAS:
- Pastas criadas: {len(ESTRUTURA_ORGANIZACAO)}
- Arquivos movidos: {len(movidos)}
- Arquivos não encontrados: {len(nao_encontrados)}
- Backup criado em: {BACKUP_PATH}

MOVIMENTAÇÕES REALIZADAS:
"""
    
    for movimento in movidos:
        relatorio_content += f"✅ {movimento}\n"
    
    if nao_encontrados:
        relatorio_content += f"\nARQUIVOS NÃO ENCONTRADOS:\n"
        for arquivo in nao_encontrados:
            relatorio_content += f"❌ {arquivo}\n"
    
    relatorio_content += f"""
CONCLUSÃO:
Reorganização concluída com sucesso!
Nova estrutura disponível com índice de navegação em _INDICE_NAVEGACAO.md

======================================================
"""
    
    with open(relatorio_path, 'w', encoding='utf-8') as f:
        f.write(relatorio_content)
    
    print(f"[RELATORIO] Relatório salvo: {relatorio_path}")

# =============================================================================
# Função principal
# =============================================================================

def main():
    """Executa a reorganização completa da pasta DEV."""
    print("=" * 60)
    print("🔄 REORGANIZAÇÃO AUTOMÁTICA DA PASTA DEV")
    print("=" * 60)
    print(f"📁 Diretório: {DEV_PATH}")
    print(f"⏰ Início: {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}")
    print()
    
    try:
        # Etapa 1: Backup
        criar_backup()
        print()
        
        # Etapa 2: Criar estrutura
        criar_estrutura_pastas()
        print()
        
        # Etapa 3: Mover arquivos
        movidos, nao_encontrados = mover_arquivos()
        print()
        
        # Etapa 4: Gerar índice
        gerar_indice_navegacao(movidos, nao_encontrados)
        print()
        
        # Etapa 5: Relatório final
        gerar_relatorio_final(movidos, nao_encontrados)
        print()
        
        # Resumo final
        print("=" * 60)
        print("✅ REORGANIZAÇÃO CONCLUÍDA COM SUCESSO!")
        print("=" * 60)
        print(f"📊 Estatísticas:")
        print(f"   • Pastas criadas: {len(ESTRUTURA_ORGANIZACAO)}")
        print(f"   • Arquivos movidos: {len(movidos)}")
        print(f"   • Arquivos não encontrados: {len(nao_encontrados)}")
        print()
        print(f"📖 Navegação: _INDICE_NAVEGACAO.md")
        print(f"💾 Backup: {BACKUP_PATH}")
        print(f"⏰ Concluído: {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ ERRO CRÍTICO: {e}")
        print(f"💾 Backup disponível em: {BACKUP_PATH}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
