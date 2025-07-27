#!/usr/bin/env python3
"""
Corretor Avançado de Imports - Nova Estrutura
==============================================

Este script corrige todos os imports da nova estrutura de código,
seguindo os padrões da Clean Architecture implementada.

FUNCIONALIDADES:
✅ Correção automática de imports relativos e absolutos
✅ Atualização de paths sys.path.insert
✅ Mapeamento inteligente de módulos movidos
✅ Backup de segurança antes das correções
✅ Validação de sintaxe após correções
✅ Relatório detalhado de alterações
"""

import re
import ast
import shutil
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from datetime import datetime
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CorretorImports:
    """
    Corretor avançado de imports para a nova estrutura.
    
    Mapeia automaticamente os imports antigos para os novos caminhos
    e corrige todas as referências de forma inteligente.
    """
    
    def __init__(self, src_novo_dir: Path = Path("src_novo")):
        self.src_novo_dir = src_novo_dir
        self.backup_dir = src_novo_dir.parent / f"backup_imports_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Mapeamento de módulos movidos
        self.mapeamento_modulos = self._criar_mapeamento_modulos()
        
        # Estatísticas
        self.arquivos_corrigidos = 0
        self.imports_corrigidos = 0
        self.erros_encontrados = []
    
    def _criar_mapeamento_modulos(self) -> Dict[str, str]:
        """Cria mapeamento dos módulos antigos para novos."""
        return {
            # Imports principais
            "src.utils": "src.utils.utils",
            "src.omie_client_async": "src.adapters.external_apis.omie.omie_client_async",
            "src.extrator_async": "src.application.services.extrator_async",
            "src.verificador_xmls": "src.application.services.verificador_xmls",
            "src.upload_onedrive": "src.adapters.external_apis.onedrive.upload_onedrive",
            "src.compactador_resultado": "src.application.services.compactador_resultado",
            "src.report_arquivos_vazios": "src.application.services.report_arquivos_vazios",
            "src.atualizar_caminhos_arquivos": "src.application.services.atualizar_caminhos_arquivos",
            "src.atualizar_query_params_ini": "src.infrastructure.config.atualizar_query_params_ini",
            
            # Imports do utils
            "utils": "src.utils.utils",
            "src.Utils.check_db_structure": "src.adapters.database.repositories.check_db_structure",
            "src.Utils.verificar_duplicatas": "src.adapters.database.repositories.verificar_duplicatas",
            "src.Utils.padronizar_datas_otimizado": "src.adapters.database.repositories.padronizar_datas_otimizado",
            
            # Deprecated movidos
            "src.Deprecated.baixar_parallel": "src.adapters.database.repositories.baixar_parallel",
            "src.Deprecated.gerenciador_modos": "src.adapters.database.repositories.gerenciador_modos",
            "src.Deprecated.main_refatorado": "src.infrastructure.config.main_refatorado",
            "src.Deprecated.relatorio_rapido": "src.adapters.external_apis.relatorio_rapido",
        }
    
    def executar_correcao(self) -> None:
        """Executa todo o processo de correção."""
        try:
            logger.info("🔧 INICIANDO CORREÇÃO AVANÇADA DE IMPORTS")
            logger.info("=" * 50)
            
            # 1. Criar backup
            self._criar_backup()
            
            # 2. Corrigir imports em todos os arquivos
            self._corrigir_todos_imports()
            
            # 3. Corrigir sys.path.insert
            self._corrigir_sys_path()
            
            # 4. Validar sintaxe
            self._validar_sintaxe()
            
            # 5. Relatório final
            self._gerar_relatorio_final()
            
            logger.info("✅ CORREÇÃO CONCLUÍDA COM SUCESSO!")
            
        except Exception as e:
            logger.exception(f"❌ Erro durante correção: {e}")
            raise
    
    def _criar_backup(self) -> None:
        """Cria backup antes das correções."""
        logger.info(f"💾 Criando backup: {self.backup_dir}")
        shutil.copytree(self.src_novo_dir, self.backup_dir)
        logger.info("✓ Backup criado")
    
    def _corrigir_todos_imports(self) -> None:
        """Corrige imports em todos os arquivos Python."""
        logger.info("Corrigindo imports...")
        
        for arquivo in self.src_novo_dir.rglob("*.py"):
            if arquivo.name == "__init__.py":
                continue
                
            try:
                corrigido = self._corrigir_arquivo(arquivo)
                if corrigido:
                    self.arquivos_corrigidos += 1
                    
            except Exception as e:
                erro = f"Erro em {arquivo}: {e}"
                self.erros_encontrados.append(erro)
                logger.warning(erro)
        
        logger.info(f"✓ {self.arquivos_corrigidos} arquivos corrigidos")
    
    def _corrigir_arquivo(self, arquivo: Path) -> bool:
        """Corrige imports em um arquivo específico."""
        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                conteudo = f.read()
            
            conteudo_original = conteudo
            imports_corrigidos_arquivo = 0
            
            # 1. Corrigir imports from
            for import_antigo, import_novo in self.mapeamento_modulos.items():
                # Padrão: from src.modulo import ...
                pattern_from = rf'from\\s+{re.escape(import_antigo)}\\s+import'
                replacement_from = f'from {import_novo} import'
                
                matches = re.findall(pattern_from, conteudo)
                if matches:
                    conteudo = re.sub(pattern_from, replacement_from, conteudo)
                    imports_corrigidos_arquivo += len(matches)
                
                # Padrão: import src.modulo
                pattern_import = rf'import\\s+{re.escape(import_antigo)}(?=\\s|$|;)'
                replacement_import = f'import {import_novo}'
                
                matches = re.findall(pattern_import, conteudo)
                if matches:
                    conteudo = re.sub(pattern_import, replacement_import, conteudo)
                    imports_corrigidos_arquivo += len(matches)
            
            # 2. Correções específicas comuns
            correcoes_especificas = [
                # Ajustar imports relativos
                (r'from\\s+src\\s+import', 'from src'),
                (r'from\\s+\\.\\s+import', 'from . import'),
                (r'from\\s+\\.\\.\\s+import', 'from .. import'),
                
                # Corrigir imports de utils específicos
                (r'from\\s+src\\.utils\\s+import\\s+([\\w,\\s]+)', r'from src.utils.utils import \\1'),
                (r'from\\s+utils\\s+import\\s+([\\w,\\s]+)', r'from src.utils.utils import \\1'),
                
                # Importações diretas de funções comuns
                (r'from\\s+src\\.omie_client_async\\s+import\\s+([\\w,\\s]+)', 
                 r'from src.adapters.external_apis.omie.omie_client_async import \\1'),
                
                # Correções de OmieClient específico
                (r'from\\s+src\\.omie_client_async\\s+import\\s+OmieClient',
                 'from src.adapters.external_apis.omie.omie_client_async import OmieClient'),
            ]
            
            for pattern, replacement in correcoes_especificas:
                matches = re.findall(pattern, conteudo)
                if matches:
                    conteudo = re.sub(pattern, replacement, conteudo)
                    imports_corrigidos_arquivo += len(matches)
            
            # 3. Salvar se houver alterações
            if conteudo != conteudo_original:
                with open(arquivo, 'w', encoding='utf-8') as f:
                    f.write(conteudo)
                
                self.imports_corrigidos += imports_corrigidos_arquivo
                logger.debug(f"  ✓ {arquivo.relative_to(self.src_novo_dir)}: {imports_corrigidos_arquivo} imports")
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Erro ao corrigir {arquivo}: {e}")
            return False
    
    def _corrigir_sys_path(self) -> None:
        """Corrige declarações sys.path.insert."""
        logger.info("🔧 Corrigindo sys.path.insert...")
        
        contador = 0
        for arquivo in self.src_novo_dir.rglob("*.py"):
            if arquivo.name == "__init__.py":
                continue
                
            try:
                with open(arquivo, 'r', encoding='utf-8') as f:
                    conteudo = f.read()
                
                conteudo_original = conteudo
                
                # Calcula profundidade relativa ao src_novo
                profundidade = len(arquivo.relative_to(self.src_novo_dir).parts) - 1
                
                # Determina quantos '.parent' são necessários
                if profundidade == 0:  # Arquivo na raiz de src_novo
                    parents_needed = 1  # src_novo -> raiz do projeto
                else:  # Arquivo em subpasta
                    parents_needed = profundidade + 1
                
                # Constrói string de parents
                parent_chain = ".parent" * parents_needed
                
                # Padrões a corrigir
                patterns = [
                    r'sys\\.path\\.insert\\(0,\\s*str\\(Path\\(__file__\\)\\.parent\\.parent\\)\\)',
                    r'sys\\.path\\.insert\\(0,\\s*str\\(Path\\(__file__\\)\\.parent\\.parent\\.parent\\)\\)',
                    r'sys\\.path\\.insert\\(0,\\s*str\\(Path\\(__file__\\)\\.parent\\)\\)',
                ]
                
                replacement = f'sys.path.insert(0, str(Path(__file__){parent_chain}))'
                
                corrigido = False
                for pattern in patterns:
                    if re.search(pattern, conteudo):
                        conteudo = re.sub(pattern, replacement, conteudo)
                        corrigido = True
                
                if corrigido and conteudo != conteudo_original:
                    with open(arquivo, 'w', encoding='utf-8') as f:
                        f.write(conteudo)
                    contador += 1
                    logger.debug(f"  ✓ sys.path corrigido: {arquivo.relative_to(self.src_novo_dir)}")
                    
            except Exception as e:
                logger.warning(f"Erro ao corrigir sys.path em {arquivo}: {e}")
        
        logger.info(f"✓ {contador} arquivos com sys.path corrigidos")
    
    def _validar_sintaxe(self) -> None:
        """Valida sintaxe de todos os arquivos."""
        logger.info("✅ Validando sintaxe...")
        
        erros_sintaxe = []
        total_arquivos = 0
        
        for arquivo in self.src_novo_dir.rglob("*.py"):
            total_arquivos += 1
            try:
                with open(arquivo, 'r', encoding='utf-8') as f:
                    conteudo = f.read()
                
                # Tenta fazer parse do AST
                ast.parse(conteudo)
                
            except SyntaxError as e:
                erro = f"{arquivo.relative_to(self.src_novo_dir)}: {e}"
                erros_sintaxe.append(erro)
                logger.error(f"  ❌ Erro de sintaxe: {erro}")
            except Exception as e:
                logger.warning(f"  ⚠️ Erro ao validar {arquivo}: {e}")
        
        if erros_sintaxe:
            logger.warning(f"⚠️ {len(erros_sintaxe)} erros de sintaxe encontrados")
            for erro in erros_sintaxe:
                logger.warning(f"    • {erro}")
        else:
            logger.info(f"✓ Todos os {total_arquivos} arquivos têm sintaxe válida")
    
    def _gerar_relatorio_final(self) -> None:
        """Gera relatório final da correção."""
        relatorio = f"""
🔧 RELATÓRIO DE CORREÇÃO DE IMPORTS
===================================

📊 ESTATÍSTICAS:
• Arquivos corrigidos: {self.arquivos_corrigidos}
• Imports corrigidos: {self.imports_corrigidos}
• Erros encontrados: {len(self.erros_encontrados)}

📁 MAPEAMENTO APLICADO:
"""
        
        for antigo, novo in self.mapeamento_modulos.items():
            relatorio += f"  {antigo} -> {novo}\n"
        
        if self.erros_encontrados:
            relatorio += f"\n❌ ERROS ENCONTRADOS:\n"
            for erro in self.erros_encontrados:
                relatorio += f"  • {erro}\n"
        
        relatorio += f"""
💾 BACKUP CRIADO: {self.backup_dir}
🏗️ ESTRUTURA CORRIGIDA: {self.src_novo_dir}

✅ CORREÇÃO CONCLUÍDA!
"""
        
        logger.info(relatorio)
        
        # Salva relatório
        relatorio_file = self.src_novo_dir.parent / f"relatorio_imports_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        relatorio_file.write_text(relatorio, encoding='utf-8')

def main():
    """Função principal."""
    try:
        corretor = CorretorImports()
        corretor.executar_correcao()
        
        print("\n" + "="*50)
        print(" CORREÇÃO DE IMPORTS CONCLUÍDA!")
        print("="*50)
        print(f"📊 Arquivos corrigidos: {corretor.arquivos_corrigidos}")
        print(f"🔧 Imports corrigidos: {corretor.imports_corrigidos}")
        print(f"💾 Backup: {corretor.backup_dir}")
        
        if corretor.erros_encontrados:
            print(f"\n⚠️ {len(corretor.erros_encontrados)} erros encontrados")
            print("Verifique o relatório para detalhes")
        
        print("\n🚀 Próximos passos:")
        print("1. Testar execução dos módulos principais")
        print("2. Atualizar main.py para usar nova estrutura")
        print("3. Executar testes para validar funcionalidade")
        
    except Exception as e:
        logger.exception(f"❌ Erro durante correção: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
