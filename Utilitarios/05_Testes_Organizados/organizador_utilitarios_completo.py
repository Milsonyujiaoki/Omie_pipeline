#!/usr/bin/env python3
"""
Organizador Completo de Utilitários - Extrator Omie v3
======================================================

Script especializado para organizar todos os arquivos utilitários do projeto
em uma estrutura lógica e funcional, seguindo as melhores práticas do Python.

Categorias de organização:
- 🗄️  Banco_de_Dados: Scripts de manipulação, diagnóstico e correção de DB
- 🔧 Configuracao: Scripts de configuração, validação e setup
- 📊 Relatorios_Analytics: Scripts de análise, métricas e relatórios
- 🚀 Execucao_Pipeline: Scripts de execução, extração e processamento
-  Monitoramento_Debug: Scripts de diagnóstico, logs e debugging
- 🧪 Ferramentas_Dev: Scripts de desenvolvimento, organização e utilitários
- 📦 Integracao_API: Scripts de integração com APIs e serviços externos

Desenvolvido seguindo:
- PEP 8: Estilo de código Python
- PEP 20: Zen of Python
- Type hints e documentação completa
- Tratamento robusto de erros
- Logging estruturado
"""

import ast
import os
import re
import shutil
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union, Any
import logging

# =============================================================================
# Configuração de Logging
# =============================================================================

def configurar_logging() -> logging.Logger:
    """
    Configura sistema de logging estruturado para o organizador.
    
    Returns:
        logging.Logger: Logger configurado com handlers apropriados
        
    Raises:
        OSError: Se não conseguir criar diretório de logs
    """
    try:
        log_dir = Path("log")
        log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = log_dir / f"organizador_utilitarios_{timestamp}.log"
        
        logger = logging.getLogger('organizador_utilitarios')
        logger.setLevel(logging.INFO)
        
        # Handler para arquivo
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        
        # Handler para console
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            '%(levelname)s: %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
        
    except OSError as e:
        raise OSError(f"Erro ao configurar logging: {e}") from e

# =============================================================================
# Classes de Dados
# =============================================================================

@dataclass
class ArquivoUtilitario:
    """
    Representa um arquivo utilitário para análise e categorização.
    
    Attributes:
        caminho: Path completo do arquivo
        nome: Nome do arquivo
        conteudo: Conteúdo do arquivo
        categoria: Categoria determinada pela análise
        funcionalidade: Descrição da funcionalidade principal
        imports: Lista de imports encontrados
        funcoes: Lista de funções encontradas
        classes: Lista de classes encontradas
    """
    caminho: Path
    nome: str
    conteudo: str = ""
    categoria: str = ""
    funcionalidade: str = ""
    imports: List[str] = field(default_factory=list)
    funcoes: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    
    def __post_init__(self) -> None:
        """Inicialização pós-criação da instância."""
        if not self.nome:
            self.nome = self.caminho.name

@dataclass
class EstatisticasOrganizacao:
    """
    Estatísticas do processo de organização.
    
    Attributes:
        arquivos_analisados: Total de arquivos analisados
        arquivos_movidos: Total de arquivos movidos
        categorias_criadas: Número de categorias criadas
        erros: Número de erros encontrados
        tempo_execucao: Tempo total de execução em segundos
    """
    arquivos_analisados: int = 0
    arquivos_movidos: int = 0
    categorias_criadas: int = 0
    erros: int = 0
    tempo_execucao: float = 0.0

# =============================================================================
# Analisador de Código
# =============================================================================

class AnalisadorCodigo:
    """
    Analisador de código Python usando AST para extração de metadados.
    """
    
    def __init__(self, logger: logging.Logger) -> None:
        """
        Inicializa o analisador de código.
        
        Args:
            logger: Logger para registro de atividades
        """
        self.logger = logger
    
    def analisar_arquivo(self, arquivo: ArquivoUtilitario) -> ArquivoUtilitario:
        """
        Analisa um arquivo Python e extrai metadados.
        
        Args:
            arquivo: Arquivo para análise
            
        Returns:
            ArquivoUtilitario: Arquivo com metadados preenchidos
            
        Raises:
            SyntaxError: Se o arquivo contém erros de sintaxe
            UnicodeDecodeError: Se o arquivo não pode ser decodificado
        """
        try:
            with open(arquivo.caminho, 'r', encoding='utf-8') as f:
                arquivo.conteudo = f.read()
        except UnicodeDecodeError:
            try:
                with open(arquivo.caminho, 'r', encoding='latin-1') as f:
                    arquivo.conteudo = f.read()
            except Exception as e:
                self.logger.warning(f"Erro ao ler {arquivo.nome}: {e}")
                return arquivo
        except Exception as e:
            self.logger.warning(f"Erro ao ler {arquivo.nome}: {e}")
            return arquivo
        
        try:
            tree = ast.parse(arquivo.conteudo)
            self._extrair_elementos_ast(tree, arquivo)
            arquivo.funcionalidade = self._extrair_funcionalidade(arquivo)
            arquivo.categoria = self._determinar_categoria(arquivo)
            
        except SyntaxError as e:
            self.logger.warning(f"Erro de sintaxe em {arquivo.nome}: {e}")
        except Exception as e:
            self.logger.warning(f"Erro ao analisar {arquivo.nome}: {e}")
        
        return arquivo
    
    def _extrair_elementos_ast(self, tree: ast.AST, arquivo: ArquivoUtilitario) -> None:
        """
        Extrai elementos do AST (imports, funções, classes).
        
        Args:
            tree: Árvore AST do código
            arquivo: Arquivo para preenchimento dos metadados
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    arquivo.imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    arquivo.imports.append(node.module)
            elif isinstance(node, ast.FunctionDef):
                arquivo.funcoes.append(node.name)
            elif isinstance(node, ast.ClassDef):
                arquivo.classes.append(node.name)
    
    def _extrair_funcionalidade(self, arquivo: ArquivoUtilitario) -> str:
        """
        Extrai a funcionalidade principal do arquivo baseada em docstring e análise.
        
        Args:
            arquivo: Arquivo para análise
            
        Returns:
            str: Descrição da funcionalidade
        """
        # Tentar extrair docstring
        try:
            tree = ast.parse(arquivo.conteudo)
            if (tree.body and isinstance(tree.body[0], ast.Expr) and 
                isinstance(tree.body[0].value, ast.Constant) and 
                isinstance(tree.body[0].value.value, str)):
                docstring = tree.body[0].value.value.strip()
                if docstring:
                    # Pegar primeira linha significativa
                    primeira_linha = next(
                        (linha.strip() for linha in docstring.split('\n') 
                         if linha.strip() and not linha.strip().startswith('=')), 
                        docstring.split('\n')[0]
                    )
                    return primeira_linha[:100]
        except:
            pass
        
        # Análise baseada no nome e conteúdo
        nome_lower = arquivo.nome.lower()
        conteudo_lower = arquivo.conteudo.lower()
        
        if any(palavra in nome_lower for palavra in ['test', 'teste']):
            return "Script de teste e validação"
        elif any(palavra in nome_lower for palavra in ['config', 'configurar']):
            return "Script de configuração do sistema"
        elif any(palavra in nome_lower for palavra in ['diagnostico', 'debug']):
            return "Script de diagnóstico e debugging"
        elif any(palavra in nome_lower for palavra in ['banco', 'db', 'sqlite']):
            return "Script de manipulação de banco de dados"
        elif any(palavra in nome_lower for palavra in ['extrator', 'download']):
            return "Script de extração e download de dados"
        elif any(palavra in nome_lower for palavra in ['relatorio', 'analise']):
            return "Script de análise e relatórios"
        elif any(palavra in nome_lower for palavra in ['organizador', 'organizar']):
            return "Script de organização e estruturação"
        else:
            return f"Utilitário para {arquivo.nome.replace('.py', '').replace('_', ' ')}"
    
    def _determinar_categoria(self, arquivo: ArquivoUtilitario) -> str:
        """
        Determina a categoria do arquivo baseada em análise de conteúdo.
        
        Args:
            arquivo: Arquivo para categorização
            
        Returns:
            str: Nome da categoria
        """
        nome_lower = arquivo.nome.lower()
        conteudo_lower = arquivo.conteudo.lower()
        imports_str = ' '.join(arquivo.imports).lower()
        funcoes_str = ' '.join(arquivo.funcoes).lower()
        
        # Banco de Dados
        if (any(palavra in nome_lower for palavra in ['db', 'banco', 'sqlite', 'diagnostico_db', 'verificar_duplicatas']) or
            any(palavra in imports_str for palavra in ['sqlite3', 'database']) or
            any(palavra in conteudo_lower for palavra in ['sqlite3', 'database', 'cursor', 'commit', 'sql'])):
            return "Banco_de_Dados"
        
        # Configuração
        elif (any(palavra in nome_lower for palavra in ['config', 'configurar', 'setup']) or
              any(palavra in imports_str for palavra in ['configparser']) or
              any(palavra in conteudo_lower for palavra in ['configparser', 'config.ini'])):
            return "Configuracao"
        
        # Relatórios e Analytics
        elif (any(palavra in nome_lower for palavra in ['relatorio', 'analise', 'analytics', 'metricas']) or
              any(palavra in funcoes_str for palavra in ['relatorio', 'analise', 'estatistica'])):
            return "Relatorios_Analytics"
        
        # Execução e Pipeline
        elif (any(palavra in nome_lower for palavra in ['extrator', 'main', 'pipeline', 'execuc']) or
              any(palavra in funcoes_str for palavra in ['executar', 'main', 'pipeline']) or
              any(palavra in conteudo_lower for palavra in ['async', 'download', 'api'])):
            return "Execucao_Pipeline"
        
        # Monitoramento e Debug
        elif (any(palavra in nome_lower for palavra in ['debug', 'log', 'monitor', 'diagnostico']) or
              any(palavra in imports_str for palavra in ['logging']) or
              any(palavra in conteudo_lower for palavra in ['logging', 'debug', 'error'])):
            return "Monitoramento_Debug"
        
        # Integração API
        elif (any(palavra in nome_lower for palavra in ['api', 'client', 'omie', 'onedrive']) or
              any(palavra in imports_str for palavra in ['requests', 'aiohttp']) or
              any(palavra in conteudo_lower for palavra in ['requests', 'api', 'client'])):
            return "Integracao_API"
        
        # Ferramentas de Desenvolvimento (padrão)
        else:
            return "Ferramentas_Dev"

# =============================================================================
# Organizador Principal
# =============================================================================

class OrganizadorUtilitarios:
    """
    Organizador principal dos utilitários do projeto.
    """
    
    def __init__(self, diretorio_base: Union[str, Path], logger: logging.Logger) -> None:
        """
        Inicializa o organizador.
        
        Args:
            diretorio_base: Diretório base do projeto
            logger: Logger para registro de atividades
        """
        self.diretorio_base = Path(diretorio_base)
        self.logger = logger
        self.analisador = AnalisadorCodigo(logger)
        self.estatisticas = EstatisticasOrganizacao()
        
        # Definir estrutura de categorias
        self.categorias = {
            "Banco_de_Dados": {
                "descricao": "Scripts para manipulação, diagnóstico e correção de banco de dados",
                "icone": "🗄️"
            },
            "Configuracao": {
                "descricao": "Scripts de configuração, validação e setup do sistema",
                "icone": "🔧"
            },
            "Relatorios_Analytics": {
                "descricao": "Scripts de análise, métricas e geração de relatórios",
                "icone": "📊"
            },
            "Execucao_Pipeline": {
                "descricao": "Scripts de execução, extração e processamento de dados",
                "icone": "🚀"
            },
            "Monitoramento_Debug": {
                "descricao": "Scripts de diagnóstico, logs e debugging",
                "icone": ""
            },
            "Ferramentas_Dev": {
                "descricao": "Scripts de desenvolvimento, organização e utilitários gerais",
                "icone": "🧪"
            },
            "Integracao_API": {
                "descricao": "Scripts de integração com APIs e serviços externos",
                "icone": "📦"
            }
        }
    
    def organizar_completo(self) -> EstatisticasOrganizacao:
        """
        Executa organização completa dos utilitários.
        
        Returns:
            EstatisticasOrganizacao: Estatísticas do processo
        """
        inicio = time.time()
        
        try:
            self.logger.info("🚀 Iniciando organização completa dos utilitários")
            
            # 1. Criar backup
            self._criar_backup()
            
            # 2. Descobrir arquivos
            arquivos = self._descobrir_arquivos()
            self.estatisticas.arquivos_analisados = len(arquivos)
            
            # 3. Analisar arquivos
            arquivos_analisados = self._analisar_arquivos(arquivos)
            
            # 4. Criar estrutura de pastas
            self._criar_estrutura_organizacao()
            
            # 5. Mover arquivos
            self._mover_arquivos(arquivos_analisados)
            
            # 6. Corrigir imports
            self._corrigir_imports_organizados()
            
            # 7. Gerar documentação
            self._gerar_documentacao(arquivos_analisados)
            
            self.estatisticas.tempo_execucao = time.time() - inicio
            self.logger.info(f"✅ Organização concluída em {self.estatisticas.tempo_execucao:.2f}s")
            
        except Exception as e:
            self.logger.error(f"❌ Erro durante organização: {e}")
            self.estatisticas.erros += 1
        
        return self.estatisticas
    
    def _criar_backup(self) -> None:
        """Cria backup dos arquivos antes da organização."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = self.diretorio_base / f"backup_utilitarios_{timestamp}"
        
        try:
            backup_dir.mkdir(exist_ok=True)
            
            # Listar arquivos a serem incluídos no backup
            arquivos_backup = []
            for pattern in ['*.py', 'organizador_*.py', 'corrigir_*.py', 'limpeza_*.py']:
                arquivos_backup.extend(self.diretorio_base.glob(pattern))
            
            for arquivo in arquivos_backup:
                if arquivo.is_file():
                    shutil.copy2(arquivo, backup_dir / arquivo.name)
            
            self.logger.info(f"📦 Backup criado em: {backup_dir}")
            
        except Exception as e:
            self.logger.warning(f"⚠️ Erro ao criar backup: {e}")
    
    def _descobrir_arquivos(self) -> List[Path]:
        """
        Descobre arquivos Python elegíveis para organização.
        
        Returns:
            List[Path]: Lista de arquivos encontrados
        """
        arquivos = []
        
        # Arquivos na raiz (excluindo main.py e outros essenciais)
        excluir_raiz = {'main.py', 'extrator_funcional.py', '__pycache__'}
        
        for arquivo in self.diretorio_base.glob('*.py'):
            if arquivo.name not in excluir_raiz:
                arquivos.append(arquivo)
        
        # Arquivos em src que são utilitários
        src_dir = self.diretorio_base / "src"
        if src_dir.exists():
            for arquivo in src_dir.rglob('*.py'):
                # Incluir apenas arquivos utilitários específicos
                if any(palavra in arquivo.name.lower() for palavra in 
                       ['utils', 'helper', 'tool', 'report']):
                    arquivos.append(arquivo)
        
        self.logger.info(f" Encontrados {len(arquivos)} arquivos para organização")
        return arquivos
    
    def _analisar_arquivos(self, arquivos: List[Path]) -> List[ArquivoUtilitario]:
        """
        Analisa todos os arquivos encontrados.
        
        Args:
            arquivos: Lista de arquivos para análise
            
        Returns:
            List[ArquivoUtilitario]: Arquivos analisados
        """
        arquivos_analisados = []
        
        self.logger.info("🔬 Analisando arquivos...")
        
        for arquivo_path in arquivos:
            try:
                arquivo = ArquivoUtilitario(caminho=arquivo_path, nome=arquivo_path.name)
                arquivo_analisado = self.analisador.analisar_arquivo(arquivo)
                arquivos_analisados.append(arquivo_analisado)
                
                self.logger.info(f"   ✅ {arquivo.nome} → {arquivo_analisado.categoria}")
                
            except Exception as e:
                self.logger.warning(f"   ❌ Erro ao analisar {arquivo_path.name}: {e}")
                self.estatisticas.erros += 1
        
        return arquivos_analisados
    
    def _criar_estrutura_organizacao(self) -> None:
        """Cria estrutura de diretórios organizados."""
        utilitarios_dir = self.diretorio_base / "Utilitarios"
        
        for categoria, info in self.categorias.items():
            categoria_dir = utilitarios_dir / f"06_{categoria}"
            categoria_dir.mkdir(parents=True, exist_ok=True)
            
            self.logger.info(f"📁 Criada categoria: {info['icone']} {categoria}")
        
        self.estatisticas.categorias_criadas = len(self.categorias)
    
    def _mover_arquivos(self, arquivos: List[ArquivoUtilitario]) -> None:
        """
        Move arquivos para suas respectivas categorias.
        
        Args:
            arquivos: Lista de arquivos analisados
        """
        utilitarios_dir = self.diretorio_base / "Utilitarios"
        
        for arquivo in arquivos:
            try:
                categoria_dir = utilitarios_dir / f"06_{arquivo.categoria}"
                destino = categoria_dir / arquivo.nome
                
                # Renomear se necessário para nome mais descritivo
                novo_nome = self._gerar_nome_descritivo(arquivo)
                if novo_nome != arquivo.nome:
                    destino = categoria_dir / novo_nome
                
                shutil.move(str(arquivo.caminho), str(destino))
                self.estatisticas.arquivos_movidos += 1
                
                self.logger.info(f"   📦 {arquivo.nome} → {arquivo.categoria}/{destino.name}")
                
            except Exception as e:
                self.logger.warning(f"   ❌ Erro ao mover {arquivo.nome}: {e}")
                self.estatisticas.erros += 1
    
    def _gerar_nome_descritivo(self, arquivo: ArquivoUtilitario) -> str:
        """
        Gera nome mais descritivo baseado na funcionalidade.
        
        Args:
            arquivo: Arquivo para renomeação
            
        Returns:
            str: Novo nome do arquivo
        """
        nome_atual = arquivo.nome.replace('.py', '')
        
        # Manter nomes já descritivos
        if len(nome_atual) > 20 or '_' in nome_atual:
            return arquivo.nome
        
        # Gerar nome baseado na categoria e funcionalidade
        mapeamento = {
            'verificar_duplicatas': 'analise_duplicatas_xml_banco.py',
            'diagnostico_db': 'diagnostico_estrutura_banco.py',
            'corrigir_view': 'correcao_views_banco.py',
            'teste_config': 'validacao_configuracao_sistema.py',
            'organizador_testes': 'organizador_arquivos_teste.py',
            'limpeza_pos_organizacao': 'limpeza_duplicatas_pos_organizacao.py'
        }
        
        return mapeamento.get(nome_atual, arquivo.nome)
    
    def _corrigir_imports_organizados(self) -> None:
        """Corrige imports dos arquivos organizados."""
        self.logger.info("🔧 Corrigindo imports dos arquivos organizados...")
        
        utilitarios_dir = self.diretorio_base / "Utilitarios"
        
        for categoria in self.categorias.keys():
            categoria_dir = utilitarios_dir / f"06_{categoria}"
            
            if categoria_dir.exists():
                for arquivo in categoria_dir.glob('*.py'):
                    self._corrigir_imports_arquivo(arquivo)
    
    def _corrigir_imports_arquivo(self, arquivo: Path) -> None:
        """
        Corrige imports de um arquivo específico.
        
        Args:
            arquivo: Arquivo para correção de imports
        """
        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                conteudo = f.read()
            
            conteudo_original = conteudo
            
            # Padrões de correção
            correcoes = [
                # sys.path.insert
                (re.compile(r'sys\.path\.insert\(0,\s*str\(Path\(__file__\)\.parent.*?\)\)'),
                 'sys.path.insert(0, str(Path(__file__).parent.parent.parent))'),
                
                # Imports relativos para absolutos
                (re.compile(r'from utils import'), 'from src.utils import'),
                (re.compile(r'import utils'), 'import src.utils as utils'),
                (re.compile(r'from src import'), 'from src import'),
            ]
            
            for pattern, replacement in correcoes:
                conteudo = pattern.sub(replacement, conteudo)
            
            if conteudo != conteudo_original:
                with open(arquivo, 'w', encoding='utf-8') as f:
                    f.write(conteudo)
                self.logger.info(f"   ✅ Imports corrigidos: {arquivo.name}")
            
        except Exception as e:
            self.logger.warning(f"   ❌ Erro ao corrigir imports de {arquivo.name}: {e}")
    
    def _gerar_documentacao(self, arquivos: List[ArquivoUtilitario]) -> None:
        """
        Gera documentação para cada categoria.
        
        Args:
            arquivos: Lista de arquivos organizados
        """
        self.logger.info("📚 Gerando documentação...")
        
        utilitarios_dir = self.diretorio_base / "Utilitarios"
        
        # Agrupar arquivos por categoria
        arquivos_por_categoria = {}
        for arquivo in arquivos:
            if arquivo.categoria not in arquivos_por_categoria:
                arquivos_por_categoria[arquivo.categoria] = []
            arquivos_por_categoria[arquivo.categoria].append(arquivo)
        
        # Gerar README para cada categoria
        for categoria, arquivos_categoria in arquivos_por_categoria.items():
            self._gerar_readme_categoria(categoria, arquivos_categoria)
        
        # Gerar índice geral
        self._gerar_indice_geral(arquivos_por_categoria)
    
    def _gerar_readme_categoria(self, categoria: str, arquivos: List[ArquivoUtilitario]) -> None:
        """
        Gera README.md para uma categoria específica.
        
        Args:
            categoria: Nome da categoria
            arquivos: Arquivos da categoria
        """
        categoria_dir = self.diretorio_base / "Utilitarios" / f"06_{categoria}"
        readme_path = categoria_dir / "README.md"
        
        info_categoria = self.categorias[categoria]
        
        conteudo = f"""# {info_categoria['icone']} {categoria.replace('_', ' ')}

{info_categoria['descricao']}

## 📋 Arquivos Disponíveis

| Arquivo | Funcionalidade | Classes | Funções |
|---------|----------------|---------|---------|
"""
        
        for arquivo in sorted(arquivos, key=lambda x: x.nome):
            nome_arquivo = self._gerar_nome_descritivo(arquivo)
            funcionalidade = arquivo.funcionalidade[:80] + "..." if len(arquivo.funcionalidade) > 80 else arquivo.funcionalidade
            classes = ", ".join(arquivo.classes[:3]) + ("..." if len(arquivo.classes) > 3 else "")
            funcoes = ", ".join(arquivo.funcoes[:3]) + ("..." if len(arquivo.funcoes) > 3 else "")
            
            conteudo += f"| `{nome_arquivo}` | {funcionalidade} | {classes} | {funcoes} |\n"
        
        conteudo += f"""
## 🚀 Como Usar

Todos os scripts podem ser executados do diretório raiz do projeto:

```bash
# Navegue para o diretório raiz
cd ../../..

# Execute um script específico
python Utilitarios/06_{categoria}/nome_do_script.py
```

## 📁 Estrutura

```
06_{categoria}/
├── README.md (este arquivo)
"""
        
        for arquivo in sorted(arquivos, key=lambda x: x.nome):
            nome_arquivo = self._gerar_nome_descritivo(arquivo)
            conteudo += f"├── {nome_arquivo}\n"
        
        conteudo += """```

## 🔗 Links Relacionados

- [Menu Principal](../menu_principal.py)
- [Documentação Geral](../README_ORGANIZACAO_UTILITARIOS.md)
- [Testes Organizados](../05_Testes_Organizados/)

---
*Documentação gerada automaticamente pelo Organizador de Utilitários*
"""
        
        try:
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(conteudo)
            self.logger.info(f"   📄 README criado: {categoria}")
        except Exception as e:
            self.logger.warning(f"   ❌ Erro ao criar README de {categoria}: {e}")
    
    def _gerar_indice_geral(self, arquivos_por_categoria: Dict[str, List[ArquivoUtilitario]]) -> None:
        """
        Gera índice geral da organização.
        
        Args:
            arquivos_por_categoria: Dicionário de arquivos agrupados por categoria
        """
        utilitarios_dir = self.diretorio_base / "Utilitarios"
        indice_path = utilitarios_dir / "INDICE_UTILITARIOS_ORGANIZADOS.md"
        
        conteudo = f"""# 📚 Índice Geral - Utilitários Organizados

## 📊 Estatísticas da Organização

- **Arquivos organizados**: {self.estatisticas.arquivos_movidos}
- **Categorias criadas**: {self.estatisticas.categorias_criadas}
- **Tempo de execução**: {self.estatisticas.tempo_execucao:.2f}s
- **Data da organização**: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

## 🗂️ Estrutura por Categorias

"""
        
        for categoria, arquivos in arquivos_por_categoria.items():
            info = self.categorias[categoria]
            conteudo += f"### {info['icone']} {categoria.replace('_', ' ')}\n\n"
            conteudo += f"**Descrição**: {info['descricao']}\n\n"
            conteudo += f"**Arquivos**: {len(arquivos)}\n\n"
            conteudo += f"📁 [Ver pasta](06_{categoria}/)\n\n"
            
            for arquivo in sorted(arquivos, key=lambda x: x.nome)[:5]:
                nome_arquivo = self._gerar_nome_descritivo(arquivo)
                conteudo += f"- `{nome_arquivo}`: {arquivo.funcionalidade[:60]}...\n"
            
            if len(arquivos) > 5:
                conteudo += f"- ... e mais {len(arquivos) - 5} arquivos\n"
            
            conteudo += "\n"
        
        conteudo += """## 🎯 Como Navegar

1. **Consulte este índice** para visão geral
2. **Acesse a categoria desejada** clicando nos links
3. **Leia o README** de cada categoria para detalhes
4. **Execute os scripts** do diretório raiz do projeto

## Execução de Scripts

Todos os scripts devem ser executados a partir do diretório raiz:

```bash
# Exemplo para categoria Banco_de_Dados
python Utilitarios/06_Banco_de_Dados/analise_duplicatas_xml_banco.py

# Exemplo para categoria Configuracao  
python Utilitarios/06_Configuracao/validacao_configuracao_sistema.py
```

## 📋 Menu Principal

Para acesso rápido aos utilitários, use o menu principal:

```bash
python Utilitarios/menu_principal.py
```

---
*Documentação gerada automaticamente pelo Organizador de Utilitários*
"""
        
        try:
            with open(indice_path, 'w', encoding='utf-8') as f:
                f.write(conteudo)
            self.logger.info("📄 Índice geral criado")
        except Exception as e:
            self.logger.warning(f"❌ Erro ao criar índice geral: {e}")

# =============================================================================
# Função Principal
# =============================================================================

def main() -> None:
    """
    Função principal do organizador de utilitários.
    
    Raises:
        SystemExit: Em caso de erro crítico durante a execução
    """
    try:
        # Configurar logging
        logger = configurar_logging()
        
        # Inicializar organizador
        diretorio_base = Path.cwd()
        organizador = OrganizadorUtilitarios(diretorio_base, logger)
        
        # Executar organização
        logger.info("🎯 ORGANIZADOR DE UTILITÁRIOS - EXTRATOR OMIE V3")
        logger.info("=" * 60)
        
        estatisticas = organizador.organizar_completo()
        
        # Exibir resultados
        logger.info("📊 RESULTADO FINAL:")
        logger.info(f"   ✅ Arquivos analisados: {estatisticas.arquivos_analisados}")
        logger.info(f"   📦 Arquivos movidos: {estatisticas.arquivos_movidos}")
        logger.info(f"   📁 Categorias criadas: {estatisticas.categorias_criadas}")
        logger.info(f"   ❌ Erros: {estatisticas.erros}")
        logger.info(f"   Tempo total: {estatisticas.tempo_execucao:.2f}s")
        logger.info(" Organização de utilitários concluída!")
        
    except KeyboardInterrupt:
        print("\n⚠️ Operação cancelada pelo usuário")
    except Exception as e:
        print(f"❌ Erro crítico: {e}")
        raise SystemExit(1) from e

if __name__ == "__main__":
    main()
