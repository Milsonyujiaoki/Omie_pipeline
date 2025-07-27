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
from pathlib import Path

# Adiciona o diretório atual ao path para importar utils
sys.path.insert(0, str(Path(__file__).parent))

from utils import gerar_xml_path, gerar_xml_path_otimizado  # Utilitario centralizado

# ------------------------------------------------------------------------------
# Configuracões globais
# ------------------------------------------------------------------------------

DB_PATH = "omie.db"  # Caminho do banco na raiz do projeto
TABLE_NAME = "notas"
MAX_WORKERS = os.cpu_count() or 4
USE_OPTIMIZED_VERSION = True  # Flag para usar versão otimizada

logger = logging.getLogger(__name__)

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
        # Usa versão otimizada ou original baseado na configuração global
        if USE_OPTIMIZED_VERSION:
            _, caminho = gerar_xml_path_otimizado(chave, dEmi, num_nfe)
        else:
            _, caminho = gerar_xml_path_otimizado(chave, dEmi, num_nfe)
            
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
    logger.info(f"[DISCO] Total de notasno banco: {total}")

    chaves_validas: list[str] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futuros = {executor.submit(verificar_arquivo_no_disco, row): row for row in rows}
        for idx, futuro in enumerate(as_completed(futuros), 1):
            try:
                chave = futuro.result()
                if chave:
                    chaves_validas.append(chave)
                if idx % batch_size == 0 or idx == total:
                    logger.info(f"[PROGRESSO] Verificados {idx}/{total} arquivos. Validos ate agora: {len(chaves_validas)}")
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
    logger.info(f"[BANCO] Iniciando atualizacao de {total} registros em lotes de {batch_size}...")
    try:
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
            logger.info(f"[BANCO] Atualizados {min(i+batch_size, total)}/{total} registros.")
        logger.info(f"[BANCO] {total} registros atualizados com sucesso.")
    except Exception as e:
        logger.exception(f"[BANCO] Falha ao atualizar registros: {e}")



def verificar(
    db_path: str = DB_PATH,
    max_workers: int = MAX_WORKERS,
    batch_size: int = 500
) -> None:
    """
    Orquestra a verificacao de XMLs e atualizacao do banco.
    Etapas:
        - Busca registros noo baixados
        - Verifica existência dos XMLs no disco
        - Atualiza status xml_baixado = 1 no banco

    Args:
        db_path: Caminho do banco SQLite.
        max_workers: Numero de threads para paralelismo.
        batch_size: Tamanho do lote para logs e atualizacao.

    Raises:
        Exception: Se ocorrer erro inesperado durante o processo.
    """
    logger.info("[verificacao] Iniciando verificacao de XMLs no disco...")
    chaves_com_arquivo = verificar_arquivos_existentes(db_path=db_path, max_workers=max_workers, batch_size=batch_size)
    atualizar_status_no_banco(chaves_com_arquivo, db_path=db_path, batch_size=batch_size)
    logger.info("[verificacao] Processo de verificacao finalizado.")

# ------------------------------------------------------------------------------
# execucao direta (modo script)
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    # Configura logging para ver a execução
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('verificador_xmls.log')
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
