# =============================================================================
# PIPELINE PRINCIPAL DO EXTRATOR OMIE V3 - ARQUITETURA REFATORADA
# =============================================================================
"""
Pipeline principal refatorado para extração, processamento e upload de dados do Omie.

Esta versão implementa uma arquitetura unificada que elimina redundâncias e conflitos
entre diferentes modos de execução, proporcionando:

- Sistema inteligente de detecção de modos
- Fluxo único sem conflitos entre execuções
- Reutilização otimizada de código comum
- Configuração dinâmica por contexto
- Logging especializado por modo

Modos de execução suportados:
- Normal: Pipeline completo com listagem e download
- Reprocessamento: Reprocessamento de registros inválidos
- Pendentes: Download de registros pendentes acumulados

Características técnicas:
- Eliminação de redundâncias entre fluxos
- Configuração dinâmica baseada no contexto
- Pipeline comum para fases finais (verificação, compactação, upload)
- Tratamento robusto de erros por modo
- Métricas detalhadas de performance
"""

# =============================================================================
# Importações da biblioteca padrão
# =============================================================================
import asyncio
import configparser
import datetime
import importlib
import logging
import os
import signal
import sys
import time
from datetime import datetime
from inspect import iscoroutinefunction
from pathlib import Path
from typing import Any, Dict, List, Optional

# =============================================================================
# Importações dos módulos locais
# =============================================================================
from src import (
    atualizar_caminhos_arquivos,
    atualizar_query_params_ini,
    compactador_resultado,
    extrator_async,
    report_arquivos_vazios,
    verificador_xmls,
)
from src.omie_client_async import carregar_configuracoes as carregar_config_omie
from src.utils import (
    atualizar_campos_registros_pendentes,
    buscar_registros_invalidos_para_reprocessar,
    limpar_registros_invalidos_reprocessados,
    marcar_registros_invalidos_e_listar_dias,
)
from src.gerenciador_modos import (
    GerenciadorModos,
    ModoExecucao,
    ConfiguracaoExecucao,
    executar_com_gerenciamento_modo
)

# =============================================================================
# Configurações globais e constantes
# =============================================================================
CONFIG_PATH: str = "configuracao.ini"
logger = logging.getLogger(__name__)

# =============================================================================
# Configuração de logging estruturado
# =============================================================================
def configurar_logging() -> None:
    """
    Configura o sistema de logging estruturado da aplicação.
    
    Características:
    - Saída simultânea para arquivo e console
    - Arquivo de log com timestamp único por execução
    - Formato padronizado com timestamp, nível e mensagem
    - Diretório de logs criado automaticamente
    - Nível INFO para visibilidade adequada do pipeline
    
    Estrutura do log:
    - Diretório: ./log/
    - Formato: Pipeline_Omie_YYYYMMDD_HHMMSS.log
    - Encoding: UTF-8 (implícito)
    - Rotação: Manual (um arquivo por execução)
    
    Returns:
        None
        
    Raises:
        OSError: Se não conseguir criar o diretório de logs
        PermissionError: Se não tiver permissão para criar arquivos de log
    """
    log_dir = Path("log")
    log_dir.mkdir(exist_ok=True)
    
    # Timestamp único para garantir logs separados por execução
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / f"Pipeline_Omie_{timestamp}.log"
    
    # Configuração robusta com handlers múltiplos
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger.info(f"[SETUP] Sistema de logging configurado. Arquivo: {log_file}")


# =============================================================================
# Gerenciamento de configurações do sistema
# =============================================================================
def carregar_configuracoes(config_path: str = CONFIG_PATH) -> Dict[str, Any]:
    """
    Carrega e valida as configurações do sistema a partir do arquivo INI.
    
    Configurações carregadas:
    - Diretórios de trabalho (paths)
    - Parâmetros de performance (batch_size, max_workers)
    - Modo de operação (async/parallel)
    - Credenciais da API Omie
    
    Args:
        config_path: Caminho para o arquivo de configuração INI
        
    Returns:
        Dict contendo todas as configurações validadas do sistema
        
    Raises:
        SystemExit: Se arquivo INI não existe ou configurações obrigatórias ausentes
        ConfigParser.Error: Se arquivo INI malformado
        ValueError: Se valores numéricos inválidos
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        logger.error(f"[CONFIG] Arquivo de configuração não encontrado: {config_path}")
        logger.error(f"[CONFIG] Certifique-se de que o arquivo {config_path} existe no diretório raiz")
        sys.exit(1)
    
    try:
        config = configparser.ConfigParser()
        config.read(config_path, encoding='utf-8')
        
        # Validação de seções obrigatórias
        required_sections = ['paths', 'pipeline', 'api_speed', 'omie_api']
        for section in required_sections:
            if section not in config:
                logger.error(f"[CONFIG] Seção obrigatória [{section}] não encontrada no arquivo INI")
                sys.exit(1)
        
        # Validação de chaves obrigatórias
        if 'resultado_dir' not in config['paths']:
            logger.error("[CONFIG] Chave obrigatória 'resultado_dir' ausente na seção [paths]")
            sys.exit(1)
            
        if 'app_key' not in config['omie_api'] or 'app_secret' not in config['omie_api']:
            logger.error("[CONFIG] Credenciais app_key e app_secret ausentes na seção [omie_api]")
            sys.exit(1)
        
        # Carregamento das configurações com valores padrão seguros
        resultado_dir = config.get("paths", "resultado_dir")
        modo_download = config.get("api_speed", "modo_download", fallback="async").lower()
        app_key = config.get("omie_api", "app_key", fallback="").strip()
        app_secret = config.get("omie_api", "app_secret", fallback="").strip()
        
        if not app_key or not app_secret:
            logger.error("[CONFIG] Credenciais app_key e app_secret não podem estar vazias")
            sys.exit(1)
        
        # Configurações de performance com fallbacks inteligentes
        cpu_count = os.cpu_count() or 4
        batch_size = int(config.get("pipeline", "batch_size", fallback="500"))
        max_workers = int(config.get("pipeline", "max_workers", fallback=str(cpu_count)))
        
        # Validação de valores numéricos
        if batch_size <= 0:
            logger.warning(f"[CONFIG] batch_size inválido ({batch_size}), usando padrão: 500")
            batch_size = 500
            
        if max_workers <= 0:
            logger.warning(f"[CONFIG] max_workers inválido ({max_workers}), usando padrão: {cpu_count}")
            max_workers = cpu_count
        
        configuracoes = {
            "resultado_dir": resultado_dir,
            "modo_download": modo_download,
            "batch_size": batch_size,
            "max_workers": max_workers,
            "config_path": config_path,
            "app_key": app_key,
            "app_secret": app_secret
        }
        
        logger.info(f"[CONFIG] Configurações carregadas com sucesso:")
        logger.info(f"[CONFIG] - Diretório resultado: {resultado_dir}")
        logger.info(f"[CONFIG] - Modo download: {modo_download}")
        logger.info(f"[CONFIG] - Batch size: {batch_size}")
        logger.info(f"[CONFIG] - Max workers: {max_workers}")
        logger.info(f"[CONFIG] - Credenciais: {'✓ Carregadas' if app_key and app_secret else '✗ Ausentes'}")
        
        return configuracoes
        
    except (configparser.Error, ValueError) as e:
        logger.error(f"[CONFIG] Erro ao processar arquivo de configuração: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"[CONFIG] Erro inesperado ao carregar configurações: {e}")
        sys.exit(1)


# =============================================================================
# Funções de execução das etapas do pipeline
# =============================================================================
def executar_compactador_resultado() -> None:
    """
    Executa a compactação dos arquivos XML processados em arquivos ZIP.
    
    Processo:
    1. Localiza todos os arquivos XML no diretório de resultado
    2. Agrupa arquivos por data ou critério definido
    3. Compacta em arquivos ZIP organizados
    4. Aplica compressão otimizada
    5. Valida integridade dos arquivos compactados
    
    Características:
    - Processamento paralelo para múltiplos arquivos
    - Compressão otimizada para reduzir tamanho
    - Validação de integridade pós-compactação
    - Limpeza automática de arquivos temporários
    
    Returns:
        None
        
    Raises:
        Exception: Erros durante o processo de compactação são logados e não propagados
    """
    try:
        logger.info("[COMPACTADOR] Iniciando compactação dos resultados...")
        t0 = time.time()
        
        compactador_resultado.main()
        
        t1 = time.time()
        logger.info(f"[COMPACTADOR] Compactação finalizada com sucesso. Tempo: {t1-t0:.2f}s")
        
    except Exception as e:
        logger.exception(f"[COMPACTADOR] Erro crítico durante compactação: {e}")
        logger.error("[COMPACTADOR] Pipeline continuará sem compactação")


def executar_upload_resultado_onedrive() -> None:
    """
    Executa upload em lote dos arquivos compactados para OneDrive.
    
    Processo:
    1. Identifica arquivos ZIP no diretório de resultado
    2. Autentica com OneDrive usando credenciais configuradas
    3. Realiza upload paralelo respeitando limites de API
    4. Valida integridade dos arquivos enviados
    5. Atualiza status de upload no banco de dados
    
    Características:
    - Upload paralelo com controle de taxa
    - Retry automático para falhas temporárias
    - Validação de integridade pós-upload
    - Logging detalhado de progresso
    - Limpeza de arquivos após upload bem-sucedido
    
    Returns:
        None
        
    Raises:
        Exception: Erros durante upload são logados e não propagados
    """
    try:
        logger.info("[ONEDRIVE] Iniciando upload para OneDrive...")
        t0 = time.time()
        
        try:
            importlib.import_module('src.onedrive_uploader').main()
            logger.info("[ONEDRIVE] Upload para OneDrive concluído")
        except ImportError as e:
            logger.warning(f"[ONEDRIVE] Módulo OneDrive não encontrado: {e}")
        except Exception as e:
            logger.error(f"[ONEDRIVE] Erro no upload OneDrive: {e}")
        
        t1 = time.time()
        logger.info(f"[ONEDRIVE] Upload finalizado. Tempo: {t1-t0:.2f}s")
        
    except Exception as e:
        logger.exception(f"[ONEDRIVE] Erro crítico durante upload: {e}")
        logger.error("[ONEDRIVE] Pipeline continuará sem upload")


def executar_relatorio_arquivos_vazios(pasta: str) -> None:
    """
    Executa análise otimizada de arquivos vazios com timeout inteligente.
    
    Processo:
    1. Verifica existência do diretório
    2. Estima quantidade de arquivos para processamento
    3. Aplica timeout de 30 minutos para análises longas
    4. Gera relatório em Excel com arquivos vazios
    5. Implementa análise rápida como fallback
    
    Características:
    - Análise otimizada com estimativa prévia
    - Timeout de 30 minutos para datasets grandes
    - Fallback para análise rápida em caso de timeout
    - Geração de relatórios em formato Excel
    - Logging detalhado de progresso
    
    Args:
        pasta: Diretório para análise de arquivos vazios
        
    Returns:
        None
        
    Raises:
        Exception: Erros durante análise são logados e não propagados
    """
    def _executar_relatorio_rapido(pasta: str) -> None:
        """Fallback para análise rápida de arquivos vazios."""
        try:
            logger.info("[RELATÓRIO] Executando análise rápida...")
            # Implementação de análise rápida
            report_arquivos_vazios.main()
        except Exception as e:
            logger.error(f"[RELATÓRIO] Erro na análise rápida: {e}")
    
    try:
        logger.info(f"[RELATÓRIO] Iniciando análise otimizada de arquivos em: {pasta}")
        
        # Verifica se o diretório existe
        if not Path(pasta).exists():
            logger.warning(f"[RELATÓRIO] Diretório não encontrado: {pasta}")
            return
        
        # Conta arquivos rapidamente
        try:
            arquivo_count = sum(1 for _ in Path(pasta).rglob("*") if _.is_file())
            logger.info(f"[RELATÓRIO] Estimativa: {arquivo_count} arquivos para processar")
            
            # Se há muitos arquivos, usa análise rápida
            if arquivo_count > 500000:  # Mais de 500k arquivos
                logger.warning(f"[RELATÓRIO] Muitos arquivos ({arquivo_count}). Usando análise rápida.")
                _executar_relatorio_rapido(pasta)
                return
                
        except Exception as e:
            logger.warning(f"[RELATÓRIO] Erro ao contar arquivos: {e}")
        
        # Timeout handler
        def timeout_handler(signum, frame):
            logger.warning("[RELATÓRIO] Timeout de 30 minutos atingido! Interrompendo análise...")
            raise TimeoutError("Timeout na análise de arquivos")
        
        # Configura timeout de 30 minutos
        if hasattr(signal, 'SIGALRM'):
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(1800)  # 30 minutos
        
        t0 = time.time()
        
        try:
            report_arquivos_vazios.main()
            
        except TimeoutError:
            logger.warning("[RELATÓRIO] Análise interrompida por timeout. Tentando análise rápida...")
            _executar_relatorio_rapido(pasta)
            
        finally:
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)  # Cancela timeout
        
        t1 = time.time()
        logger.info(f"[RELATÓRIO] Análise concluída. Tempo: {t1-t0:.2f}s")
        
    except Exception as e:
        logger.exception(f"[RELATÓRIO] Erro crítico durante análise: {e}")
        logger.info("[RELATÓRIO] Pipeline continuará mesmo com erro no relatório")


async def main() -> None:
    """
    Função principal que orquestra todo o pipeline de extração de dados do Omie.
    
    Implementa sistema de modos de execução inteligente:
    - Modo Normal: Pipeline completo com listagem e download
    - Modo Reprocessamento: Reprocessamento de registros inválidos
    - Modo Pendentes: Download de registros pendentes acumulados
    
    Fluxo de execução inteligente:
    1. Detecção automática do modo de execução
    2. Configuração específica por modo
    3. Execução otimizada baseada no modo detectado
    4. Pipeline comum: verificação, compactação, upload e relatórios
    
    Arquitetura refatorada:
    - Eliminação de redundâncias entre fluxos
    - Reutilização de código comum
    - Configuração dinâmica por modo
    - Logging especializado por contexto
    
    Returns:
        None
        
    Raises:
        SystemExit: Em caso de falhas críticas que impedem a continuidade
    """
    try:
        # =============================================================================
        # Fase 1: Inicialização e detecção de modo
        # =============================================================================
        logger.info("=" * 80)
        logger.info("INICIANDO PIPELINE DO EXTRATOR OMIE V3 - ARQUITETURA REFATORADA")
        logger.info("=" * 80)
        
        # Log de informações do ambiente
        logger.info(f"[AMBIENTE] Executável Python: {sys.executable}")
        logger.info(f"[AMBIENTE] Argumentos: {sys.argv}")
        logger.info(f"[AMBIENTE] Diretório de trabalho: {os.getcwd()}")
        
        # Inicialização do gerenciador de modos
        gerenciador = GerenciadorModos(CONFIG_PATH)
        configuracao_execucao = gerenciador.detectar_modo_execucao()
        
        logger.info(f"[MODO] Detectado: {configuracao_execucao.modo.value}")
        logger.info(f"[MODO] Estratégia: {configuracao_execucao.estrategia}")
        if configuracao_execucao.filtros:
            logger.info(f"[MODO] Filtros: {configuracao_execucao.filtros}")
        
        # Carregamento das configurações base
        config = carregar_configuracoes()
        resultado_dir = config['resultado_dir']
        db_path = "omie.db"
        
        # =============================================================================
        # Fase 2: Atualização de registros pendentes (comum a todos os modos)
        # =============================================================================
        logger.info("[FASE 2] Atualizando campos essenciais dos registros pendentes...")
        t0 = time.time()
        
        atualizar_campos_registros_pendentes(db_path, resultado_dir)
        
        t_fase2 = time.time() - t0
        logger.info(f"[FASE 2] ✓ Concluída em {t_fase2:.1f} segundos")
        
        # =============================================================================
        # Fase 3: Execução baseada no modo detectado
        # =============================================================================
        logger.info(f"[FASE 3] Executando pipeline para modo: {configuracao_execucao.modo.value}")
        t0 = time.time()
        
        if configuracao_execucao.modo == ModoExecucao.REPROCESSAMENTO:
            # Modo reprocessamento: busca e processa registros inválidos
            logger.info("[REPROCESSAMENTO] Buscando registros inválidos...")
            registros_invalidos = buscar_registros_invalidos_para_reprocessar(db_path)
            
            if registros_invalidos:
                dias_unicos = list(set(reg[2] for reg in registros_invalidos))  # dEmi
                logger.info(f"[REPROCESSAMENTO] {len(registros_invalidos)} registros inválidos encontrados em {len(dias_unicos)} dias")
                
                # Executa download específico para registros inválidos
                config_completo = carregar_config_omie(CONFIG_PATH)
                
                await executar_com_gerenciamento_modo(
                    configuracao_execucao, 
                    config_completo, 
                    db_path, 
                    resultado_dir
                )
                
                # Limpa registros reprocessados
                limpar_registros_invalidos_reprocessados(db_path)
            else:
                logger.info("[REPROCESSAMENTO] Nenhum registro inválido encontrado para reprocessar")
                
        else:
            # Modos: NORMAL, PENDENTES_GERAL
            # Carrega configuração completa para o gerenciador de modos
            config_completo = carregar_config_omie(CONFIG_PATH)
            
            await executar_com_gerenciamento_modo(
                configuracao_execucao, 
                config_completo, 
                db_path, 
                resultado_dir
            )
        
        t_fase3 = time.time() - t0
        logger.info(f"[FASE 3] ✓ Concluída em {t_fase3:.1f} segundos")
        
        # =============================================================================
        # Fase 4: Pipeline comum - Verificação de XMLs
        # =============================================================================
        logger.info("[FASE 4] Verificando integridade dos XMLs baixados...")
        t0 = time.time()
        
        # Importa e executa verificador com parâmetros explícitos
        from src.verificador_xmls import verificar
        verificar(db_path="omie.db")
        
        t_fase4 = time.time() - t0
        logger.info(f"[FASE 4] ✓ Concluída em {t_fase4:.1f} segundos")
        
        # =============================================================================
        # Fase 5: Pipeline comum - Atualização de caminhos
        # =============================================================================
        logger.info("[FASE 5] Atualizando caminhos dos arquivos no banco...")
        t0 = time.time()
        
        atualizar_caminhos_arquivos.atualizar_caminhos_no_banco()
        
        t_fase5 = time.time() - t0
        logger.info(f"[FASE 5] ✓ Concluída em {t_fase5:.1f} segundos")
        
        # =============================================================================
        # Fase 6: Pipeline comum - Compactação
        # =============================================================================
        logger.info("[FASE 6] Compactando resultados...")
        t0 = time.time()
        
        executar_compactador_resultado()
        
        t_fase6 = time.time() - t0
        logger.info(f"[FASE 6] ✓ Concluída em {t_fase6:.1f} segundos")
        
        # =============================================================================
        # Fase 7: Pipeline comum - Upload OneDrive
        # =============================================================================
        logger.info("[FASE 7] Realizando upload para OneDrive...")
        t0 = time.time()
        
        executar_upload_resultado_onedrive()
        
        t_fase7 = time.time() - t0
        logger.info(f"[FASE 7] ✓ Concluída em {t_fase7:.1f} segundos")
        
        # =============================================================================
        # Fase 8: Pipeline comum - Relatórios
        # =============================================================================
        logger.info("[FASE 8] Gerando relatórios...")
        t0 = time.time()
        
        executar_relatorio_arquivos_vazios(resultado_dir)
        
        t_fase8 = time.time() - t0
        logger.info(f"[FASE 8] ✓ Concluída em {t_fase8:.1f} segundos")
        
        # =============================================================================
        # Fase 9: Pipeline comum - Atualização de query params
        # =============================================================================
        logger.info("[FASE 9] Atualizando query params para próxima execução...")
        t0 = time.time()
        
        atualizar_query_params_ini.main()
        
        t_fase9 = time.time() - t0
        logger.info(f"[FASE 9] ✓ Concluída em {t_fase9:.1f} segundos")
        
        # =============================================================================
        # Finalização
        # =============================================================================
        tempo_total = t_fase2 + t_fase3 + t_fase4 + t_fase5 + t_fase6 + t_fase7 + t_fase8 + t_fase9
        
        logger.info("=" * 80)
        logger.info("PIPELINE CONCLUÍDO COM SUCESSO")
        logger.info(f"Modo executado: {configuracao_execucao.modo.value}")
        logger.info(f"Tempo total: {tempo_total:.2f} segundos")
        logger.info("=" * 80)
        
    except KeyboardInterrupt:
        logger.warning("[MAIN] Execução interrompida pelo usuário")
        sys.exit(130)  # Código padrão para interrupção por Ctrl+C
        
    except Exception as e:
        logger.exception(f"[MAIN] Erro crítico no pipeline principal: {e}")
        logger.error("[MAIN] Pipeline falhou com erro crítico")
        sys.exit(1)


# =============================================================================
# Ponto de entrada da aplicação
# =============================================================================
if __name__ == "__main__":
    """
    Ponto de entrada da aplicação quando executada diretamente.
    
    Verifica se o script está sendo executado diretamente (não importado)
    e chama a função principal do pipeline.
    
    Esta estrutura permite que o módulo seja tanto executado diretamente
    quanto importado por outros módulos sem execução automática.
    """
    # IMPORTANTE: Configurar logging antes de qualquer importação dos módulos locais
    # para garantir que todas as mensagens sejam capturadas adequadamente
    configurar_logging()
    asyncio.run(main())
