# =============================================================================
# PIPELINE PRINCIPAL DO EXTRATOR OMIE V3 - ESTRUTURA REFATORADA
# =============================================================================
"""
Pipeline principal refatorado seguindo Clean Architecture.

Este módulo orquestra todo o pipeline usando a nova estrutura modular:
- Core: Entidades e regras de negócio
- Application: Casos de uso e serviços
- Adapters: Infraestrutura e APIs externas
- Infrastructure: Configurações e logging

Benefícios da nova estrutura:
✅ Separação clara de responsabilidades
✅ Código mais testável e maintível
✅ Baixo acoplamento entre módulos
✅ Facilita evolução e escalabilidade
"""

# =============================================================================
# Importações da biblioteca padrão
# =============================================================================
import sys
import os
import time
import logging
import sqlite3
import configparser
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol
from contextlib import contextmanager

# =============================================================================
# Importações da nova estrutura - Clean Architecture
# =============================================================================

# Infrastructure Layer
from src_novo.infrastructure.config.atualizar_query_params_ini import atualizar_datas_configuracao_ini
from src_novo.infrastructure.logging.setup import configurar_logging

# Application Layer - Services
from src_novo.application.services.extrator_async import baixar_xmls, listar_nfs
from src_novo.application.services.verificador_xmls import verificar as verificar_xmls
from src_novo.application.services.compactador_resultado import compactar_resultados
from src_novo.application.services.atualizar_caminhos_arquivos import atualizar_caminhos_no_banco
from src_novo.application.services.report_arquivos_vazios import gerar_relatorio as gerar_relatorio_vazios

# Adapters Layer - External APIs
from src_novo.adapters.external_apis.omie.omie_client_async import OmieClient, carregar_configuracoes as carregar_config_omie
from src_novo.adapters.external_apis.onedrive.upload_onedrive import fazer_upload_lote

# Utils Layer
# Importações dos novos módulos refatorados
from src_novo.infrastructure.database import SQLiteRepository
from src_novo.application.services import (
    RepositoryService,
    NotaFiscalService,
    MetricsService,
    XMLProcessingService,
    TemporalIndexingService
)
from src_novo.utils import formatar_tempo_total

# =============================================================================
# Configurações globais
# =============================================================================
CONFIG_PATH: str = "configuracao.ini"

# =============================================================================
# Service Locator Pattern - Dependency Injection Simples
# =============================================================================

class ServiceLocator:
    """
    Service Locator para gerenciar dependências de forma centralizada.
    
    Implementa um padrão simples de dependency injection que facilita
    testes unitários e manutenção do código.
    """
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._configuracoes: Optional[Dict[str, Any]] = None
    
    def registrar_servico(self, nome: str, servico: Any) -> None:
        """Registra um serviço no locator."""
        self._services[nome] = servico
        logger.debug(f"[SERVICE_LOCATOR] Serviço registrado: {nome}")
    
    def obter_servico(self, nome: str) -> Any:
        """Obtém um serviço registrado."""
        if nome not in self._services:
            raise ValueError(f"Serviço não registrado: {nome}")
        return self._services[nome]
    
    def configurar_servicos(self, config: Dict[str, Any]) -> None:
        """Configura todos os serviços com as configurações."""
        self._configuracoes = config
        
        # Registra cliente Omie
        omie_client = OmieClient(
            app_key=config['app_key'],
            app_secret=config['app_secret'],
            calls_per_second=config.get('calls_per_second', 4)
        )
        self.registrar_servico('omie_client', omie_client)
        
        # Registra configurações
        self.registrar_servico('config', config)
        
        logger.info("[SERVICE_LOCATOR] Serviços configurados com sucesso")
    
    def obter_configuracoes(self) -> Dict[str, Any]:
        """Obtém configurações carregadas."""
        if self._configuracoes is None:
            raise ValueError("Configurações não foram carregadas")
        return self._configuracoes

# Instância global do service locator
service_locator = ServiceLocator()

# =============================================================================
# Configuração de logging - Infrastructure Layer
# =============================================================================

def configurar_sistema_logging() -> None:
    """Configura sistema de logging usando infrastructure layer."""
    try:
        # Tenta usar o configurador da nova estrutura
        configurar_logging()
        logger.info("[LOGGING] Sistema configurado via infrastructure layer")
    except ImportError:
        # Fallback para configuração básica
        _configurar_logging_basico()
        logger.warning("[LOGGING] Usando configuração básica (fallback)")

def _configurar_logging_basico() -> None:
    """Configuração básica de logging como fallback."""
    log_dir = Path("log")
    log_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / f"Pipeline_Refatorado_{timestamp}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ],
        force=True
    )

# Configuração inicial
_configurar_logging_basico()
logger = logging.getLogger(__name__)

# =============================================================================
# Gerenciamento de configurações - Infrastructure Layer
# =============================================================================

def carregar_configuracoes(config_path: str = CONFIG_PATH) -> Dict[str, Any]:
    """
    Carrega configurações usando infrastructure layer.
    
    Args:
        config_path: Caminho para arquivo de configuração
        
    Returns:
        Dict com configurações carregadas
        
    Raises:
        SystemExit: Se configurações inválidas
    """
    try:
        # Tenta usar carregador da nova estrutura
        config = carregar_config_omie()
        
        # Validações básicas
        required_keys = ['app_key', 'app_secret', 'resultado_dir']
        for key in required_keys:
            if key not in config:
                logger.error(f"[CONFIG] Chave obrigatória ausente: {key}")
                sys.exit(1)
        
        logger.info("[CONFIG] Configurações carregadas via adapters layer")
        return config
        
    except ImportError:
        # Fallback para carregamento básico
        return _carregar_configuracoes_basico(config_path)

def _carregar_configuracoes_basico(config_path: str) -> Dict[str, Any]:
    """Carregamento básico de configurações como fallback."""
    config_file = Path(config_path)
    
    if not config_file.exists():
        logger.error(f"[CONFIG] Arquivo não encontrado: {config_path}")
        sys.exit(1)
    
    try:
        config = configparser.ConfigParser()
        config.read(config_path, encoding='utf-8')
        
        # Extrai configurações essenciais
        configuracoes = {
            "resultado_dir": config.get("paths", "resultado_dir"),
            "app_key": config.get("omie_api", "app_key"),
            "app_secret": config.get("omie_api", "app_secret"),
            "calls_per_second": int(config.get("api_speed", "calls_per_second", fallback="4")),
            "start_date": config.get("query_params", "start_date"),
            "end_date": config.get("query_params", "end_date"),
        }
        
        logger.info("[CONFIG] Configurações carregadas via fallback básico")
        return configuracoes
        
    except Exception as e:
        logger.error(f"[CONFIG] Erro ao carregar configurações: {e}")
        sys.exit(1)

# =============================================================================
# Pipeline Phases - Application Layer
# =============================================================================

class PipelineExecutor:
    """
    Executor do pipeline usando a nova arquitetura.
    
    Coordena a execução de todas as fases do pipeline usando
    os serviços da application layer.
    """
    
    def __init__(self, service_locator: ServiceLocator):
        self.service_locator = service_locator
        self.config = service_locator.obter_configuracoes()
    
    async def executar_pipeline_completo(self) -> None:
        """Executa pipeline completo usando nova estrutura."""
        try:
            logger.info("[PIPELINE] [START] INICIANDO PIPELINE REFATORADO - CLEAN ARCHITECTURE")
            logger.info("=" * 70)
            
            inicio_total = time.time()
            
            # Fase 1: Inicialização
            self._fase_inicializacao()
            
            # Fase 2: Extração de dados (ASSÍNCRONA)
            await self._fase_extracao()
            
            # Fase 3: Verificação
            self._fase_verificacao()
            
            # Fase 4: Processamento
            self._fase_processamento()
            
            # Fase 5: Upload
            self._fase_upload()
            
            # Fase 6: Relatórios
            self._fase_relatorios()
            
            # Finalização
            fim_total = time.time()
            duracao_total = fim_total - inicio_total
            
            logger.info("[PIPELINE] [SUCCESS] PIPELINE CONCLUIDO COM SUCESSO!")
            logger.info(f"[PIPELINE] [TIME] Tempo total de execucao: {formatar_tempo_total(duracao_total)}")
            logger.info("=" * 70)
            
        except Exception as e:
            logger.error(f"[PIPELINE] [CRITICAL] Erro critico no pipeline: {e}")
            logger.exception("[PIPELINE] [DETAILS] Detalhes do erro:")
            raise
    
    def _fase_inicializacao(self) -> None:
        """Fase 1: Inicialização do sistema."""
        logger.info("[FASE 1] [INIT] Inicializacao e preparacao do sistema")
        logger.info("[FASE 1] [PROGRESS] Progresso: 0/4 etapas concluidas")
        
        try:
            # Etapa 1/4: Inicializar banco de dados
            logger.info("[FASE 1] [STEP 1/4] Inicializando banco de dados...")
            logger.info("[FASE 1] [DATABASE] Conectando ao SQLite: omie.db")
            SQLiteRepository("omie.db")
            logger.info("[FASE 1] [OK] Banco de dados inicializado com sucesso")
            logger.info("[FASE 1] [PROGRESS] Progresso: 1/4 etapas concluidas (25%)")
            
            # Etapa 2/4: Atualizar datas de configuração
            logger.info("[FASE 1] [STEP 2/4] Atualizando configuracoes de data...")
            logger.info("[FASE 1] [CONFIG] Processando parametros de query no arquivo INI")
            atualizar_datas_configuracao_ini()
            logger.info("[FASE 1] [OK] Configuracoes de data atualizadas")
            logger.info("[FASE 1] [PROGRESS] Progresso: 2/4 etapas concluidas (50%)")
            
            # Etapa 3/4: Atualizar campos de registros pendentes
            logger.info("[FASE 1] [STEP 3/4] Atualizando registros pendentes...")
            logger.info(f"[FASE 1] [XML] Verificando arquivos em: {self.config['resultado_dir']}")
            repository = SQLiteRepository("omie.db")
            xml_service = XMLProcessingService(repository)
            xml_service.atualizar_campos_registros_pendentes(self.config['resultado_dir'])
            logger.info("[FASE 1] [OK] Registros pendentes atualizados")
            logger.info("[FASE 1] [PROGRESS] Progresso: 3/4 etapas concluidas (75%)")
            
            # Etapa 4/4: Atualizar indexação temporal
            logger.info("[FASE 1] [STEP 4/4] Atualizando indexacao temporal...")
            logger.info("[FASE 1] [INDEX] Recalculando campos anomesdia para otimizacao")
            repository = SQLiteRepository("omie.db")
            temporal_service = TemporalIndexingService(repository)
            temporal_service.atualizar_anomesdia()
            logger.info("[FASE 1] [OK] Indexacao temporal atualizada")
            logger.info("[FASE 1] [PROGRESS] Progresso: 4/4 etapas concluidas (100%)")
            
            logger.info("[FASE 1] [SUCCESS] Inicializacao concluida com sucesso")
            
        except Exception as e:
            logger.error(f"[FASE 1] [ERROR] Falha na inicializacao: {e}")
            logger.exception(f"[FASE 1] [DETAILS] Detalhes do erro:")
            raise
    
    async def _fase_extracao(self) -> None:
        """Fase 2: Extração de dados da API."""
        logger.info("[FASE 2] [EXTRACT] Extracao de dados da API Omie")
        
        try:
            omie_client = self.service_locator.obter_servico('omie_client')
            
            logger.info("[FASE 2] [API] Executando extracao de dados...")
            logger.info("[FASE 2] [CLIENT] Usando cliente Omie configurado")
            logger.info("[FASE 2] [ASYNC] Iniciando download assincrono de XMLs...")
            
            # Executar extração assíncrona
            await baixar_xmls(omie_client, "omie.db")
            
            logger.info("[FASE 2] [SUCCESS] Extracao assincrona concluida")
            
        except Exception as e:
            logger.error(f"[FASE 2] [ERROR] Erro na extracao: {e}")
            logger.exception("[FASE 2] [DETAILS] Detalhes do erro:")
            logger.warning("[FASE 2] [CONTINUE] Continuando com dados existentes no banco")
            # Não interrompe pipeline - continua com dados existentes
    
    def _fase_verificacao(self) -> None:
        """Fase 3: Verificação de integridade."""
        logger.info("[FASE 3] [CHECK] Verificacao de integridade dos dados")
        
        try:
            logger.info("[FASE 3] [XML] Iniciando verificacao de arquivos XML...")
            verificar_xmls()
            logger.info("[FASE 3] [SUCCESS] Verificacao concluida")
            
        except Exception as e:
            logger.error(f"[FASE 3] [ERROR] Erro na verificacao: {e}")
            logger.warning("[FASE 3] [CONTINUE] Continuando pipeline apesar dos erros")
            # Continua pipeline mesmo com erros de verificação
    
    def _fase_processamento(self) -> None:
        """Fase 4: Processamento e compactação."""
        logger.info("[FASE 4] [PROCESS] Processamento e compactacao de dados")
        
        try:
            # Atualizar caminhos
            logger.info("[FASE 4] [PATHS] Atualizando caminhos de arquivos no banco...")
            atualizar_caminhos_no_banco()
            logger.info("[FASE 4] [OK] Caminhos atualizados")
            
            # Compactar resultados
            logger.info("[FASE 4] [COMPRESS] Iniciando compactacao de resultados...")
            compactar_resultados()
            logger.info("[FASE 4] [OK] Compactacao concluida")
            
            logger.info("[FASE 4] [SUCCESS] Processamento concluido")
            
        except Exception as e:
            logger.error(f"[FASE 4] [ERROR] Erro no processamento: {e}")
            logger.warning("[FASE 4] [CONTINUE] Continuando para upload mesmo com erro")
            # Continua para upload mesmo com erro de compactação
    
    def _fase_upload(self) -> None:
        """Fase 5: Upload para OneDrive."""
        logger.info("[FASE 5] [UPLOAD] Upload para OneDrive")
        
        try:
            resultado_dir = Path(self.config['resultado_dir'])
            logger.info(f"[FASE 5] [SCAN] Escaneando diretorio: {resultado_dir}")
            
            arquivos_zip = list(resultado_dir.rglob("*.zip"))
            logger.info(f"[FASE 5] [FILES] Encontrados {len(arquivos_zip)} arquivos ZIP")
            
            if arquivos_zip:
                logger.info("[FASE 5] [ONEDRIVE] Iniciando upload para pasta XML_Compactados...")
                fazer_upload_lote(arquivos_zip, "XML_Compactados")
                logger.info(f"[FASE 5] [SUCCESS] Upload de {len(arquivos_zip)} arquivos concluido")
            else:
                logger.info("[FASE 5] [SKIP] Nenhum arquivo ZIP encontrado para upload")
                
        except Exception as e:
            logger.error(f"[FASE 5] [ERROR] Erro no upload: {e}")
            logger.warning("[FASE 5] [CONTINUE] Continuando para relatorios mesmo com erro")
            # Continua para relatórios mesmo com erro de upload
    
    def _fase_relatorios(self) -> None:
        """Fase 6: Geração de relatórios."""
        logger.info("[FASE 6] [REPORTS] Geracao de relatorios")
        
        try:
            logger.info(f"[FASE 6] [GENERATE] Gerando relatorio de arquivos vazios...")
            logger.info(f"[FASE 6] [DIR] Analisando diretorio: {self.config['resultado_dir']}")
            gerar_relatorio_vazios(self.config['resultado_dir'])
            logger.info("[FASE 6] [SUCCESS] Relatorios gerados com sucesso")
            
        except Exception as e:
            logger.error(f"[FASE 6] [ERROR] Erro na geracao de relatorios: {e}")
            logger.warning("[FASE 6] [NON_CRITICAL] Erro em relatorios nao e critico")
            # Erro em relatórios não é crítico

# =============================================================================
# Função principal refatorada
# =============================================================================

async def executar_pipeline_async() -> None:
    """
    Função assíncrona para executar o pipeline.
    
    Permite execução assíncrona da fase de extração de dados
    enquanto mantém as outras fases síncronas.
    """
    try:
        # Configurar logging
        configurar_sistema_logging()
        
        logger.info("[MAIN] [START] PIPELINE OMIE V3 - ARQUITETURA REFATORADA")
        logger.info("=" * 60)
        logger.info("[MAIN] [ARCH] Estrutura: Clean Architecture + DDD")
        logger.info("[MAIN] [PATTERNS] Padroes: Service Locator, Dependency Injection")
        logger.info("[MAIN] [ASYNC] Suporte para operacoes assincronas")
        logger.info("=" * 60)
        
        # Carregar configurações
        logger.info("[MAIN] [CONFIG] Carregando configuracoes...")
        config = carregar_configuracoes()
        logger.info("[MAIN] [OK] Configuracoes carregadas")
        
        # Configurar service locator
        logger.info("[MAIN] [SERVICES] Configurando service locator...")
        service_locator.configurar_servicos(config)
        logger.info("[MAIN] [OK] Servicos configurados")
        
        # Criar e executar pipeline assíncrono
        logger.info("[MAIN] [EXECUTOR] Criando executor do pipeline...")
        executor = PipelineExecutor(service_locator)
        logger.info("[MAIN] [EXECUTE] Iniciando execucao assincrona do pipeline...")
        await executor.executar_pipeline_completo()
        
        logger.info("[MAIN] [SUCCESS] EXECUCAO ASSINCRONA CONCLUIDA COM SUCESSO!")
        
    except KeyboardInterrupt:
        logger.warning("[MAIN] [INTERRUPT] Execucao interrompida pelo usuario")
        sys.exit(1)
    except SystemExit:
        raise
    except Exception as e:
        logger.error(f"[MAIN] [CRITICAL] Erro critico no main assincrono: {e}")
        logger.exception("[MAIN] [DETAILS] Detalhes do erro:")
        sys.exit(1)

def main() -> None:
    """
    Função principal refatorada usando Clean Architecture.
    
    Implementa:
    - Service Locator para dependency injection
    - Separação clara de responsabilidades
    - Estrutura modular e testável
    - Tratamento robusto de erros
    - Suporte para execução assíncrona
    """
    try:
        logger.info("[MAIN] [ASYNC_RUNNER] Iniciando loop de eventos assincrono...")
        # Executa o pipeline assíncrono
        asyncio.run(executar_pipeline_async())
        
    except KeyboardInterrupt:
        logger.warning("[MAIN] [INTERRUPT] Execucao interrompida pelo usuario")
        sys.exit(1)
    except SystemExit:
        raise
    except Exception as e:
        logger.error(f"[MAIN] [CRITICAL] Erro critico no main: {e}")
        logger.exception("[MAIN] [DETAILS] Detalhes do erro:")
        sys.exit(1)

if __name__ == "__main__":
    main()
