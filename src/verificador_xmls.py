"""
verificador_xmls.py

Finalidade:
    Verificar quais arquivos XML de notas fiscais ja estoo presentes no disco e
    atualizar o banco de dados marcando-os como baixados.

Requisitos:
    - Python 3.9+
    - Modulos: os, sqlite3, logging, pathlib, concurrent.futures

Autor:
    Equipe de Integracoo Omie - CorpServices
"""

import os
import sqlite3
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys

# Adiciona o diretório atual ao path para importar utils
sys.path.insert(0, str(Path(__file__).parent))

from utils import gerar_xml_path_otimizado, gerar_pasta_xml_path  # Utilitario centralizado

# ------------------------------------------------------------------------------
# Configuracões globais
# ------------------------------------------------------------------------------

DB_PATH = "omie.db"  # Caminho do banco na raiz do projeto
TABLE_NAME = "notas"
MAX_WORKERS = os.cpu_count() or 4
USE_OPTIMIZED_VERSION = True  # Flag para usar versão otimizada com cache

logger = logging.getLogger(__name__)

# Log da configuração na inicialização do módulo
if logger.isEnabledFor(logging.DEBUG):
    logger.debug(f"[INIT] Módulo verificador_xmls inicializado")
    logger.debug(f"[INIT] USE_OPTIMIZED_VERSION: {USE_OPTIMIZED_VERSION}")
    logger.debug(f"[INIT] MAX_WORKERS: {MAX_WORKERS}")

# ------------------------------------------------------------------------------
# verificacao de existência de arquivos XML
# ------------------------------------------------------------------------------

def verificar_arquivo_no_disco(row: tuple[str, str, str]) -> str | None:
    """
    Verifica se o XML correspondente à nota existe no disco e possui conteudo valido (> 0 bytes).

    Args:
        row: Tupla contendo (cChaveNFe, dEmi, nNF).

    Returns:
        A chave fiscal (cChaveNFe) se o arquivo for valido, ou None caso contrario.

    Raises:
        Exception: Se ocorrer erro inesperado ao acessar o arquivo.
    """
    chave, dEmi, num_nfe = row

    if not chave or not dEmi or not num_nfe:
        logger.warning(f"[IGNORADO] Campos ausentes para chave: {chave} | {dEmi} | {num_nfe}")
        return None

    try:
        # Usa versão otimizada com cache ou versão original baseado na configuração global
        if USE_OPTIMIZED_VERSION:
            _, caminho = gerar_xml_path_otimizado(chave, dEmi, num_nfe)
        else:
            # Fallback para versão original sem cache (se implementada)
            pasta, caminho = gerar_pasta_xml_path(chave, dEmi, num_nfe)
            
        if caminho.exists() and caminho.stat().st_size > 0:
            return chave
        return None
    except Exception as e:
        logger.warning(f"[ERRO] Falha ao verificar arquivo da chave {chave}: {e}")
        return None

# ------------------------------------------------------------------------------
# Leitura do banco de dados e paralelizacoo da verificacao
# ------------------------------------------------------------------------------

def verificar_arquivos_existentes(
    db_path: str = DB_PATH,
    max_workers: int = MAX_WORKERS,
    batch_size: int = 500
) -> list[str]:
    """
    Carrega todos os registros do banco e verifica quais arquivos XML ja estoo salvos e validos no disco.

    Args:
        db_path: Caminho do banco SQLite.
        max_workers: Numero de threads para paralelismo.
        batch_size: Tamanho do lote para logs de progresso.

    Returns:
        Lista de chaves fiscais (cChaveNFe) com arquivos encontrados.

    Raises:
        Exception: Se ocorrer erro inesperado durante a verificacao.
    """
    versao_funcao = "OTIMIZADA" if USE_OPTIMIZED_VERSION else "ORIGINAL"
    logger.info(f"[DISCO] Iniciando verificacao de arquivos XML no disco... (versão {versao_funcao})")
    logger.info(f"[DISCO] Configuração: workers={max_workers}, batch={batch_size}")

    with sqlite3.connect(db_path) as conn:
        rows: list[tuple[str, str, str]] = conn.execute(
            f"SELECT cChaveNFe, dEmi, nNF FROM {TABLE_NAME}"
        ).fetchall()

    total = len(rows)
    logger.info(f"[DISCO] Total de notas no banco: {total:,}")
    
    # Determina intervalos de log baseados no volume de dados
    if total < 1000:
        progress_interval = 100  # Log a cada 100 verificações
    elif total < 10000:
        progress_interval = 1000  # Log a cada 1.000 verificações
    elif total < 100000:
        progress_interval = 10000  # Log a cada 10.000 verificações
    else:
        progress_interval = 50000  # Log a cada 50.000 verificações (alto volume)
    
    logger.info(f"[DISCO] Configuração de progresso otimizada: intervalo de {progress_interval:,} verificações")

    chaves_validas: list[str] = []
    import time
    inicio_verificacao = time.time()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futuros = {executor.submit(verificar_arquivo_no_disco, row): row for row in rows}
        for idx, futuro in enumerate(as_completed(futuros), 1):
            try:
                chave = futuro.result()
                if chave:
                    chaves_validas.append(chave)
                
                # Log otimizado baseado no intervalo inteligente
                if (idx % progress_interval == 0) or (idx == total):
                    tempo_decorrido = time.time() - inicio_verificacao
                    percentual = (idx / total) * 100
                    velocidade = idx / tempo_decorrido if tempo_decorrido > 0 else 0
                    
                    logger.info(f"[PROGRESSO] ✓ {idx:,}/{total:,} verificados ({percentual:.1f}%) - "
                               f"Válidos: {len(chaves_validas):,} - Velocidade: {velocidade:.0f} verif/s")
            except Exception as e:
                logger.error(f"[DISCO] Erro ao processar verificacao paralela: {e}")

    taxa_sucesso = (len(chaves_validas) / total) * 100 if total > 0 else 0
    logger.info(f"[DISCO] XMLs validos encontrados: {len(chaves_validas)} ({taxa_sucesso:.2f}%)")
    logger.info(f"[DISCO] Função utilizada: {versao_funcao}")
    
    return chaves_validas

# ------------------------------------------------------------------------------
# atualizacao do status xml_baixado no banco
# ------------------------------------------------------------------------------


def atualizar_status_no_banco(
    chaves: list[str],
    db_path: str = DB_PATH,
    batch_size: int = 500
) -> None:
    """
    Atualiza o campo xml_baixado = 1 para todas as chaves com arquivos confirmados no disco.

    Args:
        chaves: Lista de chaves fiscais encontradas no disco.
        db_path: Caminho do banco SQLite.
        batch_size: Tamanho do lote para atualizacao.

    Raises:
        Exception: Se ocorrer erro inesperado durante a atualizacao.
    """
    if not chaves:
        logger.info("[BANCO] Nenhuma chave para atualizar.")
        return

    total = len(chaves)
    logger.info(f"[BANCO] Iniciando atualizacao de {total:,} registros em lotes de {batch_size}...")
    
    # Determina intervalos de log baseados no volume de dados
    if total < 1000:
        log_interval = 100  # Log a cada 100 registros (pequeno volume)
    elif total < 10000:
        log_interval = 1000  # Log a cada 1.000 registros
    elif total < 100000:
        log_interval = 10000  # Log a cada 10.000 registros
    else:
        log_interval = 100000  # Log a cada 100.000 registros (alto volume)

    logger.info(f"[BANCO] Configuração de log otimizada: intervalo de {log_interval:,} registros")
    
    try:
        import time
        inicio_batch = time.time()
        
        for i in range(0, total, batch_size):
            lote = chaves[i:i+batch_size]
            with sqlite3.connect(db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA temp_store=MEMORY")
                conn.executemany(
                    f"UPDATE {TABLE_NAME} SET xml_baixado = 1 WHERE cChaveNFe = ?",
                    [(chave,) for chave in lote]
                )
                conn.commit()
            
            # Log otimizado baseado no intervalo inteligente
            registros_atualizados = min(i + batch_size, total)
            
            # Log apenas nos intervalos definidos ou no final
            if (registros_atualizados % log_interval == 0) or (registros_atualizados == total):
                tempo_decorrido = time.time() - inicio_batch
                percentual = (registros_atualizados / total) * 100
                velocidade = registros_atualizados / tempo_decorrido if tempo_decorrido > 0 else 0
                
                logger.info(f"[BANCO] ✓ {registros_atualizados:,}/{total:,} registros ({percentual:.1f}%) - "
                           f"Velocidade: {velocidade:.0f} reg/s")
        
        tempo_total = time.time() - inicio_batch
        velocidade_final = total / tempo_total if tempo_total > 0 else 0
        
        logger.info(f"[BANCO] ✅ {total:,} registros atualizados com sucesso em {tempo_total:.1f}s "
                   f"(Velocidade média: {velocidade_final:.0f} reg/s)")
                   
    except Exception as e:
        logger.exception(f"[BANCO] Falha ao atualizar registros: {e}")



def verificar(
    db_path: str = DB_PATH,
    max_workers: int = MAX_WORKERS,
    batch_size: int = 500
) -> None:
    """
    Orquestra a verificacao de XMLs e atualizacao do banco.
    
    VERSÃO OTIMIZADA: Utiliza sistema de cache global para melhor performance.
    
    Etapas:
        - Busca registros não baixados
        - Verifica existência dos XMLs no disco (com cache)
        - Atualiza status xml_baixado = 1 no banco
        - Reporta estatísticas de performance

    Args:
        db_path: Caminho do banco SQLite.
        max_workers: Numero de threads para paralelismo.
        batch_size: Tamanho do lote para logs e atualizacao.

    Raises:
        Exception: Se ocorrer erro inesperado durante o processo.
    """
    import time
    from utils import obter_estatisticas_cache, limpar_cache_indexacao_xmls
    
    inicio = time.time()
    logger.info("[VERIFICACAO] Iniciando verificacao de XMLs no disco...")
    logger.info(f"[VERIFICACAO] Configuracao: otimizado={USE_OPTIMIZED_VERSION}, workers={max_workers}")
    
    # Limpa cache anterior se necessário (opcional - apenas para debug)
    if logger.isEnabledFor(logging.DEBUG):
        stats_inicial = obter_estatisticas_cache()
        if stats_inicial['directories_cached'] > 0:
            logger.debug(f"[VERIFICACAO] Cache existente: {stats_inicial}")
    
    # Executa verificação
    chaves_com_arquivo = verificar_arquivos_existentes(db_path=db_path, max_workers=max_workers, batch_size=batch_size)
    atualizar_status_no_banco(chaves_com_arquivo, db_path=db_path, batch_size=batch_size)
    
    # Relatório final com estatísticas de cache
    fim = time.time()
    tempo_total = fim - inicio
    
    logger.info("[VERIFICACAO] Processo de verificacao finalizado.")
    logger.info(f"[VERIFICACAO] Tempo total: {tempo_total:.2f}s")
    
    if USE_OPTIMIZED_VERSION:
        stats_final = obter_estatisticas_cache()
        logger.info(f"[VERIFICACAO] Estatisticas de cache:")
        logger.info(f"[VERIFICACAO]   Diretorios indexados: {stats_final['directories_indexed']}")
        logger.info(f"[VERIFICACAO]   Arquivos em cache: {stats_final['total_files_cached']}")
        logger.info(f"[VERIFICACAO]   Cache hits: {stats_final['cache_hits']}")
        logger.info(f"[VERIFICACAO]   Hit rate: {stats_final['hit_rate_percent']:.1f}%")

# ------------------------------------------------------------------------------
# execucao direta (modo script)
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    # Configura logging para ver a execução
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('log/verificador_xmls.log')
        ]
    )
    
    # Ajusta o caminho do banco conforme o diretório de execução
    import os
    if os.path.basename(os.getcwd()) == 'src':
        # Se executando do diretório src, vai para o nível superior
        db_path = "../omie.db"
    else:
        # Se executando da raiz do projeto
        db_path = "omie.db"
    
    # Verifica se o banco existe
    if not os.path.exists(db_path):
        logger.error(f"[ERRO] Banco de dados não encontrado: {db_path}")
        logger.error(f"[ERRO] Diretório atual: {os.getcwd()}")
        logger.error("[ERRO] Execute o script da raiz do projeto ou verifique o caminho do banco")
        sys.exit(1)
    
    logger.info(f"[CONFIG] Usando banco de dados: {os.path.abspath(db_path)}")
    logger.info(f"[CONFIG] Usando versão {'OTIMIZADA' if USE_OPTIMIZED_VERSION else 'ORIGINAL'} das funções XML")
    
 
    
    # Permite configuracoo via env vars ou argumentos futuros
    verificar(db_path=db_path)
