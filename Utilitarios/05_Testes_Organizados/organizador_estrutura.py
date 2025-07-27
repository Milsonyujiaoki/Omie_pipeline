#!/usr/bin/env python3
"""
Organizador de Estrutura de Código - Pipeline Omie V3
======================================================

Este script refatora a estrutura do projeto seguindo as melhores práticas de arquitetura Python:

ARQUITETURA IMPLEMENTADA:
- Clean Architecture (Robert C. Martin)
- Domain-Driven Design (DDD)
- Separation of Concerns
- SOLID Principles

ESTRUTURA PROPOSTA:
```
src/
├── __init__.py
├── core/                    # Núcleo da aplicação (Domain Layer)
│   ├── __init__.py
│   ├── entities/            # Entidades de domínio
│   │   ├── __init__.py
│   │   ├── nota_fiscal.py   # Entidade NotaFiscal
│   │   └── xml_document.py  # Entidade XMLDocument
│   ├── value_objects/       # Objetos de valor
│   │   ├── __init__.py
│   │   ├── chave_nfe.py     # ChaveNFe value object
│   │   └── periodo.py       # Período de consulta
│   └── exceptions.py        # Exceções de domínio
│
├── adapters/               # Adaptadores (Infrastructure Layer)
│   ├── __init__.py
│   ├── database/           # Adaptadores de banco de dados
│   │   ├── __init__.py
│   │   ├── repositories/   # Implementações de repositórios
│   │   │   ├── __init__.py
│   │   │   ├── nota_fiscal_repository.py
│   │   │   └── xml_repository.py
│   │   ├── models/         # Modelos de dados SQLite
│   │   │   ├── __init__.py
│   │   │   └── nota_model.py
│   │   └── connection.py   # Gerenciamento de conexões
│   ├── external_apis/      # Adaptadores para APIs externas
│   │   ├── __init__.py
│   │   ├── omie/          # Cliente da API Omie
│   │   │   ├── __init__.py
│   │   │   ├── client.py
│   │   │   └── dto.py     # Data Transfer Objects
│   │   └── onedrive/      # Cliente OneDrive
│   │       ├── __init__.py
│   │       └── client.py
│   └── file_system/       # Adaptadores do sistema de arquivos
│       ├── __init__.py
│       ├── xml_storage.py
│       └── file_utils.py
│
├── application/           # Camada de aplicação (Use Cases)
│   ├── __init__.py
│   ├── services/         # Serviços de aplicação
│   │   ├── __init__.py
│   │   ├── extrator_service.py     # Serviço de extração
│   │   ├── verificador_service.py  # Serviço de verificação
│   │   └── compactador_service.py  # Serviço de compactação
│   ├── use_cases/        # Casos de uso específicos
│   │   ├── __init__.py
│   │   ├── extrair_notas_fiscais.py
│   │   ├── verificar_xmls.py
│   │   └── fazer_upload.py
│   └── interfaces/       # Interfaces (ports)
│       ├── __init__.py
│       ├── repositories.py
│       └── external_services.py
│
├── infrastructure/       # Infraestrutura (Framework Layer)
│   ├── __init__.py
│   ├── logging/         # Sistema de logging
│   │   ├── __init__.py
│   │   └── setup.py
│   ├── config/          # Configurações
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   └── validators.py
│   └── monitoring/      # Métricas e monitoramento
│       ├── __init__.py
│       └── metrics.py
│
├── utils/               # Utilitários transversais
│   ├── __init__.py
│   ├── date_utils.py    # Utilitários de data
│   ├── file_utils.py    # Utilitários de arquivo
│   └── validation.py    # Validações gerais
│
└── presentation/        # Camada de apresentação (opcional)
    ├── __init__.py
    ├── cli/            # Interface de linha de comando
    │   ├── __init__.py
    │   └── commands.py
    └── web/            # Interface web (futuro)
        ├── __init__.py
        └── api.py
```

BENEFÍCIOS DA NOVA ESTRUTURA:
✅ Separação clara de responsabilidades
✅ Facilita testes unitários e de integração
✅ Código mais maintível e extensível
✅ Reduz acoplamento entre módulos
✅ Facilita onboarding de novos desenvolvedores
✅ Permite evolução incremental
✅ Suporte a diferentes interfaces (CLI, Web, API)
"""

import ast
import shutil
import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
from datetime import datetime

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class AnaliseArquivo:
    """Análise detalhada de um arquivo Python."""
    caminho: Path
    nome: str
    categoria: str
    responsabilidades: List[str]
    dependencias: List[str]
    tipo_codigo: str  # 'entity', 'service', 'repository', 'util', 'adapter', etc.
    complexidade: int
    linhas_codigo: int
    docstring: Optional[str] = None

@dataclass
class EstruturaNova:
    """Definição da nova estrutura de diretórios."""
    nome: str
    caminho_relativo: str
    descricao: str
    arquivos: List[Path]

class OrganizadorEstrutura:
    """
    Organizador principal da estrutura de código.
    
    Implementa análise AST para compreender dependências e responsabilidades,
    criando uma estrutura modular e bem organizada.
    """
    
    def __init__(self, src_dir: Path = Path("src")):
        self.src_dir = src_dir
        self.novo_src_dir = src_dir.parent / "src_novo"
        self.backup_dir = src_dir.parent / f"backup_src_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.arquivos_analisados: List[AnaliseArquivo] = []
        self.mapeamento_movimentacao: Dict[Path, Path] = {}
        
        # Definição da nova estrutura
        self.estrutura_nova = self._definir_estrutura_nova()
    
    def _definir_estrutura_nova(self) -> List[EstruturaNova]:
        """Define a nova estrutura de diretórios baseada na análise."""
        return [
            # Core Domain
            EstruturaNova("core", "core", "Núcleo de domínio - entidades e regras de negócio", []),
            EstruturaNova("entities", "core/entities", "Entidades de domínio", []),
            EstruturaNova("value_objects", "core/value_objects", "Objetos de valor", []),
            
            # Application Layer
            EstruturaNova("application", "application", "Camada de aplicação - casos de uso", []),
            EstruturaNova("services", "application/services", "Serviços de aplicação", []),
            EstruturaNova("use_cases", "application/use_cases", "Casos de uso específicos", []),
            EstruturaNova("interfaces", "application/interfaces", "Interfaces e ports", []),
            
            # Adapters/Infrastructure
            EstruturaNova("adapters", "adapters", "Adaptadores para infraestrutura", []),
            EstruturaNova("database", "adapters/database", "Adaptadores de banco de dados", []),
            EstruturaNova("repositories", "adapters/database/repositories", "Implementações de repositórios", []),
            EstruturaNova("models", "adapters/database/models", "Modelos de dados", []),
            EstruturaNova("external_apis", "adapters/external_apis", "Clientes de APIs externas", []),
            EstruturaNova("omie_api", "adapters/external_apis/omie", "Cliente da API Omie", []),
            EstruturaNova("onedrive_api", "adapters/external_apis/onedrive", "Cliente OneDrive", []),
            EstruturaNova("file_system", "adapters/file_system", "Sistema de arquivos", []),
            
            # Infrastructure
            EstruturaNova("infrastructure", "infrastructure", "Infraestrutura técnica", []),
            EstruturaNova("config", "infrastructure/config", "Configurações", []),
            EstruturaNova("logging", "infrastructure/logging", "Sistema de logging", []),
            EstruturaNova("monitoring", "infrastructure/monitoring", "Monitoramento", []),
            
            # Utils
            EstruturaNova("utils", "utils", "Utilitários transversais", []),
            
            # Presentation (opcional)
            EstruturaNova("presentation", "presentation", "Camada de apresentação", []),
            EstruturaNova("cli", "presentation/cli", "Interface de linha de comando", []),
        ]
    
    def executar_organizacao(self) -> None:
        """Executa todo o processo de organização."""
        try:
            logger.info("🚀 INICIANDO ORGANIZAÇÃO DA ESTRUTURA DE CÓDIGO")
            logger.info("=" * 60)
            
            # 1. Análise dos arquivos existentes
            self._analisar_arquivos_existentes()
            
            # 2. Criar backup
            self._criar_backup()
            
            # 3. Criar nova estrutura
            self._criar_nova_estrutura()
            
            # 4. Mover e reorganizar arquivos
            self._mover_arquivos()
            
            # 5. Corrigir imports
            self._corrigir_imports()
            
            # 6. Criar arquivos de interface
            self._criar_arquivos_interfaces()
            
            # 7. Gerar documentação
            self._gerar_documentacao()
            
            # 8. Relatório final
            self._gerar_relatorio_final()
            
            logger.info("✅ ORGANIZAÇÃO CONCLUÍDA COM SUCESSO!")
            logger.info(f"📁 Nova estrutura: {self.novo_src_dir}")
            logger.info(f"💾 Backup criado: {self.backup_dir}")
            
        except Exception as e:
            logger.exception(f"❌ Erro durante organização: {e}")
            raise
    
    def _analisar_arquivos_existentes(self) -> None:
        """Analisa todos os arquivos Python existentes."""
        logger.info("📊 Analisando arquivos existentes...")
        
        for arquivo in self.src_dir.rglob("*.py"):
            if arquivo.name.startswith("__") and arquivo.name.endswith("__.py"):
                continue  # Pula __init__.py e __pycache__
                
            try:
                analise = self._analisar_arquivo(arquivo)
                self.arquivos_analisados.append(analise)
                logger.debug(f"  ✓ Analisado: {arquivo.name} -> {analise.categoria}")
                
            except Exception as e:
                logger.warning(f"  ⚠️ Erro ao analisar {arquivo}: {e}")
        
        logger.info(f"📊 {len(self.arquivos_analisados)} arquivos analisados")
        self._imprimir_estatisticas_analise()
    
    def _analisar_arquivo(self, arquivo: Path) -> AnaliseArquivo:
        """Analisa um arquivo Python usando AST."""
        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                conteudo = f.read()
            
            # Parse AST
            tree = ast.parse(conteudo)
            
            # Extrai informações
            docstring = ast.get_docstring(tree)
            dependencias = self._extrair_dependencias(tree)
            responsabilidades = self._inferir_responsabilidades(arquivo, tree, conteudo)
            categoria = self._determinar_categoria(arquivo, responsabilidades, dependencias)
            tipo_codigo = self._determinar_tipo_codigo(arquivo, tree, responsabilidades)
            complexidade = self._calcular_complexidade(tree)
            linhas = len(conteudo.splitlines())
            
            return AnaliseArquivo(
                caminho=arquivo,
                nome=arquivo.name,
                categoria=categoria,
                responsabilidades=responsabilidades,
                dependencias=dependencias,
                tipo_codigo=tipo_codigo,
                complexidade=complexidade,
                linhas_codigo=linhas,
                docstring=docstring
            )
            
        except Exception as e:
            logger.warning(f"Erro ao analisar {arquivo}: {e}")
            # Fallback para análise básica
            return self._analise_fallback(arquivo)
    
    def _extrair_dependencias(self, tree: ast.AST) -> List[str]:
        """Extrai dependências de imports."""
        dependencias = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    dependencias.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    dependencias.append(node.module)
        
        return list(set(dependencias))  # Remove duplicatas
    
    def _inferir_responsabilidades(self, arquivo: Path, tree: ast.AST, conteudo: str) -> List[str]:
        """Infere responsabilidades baseado no conteúdo."""
        responsabilidades = []
        nome_arquivo = arquivo.name.lower()
        conteudo_lower = conteudo.lower()
        
        # Análise por nome do arquivo
        if "client" in nome_arquivo or "api" in nome_arquivo:
            responsabilidades.append("comunicacao_api")
        if "repository" in nome_arquivo or "repo" in nome_arquivo:
            responsabilidades.append("persistencia_dados")
        if "service" in nome_arquivo:
            responsabilidades.append("logica_negocio")
        if "util" in nome_arquivo:
            responsabilidades.append("utilitarios")
        if "config" in nome_arquivo:
            responsabilidades.append("configuracao")
        if "async" in nome_arquivo:
            responsabilidades.append("processamento_assincrono")
        
        # Análise por conteúdo
        if "sqlite3" in conteudo_lower or "database" in conteudo_lower:
            responsabilidades.append("banco_dados")
        if "aiohttp" in conteudo_lower or "asyncio" in conteudo_lower:
            responsabilidades.append("processamento_assincrono")
        if "xml" in conteudo_lower:
            responsabilidades.append("processamento_xml")
        if "upload" in conteudo_lower or "onedrive" in conteudo_lower:
            responsabilidades.append("upload_arquivos")
        if "logging" in conteudo_lower:
            responsabilidades.append("logging")
        if "config" in conteudo_lower:
            responsabilidades.append("configuracao")
        
        # Análise AST - classes e funções
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if "client" in node.name.lower():
                    responsabilidades.append("cliente_api")
                if "repository" in node.name.lower():
                    responsabilidades.append("repositorio")
                if "service" in node.name.lower():
                    responsabilidades.append("servico")
            elif isinstance(node, ast.FunctionDef):
                if "download" in node.name.lower() or "baixar" in node.name.lower():
                    responsabilidades.append("download")
                if "upload" in node.name.lower():
                    responsabilidades.append("upload")
                if "verificar" in node.name.lower():
                    responsabilidades.append("verificacao")
                if "conectar" in node.name.lower() or "connection" in node.name.lower():
                    responsabilidades.append("conexao")
        
        return list(set(responsabilidades))
    
    def _determinar_categoria(self, arquivo: Path, responsabilidades: List[str], dependencias: List[str]) -> str:
        """Determina a categoria principal do arquivo."""
        nome = arquivo.name.lower()
        
        # Mapeamento direto por nome
        mapeamento_nome = {
            "utils.py": "utils",
            "omie_client_async.py": "external_apis",
            "extrator_async.py": "services",
            "verificador_xmls.py": "services", 
            "upload_onedrive.py": "external_apis",
            "compactador_resultado.py": "services",
            "report_arquivos_vazios.py": "services",
            "atualizar_caminhos_arquivos.py": "services",
            "atualizar_query_params_ini.py": "config"
        }
        
        if nome in mapeamento_nome:
            return mapeamento_nome[nome]
        
        # Análise por responsabilidades
        if "cliente_api" in responsabilidades or "comunicacao_api" in responsabilidades:
            return "external_apis"
        if "repositorio" in responsabilidades or "banco_dados" in responsabilidades:
            return "repositories"
        if "servico" in responsabilidades or "logica_negocio" in responsabilidades:
            return "services"
        if "configuracao" in responsabilidades:
            return "config"
        if "utilitarios" in responsabilidades:
            return "utils"
        if "logging" in responsabilidades:
            return "logging"
        
        # Fallback
        return "utils"
    
    def _determinar_tipo_codigo(self, arquivo: Path, tree: ast.AST, responsabilidades: List[str]) -> str:
        """Determina o tipo específico de código."""
        nome = arquivo.name.lower()
        
        # Análise de classes para determinar padrões
        classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        
        if any("client" in cls.lower() for cls in classes):
            return "client"
        if any("repository" in cls.lower() for cls in classes):
            return "repository"
        if any("service" in cls.lower() for cls in classes):
            return "service"
        if "entity" in responsabilidades:
            return "entity"
        if "config" in nome:
            return "config"
        if "util" in nome:
            return "utility"
        
        return "module"
    
    def _calcular_complexidade(self, tree: ast.AST) -> int:
        """Calcula complexidade ciclomática básica."""
        complexidade = 1  # Base
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.With, ast.Try, ast.ExceptHandler)):
                complexidade += 1
            elif isinstance(node, ast.BoolOp):
                complexidade += len(node.values) - 1
        
        return complexidade
    
    def _analise_fallback(self, arquivo: Path) -> AnaliseArquivo:
        """Análise básica quando AST falha."""
        return AnaliseArquivo(
            caminho=arquivo,
            nome=arquivo.name,
            categoria="utils",
            responsabilidades=["unknown"],
            dependencias=[],
            tipo_codigo="module",
            complexidade=1,
            linhas_codigo=0
        )
    
    def _imprimir_estatisticas_analise(self) -> None:
        """Imprime estatísticas da análise."""
        categorias = {}
        tipos = {}
        total_linhas = 0
        
        for analise in self.arquivos_analisados:
            categorias[analise.categoria] = categorias.get(analise.categoria, 0) + 1
            tipos[analise.tipo_codigo] = tipos.get(analise.tipo_codigo, 0) + 1
            total_linhas += analise.linhas_codigo
        
        logger.info("📈 Estatísticas da análise:")
        logger.info(f"  • Total de linhas: {total_linhas:,}")
        logger.info(f"  • Categorias: {dict(sorted(categorias.items()))}")
        logger.info(f"  • Tipos: {dict(sorted(tipos.items()))}")
    
    def _criar_backup(self) -> None:
        """Cria backup da estrutura atual."""
        logger.info(f"💾 Criando backup em: {self.backup_dir}")
        shutil.copytree(self.src_dir, self.backup_dir)
        logger.info("✓ Backup criado com sucesso")
    
    def _criar_nova_estrutura(self) -> None:
        """Cria a nova estrutura de diretórios."""
        logger.info("📁 Criando nova estrutura de diretórios...")
        
        # Remove diretório se existir
        if self.novo_src_dir.exists():
            shutil.rmtree(self.novo_src_dir)
        
        # Cria estrutura base
        for estrutura in self.estrutura_nova:
            dir_path = self.novo_src_dir / estrutura.caminho_relativo
            dir_path.mkdir(parents=True, exist_ok=True)
            
            # Cria __init__.py
            init_file = dir_path / "__init__.py"
            init_file.write_text(f'"""{estrutura.descricao}"""\n', encoding='utf-8')
            
            logger.debug(f"  ✓ Criado: {estrutura.caminho_relativo}")
        
        logger.info("✓ Nova estrutura criada")
    
    def _mover_arquivos(self) -> None:
        """Move arquivos para nova estrutura."""
        logger.info("Movendo arquivos para nova estrutura...")
        
        mapeamento = {
            # Core/Domain
            "utils.py": "utils",  # Será dividido posteriormente
            
            # External APIs
            "omie_client_async.py": "adapters/external_apis/omie",
            "upload_onedrive.py": "adapters/external_apis/onedrive",
            
            # Services
            "extrator_async.py": "application/services",
            "verificador_xmls.py": "application/services", 
            "compactador_resultado.py": "application/services",
            "report_arquivos_vazios.py": "application/services",
            "atualizar_caminhos_arquivos.py": "application/services",
            
            # Config
            "atualizar_query_params_ini.py": "infrastructure/config",
        }
        
        for analise in self.arquivos_analisados:
            arquivo_nome = analise.nome
            
            if arquivo_nome in mapeamento:
                destino_relativo = mapeamento[arquivo_nome]
                destino = self.novo_src_dir / destino_relativo / arquivo_nome
            else:
                # Mapeia por categoria
                destino = self._mapear_por_categoria(analise)
            
            # Cria diretório se não existir
            destino.parent.mkdir(parents=True, exist_ok=True)
            
            # Copia arquivo
            shutil.copy2(analise.caminho, destino)
            self.mapeamento_movimentacao[analise.caminho] = destino
            
            logger.debug(f"  ✓ {arquivo_nome} -> {destino.relative_to(self.novo_src_dir)}")
        
        # Move arquivos do Utils/
        utils_dir = self.src_dir / "Utils"
        if utils_dir.exists():
            for arquivo in utils_dir.glob("*.py"):
                destino = self.novo_src_dir / "utils" / arquivo.name
                shutil.copy2(arquivo, destino)
                logger.debug(f"  ✓ Utils/{arquivo.name} -> utils/{arquivo.name}")
        
        logger.info(f"✓ {len(self.mapeamento_movimentacao)} arquivos movidos")
    
    def _mapear_por_categoria(self, analise: AnaliseArquivo) -> Path:
        """Mapeia arquivo por categoria."""
        mapeamento = {
            "external_apis": "adapters/external_apis",
            "repositories": "adapters/database/repositories", 
            "services": "application/services",
            "config": "infrastructure/config",
            "utils": "utils",
            "logging": "infrastructure/logging"
        }
        
        categoria = mapeamento.get(analise.categoria, "utils")
        return self.novo_src_dir / categoria / analise.nome
    
    def _corrigir_imports(self) -> None:
        """Corrige imports na nova estrutura."""
        logger.info("🔧 Corrigindo imports...")
        
        contador = 0
        for novo_arquivo in self.novo_src_dir.rglob("*.py"):
            if novo_arquivo.name == "__init__.py":
                continue
                
            try:
                with open(novo_arquivo, 'r', encoding='utf-8') as f:
                    conteudo = f.read()
                
                conteudo_original = conteudo
                
                # Correções básicas de imports
                conteudo = conteudo.replace("from src.utils import", "from src.utils import")
                conteudo = conteudo.replace("from src import", "from src import") 
                conteudo = conteudo.replace("sys.path.insert(0, str(Path(__file__).parent.parent))", 
                                          "sys.path.insert(0, str(Path(__file__).parent.parent.parent))")
                
                if conteudo != conteudo_original:
                    with open(novo_arquivo, 'w', encoding='utf-8') as f:
                        f.write(conteudo)
                    contador += 1
                    
            except Exception as e:
                logger.warning(f"Erro ao corrigir imports em {novo_arquivo}: {e}")
        
        logger.info(f"✓ {contador} arquivos com imports corrigidos")
    
    def _criar_arquivos_interfaces(self) -> None:
        """Cria arquivos de interfaces e abstrações."""
        logger.info("📄 Criando arquivos de interfaces...")
        
        # Interface de repositório
        repo_interface = self.novo_src_dir / "application/interfaces/repositories.py"
        repo_interface.write_text('''"""
Interfaces de repositórios para o domínio da aplicação.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pathlib import Path

class NotaFiscalRepositoryInterface(ABC):
    """Interface para repositório de notas fiscais."""
    
    @abstractmethod
    def salvar_nota(self, nota_data: Dict[str, Any]) -> bool:
        """Salva uma nota fiscal no repositório."""
        pass
    
    @abstractmethod
    def obter_notas_pendentes(self, limite: int = 100) -> List[Dict[str, Any]]:
        """Obtém notas pendentes de processamento."""
        pass
    
    @abstractmethod
    def marcar_como_processada(self, chave_nfe: str) -> bool:
        """Marca nota como processada."""
        pass

class XMLRepositoryInterface(ABC):
    """Interface para repositório de XMLs."""
    
    @abstractmethod
    def salvar_xml(self, chave_nfe: str, conteudo_xml: str, caminho: Path) -> bool:
        """Salva XML no repositório."""
        pass
    
    @abstractmethod
    def obter_caminho_xml(self, chave_nfe: str) -> Optional[Path]:
        """Obtém caminho do XML."""
        pass
''', encoding='utf-8')
        
        # Interface de serviços externos
        external_interface = self.novo_src_dir / "application/interfaces/external_services.py"
        external_interface.write_text('''"""
Interfaces para serviços externos.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class OmieAPIInterface(ABC):
    """Interface para API do Omie."""
    
    @abstractmethod
    async def buscar_notas_fiscais(self, periodo: Dict[str, str]) -> List[Dict[str, Any]]:
        """Busca notas fiscais no período especificado."""
        pass
    
    @abstractmethod
    async def baixar_xml(self, chave_nfe: str) -> Optional[str]:
        """Baixa XML da nota fiscal."""
        pass

class OneDriveInterface(ABC):
    """Interface para OneDrive."""
    
    @abstractmethod
    async def fazer_upload(self, arquivo_local: str, pasta_destino: str) -> bool:
        """Faz upload de arquivo para OneDrive."""
        pass
''', encoding='utf-8')
        
        logger.info("✓ Interfaces criadas")
    
    def _gerar_documentacao(self) -> None:
        """Gera documentação da nova estrutura."""
        logger.info("📚 Gerando documentação...")
        
        readme = self.novo_src_dir / "README.md"
        readme.write_text(f'''# Pipeline Omie V3 - Estrutura Refatorada

## 🏗️ Arquitetura

Esta estrutura segue os princípios da **Clean Architecture** e **Domain-Driven Design**:

### 📁 Estrutura de Diretórios

```
src/
├── core/                    # 🎯 Domínio - Regras de negócio
│   ├── entities/            # Entidades de domínio
│   ├── value_objects/       # Objetos de valor
│   └── exceptions.py        # Exceções de domínio
│
├── application/             # 📋 Aplicação - Casos de uso
│   ├── services/            # Serviços de aplicação
│   ├── use_cases/           # Casos de uso específicos
│   └── interfaces/          # Contratos/Ports
│
├── adapters/               # 🔌 Adaptadores - Infraestrutura
│   ├── database/           # Persistência
│   ├── external_apis/      # APIs externas (Omie, OneDrive)
│   └── file_system/        # Sistema de arquivos
│
├── infrastructure/         # ⚙️ Infraestrutura técnica
│   ├── config/             # Configurações
│   ├── logging/            # Sistema de logging
│   └── monitoring/         # Monitoramento
│
├── utils/                  # 🛠️ Utilitários transversais
└── presentation/           # 🖥️ Interfaces (CLI, Web)
```

## 🚀 Benefícios da Nova Estrutura

✅ **Separação Clara**: Cada camada tem responsabilidade bem definida  
✅ **Testabilidade**: Estrutura facilita criação de testes unitários  
✅ **Manutenibilidade**: Código mais organizado e fácil de evoluir  
✅ **Escalabilidade**: Permite adicionar novas funcionalidades facilmente  
✅ **Baixo Acoplamento**: Dependências bem controladas entre camadas  

## 📊 Estatísticas da Migração

- **Arquivos analisados**: {len(self.arquivos_analisados)}
- **Backup criado**: {self.backup_dir.name}
- **Data da migração**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 🔧 Como Usar

1. **Desenvolvimento**: Comece sempre pelas entidades no `/core`
2. **Casos de Uso**: Implemente lógica em `/application/use_cases`
3. **Infraestrutura**: Adapte em `/adapters` conforme necessário
4. **Configuração**: Centralize em `/infrastructure/config`

## 📝 Próximos Passos

1. [ ] Revisar imports corrigidos
2. [ ] Implementar testes unitários
3. [ ] Adicionar documentação específica de cada módulo
4. [ ] Implementar dependency injection
5. [ ] Adicionar métricas e monitoramento

---
*Estrutura gerada automaticamente em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
''', encoding='utf-8')
        
        logger.info("✓ Documentação gerada")
    
    def _gerar_relatorio_final(self) -> None:
        """Gera relatório final da organização."""
        logger.info("📋 Gerando relatório final...")
        
        relatorio = f"""
 RELATÓRIO FINAL - ORGANIZAÇÃO DE ESTRUTURA
=============================================

📊 ESTATÍSTICAS:
• Arquivos processados: {len(self.arquivos_analisados)}
• Arquivos movidos: {len(self.mapeamento_movimentacao)}
• Nova estrutura: {len(self.estrutura_nova)} diretórios criados

📁 MAPEAMENTO DE ARQUIVOS:
"""
        
        for original, novo in self.mapeamento_movimentacao.items():
            relatorio += f"  {original.name} -> {novo.relative_to(self.novo_src_dir)}\n"
        
        relatorio += f"""

💾 BACKUP CRIADO: {self.backup_dir}
🏗️ NOVA ESTRUTURA: {self.novo_src_dir}

✅ ORGANIZAÇÃO CONCLUÍDA COM SUCESSO!
"""
        
        logger.info(relatorio)
        
        # Salva relatório em arquivo
        relatorio_file = self.novo_src_dir.parent / f"relatorio_organizacao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        relatorio_file.write_text(relatorio, encoding='utf-8')

def main():
    """Função principal."""
    try:
        organizador = OrganizadorEstrutura()
        organizador.executar_organizacao()
        
        print("\n" + "="*60)
        print(" ORGANIZAÇÃO CONCLUÍDA COM SUCESSO!")
        print("="*60)
        print(f"📁 Nova estrutura criada em: {organizador.novo_src_dir}")
        print(f"💾 Backup preservado em: {organizador.backup_dir}")
        print("\n🚀 Próximos passos:")
        print("1. Revisar a nova estrutura")
        print("2. Testar imports e funcionalidades")
        print("3. Atualizar main.py para usar nova estrutura")
        print("4. Implementar testes unitários")
        
    except Exception as e:
        logger.exception(f"❌ Erro durante organização: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
