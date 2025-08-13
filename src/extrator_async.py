# extrator_async.py
# Requer: Python 3.9+
# Dependências: aiohttp, asyncio, html, sqlite3, logging, pathlib, datetime, typing, time, threading

from __future__ import annotations

import os
import sys
import html
import sqlite3
import asyncio
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from threading import Lock
import concurrent.futures
import aiohttp
import aiosqlite
import aiofiles

# Adicionar o diretório raiz ao path para importações
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import (
    atualizar_status_xml,
    iniciar_db,
    salvar_varias_notas,
    gerar_xml_path_otimizado,
    conexao_otimizada,
    gerar_pasta_xml_path,
    normalizar_data,
    respeitar_limite_requisicoes_async,
    log_configuracoes
)
from src.omie_client_async import OmieClient, carregar_configuracoes_client

# Configuração de logging centralizado
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

TABLE_NAME = "notas"

# Carregamento de configurações do arquivo INI
def _carregar_configuracoes_extrator():
    """Carrega configurações específicas do extrator."""
    import configparser
    config = configparser.ConfigParser()
    config_path = Path("configuracao.ini")
    
    if config_path.exists():
        config.read(config_path)
        
        return {
            'calls_per_second': config.getint('concorrencia', 'calls_per_second_global', fallback=4),
            'max_concurrent': config.getint('concorrencia', 'max_concurrent', fallback=4),
            'intervalo_minimo': config.getfloat('concorrencia', 'intervalo_minimo_requisicoes', fallback=0.25),
            'timeout_conexao': config.getint('retry', 'timeout_conexao', fallback=60),
            'max_retries': config.getint('retry', 'max_retries', fallback=3),
            'sqlite_cache_size': config.getint('cache', 'sqlite_cache_size', fallback=-64000),
            'sqlite_mmap_size': config.getint('cache', 'sqlite_mmap_size', fallback=268435456),
        }
    else:
        # Valores padrão se não houver configuração
        return {
            'calls_per_second': 4,
            'max_concurrent': 4,
            'intervalo_minimo': 0.25,
            'timeout_conexao': 60,
            'max_retries': 3,
            'sqlite_cache_size': -64000,
            'sqlite_mmap_size': 268435456,
        }

# Configurações carregadas do arquivo INI
_config_extrator = _carregar_configuracoes_extrator()

# === Controle de limite de requisicões (configurável) ===
ULTIMA_REQUISICAO = 0.0
LOCK = Lock()

# Configurações de otimização SQLite (vindas da configuração)
SQLITE_PRAGMAS: Dict[str, str] = {
    "journal_mode": "WAL",
    "synchronous": "NORMAL",
    "temp_store": "MEMORY",
    "cache_size": str(_config_extrator['sqlite_cache_size']),  # Configurável
    "mmap_size": str(_config_extrator['sqlite_mmap_size'])     # Configurável
}


def respeitar_limite_requisicoes() -> None:
    global ULTIMA_REQUISICAO
    with LOCK:
        agora = time.monotonic()
        tempo_decorrido = agora - ULTIMA_REQUISICAO
        intervalo_minimo = _config_extrator['intervalo_minimo']
        if tempo_decorrido < intervalo_minimo:
            time.sleep(intervalo_minimo - tempo_decorrido)
        ULTIMA_REQUISICAO = time.monotonic()


def normalizar_nota(nf: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return {
            "cChaveNFe": nf["compl"].get("cChaveNFe"),
            "nIdNF": nf["compl"].get("nIdNF"),
            "nIdPedido": nf["compl"].get("nIdPedido"),
            "dCan": nf["ide"].get("dCan"),
            "dEmi": nf["ide"].get("dEmi"),
            "dInut": nf["ide"].get("dInut"),
            "dReg": nf["ide"].get("dReg"),
            "dSaiEnt": nf["ide"].get("dSaiEnt"),
            "hEmi": nf["ide"].get("hEmi"),
            "hSaiEnt": nf["ide"].get("hSaiEnt"),
            "mod": nf["ide"].get("mod"),
            "nNF": nf["ide"].get("nNF"),
            "serie": nf["ide"].get("serie"),
            "tpAmb": nf["ide"].get("tpAmb"),
            "tpNF": nf["ide"].get("tpNF"),
            "cnpj_cpf": nf["nfDestInt"].get("cnpj_cpf"),
            "cRazao": nf["nfDestInt"].get("cRazao"),
            "vNF": float(nf["total"]["ICMSTot"].get("vNF") or 0),
        }
    except Exception as exc:
        logger.warning("[NORMALIZAR] Falha ao normalizar nota: %s", exc)
        return {}


async def call_api(
    client: OmieClient,
    session: aiohttp.ClientSession,
    metodo: str,
    payload: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Função síncrona para chamada de API com retentativas e backoff.
    """
    import time
    max_retentativas = _config_extrator['max_retries']
    for tentativa in range(1, max_retentativas + 1):
        try:
            await respeitar_limite_requisicoes_async()
            return await client.call_api(session, metodo, payload)

        except asyncio.TimeoutError as exc:
            logger.warning("[RETRY] Timeout - Esperando %ss (tentativa %s)", 10 * tentativa, tentativa)
            await asyncio.sleep(5 * tentativa)
        except asyncio.CancelledError as exc:
            logger.warning("[RETRY] CancelledError - Esperando %ss (tentativa %s)", 5 * tentativa, tentativa)
            await asyncio.sleep(5 * tentativa)

        except aiohttp.ClientResponseError as exc:
            if exc.status == 429:
                tempo_espera = 2**tentativa
                logger.warning(
                    "[RETRY] 429 - Esperando %ss (tentativa %s)", tempo_espera, tentativa
                )
                time.sleep(tempo_espera)
            
            if exc.status == 403:
                logger.error("[API] Permissão negada (403 Forbidden): %s", exc)
                raise RuntimeError(
                    "Permissão negada pela API Omie (403 Forbidden). "
                    "Verifique app_key, app_secret, permissões do app e se o endpoint está correto."
                ) from exc    
            
            elif exc.status == 404:
                logger.error("[API] Recurso não encontrado: %s", exc)
                raise
            elif exc.status >= 500:
                tempo_espera = 1 + tentativa
                logger.warning(
                    "[RETRY] %s - Erro servidor. Tentativa %s", exc.status, tentativa
                )
                time.sleep(tempo_espera)
            else:
                logger.error("[API] Falha irreversivel: %s", exc)
                raise

        except Exception as exc:
            logger.error("[API] Erro inesperado: %s", exc)
            raise

    raise RuntimeError(f"[API] Falha apos {max_retentativas} tentativas para {metodo}")


async def atualizar_anomesdia(db_path: str = "omie.db", table_name: str = "notas") -> int:
    """
    Atualiza o campo anomesdia (YYYYMMDD) baseado no campo dEmi, de forma assíncrona.
    Usa aiosqlite para operações não bloqueantes.
    """
    try:
        async with aiosqlite.connect(db_path) as conn:
            # Otimizações de performance
            for pragma, valor in SQLITE_PRAGMAS.items():
                await conn.execute(f"PRAGMA {pragma}={valor}")
            
            cursor = await conn.execute(f"""
                SELECT cChaveNFe, dEmi 
                FROM {table_name} 
                WHERE dEmi IS NOT NULL 
                AND dEmi != '' 
                AND dEmi != '-'
            """)
            registros = await cursor.fetchall()
            await cursor.close()
            
            if not registros:
                logger.info("[ANOMESDIA] Nenhum registro para atualizar")
                return 0
            
            registros_list = list(registros)  # Converte para lista para usar len()
            logger.info(f"[ANOMESDIA] Processando {len(registros_list)} registros...")
            atualizacoes = []
            erros = 0
            for chave, dEmi in registros_list:
                try:
                    data_normalizada = normalizar_data(dEmi)
                    if data_normalizada:
                        # Converte para YYYYMMDD
                        dia, mes, ano = data_normalizada.split('/')
                        anomes = int(f"{ano}{mes}")
                        anomesdia = int(f"{ano}{mes}{dia}")
                        atualizacoes.append((anomesdia, anomes, chave))
                    else:
                        logger.warning(f"[ANOMESDIA] Data inválida para chave {chave}: {dEmi}")
                        erros += 1
                except Exception as e:
                    logger.warning(f"[ANOMESDIA] Erro ao processar {chave}: {e}")
                    erros += 1
            if atualizacoes:
                await conn.executemany(f"""
                    UPDATE {table_name} 
                    SET anomesdia = ?, anomes = ?
                    WHERE cChaveNFe = ?
                """, atualizacoes)
                await conn.commit()
                atualizados = len(atualizacoes)
                logger.info(f"[ANOMESDIA] ✓ {atualizados} registros atualizados")
                if erros > 0:
                    logger.warning(f"[ANOMESDIA] ⚠ {erros} registros com erro")
                return atualizados
            else:
                logger.info("[ANOMESDIA] Nenhuma atualização válida encontrada")
                return 0
    except aiosqlite.Error as e:
        logger.error(f"[ANOMESDIA] Erro de banco: {e}")
        return 0
    except Exception as e:
        logger.error(f"[ANOMESDIA] Erro inesperado: {e}")
        return 0


async def listar_nfs(client: OmieClient, config: Dict[str, Any], db_name: str) -> None:
    logger.info("[EXTRATOR.ASYNC.LISTAR.NFS] Iniciando listagem de notas fiscais...")

    try:
        from src.utils import _verificar_views_e_indices_disponiveis
        db_otimizacoes = _verificar_views_e_indices_disponiveis(db_name)
        usar_views = True
    except ImportError:
        db_otimizacoes = {}
        usar_views = False

    total_registros_salvos = 0

    async def processar_pagina(pagina: int, semaphore: asyncio.Semaphore, session: aiohttp.ClientSession) -> int:
        async with semaphore:
            payload = {
                "pagina": pagina,
                "registros_por_pagina": config.get("records_per_page", 200),
                "apenas_importado_api": "N",
                "dEmiInicial": config.get("start_date", "01/01/2025"),
                "dEmiFinal": config.get("end_date", "31/12/2025"),
                "tpNF": 1,
                "tpAmb": 1,
                "cDetalhesPedido": "N",
                "cApenasResumo": "S",
                "ordenar_por": "CODIGO",
            }
            try:
                data = await client.call_api(session, "ListarNF", payload)
                if data is None:
                    logger.warning("[NFS] Resposta nula da API para página %s", pagina)
                    return 0
                
                notas = data.get("nfCadastro", [])
                if not notas:
                    logger.info("[NFS] Pagina %s sem notas.", pagina)
                    return 0

                loop = asyncio.get_running_loop()
                registros = await loop.run_in_executor(
                    None,
                    lambda: [r for nf in notas if (r := normalizar_nota(nf))]
                )
                resultado_salvamento = await loop.run_in_executor(
                    None,
                    lambda: salvar_varias_notas(registros, db_name)
                )
                total_registros_processados = resultado_salvamento.get('total_processados', len(registros))
                logger.info("[NFS] Pagina %s processada (%s registros).", pagina, total_registros_processados)
                inseridos = resultado_salvamento.get('inseridos', len(registros))
                return inseridos if isinstance(inseridos, int) else len(registros)
            except Exception as exc:
                logger.exception("[NFS] Erro na listagem pagina %s: %s", pagina, exc)
                return 0

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=360)) as session:
        # Descobrir o total de páginas primeiro
        payload_inicial = {
            "pagina": 1,
            "registros_por_pagina": config.get("records_per_page", 200),
            "apenas_importado_api": "N",
            "dEmiInicial": config.get("start_date", "01/01/2025"),
            "dEmiFinal": config.get("end_date", "31/12/2025"),
            "tpNF": 1,
            "tpAmb": 1,
            "cDetalhesPedido": "N",
            "cApenasResumo": "S",
            "ordenar_por": "CODIGO",
        }
        data_inicial = await client.call_api(session, "ListarNF", payload_inicial)
        if data_inicial is None:
            logger.error("[NFS] Falha ao obter informações iniciais da API")
            return
        
        total_paginas = data_inicial.get("total_de_paginas", 1)
        logger.info(f"[NFS] Total de páginas a processar: {total_paginas}")

        semaphore = asyncio.Semaphore(2)  # Limite de 2 requisições concorrentes
        tasks = [processar_pagina(p, semaphore, session) for p in range(1, total_paginas + 1)]
        resultados = await asyncio.gather(*tasks)
        total_registros_salvos = sum(r for r in resultados if isinstance(r, int))

    logger.info(f"[NFS] Listagem concluida. {total_registros_salvos} registros processados.")
    
async def baixar_xml_individual(
    session: aiohttp.ClientSession,
    client: OmieClient,
    row: tuple,
    semaphore: asyncio.Semaphore,
    db_name: str,
):
    async with semaphore:
        # Validação do tamanho da tupla antes do desempacotamento
        if len(row) < 4:
            logger.error(f"[XML] Tupla com dados insuficientes: {row}")
            return
            
        # Adaptação para suportar tanto 4 quanto 5 campos (com anomesdia da consulta otimizada)
        try:
            if len(row) > 4:
                chave, dEmi, num_nfe, nIdNF, anomesdia = row[0], row[1], row[2], row[3], row[4]
            else:
                chave, dEmi, num_nfe, nIdNF = row[0], row[1], row[2], row[3]
                anomesdia = None
        except IndexError as e:
            logger.error(f"[XML] Erro ao desempacotar row {row}: {e}")
            return
            
        try:
            pasta, caminho = gerar_pasta_xml_path(chave, dEmi, num_nfe)
            
            
            pasta.mkdir(parents=True, exist_ok=True)
            baixado_novamente = caminho.exists()

            data = await client.call_api(session, "ObterNfe", {"nIdNfe": nIdNF})
            if data is None:
                logger.warning(f"[XML] Resposta nula da API para chave {chave}")
                return
            
            xml_str = html.unescape(data.get("cXmlNfe", ""))

            if not xml_str.strip():
                logger.warning(f"[XML] XML vazio recebido para chave {chave}. Não será salvo.")
                atualizar_status_xml(db_name, chave, caminho, xml_str, baixado_novamente, xml_vazio=1)
            else:
                async with aiofiles.open(caminho, "w", encoding="utf-8") as f:
                    await f.write(xml_str)
                atualizar_status_xml(db_name, chave, caminho, xml_str, baixado_novamente)
                logger.info("[XML] XML salvo: %s", caminho)
        except Exception as exc:
            logger.error("[XML] Falha ao baixar XML %s: %s", chave, exc)


async def baixar_xmls(client: OmieClient, db_name: str, db_path: str = "omie.db"):
    logger.info("[XML] Iniciando download de XMLs pendentes...")
    
    # Importa função de otimização do utils.py
    try:
        from utils import _verificar_views_e_indices_disponiveis, SQLITE_PRAGMAS
        usar_otimizacoes_avancadas = True
    except ImportError:
        logger.warning("[XML] Funções de otimização não disponíveis, usando método padrão")
        usar_otimizacoes_avancadas = False
        SQLITE_PRAGMAS = {
            "journal_mode": "WAL",
            "synchronous": "NORMAL", 
            "temp_store": "MEMORY"
        }
    
    try:
        with conexao_otimizada(db_path) as conn:
            cursor = conn.execute(""" 
                         SELECT cChaveNFe, dEmi, nNF, nIdNF, anomesdia
                         FROM notas
                         WHERE xml_baixado = 0
                         order by anomesdia DESC                         
                         """)
            rows = cursor.fetchall()
              
    except sqlite3.OperationalError as e:
        logger.error("[XML] Erro ao conectar ao banco de dados: %s", e)
        return
    
    total_pendentes = len(rows)
    logger.info(f"[XML] {total_pendentes} XMLs pendentes encontrados para download")
    
    if not rows:
        logger.info("[XML] Nenhum XML pendente para download")
        return

    semaphore = asyncio.Semaphore(client.semaphore._value)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=360)) as session:
        await asyncio.gather(*[baixar_xml_individual(session, client, row, semaphore, db_name) for row in rows])
    logger.info("[XML] Concluido download de XMLs.")
    
# ---------------------------------------------------------------------------


async def main():
    logger.info("[MAIN] Inicio da execucao assincrona")

    # Criação do diretório
    log_dir = Path("log")
    log_dir.mkdir(exist_ok=True)
    
    # Timestamp único
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / f"extrator_async_{timestamp}.log" 

    # Configuração básica de logging para acompanhar execução
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    # Use explicitamente o carregar_configuracoes do omie_client_async
    config = carregar_configuracoes_client()

    # Log das credenciais para debug
    logger.info(f"[CREDENCIAIS] app_key: {config.get('app_key')}, app_secret: {config.get('app_secret')}")
    if not config.get('app_key') or not config.get('app_secret'):
        logger.error("[CREDENCIAIS] app_key ou app_secret estão vazios! Verifique o arquivo configuracao.ini e a função carregar_configuracoes.")

    db_name = config.get("db_name", "omie.db")

    client = OmieClient(
        app_key=config["app_key"],
        app_secret=config["app_secret"],
        calls_per_second=config["calls_per_second"],
        base_url_nf=config["base_url_nf"],
        base_url_xml=config["base_url_xml"],
    )

    iniciar_db(db_name, TABLE_NAME)
    await listar_nfs(client, config, db_name)
    await atualizar_anomesdia(db_name)
    await baixar_xmls(client, db_name)
    logger.info("[MAIN] Processo finalizado com sucesso")


if __name__ == "__main__":
    asyncio.run(main())
