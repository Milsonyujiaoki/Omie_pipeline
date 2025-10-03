# =============================================================================
# PIPELINE PRINCIPAL DO EXTRATOR OMIE V3
# =============================================================================
"""
Pipeline principal para extracoo, processamento e upload de dados do Omie.

Este modulo orquestra todo o pipeline de extracoo de dados da API Omie,
processamento de XMLs, compactacoo de resultados e upload para OneDrive.
Implementa paralelizacoo, tratamento robusto de erros e logging detalhado.

Modulos principais:
- Extracoo assincrona de dados da API Omie
- Processamento e validacoo de XMLs
- Compactacoo de resultados
- Upload para OneDrive
- Geracoo de relatorios

Caracteristicas tecnicas:
- Processamento paralelo com ThreadPoolExecutor
- Operacões batch para otimizacoo de performance
- Logging estruturado com timestamps
- Tratamento de erros centralizados
- Configuracoo via arquivo INI
"""

# =============================================================================
# Importacões da biblioteca padroo
# =============================================================================
import asyncio
import configparser
import html
import locale
import logging
import os
import sys
import time
import sqlite3
import re
import signal
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, NamedTuple, Tuple
from dataclasses import dataclass
from contextlib import contextmanager
import xml.etree.ElementTree as ET
import threading
from src.utils import (
    atualizar_campos_registros_pendentes, 
    conexao_otimizada,
    limpar_cache_indexacao_xmls,
    obter_estatisticas_cache,
    gerar_xml_path_otimizado
)

# Importação do sistema de paths portável
from src.path_resolver import PathResolver

# =============================================================================
# Importacões dos modulos locais
# =============================================================================
# Imports feitos sob demanda para evitar dependências circulares
# Os módulos serão importados nas funções específicas que os utilizam

# =============================================================================
# Configurações globais e constantes
# =============================================================================
CONFIG_PATH: str = "configuracao.ini"  # Caminho padrão do arquivo de configuração INI

# Logger será configurado na função main()
# Por enquanto, configuração básica para evitar erros de importação
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)

# =============================================================================
# Configuracoo de SQLite otimizadas
# =============================================================================

SQLITE_PRAGMAS: Dict[str, str] = {
    "journal_mode": "WAL",      # Write-Ahead Logging para melhor concorrência
    "synchronous": "NORMAL",    # Balance entre segurança e performance
    "temp_store": "MEMORY",     # Operações temporárias em RAM
    "cache_size": "-64000",     # 64MB de cache (valor negativo = KB)
    "mmap_size": "268435456",   # 256MB memory-mapped
    "query_planner": "1",       # Habilita query planner
}

# Instância global do PathResolver (será inicializada na main)
path_resolver: Optional[PathResolver] = None

# =============================================================================
# Inicialização do sistema de paths portável
# =============================================================================

def inicializar_path_resolver() -> PathResolver:
    """Inicializa o sistema de paths portável."""
    global path_resolver
    if path_resolver is None:
        path_resolver = PathResolver()
        path_resolver.validar_ambiente()
    return path_resolver

# =============================================================================
# Configuracoo de logging estruturado
# =============================================================================
def configurar_logging() -> None:
    """
    Configura sistema de logging com encoding consistente.
    
    Solução simples:
    - Detecta encoding do console automaticamente
    - Aplica mesmo encoding para arquivo e console
    - Fallback seguro para UTF-8
    - Tratamento de erros robusto
    
    Benefícios:
    - Compatibilidade total Windows/Linux
    - Consistência entre arquivo e console
    - Implementação minimalista (< 20 linhas)
    - Zero dependências externas
    
    Returns:
        None
        
    Raises:
        OSError: Se não conseguir criar diretório de logs
    """
    # Criação do diretório
    log_dir = Path("log")
    log_dir.mkdir(exist_ok=True)
    
    # Timestamp único
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / f"Pipeline_Omie_{timestamp}.log"
    
    # Detecta encoding do console de forma inteligente
    console_encoding = _detectar_encoding_console()
    
    # Formato padronizado
    formato = "%(asctime)s - %(levelname)s - %(message)s"
    
    try:
        # Configuração com encoding consistente
        logging.basicConfig(
            level=logging.INFO,
            format=formato,
            handlers=[
                # Arquivo: mesmo encoding do console + tratamento de erros
                logging.FileHandler(
                    log_file, 
                    encoding=console_encoding, 
                    errors='replace'  # Substitui caracteres problemáticos
                ),
                # Console: encoding nativo com fallback
                _criar_console_handler(formato, console_encoding)
            ],
            force=True  # Reconfigura se já existir
        )
        
        # Log de confirmação
        logger.info(f"[SETUP] Logging configurado com encoding: {console_encoding}")
        logger.info(f"[SETUP] Arquivo: {log_file}")
        
        # Teste rápido de caracteres especiais
        logger.info("[TESTE] Caracteres: ção, não, são, então, €, ©")
        
    except Exception as e:
        # Fallback ultra-simples em caso de erro
        logging.basicConfig(
            level=logging.INFO,
            format=formato,
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8', errors='replace'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        logging.warning(f"[PIPELINE.CONFIG] Usando configuração básica devido a: {e}")

def _detectar_encoding_console() -> str:
    """
    Detecta encoding do console de forma robusta e simples.
    
    Estratégia:
    1. Tenta encoding do stdout se disponível
    2. Fallback para encoding preferido do sistema  
    3. Último recurso: UTF-8
    
    Returns:
        str: Encoding detectado ou 'utf-8' como fallback
    """
    try:
        # Prioridade 1: Encoding do stdout (mais confiável)
        if hasattr(sys.stdout, 'encoding') and sys.stdout.encoding:
            encoding = sys.stdout.encoding.lower()
            # Normaliza variações comuns
            if encoding in ['cp1252', 'windows-1252']:
                return 'cp1252'  # Windows padrão
            elif encoding.startswith('utf'):
                return 'utf-8'   # Qualquer variação UTF
            else:
                return encoding
        
        # Prioridade 2: Encoding preferido do sistema
        import locale
        system_encoding = locale.getpreferredencoding()
        if system_encoding:
            return system_encoding.lower()
            
    except (AttributeError, ImportError):
        pass
    
    # Fallback universal
    return 'utf-8'

def _criar_console_handler(formato: str, encoding: str) -> logging.StreamHandler:
    """
    Cria handler de console com encoding otimizado.
    
    Args:
        formato: String de formatação do log
        encoding: Encoding a ser usado
        
    Returns:
        logging.StreamHandler: Handler configurado
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(formato))
    
    # Tenta configurar encoding se suportado (Python 3.7+)
    try:
        # Verifica se o método reconfigure existe antes de chamar
        reconfigure_method = getattr(handler.stream, 'reconfigure', None)
        if reconfigure_method is not None:
            reconfigure_method(encoding=encoding, errors='replace')
    except (AttributeError, Exception):
        # Falha silenciosa - usa encoding padrão
        pass
    
    return handler

# =============================================================================
# Inicialização do sistema de logging
# =============================================================================
# IMPORTANTE: Configurar logging antes de qualquer importacoo dos modulos locais
# para garantir que todas as mensagens sejam capturadas adequadamente
# NOTA: Movido para dentro da função main() para evitar problemas de importação
# configurar_logging()

# =============================================================================
# Utilitários para formatação de tempo
# =============================================================================

def formatar_tempo_total(segundos: float) -> str:
    """
    Converte segundos em formato legível (Xh Ym Zs).
    
    Args:
        segundos: Tempo em segundos
        
    Returns:
        str: Tempo formatado (ex: "2h 15m 30s" ou "45m 12s" ou "23s")
    """
    if segundos < 0:
        return "0s"
    
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    segs = int(segundos % 60)
    
    if horas > 0:
        return f"{horas}h {minutos}m {segs}s"
    elif minutos > 0:
        return f"{minutos}m {segs}s"
    else:
        return f"{segs}s"

# =============================================================================
# Gerenciamento de configurações do sistema
# =============================================================================
from pathlib import Path

def carregar_configuracoes(config_path: str = "configuracao.ini") -> dict:
    """
    Carrega configurações com busca automática do arquivo.
    Usa o mesmo sistema de busca do PathResolver para compatibilidade.
    """
    # Busca o arquivo nos mesmos locais que o PathResolver
    locais_possiveis = [
        Path(config_path),  # Caminho atual/absoluto
        Path(__file__).parent / config_path,  # Ao lado do main_old.py
        Path.cwd() / config_path,  # Diretório atual
    ]
    
    config_file = None
    for local in locais_possiveis:
        if local.exists():
            config_file = local
            break
    
    if not config_file:
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {config_path}")

    config = configparser.ConfigParser()
    config.read(config_file, encoding='utf-8')

    # Leitura de todas as seções e conversão de tipos
    return {
        "paths": {
            "resultado_dir": config.get("paths", "resultado_dir", fallback="resultado"),
            "db_name": config.get("paths", "db_name", fallback="omie.db"),
            "log_dir": config.get("paths", "log_dir", fallback="log"),
            "temp_dir": config.get("paths", "temp_dir", fallback="temp"),
        },
        "compactador": {
            "arquivos_por_pasta": config.getint("compactador", "arquivos_por_pasta", fallback=10000),
            "max_workers": config.getint("compactador", "max_workers", fallback=4),
            "batch_size": config.getint("compactador", "batch_size", fallback=1000),
        },
        "ONEDRIVE": {
            "upload_onedrive": config.getboolean("ONEDRIVE", "upload_onedrive", fallback=False),
            "pasta_destino": config.get("ONEDRIVE", "pasta_destino", fallback="Documentos Compartilhados"),
            "upload_max_retries": config.getint("ONEDRIVE", "upload_max_retries", fallback=3),
            "upload_backoff_factor": config.getfloat("ONEDRIVE", "upload_backoff_factor", fallback=1.5),
            "upload_retry_status": config.get("ONEDRIVE", "upload_retry_status", fallback="429,500,502,503,504"),
        },
        "omie_api": {
            "app_key": config.get("omie_api", "app_key"),
            "app_secret": config.get("omie_api", "app_secret"),
            "base_url_nf": config.get("omie_api", "base_url_nf"),
            "base_url_xml": config.get("omie_api", "base_url_xml"),
            "calls_per_second": config.getint("omie_api", "calls_per_second", fallback=4),
        },
        "query_params": {
            "start_date": config.get("query_params", "start_date"),
            "end_date": config.get("query_params", "end_date"),
            "records_per_page": config.getint("query_params", "records_per_page", fallback=200),
        },
        "pipeline": {
            "modo_hibrido_ativo": config.getboolean("pipeline", "modo_hibrido_ativo", fallback=True),
            "min_erros_para_reprocessamento": config.getint("pipeline", "min_erros_para_reprocessamento", fallback=30000),
            "reprocessar_automaticamente": config.getboolean("pipeline", "reprocessar_automaticamente", fallback=True),
            "apenas_normal": config.getboolean("pipeline", "apenas_normal", fallback=False),
        },
        "logging": {
            "log_level": config.get("logging", "log_level", fallback="INFO"),
            "log_file": config.get("logging", "log_file", fallback="extrator.log"),
        }
    }

def log_configuracoes(config: dict, logger) -> None:
    for secao, valores in config.items():
        logger.info(f"[MAIN.CONFIG] Seção: {secao}")
        for chave, valor in valores.items():
            logger.info(f"    {chave}: {valor}")
# =============================================================================
# Funcões de execucao das etapas do pipeline
# =============================================================================

def executar_atualizador_datas_query() -> None:
    """
    Atualiza as datas de consulta no arquivo de configuracoo INI.
    
    Processo:
    1. Calcula proximo periodo de consulta baseado na data atual
    2. Atualiza datas inicial e final no arquivo INI
    3. Valida formato das datas
    4. Cria backup da configuracoo anterior
    5. Registra alteracões no log
    
    Caracteristicas:
    - Calculo automatico de periodos
    - Backup de configuracões anteriores
    - Validacoo de formato de datas
    - Tratamento de feriados e fins de semana
    - Logging detalhado de alteracões
    
    Returns:
        None
        
    Raises:
        Exception: Erros durante atualizacao soo logados e noo propagados
    """
    try:
        logger.info("[PIPELINE.DATAS] Iniciando atualizacao das datas de consulta")
        t0 = time.time()
        
        # Import local para evitar dependência circular
        from src import atualizar_query_params_ini
        
        # Log de contexto antes da atualização
        try:
            import configparser
            config = configparser.ConfigParser()
            config.read("configuracao.ini", encoding='utf-8')
            if config.has_section('query_params'):
                data_atual_inicio = config.get('query_params', 'start_date', fallback='N/A')
                data_atual_fim = config.get('query_params', 'end_date', fallback='N/A')
                logger.info(f"[PIPELINE.DATAS.CONTEXTO] Periodo atual: {data_atual_inicio} a {data_atual_fim}")
        except Exception as ctx_error:
            logger.debug(f"[PIPELINE.DATAS.CONTEXTO] Erro ao ler configuracao atual: {ctx_error}")
        
        logger.info("[PIPELINE.DATAS.INICIO] Calculando novo periodo")
        atualizar_query_params_ini.atualizar_datas_configuracao_ini()
        
        # Log das novas datas
        try:
            import configparser
            config = configparser.ConfigParser()
            config.read("configuracao.ini", encoding='utf-8')
            if config.has_section('query_params'):
                nova_data_inicio = config.get('query_params', 'start_date', fallback='N/A')
                nova_data_fim = config.get('query_params', 'end_date', fallback='N/A')
                logger.info(f"[PIPELINE.DATAS.RESULTADO] Novo periodo: {nova_data_inicio} a {nova_data_fim}")
        except Exception as new_error:
            logger.debug(f"[PIPELINE.DATAS.RESULTADO] Erro ao ler novas configuracoes: {new_error}")
        
        t1 = time.time()
        duracao = t1 - t0
        logger.info(f"[PIPELINE.DATAS.SUCESSO] Atualizacao de datas finalizada - Tempo total: {formatar_tempo_total(duracao)} ({duracao:.2f}s)")
        
    except Exception as e:
        logger.exception(f"[PIPELINE.DATAS.ERRO] Erro durante atualizacao de datas: {e}")
        logger.error("[PIPELINE.DATAS.CONTINUACAO] Pipeline continuara com datas atuais")


def executar_atualizacao_caminhos() -> None:
    """
    Atualiza os caminhos dos arquivos XML no banco de dados.
    
    MELHORIAS IMPLEMENTADAS:
    - Executa APÓS compactação para capturar caminhos em ZIPs
    - Valida se há arquivos para processar antes de executar
    - Detecta e corrige arquivos vazios automaticamente
    
    Processo:
    1. Varre o diretorio de resultado recursivamente (incluindo ZIPs)
    2. Localiza arquivos XML baixados
    3. Atualiza caminhos no banco de dados
    4. Valida consistência dos registros
    5. Corrige inconsistências encontradas
    
    Caracteristicas:
    - Varredura recursiva otimizada
    - atualizacao em lote para performance
    - Validacoo de consistência de dados
    - Correcoo automatica de inconsistências
    - Logging detalhado de alteracões
    - Suporte a arquivos compactados (ZIP)
    
    Returns:
        None
        
    Raises:
        Exception: Erros durante atualizacao soo logados e noo propagados
    """
    try:
        logger.info("[CAMINHOS] Iniciando atualizacao de caminhos no banco...")
        t0 = time.time()
        
        # Verificação prévia: há arquivos para processar?
        config = carregar_configuracoes()
        resolver = inicializar_path_resolver()
        resultado_dir = resolver.get_path_by_key("resultado_dir")
        
        # Conta arquivos XML e ZIPs
        arquivos_xml = list(resultado_dir.rglob("*.xml"))
        #arquivos_zip = list(resultado_dir.rglob("*.zip"))
        total_arquivos = len(arquivos_xml)  # + len(arquivos_zip)
        
        #total_arquivos = len(arquivos_xml) + len(arquivos_zip)
        
        if total_arquivos == 0:
            logger.warning("[CAMINHOS] Nenhum arquivo XML ou ZIP encontrado - pulando atualização")
            return

        logger.info(f"[CAMINHOS] Encontrados {len(arquivos_xml)} XMLs para processar")

        # Import local para evitar dependência circular
        from src import atualizar_caminhos_arquivos
        atualizar_caminhos_arquivos.atualizar_caminhos_no_banco()
        
        t1 = time.time()
        duracao = t1 - t0
        logger.info(f"[CAMINHOS] atualizacao finalizada com sucesso. Tempo total: {formatar_tempo_total(duracao)} ({duracao:.2f}s)")
        
        # Validação pós-atualização: estatísticas
        try:
            import sqlite3
            db_path = resolver.get_path_by_key("db_name")
            with sqlite3.connect(str(db_path)) as conn:
                cursor = conn.execute("SELECT COUNT(*) as total FROM notas WHERE xml_baixado = 1")
                total_baixados = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT COUNT(*) as total FROM notas WHERE xml_vazio = 1")
                total_vazios = cursor.fetchone()[0]
                
                logger.info(f"[CAMINHOS] Estatísticas pós-atualização:")
                logger.info(f"  • Arquivos marcados como baixados: {total_baixados:,}")
                if total_vazios > 0:
                    logger.warning(f"  • Arquivos vazios detectados: {total_vazios:,}")
                else:
                    logger.info(f"  • Arquivos vazios: {total_vazios}")
        except Exception as e:
            logger.debug(f"[CAMINHOS] Erro ao obter estatísticas: {e}")
        
    except Exception as e:
        logger.exception(f"[CAMINHOS] Erro durante atualizacao de caminhos: {e}")
        logger.error("[CAMINHOS] Pipeline continuara sem atualizacao")


def executar_atualizacao_anomesdia() -> None:
    """
    Executa atualização da indexação temporal (anomesdia) no banco de dados.
    
    FUNCIONALIDADES:
    - Atualiza campo anomesdia para registros sem indexação temporal
    - Usa função otimizada do módulo utils
    - Logging detalhado de progresso e resultados
    - Tratamento robusto de erros
    
    Processo:
    1. Identifica registros sem campo anomesdia preenchido
    2. Extrai data de emissão (dEmi) e converte para formato numérico
    3. Atualiza registros em lotes otimizados
    4. Gera estatísticas de progresso
    
    Benefícios:
    - Consultas temporais mais rápidas (índice numérico)
    - Views otimizadas funcionam corretamente
    - Relatórios por período mais eficientes
    - Análises temporais otimizadas
    
    Returns:
        None
        
    Raises:
        Exception: Erros durante atualização são logados e não propagados
    """
    try:
        logger.info("[PIPELINE.ANOMESDIA] Iniciando atualização do campo anomesdia ...")
        t0 = time.time()
        
        # Importa função do módulo utils
        from src.utils import atualizar_anomesdia
        
        # Executa atualização com logging detalhado
        logger.info("[PIPELINE.ANOMESDIA] Processando registros sem campo anomesdia...")
        resolver = inicializar_path_resolver()
        db_path = str(resolver.get_path_by_key("db_name"))
        registros_atualizados = atualizar_anomesdia(db_path=db_path)
        
        t1 = time.time()
        duracao = t1 - t0
        
        # Log de resultados
        if registros_atualizados > 0:
            velocidade = registros_atualizados / duracao if duracao > 0 else 0
            logger.info(f"[PIPELINE.ANOMESDIA.SUCESSO] {registros_atualizados:,} registros indexados temporalmente")
            logger.info(f"[PIPELINE.ANOMESDIA.PERFORMANCE] Tempo: {formatar_tempo_total(duracao)} ({duracao:.2f}s), Velocidade: {velocidade:.0f} reg/s")
        else:
            logger.info("[PIPELINE.ANOMESDIA.NENHUM] Todos os registros já possuem indexação temporal")
            logger.info(f"[PIPELINE.ANOMESDIA.PERFORMANCE] Tempo total: {duracao:.2f}s, nenhum registro atualizado")
        
    except Exception as e:
        logger.exception(f"[PIPELINE.ANOMESDIA.ERRO] Erro durante atualização da indexação temporal: {e}")
        logger.warning("[PIPELINE.ANOMESDIA.CONTINUACAO] Pipeline continuará sem indexação temporal completa")


def _executar_async_com_config(config: Dict[str, Any]) -> None:
    """
    Executa extrator assíncrono com configurações específicas.
    
    Args:
        config: Configurações personalizadas
    """
    try:
        # Import local para evitar dependência circular
        from src.extrator_async import baixar_xmls, listar_nfs
        from src.omie_client_async import OmieClient, carregar_configuracoes_client
        
        # CORREÇÃO: Não sobrescrever a config passada como parâmetro
        # Usar config completa do omie_client_async mas manter parâmetros customizados
        config_client = carregar_configuracoes_client()
        
        # Mesclar configurações - prioridade para config passada como parâmetro
        config_merged = {**config_client, **config}
        
        # Credenciais e URLs da API Omie
        # Validar que as chaves obrigatórias existem
        app_key = config_merged.get('app_key')
        app_secret = config_merged.get('app_secret')
        
        if not app_key or not app_secret:
            raise ValueError("app_key e app_secret são obrigatórios no arquivo de configuração")
            
        for v, k in config_merged.items():
            logger.info(f"[ASYNC.CONFIG] Configurações carregadas com sucesso {v}: {k}")

        # CORREÇÃO: Criar cliente com TODAS as configurações necessárias
        client = OmieClient(
            app_key=app_key,
            app_secret=app_secret,
            calls_per_second=config_merged.get('calls_per_second', 4),
            base_url_nf=config_merged.get('base_url_nf', 'https://app.omie.com.br/api/v1/produtos/nfconsultar/'),
            base_url_xml=config_merged.get('base_url_xml', 'https://app.omie.com.br/api/v1/produtos/dfedocs/')
        )
        
        # Executar pipeline assíncrono
        import asyncio
        
        # CORREÇÃO: Usar abordagem mais simples e direta
        logger.info("[ASYNC.CONFIG] Iniciando pipeline assíncrono...")
        asyncio.run(_pipeline_async_completo(client, config_merged))
        
    except Exception as e:
        logger.exception(f"[ASYNC.CONFIG] Erro durante execução async: {e}")
        raise


async def _pipeline_async_completo(client, config: Dict[str, Any]) -> None:
    """Pipeline assíncrono completo."""
    from src.extrator_async import baixar_xmls, listar_nfs
    from src.utils import iniciar_db
    
    resolver = inicializar_path_resolver()
    # CORREÇÃO: Usar path relativo para manter compatibilidade
    db_name_relativo = config.get("db_name", "omie.db")
    db_name = str(Path.cwd() / db_name_relativo)  # Forçar usar diretório atual
    
    # DEBUG: Comparar com o que o extrator_async standalone faria
    db_name_fallback = config.get("db_name", "omie.db")
    logger.info(f"[PIPELINE.ASYNC.DEBUG] db_name corrigido: {db_name}")
    logger.info(f"[PIPELINE.ASYNC.DEBUG] db_name via config (como standalone): {db_name_fallback}")
    logger.info(f"[PIPELINE.ASYNC.DEBUG] Current working directory: {Path.cwd()}")
    
    t1 = time.time()
    logger.info("[PIPELINE.ASYNC] Iniciando pipeline assíncrono completo")
    logger.info(f"[PIPELINE.ASYNC] iniciando iniciar banco de dados: {db_name}")

    # Inicializar banco
    # CORREÇÃO: Usar TABLE_NAME como no extrator_async standalone
    from src.extrator_async import TABLE_NAME
    iniciar_db(db_name, TABLE_NAME)
    t2 = time.time()
    logger.info(f"[PIPELINE.ASYNC] Banco de dados inicializado em {formatar_tempo_total(t2 - t1)} ({t2 - t1:.2f}s)")
    logger.info("[PIPELINE.ASYNC] Iniciando listagem e download de notas fiscais assíncronos")
    t3 = time.time()
    # Lista as notas fiscais da API Omie e salva no banco de dados
    logger.info(f"[PIPELINE.ASYNC.DEBUG] Iniciando listar_nfs com config: start_date={config.get('start_date')}, end_date={config.get('end_date')}")
    logger.info(f"[PIPELINE.ASYNC.DEBUG] Client configurado: app_key={client.app_key[:10]}..., calls_per_second={client.calls_per_second}")
    logger.info("[PIPELINE.ASYNC.DEBUG] Antes de chamar listar_nfs...")
    
    try:
        await listar_nfs(client, config, db_name)
        logger.info("[PIPELINE.ASYNC.DEBUG] listar_nfs completou com sucesso!")
    except Exception as e:
        logger.exception(f"[PIPELINE.ASYNC.DEBUG] Erro em listar_nfs: {e}")
        raise
        
    t4 = time.time()
    logger.info(f"[PIPELINE.ASYNC] Listagem concluída em {formatar_tempo_total(t4 - t3)} ({t4 - t3:.2f}s)")
    
    
    # =============================================================================
    # Fase 3.5: Indexação temporal otimizada
    # =============================================================================
    logger.info("[FASE 3.5] - Atualizando indexação temporal (anomesdia)...")
    try:
        logger.info("[PIPELINE.ASYNC] Iniciando indexação temporal - ANOMESDIA EM TODOS CAMPOS")
        # Vai popular o campo anomesdia
        executar_atualizacao_anomesdia()
        logger.info("[PIPELINE.ASYNC] Indexação temporal concluída com sucesso")
        logger.info("[FASE 3.5] - ✓ Indexação temporal concluída com sucesso")
    except Exception as e:
        logger.exception(f"[FASE 3.5] Erro durante indexação temporal: {e}")
        logger.warning("[FASE 3.5] Pipeline continuará sem indexação temporal completa")


    # Executar download com configurações otimizadas
    logger.info("[ASYNC.PIPELINE] Iniciando download assíncrono")
    t5 = time.time()
    await baixar_xmls(client, db_name)
    t6 = time.time()
    logger.info(f"[ASYNC.PIPELINE] Download concluído em {formatar_tempo_total(t6 - t5)} ({t6 - t5:.2f}s)")


def executar_compactador_resultado() -> None:
    """
    Executa a compactacoo dos arquivos XML processados em arquivos ZIP.
    
    Processo:
    1. Localiza todos os arquivos XML no diretorio de resultado
    2. Agrupa arquivos por data ou criterio definido
    3. Compacta em arquivos ZIP organizados
    4. Aplica compressoo otimizada
    5. Valida integridade dos arquivos compactados
    
    Caracteristicas:
    - Processamento paralelo para multiplos arquivos
    - Compressoo otimizada para reduzir tamanho
    - Validacoo de integridade pos-compactacoo
    - Limpeza automatica de arquivos temporarios
    
    Returns:
        None
        
    Raises:
        Exception: Erros durante o processo de compactacoo soo logados e noo propagados
    """
    try:
        logger.info("[PIPELINE.COMPACTADOR] Iniciando compactacoo dos resultados")
        t0 = time.time()
        
        # Import local para evitar dependência circular
        from src import compactador_resultado
        
        # Log de início com informações contextuais
        logger.info("[PIPELINE.COMPACTADOR.INICIO] Verificando arquivos para compactacao")
        
        compactador_resultado.compactar_resultados()
        
        t1 = time.time()
        duracao = t1 - t0
        logger.info(f"[PIPELINE.COMPACTADOR.SUCESSO] Compactacao finalizada - Tempo total: {formatar_tempo_total(duracao)} ({duracao:.2f}s)")
        
        # Adicionar métricas se disponível
        try:
            resolver = inicializar_path_resolver()
            resultado_dir = resolver.get_path_by_key("resultado_dir")
            if resultado_dir.exists():
                total_arquivos = len(list(resultado_dir.rglob("*.xml")))
                total_zips = len(list(resultado_dir.rglob("*.zip")))
                logger.info(f"[PIPELINE.COMPACTADOR.METRICAS] {total_arquivos} XMLs, {total_zips} ZIPs criados")
        except Exception as metric_error:
            logger.debug(f"[PIPELINE.COMPACTADOR.METRICAS] Erro ao coletar métricas: {metric_error}")
        
    except Exception as e:
        logger.exception(f"[PIPELINE.COMPACTADOR.ERRO] Erro critico durante compactacao: {e}")
        logger.error("[PIPELINE.COMPACTADOR.CONTINUACAO] Pipeline continuara sem compactacao")


def executar_upload_resultado_onedrive() -> None:
    """
    Executa upload em lote dos arquivos compactados para OneDrive.
    
    Processo:
    1. Identifica arquivos ZIP no diretorio de resultado
    2. Autentica com OneDrive usando credenciais configuradas
    3. Realiza upload paralelo respeitando limites de API
    4. Valida integridade dos arquivos enviados
    5. Atualiza status de upload no banco de dados
    
    Caracteristicas:
    - Upload paralelo com controle de taxa
    - Retry automatico para falhas temporarias
    - Validacoo de integridade pos-upload
    - Logging detalhado de progresso
    - Limpeza de arquivos apos upload bem-sucedido
    
    Returns:
        None
        
    Raises:
        Exception: Erros durante upload soo logados e noo propagados
    """
    try:
        logger.info("[PIPELINE.ONEDRIVE] Iniciando upload em lote dos resultados")
        
        # Import local para evitar dependência circular
        from src.upload_onedrive import fazer_upload_lote
        logger.info("[PIPELINE.UPLOAD] Usando sistema legado de upload")
        
        t0 = time.time()
        
        # Busca por arquivos ZIP na pasta resultado
        resultado_dir = Path("resultado")
        if not resultado_dir.exists():
            logger.warning("[PIPELINE.ONEDRIVE.VERIFICACAO] Pasta resultado nao encontrada")
            return
        
        # Lista todos os arquivos .zip
        arquivos_zip = list(resultado_dir.rglob("*.zip"))
        
        if not arquivos_zip:
            logger.info("[PIPELINE.ONEDRIVE.VERIFICACAO] Nenhum arquivo ZIP encontrado para upload")
            return
        
        total = len(arquivos_zip)
        logger.info(f"[PIPELINE.ONEDRIVE.INICIO] Encontrados {total} arquivos ZIP para upload")
        
        # Calcular tamanho total aproximado
        try:
            tamanho_total = sum(arquivo.stat().st_size for arquivo in arquivos_zip)
            tamanho_mb = tamanho_total / (1024 * 1024)
            logger.info(f"[PIPELINE.ONEDRIVE.METRICAS] Tamanho total: {tamanho_mb:.1f} MB")
        except Exception as size_error:
            logger.debug(f"[PIPELINE.ONEDRIVE.METRICAS] Erro ao calcular tamanho: {size_error}")
        
        # Executa upload em lote
        resultados = fazer_upload_lote(arquivos_zip, "XML_Compactados")
        
        # Estatisticas detalhadas
        sucessos = sum(1 for sucesso in resultados.values() if sucesso)
        falhas = total - sucessos
        taxa_sucesso = (sucessos / total * 100) if total > 0 else 0
        
        t1 = time.time()
        duracao = t1 - t0
        velocidade = sucessos / (duracao / 60) if duracao > 0 else 0
        
        logger.info(f"[PIPELINE.ONEDRIVE.SUCESSO] Upload finalizado: {sucessos}/{total} arquivos ({taxa_sucesso:.1f}%)")
        if falhas > 0:
            logger.warning(f"[PIPELINE.ONEDRIVE.FALHAS] {falhas} uploads falharam")
        logger.info(f"[PIPELINE.ONEDRIVE.TEMPO] Duracao total: {formatar_tempo_total(duracao)} ({duracao:.2f}s), Velocidade: {velocidade:.1f} arquivos/min")
        
    except Exception as e:
        logger.exception(f"[PIPELINE.ONEDRIVE.ERRO] Erro critico durante upload: {e}")
        logger.error("[PIPELINE.ONEDRIVE.CONTINUACAO] Pipeline continuara sem upload")

def executar_verificador_xmls() -> None:
    """
    Executa verificacao de integridade dos arquivos XML baixados.
    
    OTIMIZAÇÕES IMPLEMENTADAS:
    - Cria índices de performance antes da execução
    - Usa conexão otimizada com PRAGMAs
    - Aplica índices específicos para consulta xml_baixado = 0
    - Logging detalhado de performance
    
    Verificacões realizadas:
    1. Validacoo de estrutura XML (well-formed)
    2. verificacao de encoding correto
    3. Validacoo de campos obrigatorios
    4. Checagem de consistência de dados
    5. atualizacao de status no banco de dados
    
    Caracteristicas:
    - Processamento paralelo para performance
    - Validacoo XML rigorosa
    - Deteccoo de arquivos corrompidos
    - Marcacoo automatica de reprocessamento
    - Estatisticas detalhadas de validacoo
    - Índices otimizados para consultas rápidas
    
    Returns:
        None
        
    Raises:
        Exception: Erros durante verificacao soo logados e noo propagados
    """
    try:
        logger.info("[PIPELINE.VERIFICADOR] Iniciando verificacao de integridade dos XMLs")
        t0 = time.time()
        
        # 0. CACHE: Limpar cache para execução limpa e obter estatísticas iniciais
        logger.info("[PIPELINE.VERIFICADOR.CACHE] Preparando sistema de cache...")
        try:
            # Obtém estatísticas antes da limpeza
            stats_iniciais = obter_estatisticas_cache()
            if stats_iniciais['directories_cached'] > 0:
                logger.info(f"[PIPELINE.VERIFICADOR.CACHE] Cache existente: {stats_iniciais['directories_cached']} dirs, {stats_iniciais['total_files_cached']} arquivos")
            
            # Limpa cache para execução limpa (opcional, baseado em configuração)
            cache_limpo = limpar_cache_indexacao_xmls()
            if cache_limpo > 0:
                logger.info(f"[PIPELINE.VERIFICADOR.CACHE] Cache limpo: {cache_limpo} entradas removidas")
            else:
                logger.info("[PIPELINE.VERIFICADOR.CACHE] Cache já estava limpo")
                
        except Exception as cache_error:
            logger.warning(f"[PIPELINE.VERIFICADOR.CACHE] Erro no gerenciamento de cache: {cache_error}")
        
        # 1. OTIMIZAÇÃO: Criar índices de performance ANTES da verificação
        logger.info("[PIPELINE.VERIFICADOR.INDICES] Criando índices de performance para verificação")
        try:
            #criar_indices_performance("omie.db")
            logger.info("[PIPELINE.VERIFICADOR.INDICES] ✓ Índices criados/verificados com sucesso")
        except Exception as idx_error:
            logger.warning(f"[PIPELINE.VERIFICADOR.INDICES] Erro ao criar índices: {idx_error}")
        
        # 2. Log de contexto antes da verificação (usando índice otimizado)
        try:
            resolver = inicializar_path_resolver()
            db_path = str(resolver.get_path_by_key("db_name"))
            with conexao_otimizada(db_path) as conn:
                cursor = conn.cursor()
                
                # Usa o índice idx_status_download para consulta rápida
                cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 1")
                total_baixados = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 0")
                total_pendentes = cursor.fetchone()[0]
                
                logger.info(f"[PIPELINE.VERIFICADOR.CONTEXTO] {total_baixados:,} XMLs marcados como baixados")
                logger.info(f"[PIPELINE.VERIFICADOR.CONTEXTO] {total_pendentes:,} XMLs pendentes para verificacao")
                
                # Log adicional de performance
                if total_pendentes > 0:
                    logger.info(f"[PIPELINE.VERIFICADOR.PERFORMANCE] Verificacao otimizada com índices para {total_pendentes:,} registros")
                
        except Exception as ctx_error:
            logger.debug(f"[PIPELINE.VERIFICADOR.CONTEXTO] Erro ao obter contexto: {ctx_error}")
        
        # 3. Import local para evitar dependência circular
        from src import verificador_xmls
        
        # 4. Execução do verificador (agora com índices otimizados)
        logger.info("[PIPELINE.VERIFICADOR.INICIO] Executando verificacao detalhada com índices otimizados")
        verificador_xmls.verificar()
        
        t1 = time.time()
        duracao = t1 - t0
        logger.info(f"[PIPELINE.VERIFICADOR.SUCESSO] Verificacao finalizada - Tempo total: {formatar_tempo_total(duracao)} ({duracao:.2f}s)")
        
        # 5. CACHE: Relatório final de estatísticas de cache
        try:
            stats_finais = obter_estatisticas_cache()
            if stats_finais['directories_cached'] > 0:
                logger.info("[PIPELINE.VERIFICADOR.CACHE] Estatísticas finais do cache:")
                logger.info(f"   • Diretórios indexados: {stats_finais['directories_indexed']}")
                logger.info(f"   • Arquivos em cache: {stats_finais['total_files_cached']}")
                logger.info(f"   • Cache hits: {stats_finais['cache_hits']}")
                logger.info(f"   • Cache misses: {stats_finais['cache_misses']}")
                logger.info(f"   • Hit rate: {stats_finais['hit_rate_percent']:.1f}%")
                
                # Análise de performance do cache
                if stats_finais['cache_hits'] > 0:
                    logger.info(f"   ✅ Cache FUNCIONOU - {stats_finais['cache_hits']} acessos otimizados")
                    performance_gain = "significativo" if stats_finais['hit_rate_percent'] > 50 else "moderado"
                    logger.info(f"   🚀 Ganho de performance: {performance_gain}")
                else:
                    logger.info("   ℹ️  Cache não foi utilizado nesta execução")
            else:
                logger.debug("[PIPELINE.VERIFICADOR.CACHE] Nenhum cache utilizado nesta execução")
                
        except Exception as stats_error:
            logger.debug(f"[PIPELINE.VERIFICADOR.CACHE] Erro ao obter estatísticas: {stats_error}")
        
        # 6. Log de resultados pós-verificação (usando índices)
        try:
            resolver = inicializar_path_resolver()
            db_path = str(resolver.get_path_by_key("db_name"))
            with conexao_otimizada(db_path) as conn:
                cursor = conn.cursor()
                
                # Consultas otimizadas com índices
                cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_vazio = 1")
                vazios = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 1")
                total_baixados_final = cursor.fetchone()[0]
                
                logger.info(f"[PIPELINE.VERIFICADOR.RESULTADO] XMLs baixados após verificação: {total_baixados_final:,}")
                
                if vazios > 0:
                    logger.warning(f"[PIPELINE.VERIFICADOR.RESULTADO] {vazios:,} XMLs vazios detectados")
                else:
                    logger.info("[PIPELINE.VERIFICADOR.RESULTADO] Todos os XMLs estao validos")
                    
                # Calcula velocidade de processamento
                if duracao > 0:
                    velocidade = total_pendentes / duracao if 'total_pendentes' in locals() else 0
                    logger.info(f"[PIPELINE.VERIFICADOR.PERFORMANCE] Velocidade: {velocidade:.1f} XMLs/s")
                    
        except Exception as result_error:
            logger.debug(f"[PIPELINE.VERIFICADOR.RESULTADO] Erro ao obter resultados: {result_error}")
        
    except Exception as e:
        logger.exception(f"[PIPELINE.VERIFICADOR.ERRO] Erro durante verificacao de XMLs: {e}")
        logger.error("[PIPELINE.VERIFICADOR.CONTINUACAO] Pipeline continuara sem verificacao")


def executar_atualizacao_status_nfe() -> None:
    """
    Executa atualização de status das NFe usando a API Omie.
    
    NOVA FUNCIONALIDADE:
    - Consulta endpoints da API Omie para obter status atualizado das NFe
    - Atualiza campo 'status' no banco de dados
    - Identifica notas canceladas, rejeitadas, autorizadas, etc.
    - Processa em lotes para otimizar performance
    - Respeita limites de taxa da API
    
    Processo:
    1. Consulta notas sem status ou com status indefinido
    2. Utiliza endpoints ListarNFesEmitidas e ObterNfe
    3. Normaliza diferentes formatos de status
    4. Atualiza banco de dados em lotes
    5. Gera estatísticas detalhadas
    
    Características:
    - Processamento assíncrono para melhor performance
    - Controle de rate limiting automático
    - Tratamento robusto de erros da API
    - Logging detalhado de progresso
    - Suporte a modo dry-run para testes
    
    Returns:
        None
        
    Raises:
        Exception: Erros durante atualização são logados e não propagados
    """
    try:
        logger.info("[MAIN.STATUS_NFE] Iniciando atualização de status das NFe...")
        t0 = time.time()
        
        # Import local para evitar dependência circular
        from src.status_nfe_updater import executar_atualizacao_status_nfe_sync
        
        # Executa atualização com limite conservador
        limite_notas = 500  # Limite conservador para não impactar muito a API
        
        logger.info(f"[MAIN.STATUS_NFE] Processando até {limite_notas} notas para atualização de status")
        
        # Chama função síncrona para integração com pipeline atual
        sucesso = executar_atualizacao_status_nfe_sync(
            config_path="configuracao.ini",
            limite_notas=limite_notas,
            dry_run=False
        )
        
        t1 = time.time()
        
        if sucesso:
            logger.info("[MAIN.STATUS_NFE] ✅ Atualização de status concluída com sucesso")
            logger.info(f"[MAIN.STATUS_NFE] Tempo de execução: {formatar_tempo_total(t1-t0)} ({t1-t0:.2f}s)")
        else:
            logger.warning("[MAIN.STATUS_NFE] ⚠️ Atualização concluída com alguns erros")
            logger.warning("[MAIN.STATUS_NFE] Verifique logs detalhados para informações específicas")
        
    except Exception as e:
        logger.exception(f"[MAIN.STATUS_NFE] Erro na atualização de status: {e}")
        logger.warning("[MAIN.STATUS_NFE] Pipeline continuará sem atualização de status")


def executar_relatorio_arquivos_vazios(pasta: str) -> None:
    """
    Gera relatorio detalhado de arquivos vazios ou corrompidos.
    
    Versão otimizada com timeout para evitar execução infinita.
    
    Analise realizada:
    1. Varre recursivamente o diretorio especificado
    2. Identifica arquivos com tamanho zero
    3. Detecta arquivos XML malformados
    4. Analisa arquivos com conteudo suspeito
    5. Gera relatorio Excel com estatisticas
    
    Args:
        pasta: Diretorio raiz para analise de arquivos
        
    Caracteristicas:
    - Analise recursiva de subdiretorios
    - Deteccoo de multiplos tipos de problemas
    - Geracoo de relatorio Excel formatado
    - Estatisticas detalhadas por categoria
    - Timeout de 30 minutos para evitar travamento
    
    Returns:
        None
        
    Raises:
        Exception: Erros durante geracoo do relatorio soo logados e noo propagados
    """
    try:
        logger.info(f"[PIPELINE.RELATORIO] Iniciando analise otimizada de arquivos vazios")
        logger.info(f"[PIPELINE.RELATORIO.PASTA] Diretorio: {pasta}")
        
        # Verifica se o diretorio existe
        pasta_obj = Path(pasta)
        if not pasta_obj.exists():
            logger.warning(f"[PIPELINE.RELATORIO.VERIFICACAO] Diretorio nao encontrado: {pasta}")
            return
        
        # Conta arquivos e subdiretórios sem usar len/sum
        try:
            logger.info("[PIPELINE.RELATORIO.CONTAGEM] Estimando quantidade de arquivos e subdiretórios")
            arquivo_count = 0
            xml_count = 0
            subdir_count = 0
            for root, dirs, files in os.walk(pasta_obj):
                subdir_count += len(dirs)
                for file in files:
                    arquivo_count += 1
                    if file.lower().endswith('.xml'):
                        xml_count += 1
            logger.info(f"[PIPELINE.RELATORIO.METRICAS] Total de arquivos: {arquivo_count:,}")
            logger.info(f"[PIPELINE.RELATORIO.METRICAS] Arquivos XML: {xml_count:,}")
            logger.info(f"[PIPELINE.RELATORIO.METRICAS] Subdiretórios: {subdir_count:,}")
            # Estima tempo baseado na quantidade
            tempo_estimado = arquivo_count / 10000  # ~10k arquivos por minuto
            logger.info(f"[PIPELINE.RELATORIO.ESTIMATIVA] Tempo estimado: {tempo_estimado:.1f} minutos")
            # Se ha muitos arquivos, usa analise rapida
            if arquivo_count > 500000:  # Mais de 500k arquivos
                logger.warning(f"[PIPELINE.RELATORIO.OTIMIZACAO] Muitos arquivos ({arquivo_count:,}). Usando analise rapida")
                _executar_relatorio_rapido(pasta)
                return
        except Exception as e:
            logger.warning(f"[PIPELINE.RELATORIO.CONTAGEM] Erro ao contar arquivos/subdiretórios: {e}")
        
        # Sistema de timeout compatível com Windows usando threading
        timeout_seconds = 1800  # 30 minutos
        timeout_event = threading.Event()
        timeout_occurred = False
        
        def timeout_handler():
            nonlocal timeout_occurred
            if not timeout_event.wait(timeout_seconds):
                timeout_occurred = True
                logger.warning("[PIPELINE.RELATORIO.TIMEOUT] Timeout de 30 minutos atingido!")
        
        # Inicia o timer de timeout
        timeout_thread = threading.Thread(target=timeout_handler, daemon=True)
        timeout_thread.start()
        logger.debug("[PIPELINE.RELATORIO.TIMEOUT] Timeout de 30 minutos configurado")
        
        t0 = time.time()
        logger.info("[PIPELINE.RELATORIO.INICIO] Iniciando analise detalhada")
        
        try:
            # Import local para evitar dependência circular
            from src import report_arquivos_vazios
            
            # Verifica timeout antes de continuar
            if timeout_occurred:
                raise TimeoutError("Timeout na analise de arquivos")
                
            report_arquivos_vazios.gerar_relatorio(pasta)
            
        except TimeoutError:
            logger.warning("[PIPELINE.RELATORIO.TIMEOUT] Analise interrompida por timeout. Tentando analise rapida")
            _executar_relatorio_rapido(pasta)
            
        finally:
            # Cancela o timeout
            timeout_event.set()
        
        t1 = time.time()
        duracao = t1 - t0
        logger.info(f"[PIPELINE.RELATORIO.SUCESSO] Analise concluida - Tempo total: {formatar_tempo_total(duracao)} ({duracao:.2f}s)")
        
    except Exception as e:
        logger.exception(f"[PIPELINE.RELATORIO.ERRO] Erro critico durante analise: {e}")
        logger.info("[PIPELINE.RELATORIO.CONTINUACAO] Pipeline continuara mesmo com erro no relatorio")


def _executar_relatorio_rapido(pasta: str) -> None:
    """
    Executa analise rapida focando apenas em arquivos modificados recentemente.
    
    Args:
        pasta: Diretorio para analise
    """
    try:
        logger.info("[PIPELINE.RELATORIO.RAPIDO] Iniciando analise rapida (ultimos 7 dias)")
        t_inicio = time.time()
        
        root = Path(pasta)
        sete_dias_atras = datetime.now() - timedelta(days=7)
        timestamp_limite = sete_dias_atras.timestamp()
        
        logger.info(f"[PIPELINE.RELATORIO.RAPIDO.FILTRO] Analisando arquivos modificados apos: {sete_dias_atras.strftime('%Y-%m-%d %H:%M:%S')}")
        
        arquivos_recentes = []
        contador_total = 0
        contador_validos = 0
        
        logger.info("[PIPELINE.RELATORIO.RAPIDO.BUSCA] Buscando arquivos recentes")
        
        for arquivo in root.rglob("*"):
            if arquivo.is_file():
                contador_total += 1
                try:
                    if arquivo.stat().st_mtime > timestamp_limite:
                        arquivos_recentes.append(arquivo)
                        contador_validos += 1
                        
                        # Log de progresso a cada 1000 arquivos encontrados
                        if contador_validos % 1000 == 0:
                            logger.debug(f"[PIPELINE.RELATORIO.RAPIDO.PROGRESSO] {contador_validos} arquivos recentes encontrados")
                        
                        # Limite para evitar uso excessivo de memoria
                        if contador_validos > 10000:
                            logger.info("[PIPELINE.RELATORIO.RAPIDO.LIMITE] Limite de 10k arquivos atingido. Parando busca")
                            break
                            
                except (OSError, PermissionError):
                    pass  # Ignora arquivos inacessíveis
        
        logger.info(f"[PIPELINE.RELATORIO.RAPIDO.RESULTADO] {contador_validos:,} arquivos recentes de {contador_total:,} total")
        
        if not arquivos_recentes:
            logger.info("[PIPELINE.RELATORIO.RAPIDO.VAZIO] Nenhum arquivo recente para analisar")
            return
        
        # Analise dos arquivos encontrados
        logger.info(f"[PIPELINE.RELATORIO.RAPIDO.ANALISE] Analisando {len(arquivos_recentes):,} arquivos modificados recentemente")
        
        problemas = []
        for i, arquivo in enumerate(arquivos_recentes):
            try:
                # Log de progresso a cada 500 arquivos
                if (i + 1) % 500 == 0:
                    percentual = ((i + 1) / len(arquivos_recentes)) * 100
                    logger.debug(f"[PIPELINE.RELATORIO.RAPIDO.ANALISE] Progresso: {i+1:,}/{len(arquivos_recentes):,} ({percentual:.1f}%)")
                
                if arquivo.suffix.lower() == '.xml' and arquivo.stat().st_size == 0:
                    problemas.append({
                        'arquivo': str(arquivo),
                        'problema': 'Arquivo vazio',
                        'tamanho': 0,
                        'modificado': datetime.fromtimestamp(arquivo.stat().st_mtime)
                    })
            except Exception:
                pass  # Ignora erros individuais
        
        # Salva resultado
        try:
            import pandas as pd
            if problemas:
                df = pd.DataFrame(problemas)
                relatorio_path = f"relatorio_arquivos_vazios_rapido_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                df.to_excel(relatorio_path, index=False)
                logger.info(f"[PIPELINE.RELATORIO.RAPIDO.SALVO] Relatorio salvo: {relatorio_path} com {len(problemas):,} problemas")
            else:
                logger.info("[PIPELINE.RELATORIO.RAPIDO.LIMPO] Nenhum problema encontrado nos arquivos recentes")
        except ImportError:
            logger.warning("[PIPELINE.RELATORIO.RAPIDO.PANDAS] Pandas nao disponivel para salvar relatorio")
        except Exception as save_error:
            logger.error(f"[PIPELINE.RELATORIO.RAPIDO.ERRO_SALVAR] Erro ao salvar relatorio: {save_error}")
        
        t_fim = time.time()
        duracao = t_fim - t_inicio
        velocidade = len(arquivos_recentes) / duracao if duracao > 0 else 0
        
        logger.info(f"[PIPELINE.RELATORIO.RAPIDO.CONCLUIDO] Analise rapida finalizada")
        logger.info(f"[PIPELINE.RELATORIO.RAPIDO.TEMPO] Duracao total: {formatar_tempo_total(duracao)} ({duracao:.2f}s), Velocidade: {velocidade:.0f} arquivos/s")
        
    except Exception as e:
        logger.exception(f"[PIPELINE.RELATORIO.RAPIDO.ERRO] Erro durante geração do relatorio: {e}")
        logger.error("[PIPELINE.RELATORIO.RAPIDO.CONTINUACAO] Pipeline continuara sem relatorio")


# =============================================================================
# Estruturas de dados e context managers otimizados
# =============================================================================

@contextmanager
def conexao_otimizada(db_path: str):
    """
    Context manager para conexão SQLite otimizada.
    
    Aplica PRAGMAs de performance e garante fechamento adequado.
    
    Args:
        db_path: Caminho para o banco SQLite
        
    Yields:
        sqlite3.Connection: Conexão otimizada
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row  # Acesso por nome de coluna
        
        # Aplica PRAGMAs de otimização
        for pragma, valor in SQLITE_PRAGMAS.items():
            conn.execute(f"PRAGMA {pragma} = {valor}")
        
        yield conn
        
    except Exception as e:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


# =============================================================================
# Função principal do pipeline
# =============================================================================


def main() -> None:
    """
    Função principal que orquestra todo o pipeline de extração de dados do Omie.
    
    Fluxo de execução simplificado:
    1. Carregamento e validação de configurações
    2. Atualização de campos essenciais dos registros pendentes
    3. Execução do pipeline principal com detecção automática de modo
    4. Verificação de integridade dos XMLs
    5. Atualização de caminhos no banco
    6. Compactação dos resultados
    7. Upload para OneDrive
    8. Geração de relatórios
    
    Características:
    - Detecção automática do modo de execução (normal/pendentes/reprocessamento)
    - Execução sequencial com tratamento de erros robusto
    - Logging detalhado de cada etapa
    - Recuperação automática de falhas não críticas
    - Métricas de performance por etapa
    
    Returns:
        None
        
    Raises:
        SystemExit: Em caso de falhas críticas que impedem a continuidade
    """
    try:
        # =============================================================================
        # Configuração inicial do sistema de logging
        # =============================================================================
        # Import local para evitar dependência circular
        import sqlite3
        import os
        import sys
        import time
        import logging
        import configparser
        
        # =============================================================================
        # Inicialização do sistema de paths portável
        # =============================================================================
        logger.info("[MAIN.INIT] Inicializando sistema de paths portável...")
        try:
            resolver = inicializar_path_resolver()
            logger.info("[MAIN.INIT] ✅ Sistema de paths portável inicializado com sucesso")
        except Exception as resolver_error:
            logger.exception(f"[MAIN.INIT] Erro crítico na inicialização do PathResolver: {resolver_error}")
            logger.error("[MAIN.INIT] O sistema não pode continuar sem paths válidos")
            sys.exit(1)
        
        configurar_logging()
        
        # =============================================================================
        # Fase 1: Inicialização e configuração
        # =============================================================================
        
        # Inicializar variáveis com valores padrão
        config = {}
        resultado_dir = "resultado"
        db_path = "omie.db"
        
        try:
            logger.info("=" * 80)
            logger.info("INICIANDO PIPELINE DO EXTRATOR OMIE V3 SIMPLIFICADO")
            logger.info("=" * 80)
            
            # CACHE: Inicialização e limpeza do sistema de cache
            logger.info("[MAIN.CACHE] Inicializando sistema de cache global...")
            try:
                # Obtém estatísticas iniciais
                stats_iniciais = obter_estatisticas_cache()
                logger.info(f"[MAIN.CACHE] Estado inicial: {stats_iniciais['directories_cached']} dirs em cache")
                
                # Limpa cache para execução limpa (recomendado no início)
                cache_limpo = limpar_cache_indexacao_xmls()
                if cache_limpo > 0:
                    logger.info(f"[MAIN.CACHE] Cache inicial limpo: {cache_limpo} entradas removidas")
                else:
                    logger.info("[MAIN.CACHE] Cache já estava limpo")
                    
                logger.info("[MAIN.CACHE] ✅ Sistema de cache inicializado e pronto")
                
            except Exception as cache_error:
                logger.warning(f"[MAIN.CACHE] Erro na inicialização do cache: {cache_error}")
                logger.info("[MAIN.CACHE] Pipeline continuará sem otimizações de cache")
            
            # Log de informações do ambiente
            logger.info(f"[MAIN.AMBIENTE] Executável Python: {sys.executable}")
            logger.info(f"[MAIN.AMBIENTE] Argumentos: {sys.argv}")
            logger.info(f"[MAIN.AMBIENTE] Diretório de trabalho: {os.getcwd()}")
            logger.info(f"[MAIN.AMBIENTE] Versão do Python: {sys.version}")
            
            # Carregamento das configurações
            config = carregar_configuracoes()
            log_configuracoes(config, logger)
            resolver = inicializar_path_resolver()
            resultado_dir = config.get('resultado_dir', 'resultado')
            db_path = str(resolver.get_path_by_key("db_name"))  # Caminho do banco SQLite portável
            
        except Exception as e:
            logger.exception(f"[FASE 1] Erro ao carregar configurações: {e}")
            logger.error("[FASE 1] Usando configurações padrão para continuidade")
            # Garantir que pelo menos as variáveis básicas estejam definidas
            if not config:
                config = {'resultado_dir': 'resultado'}
            try:
                resolver = inicializar_path_resolver()
                db_path = str(resolver.get_path_by_key("db_name"))
            except Exception as path_error:
                logger.error(f"[FASE 1] Erro crítico no PathResolver: {path_error}")
                sys.exit(1)
        
        # =============================================================================
        # Fase 2: Atualização de campos essenciais dos registros pendentes
        # =============================================================================
        logger.info("[FASE 2] - Atualizando campos essenciais dos registros pendentes...")
        t0 = time.time()
        
        try:
            # Import local para evitar dependência circular
            # Verifica se os arquivos marcados como xml_baixado = 0 realmente não foram baixados,
            # atualizando o status quando encontrados nos diretórios locais.

            logger.info("[MAIN.ATUALIZACAO_PENDENTES] Atualizando campos essenciais dos registros pendentes...")
            atualizar_campos_registros_pendentes(db_path, resultado_dir)
            logger.info("[MAIN.ATUALIZACAO_PENDENTES] Atualização concluída com sucesso")
            t1 = time.time()
            logger.info(f"[FASE 2] Atualização concluída. Tempo: {formatar_tempo_total(t1-t0)} ({t1-t0:.2f}s)")
            
        except Exception as e:
            logger.exception(f"[FASE 2] Erro durante atualização: {e}")
            logger.warning("[FASE 2] Pipeline continuará sem esta atualização")

        
            
        
        # =============================================================================
        # Fase 2.5: Pipeline principal (download de XMLs)
        # =============================================================================
        logger.info("[FASE 2.5] - Executando pipeline download de XMLs...")

        try:
            # Atualiza datas de consulta antes da execução
            logger.info("[FASE 2.5] - Atualizando datas de consulta...")
            try:
                logger.info("[MAIN.ATUALIZADOR_DATAS] Atualizando datas de consulta...")
                #executar_atualizador_datas_query()
                logger.info("[MAIN.ATUALIZADOR_DATAS] Datas de consulta atualizadas")
                logger.info("[FASE 2.5] - ✓ Datas atualizadas com sucesso")
            except Exception as e:
                logger.error(f"[FASE 2.5] - Erro ao atualizar datas: {e}")
                logger.warning("[FASE 2.5] - Continuando com datas atuais")
                
            try:
                # Executa o extrator adaptativo
                logger.info("[FASE 3] - Iniciando extração de dados...")
                logger.info("[MAIN.EXECUTAR_ASYNC_CONFIG] Executando extrator adaptativo com configuração...")
                t2 = time.time()
                _executar_async_com_config(config)
                t3 = time.time()
                logger.info("[MAIN.EXECUTAR_ASYNC_CONFIG] Extração adaptativa concluída")
                logger.info("[FASE 3] - Extração de dados concluída com sucesso")
                logger.info(f"[FASE 3] - Tempo total de extração: {formatar_tempo_total(t3-t2)} ({t3-t2:.2f}s)")
            except Exception as e:  
                logger.exception(f"[FASE 3] - Erro durante extração de dados: {e}")
                logger.error("[FASE 3] - Pipeline falhou na extração de dados")
                raise
            # =============================================================================
            # Fase 4: Verificação de integridade
            # =============================================================================
            logger.info("[FASE 4] - Verificando integridade dos arquivos...")
            try:
                logger.info("[MAIN.VERIFICADOR_XMLS] Iniciando verificação de integridade dos XMLs baixados...")
                executar_verificador_xmls()
                logger.info("[MAIN.VERIFICADOR_XMLS] Verificação de integridade concluída")
                logger.info("[FASE 4] - Verificação de integridade concluída com sucesso")
            except Exception as e:
                logger.exception(f"[FASE 4] - Erro durante verificação: {e}")
                logger.warning("[FASE 4] - Pipeline continuará sem verificação completa")

            # =============================================================================
            # Fase 5: Compactação dos resultados
            # =============================================================================
            logger.info("[FASE 5] - Compactando resultados...")
            try:
                logger.info("[MAIN.COMPACTADOR_RESULTADO] Iniciando compactação dos resultados...")
                executar_compactador_resultado()
                logger.info("[MAIN.COMPACTADOR_RESULTADO] Compactação concluída com sucesso")
                logger.info("[FASE 5] - ✓ Compactação concluída com sucesso")
            except Exception as e:
                logger.exception(f"[FASE 5] - Erro durante compactação: {e}")
                logger.warning("[FASE 5] - Pipeline continuará sem compactação")

            # =============================================================================
            # Fase 6: Atualização de caminhos (APÓS compactação)
            # =============================================================================
            logger.info("[FASE 6] - Atualizando caminhos no banco de dados...")
            try:
                logger.info("[MAIN.ATUALIZACAO_CAMINHOS] Iniciando atualização de caminhos...")
                executar_atualizacao_caminhos()
                logger.info("[MAIN.ATUALIZACAO_CAMINHOS] Atualização concluída com sucesso")
                logger.info("[FASE 6] - ✓ Atualização de caminhos concluída com sucesso")
            except Exception as e:
                logger.exception(f"[FASE 6] - Erro durante atualização de caminhos: {e}")
                logger.warning("[FASE 6] - Pipeline continuará sem atualização de caminhos")

            # =============================================================================
            # Fase 6.5: Atualização de Status das NFe (NOVA FUNCIONALIDADE)
            # =============================================================================
            logger.info("[FASE 6.5] - Atualizando status das NFe...")
            try:
                logger.info("[MAIN.STATUS_NFE] Iniciando atualização de status das NFe...")
                #executar_atualizacao_status_nfe()
                logger.info("[MAIN.STATUS_NFE] Atualização de status concluída")
                logger.info("[FASE 6.5] - ✓ Status das NFe atualizado com sucesso")
            except Exception as e:
                logger.exception(f"[FASE 6.5] - Erro durante atualização de status: {e}")
                logger.warning("[FASE 6.5] - Pipeline continuará sem atualização de status")

            # =============================================================================
            # Fase 7: Upload para OneDrive
            # =============================================================================
            logger.info("[FASE 7] - Enviando para OneDrive...")
            try:
                logger.info("[MAIN.UPLOAD_ONEDRIVE] Iniciando upload dos resultados compactados para OneDrive...")
                #executar_upload_resultado_onedrive()
                logger.info("[MAIN.UPLOAD_ONEDRIVE] Upload concluído com sucesso")
                logger.info("[FASE 7] - Upload concluído com sucesso")
            except Exception as e:
                logger.exception(f"[FASE 7] - Erro durante upload: {e}")
                logger.warning("[FASE 7] - Pipeline continuará sem upload")

            # =============================================================================
            # Fase 8: Geração de relatórios
            # =============================================================================
            logger.info("[FASE 8] - Gerando relatórios finais...")
            try:
                logger.info("[MAIN.GERADOR_RELATORIOS] Iniciando geração de relatórios...")
                executar_relatorio_arquivos_vazios(resultado_dir)
                logger.info("[MAIN.GERADOR_RELATORIOS] Geração de relatórios concluída com sucesso")
                logger.info("[FASE 8] - Relatórios gerados com sucesso")
            except Exception as e:
                logger.exception(f"[FASE 8] - Erro durante geração de relatórios: {e}")
                logger.warning("[FASE 8] - Pipeline concluído sem relatórios")

        except Exception as e:
            logger.exception(f"[FASE 3] - Erro crítico no pipeline de download: {e}")
            logger.error("[FASE 3] - Falha crítica - pipeline será interrompido")
            raise
        
        logger.info("[FASE 3] Pipeline principal concluído com sucesso")
        
        # =============================================================================
        # Conclusão com métricas finais
        # =============================================================================
        logger.info("=" * 80)
        logger.info("PIPELINE CONCLUÍDO COM SUCESSO")
        
        # =============================================================================
        # CACHE: Relatório final de performance do cache
        # =============================================================================
        logger.info("RELATÓRIO FINAL DE PERFORMANCE DO CACHE:")
        try:
            stats_finais = obter_estatisticas_cache()
            
            if stats_finais['directories_cached'] > 0:
                logger.info("[CACHE.FINAL] ✅ Sistema de cache foi utilizado com sucesso!")
                logger.info(f"[CACHE.FINAL]   • Diretórios indexados: {stats_finais['directories_indexed']}")
                logger.info(f"[CACHE.FINAL]   • Arquivos em cache: {stats_finais['total_files_cached']:,}")
                logger.info(f"[CACHE.FINAL]   • Cache hits: {stats_finais['cache_hits']}")
                logger.info(f"[CACHE.FINAL]   • Cache misses: {stats_finais['cache_misses']}")
                logger.info(f"[CACHE.FINAL]   • Hit rate: {stats_finais['hit_rate_percent']:.1f}%")
                
                # Análise final de performance
                total_requests = stats_finais['cache_hits'] + stats_finais['cache_misses']
                if total_requests > 0:
                    efficiency = "EXCELENTE" if stats_finais['hit_rate_percent'] > 80 else \
                               "BOA" if stats_finais['hit_rate_percent'] > 50 else \
                               "REGULAR" if stats_finais['hit_rate_percent'] > 20 else "BAIXA"
                    
                    logger.info(f"[CACHE.FINAL] 🚀 Eficiência do cache: {efficiency}")
                    
                    if stats_finais['hit_rate_percent'] > 50:
                        logger.info("[CACHE.FINAL] 💡 Cache proporcionou ganho significativo de performance!")
                    else:
                        logger.info("[CACHE.FINAL] 💡 Cache teve uso limitado - considere ajustes")
                else:
                    logger.info("[CACHE.FINAL] ℹ️  Cache inicializado mas não utilizado nesta execução")
            else:
                logger.info("[CACHE.FINAL] ℹ️  Cache não foi utilizado nesta execução")
                
        except Exception as cache_final_error:
            logger.warning(f"[CACHE.FINAL] Erro ao obter estatísticas finais: {cache_final_error}")

        # =============================================================================
        # Métricas de banco de dados otimizadas
        # =============================================================================
        logger.info("MÉTRICAS COMPLETAS DO BANCO DE DADOS:")
        try:
            logger.info("[MAIN.METRICAS_COMPLETAS] Iniciando exibição de métricas completas...")
            # Import local para evitar dependência circular
            from src.utils import exibir_metricas_completas
            resolver = inicializar_path_resolver()
            db_path = str(resolver.get_path_by_key("db_name"))
            exibir_metricas_completas(db_path)
            logger.info("[MAIN.METRICAS_COMPLETAS] Exibição de métricas completas concluída com sucesso")
        except Exception as e:
            logger.error(f"[MÉTRICAS] Erro ao obter métricas completas: {e}")
            
            # Fallback para métricas básicas em caso de erro
            try:
                import sqlite3
                resolver = inicializar_path_resolver()
                db_path = str(resolver.get_path_by_key("db_name"))
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("SELECT COUNT(*) FROM notas")
                    total_notas = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 1")
                    baixados = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 0")
                    pendentes = cursor.fetchone()[0]
                    
                    percentual = (baixados / max(1, total_notas)) * 100
                    
                    logger.info(f"   • Total de notas: {total_notas:,}")
                    logger.info(f"   • XMLs baixados: {baixados:,} ({percentual:.1f}%)")
                    logger.info(f"   • Pendentes: {pendentes:,}")
                    
            except Exception as fallback_error:
                logger.error(f"[MÉTRICAS] Erro no fallback: {fallback_error}")
        
        logger.info("=" * 80)
        
    except KeyboardInterrupt:
        logger.warning("[MAIN] Execução interrompida pelo usuário")
        logger.info("[MAIN] Pipeline foi cancelado graciosamente")
        sys.exit(130)  # Código padrão para interrupção por Ctrl+C
        
    except SystemExit:
        # Re-propaga SystemExit sem logging adicional
        raise
        
    except Exception as e:
        logger.exception(f"[MAIN] Erro crítico no pipeline principal: {e}")
        logger.error("[MAIN] Pipeline falhou com erro crítico")

        # Análise do tipo de erro para melhor debugging
        if isinstance(e, FileNotFoundError):
            logger.error("[DEBUG] Erro relacionado a arquivo não encontrado")
        elif isinstance(e, PermissionError):
            logger.error("[DEBUG] Erro de permissão de acesso")
        elif isinstance(e, sqlite3.Error):
            logger.error("[DEBUG] Erro relacionado ao banco de dados")
        else:
            logger.error(f"[DEBUG] Tipo de erro: {type(e).__name__}")

        sys.exit(1)


# =============================================================================
# Ponto de entrada da aplicacoo
# =============================================================================


if __name__ == "__main__":
    """
    Ponto de entrada da aplicacoo quando executada diretamente.
    
    Verifica se o script esta sendo executado diretamente (noo importado)
    e chama a funcao principal do pipeline.
    
    Esta estrutura permite que o modulo seja tanto executado diretamente
    quanto importado por outros modulos sem execucao automatica.
    """
    main()
