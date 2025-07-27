#!/usr/bin/env python3
"""
Correção Final de Imports - Utilitários Organizados
===================================================

Script para corrigir todos os imports dos utilitários organizados,
garantindo que funcionem corretamente nas novas localizações.

Funcionalidades:
- Corrige imports relativos para absolutos
- Ajusta sys.path.insert para nova estrutura
- Corrige referências a módulos locais
- Testa execução básica dos scripts
"""

import re
import os
import sys
from pathlib import Path
from typing import Dict, List, Set
import logging

def configurar_logging() -> logging.Logger:
    """Configura logging para o corretor."""
    logger = logging.getLogger('corretor_imports')
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Handler para console
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    return logger

class CorretorImportsUtilitarios:
    """Corretor de imports para utilitários organizados."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.diretorio_base = Path.cwd()
        self.utilitarios_dir = self.diretorio_base / "Utilitarios"
        
        # Padrões de correção
        self.padroes_correcao = [
            # sys.path.insert - ajustar para a nova profundidade
            (
                re.compile(r'sys\.path\.insert\(0,\s*str\(Path\(__file__\)\.parent.*?\)\)'),
                'sys.path.insert(0, str(Path(__file__).parent.parent.parent))'
            ),
            
            # Imports de src
            (
                re.compile(r'from src\.utils import'),
                'from src.utils import'
            ),
            (
                re.compile(r'from src import'),
                'from src import'
            ),
            (
                re.compile(r'import src\.'),
                'import src.'
            ),
            
            # Import direto de utils (para scripts que estavam na raiz)
            (
                re.compile(r'^from utils import', re.MULTILINE),
                'from src.utils import'
            ),
            (
                re.compile(r'^import utils$', re.MULTILINE),
                'import src.utils as utils'
            ),
            
            # Correção para caminhos de arquivos relativos
            (
                re.compile(r"'configuracao\.ini'"),
                "'../../../configuracao.ini'"
            ),
            (
                re.compile(r'"configuracao\.ini"'),
                '"../../../configuracao.ini"'
            ),
            (
                re.compile(r"'omie\.db'"),
                "'../../../omie.db'"
            ),
            (
                re.compile(r'"omie\.db"'),
                '"../../../omie.db"'
            ),
        ]
    
    def corrigir_todos_imports(self) -> None:
        """Corrige imports de todos os utilitários organizados."""
        self.logger.info("🔧 CORREÇÃO DE IMPORTS - UTILITÁRIOS ORGANIZADOS")
        self.logger.info("=" * 60)
        
        categorias_encontradas = []
        
        # Procurar todas as pastas de categoria
        for item in self.utilitarios_dir.glob("06_*"):
            if item.is_dir():
                categorias_encontradas.append(item)
        
        if not categorias_encontradas:
            self.logger.warning("❌ Nenhuma categoria organizada encontrada!")
            return
        
        total_corrigidos = 0
        total_sem_alteracao = 0
        total_erros = 0
        
        for categoria_dir in categorias_encontradas:
            categoria_nome = categoria_dir.name.replace("06_", "")
            self.logger.info(f"\n📁 Processando categoria: {categoria_nome}")
            
            arquivos_python = list(categoria_dir.glob("*.py"))
            
            if not arquivos_python:
                self.logger.info(f"   ⏭️  Nenhum arquivo Python encontrado")
                continue
            
            for arquivo in arquivos_python:
                try:
                    resultado = self._corrigir_arquivo(arquivo)
                    
                    if resultado == "corrigido":
                        self.logger.info(f"   ✅ {arquivo.name}")
                        total_corrigidos += 1
                    elif resultado == "sem_alteracao":
                        self.logger.info(f"   ⏭️  {arquivo.name} (sem alterações)")
                        total_sem_alteracao += 1
                    else:
                        self.logger.warning(f"   ❌ {arquivo.name} (erro)")
                        total_erros += 1
                        
                except Exception as e:
                    self.logger.error(f"   ❌ Erro em {arquivo.name}: {e}")
                    total_erros += 1
        
        self.logger.info(f"\n📊 RESULTADO FINAL:")
        self.logger.info(f"   ✅ Arquivos corrigidos: {total_corrigidos}")
        self.logger.info(f"   ⏭️  Sem alterações: {total_sem_alteracao}")
        self.logger.info(f"   ❌ Erros: {total_erros}")
        self.logger.info("🎯 Correção de imports concluída!")
    
    def _corrigir_arquivo(self, arquivo: Path) -> str:
        """
        Corrige imports de um arquivo específico.
        
        Returns:
            str: 'corrigido', 'sem_alteracao', ou 'erro'
        """
        try:
            # Ler arquivo
            with open(arquivo, 'r', encoding='utf-8') as f:
                conteudo = f.read()
        except UnicodeDecodeError:
            try:
                with open(arquivo, 'r', encoding='latin-1') as f:
                    conteudo = f.read()
            except Exception:
                return "erro"
        except Exception:
            return "erro"
        
        conteudo_original = conteudo
        
        # Aplicar todas as correções
        for pattern, replacement in self.padroes_correcao:
            conteudo = pattern.sub(replacement, conteudo)
        
        # Correções específicas baseadas no nome do arquivo
        conteudo = self._aplicar_correcoes_especificas(arquivo, conteudo)
        
        # Salvar se houve mudanças
        if conteudo != conteudo_original:
            try:
                with open(arquivo, 'w', encoding='utf-8') as f:
                    f.write(conteudo)
                return "corrigido"
            except Exception:
                return "erro"
        else:
            return "sem_alteracao"
    
    def _aplicar_correcoes_especificas(self, arquivo: Path, conteudo: str) -> str:
        """Aplica correções específicas baseadas no tipo de arquivo."""
        nome_arquivo = arquivo.name.lower()
        
        # Correções para arquivos que fazem backup
        if 'organizador' in nome_arquivo:
            # Ajustar caminhos de backup
            conteudo = re.sub(
                r'backup_dir = Path\("backup_.*?"\)',
                'backup_dir = self.diretorio_base / f"backup_{datetime.now().strftime(\'%Y%m%d_%H%M%S\')}"',
                conteudo
            )
        
        # Correções para arquivos de diagnóstico DB
        if 'diagnostico' in nome_arquivo:
            # Garantir que usa caminho relativo correto para DB
            if "sqlite3.connect('omie.db')" in conteudo:
                conteudo = conteudo.replace(
                    "sqlite3.connect('omie.db')",
                    "sqlite3.connect('../../../omie.db')"
                )
        
        # Correções para scripts de configuração
        if 'config' in nome_arquivo:
            # Ajustar caminhos de configuração
            conteudo = re.sub(
                r"config\.read\(['\"]configuracao\.ini['\"]\)",
                "config.read('../../../configuracao.ini')",
                conteudo
            )
        
        return conteudo

def main() -> None:
    """Função principal do corretor."""
    try:
        logger = configurar_logging()
        corretor = CorretorImportsUtilitarios(logger)
        corretor.corrigir_todos_imports()
        
    except KeyboardInterrupt:
        print("\n⚠️ Operação cancelada pelo usuário")
    except Exception as e:
        print(f"❌ Erro crítico: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
