
# Refatoracoo: uso de funcões utilitarias centralizadas do utils.py
import logging
import sqlite3
import time
import sys
from pathlib import Path
import asyncio
import aiosqlite

# Adiciona o diretório atual ao path para importar utils
sys.path.insert(0, str(Path(__file__).parent))

from pathlib import Path
from utils import conexao_otimizada
from utils import listar_xmls_hibrido
from utils import normalizar_data
from utils import CAMPOS_ESSENCIAIS
from typing import List, Dict

logger = logging.getLogger(__name__)
TABLE_NAME = 'notas'

def carregar_resultado_dir(config_path: str = 'configuracao.ini') -> Path:
    from configparser import ConfigParser
    config = ConfigParser()
    
    # Se o arquivo está no src, procura na raiz do projeto
    config_file = Path(__file__).parent.parent / config_path
    if not config_file.exists():
        config_file = Path(config_path)
    
    config.read(str(config_file))
    resultado_dir = Path(config.get('paths', 'resultado_dir', fallback='resultado'))
    
    # Se não é absoluto, faz relativo à raiz do projeto
    if not resultado_dir.is_absolute():
        projeto_root = Path(__file__).parent.parent
        resultado_dir = projeto_root / resultado_dir
        
    return resultado_dir

from concurrent.futures import ThreadPoolExecutor, as_completed

def listar_arquivos_xml_multithreading(root: Path, max_workers: int = 5) -> list[Path]:
    """
    Busca recursiva eficiente de arquivos XML usando os.scandir e multithreading.
    Percorre toda a árvore a partir de root, retornando todos os arquivos .xml encontrados.
    """
    arquivos_xml = []
    stack = [root]

    def _scan_dir(pasta: Path):
        encontrados = []
        try:
            for entry in pasta.iterdir():
                if entry.is_dir():
                    encontrados.append(entry)
                elif entry.is_file() and entry.name.lower().endswith('.xml'):
                    arquivos_xml.append(entry)
        except Exception as e:
            logger.warning(f"[LISTAR_XMLS] Erro ao acessar {pasta}: {e}")
        return encontrados

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        while stack:
            # Processa até 32 subpastas por vez para evitar sobrecarga
            batch = stack[:32]
            stack = stack[32:]
            futures = [executor.submit(_scan_dir, p) for p in batch]
            for f in as_completed(futures):
                novas = f.result()
                stack.extend(novas)
    logger.info(f"[LISTAR_XMLS] {len(arquivos_xml):,} arquivos XML encontrados em {root}")
    return arquivos_xml

def atualizar_caminhos_no_banco(db_path: str = 'omie.db', max_workers: int = 4) -> None:
    """
    Atualiza o banco SQLite com os caminhos dos arquivos XML, marcando se foram baixados e se estão vazios.
    
    OTIMIZAÇÕES IMPLEMENTADAS:
    - PRAGMA otimizados para máxima performance
    - Usa views e índices otimizados existentes
    - Busca apenas registros pendentes usando view otimizada
    - Processamento em lotes para melhor throughput
    - Detecção inteligente de arquivos vazios
    """
    import time
    
    logger.info("[ATUALIZADOR.CAMINHOS] Iniciando atualizador otimizado de caminhos")
    t_inicio = time.time()
    
    resultado_dir = carregar_resultado_dir()
    
    # =============================================================================
    # FASE 1: Verificação inicial otimizada usando views
    # =============================================================================
    try:
        logger.info("[FASE 1] Verificação inicial otimizada usando views")
        with sqlite3.connect(db_path) as conn:
            # PRAGMA otimizados para máxima performance
            _aplicar_pragmas_otimizados(conn)
            
            cursor = conn.cursor()
            
            # Usa view otimizada para contar pendentes
            cursor.execute("SELECT COUNT(*) FROM vw_notas_pendentes")
            total_pendentes = cursor.fetchone()[0]
            logger.info(f"[ATUALIZADOR.CAMINHOS.VIEW] {total_pendentes:,} registros pendentes (via view otimizada)")

            # Comentado temporariamente para forçar execução
            if total_pendentes == 0:
                logger.info("[ATUALIZADOR.CAMINHOS] Todos os registros já têm caminhos atualizados")
                return
                
    except Exception as e:
        logger.warning(f"[ATUALIZADOR.CAMINHOS.VIEW] View não disponível, usando consulta tradicional: ")
        logger.exception(e)
        # Fallback para consulta tradicional
        with conexao_otimizada(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
            total_pendentes = cursor.fetchone()[0]


    # =============================================================================
    # FASE 2: Descoberta de arquivos XML otimizada
    # =============================================================================
    logger.info("[FASE 2] Descoberta de arquivos XML otimizada")
    logger.info("[ATUALIZADOR.CAMINHOS.DESCOBERTA] Descobrindo arquivos XML")
    
    # Busca recursiva eficiente usando os.scandir + multithreading
    arquivos_xml = []
    if resultado_dir.exists():
        logger.info(f"[ATUALIZADOR.CAMINHOS.DESCOBERTA] Iniciando busca otimizada de XMLs com os.scandir + ThreadPoolExecutor...")
        t0 = time.perf_counter()
        arquivos_xml = listar_xmls_hibrido(resultado_dir, max_workers=5)
        t1 = time.perf_counter()
        logger.info(f"[ATUALIZADOR.CAMINHOS.DESCOBERTA] {len(arquivos_xml):,} arquivos XML encontrados em {t1-t0:.2f}s (busca paralela)")
    else:
        logger.warning(f"[ATUALIZADOR.CAMINHOS.DESCOBERTA] Pasta resultado não existe: {resultado_dir}")

    todos_arquivos = list(arquivos_xml)
    logger.info(f"[ATUALIZADOR.CAMINHOS.DESCOBERTA] Total: {len(todos_arquivos):,} arquivos para processamento")

    if len(todos_arquivos) == 0:
        logger.warning("[ATUALIZADOR.CAMINHOS.DESCOBERTA] Nenhum arquivo XML encontrado")
        return

    # =============================================================================
    # FASE 3: Mapeamento otimizado chave -> arquivo
    # =============================================================================
    logger.info("[FASE 3] Mapeamento otimizado chave -> arquivo")
    logger.info("[ATUALIZADOR.CAMINHOS.MAPEAMENTO] Criando mapeamento chave -> arquivo")
    
    def processar_arquivo(path):
        try:
            chave = extrair_chave_do_nome(path.name)
            if not chave:
                return None
            caminho_arquivo = str(path.resolve())
            xml_vazio = _verificar_arquivo_vazio(path)
            return (chave, {
                'caminho': caminho_arquivo,
                'xml_baixado': 1,
                'xml_vazio': xml_vazio
            }, xml_vazio)
        except Exception as e:
            logger.warning(f"[ATUALIZADOR.CAMINHOS.MAPEAMENTO] Erro ao processar {path}: {e}")
            return None

    mapeamento_chaves = {}
    arquivos_vazios_detectados = 0
    arquivos_processados = 0
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(processar_arquivo, path) for path in todos_arquivos]
        for f in as_completed(futures):
            result = f.result()
            if result:
                chave, dados, xml_vazio = result
                mapeamento_chaves[chave] = dados
                arquivos_processados += 1
                if xml_vazio:
                    arquivos_vazios_detectados += 1
                if arquivos_processados % 20000 == 0:
                    logger.info(f"[ATUALIZADOR.CAMINHOS.MAPEAMENTO] {arquivos_processados:,} arquivos processados...")
    t1 = time.perf_counter()
    logger.info(f"[ATUALIZADOR.CAMINHOS.MAPEAMENTO] {arquivos_processados:,} arquivos mapeados em {t1-t0:.2f}s (paralelo)")
    if arquivos_vazios_detectados > 0:
        logger.warning(f"[ATUALIZADOR.CAMINHOS.MAPEAMENTO] {arquivos_vazios_detectados} arquivos vazios detectados")
    
    # =============================================================================
    # FASE 4: Atualização em lotes otimizada
    # =============================================================================
    logger.info("[FASE 4] Atualização em lotes otimizada")
    if mapeamento_chaves:
        logger.info("[ATUALIZADOR.CAMINHOS.ATUALIZACAO] Atualizando banco em lotes otimizados")
        _atualizar_banco_otimizado(db_path, mapeamento_chaves)
    else:
        logger.info("[ATUALIZADOR.CAMINHOS.ATUALIZACAO] Nenhum arquivo correspondeu a registros no banco")
    
    # =============================================================================
    # FASE 5: Relatório final usando views otimizadas
    # =============================================================================
    logger.info("[FASE 5] Relatório final usando views otimizadas")
    t_total = time.time() - t_inicio
    _gerar_relatorio_final(db_path, t_total)


def _aplicar_pragmas_otimizados(conn: sqlite3.Connection) -> None:
    """Aplica PRAGMAs otimizados para máxima performance na atualização."""
    pragmas = {
        "journal_mode": "WAL",           # Write-Ahead Logging para concorrência
        "synchronous": "NORMAL",         # Balance performance/segurança  
        "temp_store": "MEMORY",          # Operações temporárias em RAM
        "cache_size": "-128000",         # 128MB de cache (2x maior)
        "mmap_size": "536870912",        # 512MB memory-mapped (2x maior)
        "page_size": "32768",            # Page size otimizado (32KB)
        "auto_vacuum": "INCREMENTAL",    # Vacuum automático incremental
        "optimize": "",                  # Otimiza estatísticas do query planner
    }
    
    for pragma, valor in pragmas.items():
        try:
            if valor:
                conn.execute(f"PRAGMA {pragma}={valor}")
            else:
                conn.execute(f"PRAGMA {pragma}")
        except sqlite3.Error as e:
            logger.debug(f"[ATUALIZADOR.PRAGMA] Aviso: {pragma} = {e}")


def _verificar_arquivo_vazio(path: Path) -> int:
    """
    Verificação inteligente e rápida de arquivo vazio.
    
    Returns:
        1 se arquivo vazio, 0 se válido
    """
    try:
        # Verificação rápida por tamanho
        if path.stat().st_size == 0:
            return 1
        
        # Verificação rápida do início do arquivo
        with path.open('rb') as f:
            chunk = f.read(1024)  # Lê apenas 1KB
            if not chunk.strip():
                return 1
            
            # Verifica se parece XML válido
            if b'<?xml' in chunk or b'<nfeProc' in chunk:
                return 0
            else:
                return 1
                
    except Exception as e:
        logger.debug(f"[ATUALIZADOR.ARQUIVO.VAZIO] Erro ao verificar {path}: {e}")
        return 0  # Assume válido em caso de erro


def _atualizar_banco_otimizado(db_path: str, mapeamento_chaves: Dict) -> None:
    """Atualização otimizada em lotes usando índices."""
    
    # Prepara dados em lotes
    LOTE_SIZE = 50000
    chaves = list(mapeamento_chaves.keys())
    total_chaves = len(chaves)
    atualizados = 0
    
    logger.info(f"[ATUALIZADOR.BANCO] Processando {total_chaves:,} atualizações em lotes de {LOTE_SIZE}")
    
    try:
        with sqlite3.connect(db_path) as conn:
            _aplicar_pragmas_otimizados(conn)
            
            # Garante que índices otimizados existem
            # _criar_indices_otimizados(conn)
            
            cursor = conn.cursor()
            
            # Processa em lotes
            for i in range(0, total_chaves, LOTE_SIZE):
                lote_chaves = chaves[i:i + LOTE_SIZE]
                lote_dados = []
                
                for chave in lote_chaves:
                    info = mapeamento_chaves[chave]
                    lote_dados.append((
                        info['caminho'],
                        info['xml_baixado'],
                        info['xml_vazio'],
                        chave
                    ))
                
                # Executa atualização em lote
                cursor.executemany(f'''
                    UPDATE {TABLE_NAME}
                    SET caminho_arquivo = ?,
                        xml_baixado = ?,
                        xml_vazio = ?
                    WHERE cChaveNFe = ?
                ''', lote_dados)
                
                atualizados += cursor.rowcount

                if (i // LOTE_SIZE + 1) % 1 == 0:  # Log a cada 1 lote
                    logger.debug(f"[ATUALIZADOR.BANCO.LOTE] Processados {i + len(lote_chaves):,}/{total_chaves:,} registros")
            
            conn.commit()
            logger.info(f"[ATUALIZADOR.BANCO] {atualizados:,} registros atualizados com sucesso")
            
    except Exception as e:
        logger.error(f"[ATUALIZADOR.BANCO] Erro durante atualização: {e}")
        raise


def _criar_indices_otimizados(conn: sqlite3.Connection) -> None:
    """Cria índices otimizados se não existirem."""
    indices = [
        "CREATE INDEX IF NOT EXISTS idx_chave_nfe_otim ON notas(cChaveNFe)",
        "CREATE INDEX IF NOT EXISTS idx_xml_baixado_otim ON notas(xml_baixado)",
        "CREATE INDEX IF NOT EXISTS idx_caminho_arquivo ON notas(caminho_arquivo)",
        "CREATE INDEX IF NOT EXISTS idx_xml_vazio ON notas(xml_vazio)",
        # Índice composto para queries de status
        "CREATE INDEX IF NOT EXISTS idx_status_completo ON notas(xml_baixado, xml_vazio, erro)"
    ]
    
    for sql in indices:
        try:
            conn.execute(sql)
        except sqlite3.Error as e:
            logger.debug(f"[ATUALIZADOR.BANCO.INDICE] {e}")


def _gerar_relatorio_final(db_path: str, tempo_execucao: float) -> None:
    """Gera relatório final usando views otimizadas."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            logger.info("==========================================================================")
            logger.info("[ATUALIZADOR.RELATORIO] Estatísticas finais:")
            
            # Usa views otimizadas se disponíveis
            try:
                cursor.execute("SELECT COUNT(*) FROM vw_notas_pendentes")
                pendentes = cursor.fetchone()[0]
                logger.info(f"[ATUALIZADOR.RELATORIO.PENDENTES] Registros pendentes: {pendentes:,}")

                cursor.execute("SELECT COUNT(*) FROM notas")
                total = cursor.fetchone()
                if total:
                    logger.info(f"[ATUALIZADOR.RELATORIO.TOTAL] Total de notas: {total:,}")
                logger.info("==========================================================================")
                
            except sqlite3.Error:
                # Fallback para consultas tradicionais
                cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 1")
                baixados = cursor.fetchone()[0]
                logger.info(f"[ATUALIZADOR.RELATORIO.BAIXADOS] XMLs baixados: {baixados:,}")
                
                cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_vazio = 1")
                vazios = cursor.fetchone()[0]
                if vazios > 0:
                    logger.warning(f"[ATUALIZADOR.RELATORIO.VAZIOS] XMLs vazios: {vazios:,}")
                
                cursor.execute("SELECT COUNT(*) FROM notas WHERE caminho_arquivo IS NOT NULL")
                com_caminho = cursor.fetchone()[0]
                logger.info(f"[ATUALIZADOR.RELATORIO.CAMINHOS] Com caminho: {com_caminho:,}")
            
            logger.info(f"[ATUALIZADOR.RELATORIO.TEMPO] Tempo execução: {tempo_execucao:.2f}s")
            logger.info("[ATUALIZADOR.CAMINHOS] Atualização concluída com sucesso")
            
    except Exception as e:
        logger.warning(f"[ATUALIZADOR.RELATORIO] Erro ao gerar relatório: {e}")


def extrair_chave_do_nome(nome_arquivo: str) -> str:
    """
    Extrai a chave NFe do nome do arquivo.
    
    Suporta os formatos:
    - NFe_2024_35241234567890001234550010000012345123456789.xml (formato antigo)
    - 00294964_20250328_35250359279145000116550010002949641491012818.xml (formato atual)
    
    Args:
        nome_arquivo: Nome do arquivo
        
    Returns:
        Chave NFe extraída ou string vazia se não encontrar
    """
    # Remove extensão
    nome_sem_ext = nome_arquivo.replace('.xml', '').replace('.XML', '')
    
    # Formato atual: 00294964_20250328_35250359279145000116550010002949641491012818
    if '_' in nome_sem_ext:
        partes = nome_sem_ext.split('_')
        
        # Formato antigo: NFe_2024_chave
        if len(partes) >= 3 and partes[0].startswith('NFe'):
            return partes[2]
        
        # Formato atual: numero_data_chave
        elif len(partes) >= 3:
            chave_candidata = partes[2]
            # Verifica se tem 44 dígitos (tamanho padrão da chave NFe)
            if len(chave_candidata) == 44 and chave_candidata.isdigit():
                return chave_candidata
    
    # Se não tem underscore, pode ser só a chave
    if len(nome_sem_ext) == 44 and nome_sem_ext.isdigit():
        return nome_sem_ext
        
    return ""

if __name__ == "__main__":
    
    """  Executa o script principal para atualizar caminhos dos XMLs no banco SQLite e marcado como baixados. 
        - Atualiza o campo xml_baixado = 1 para todas as cChaveNFes com arquivos confirmados no disco.
        - Atualiza campo caminho do arquivo para o caminho correto no banco de dados.
        - Usar no começo do pipeline para corrigir pós compactação de arquivos   
    """
    
    
    # Configura logging para ver a execução
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('atualizar_caminhos.log')
        ]
    )
    
    import argparse
    parser = argparse.ArgumentParser(description="Atualiza caminhos dos XMLs no banco SQLite.")
    parser.add_argument(
        "--db", 
        default="omie.db",
        help="Caminho para o arquivo .db (padroo: omie.db)"
    )
    args = parser.parse_args()
    atualizar_caminhos_no_banco(db_path=args.db)
