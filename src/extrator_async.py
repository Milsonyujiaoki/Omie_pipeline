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
            'timeout_conexao': config.getint('retry', 'timeout_conexao', fallback=3600),
            'timeout_total': config.getint('retry', 'timeout_total', fallback=600),
            'max_retries': config.getint('retry', 'max_retries', fallback=5),
            'sqlite_cache_size': config.getint('cache', 'sqlite_cache_size', fallback=-64000),
            'sqlite_mmap_size': config.getint('cache', 'sqlite_mmap_size', fallback=268435456),
        }
    else:
        # Valores padrão se não houver configuração
        return {
            'calls_per_second': 4,
            'max_concurrent': 4,
            'intervalo_minimo': 0.25,
            'timeout_conexao': 3600,
            'timeout_total': 600,
            'max_retries': 5,
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
        logger.warning("[EXTRATOR.ASYNC.NORMALIZAR] Falha ao normalizar nota: %s", exc)
        return {}


async def call_api(
    client: OmieClient,
    session: aiohttp.ClientSession,
    metodo: str,
    payload: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Função assíncrona para chamada de API com retentativas e backoff para TimeoutError.
    """
    max_retentativas = _config_extrator['max_retries']
    for tentativa in range(1, max_retentativas + 1):
        try:
            await respeitar_limite_requisicoes_async()
            return await client.call_api(session, metodo, payload)

        except asyncio.TimeoutError as exc:
            # Tratamento específico para timeout - aumenta o tempo de espera progressivamente
            tempo_espera = min(30 * tentativa, 180)  # Max 3 minutos entre tentativas
            logger.warning("[EXTRATOR.ASYNC.API.RETRY] TimeoutError - Tentativa %d/%d falhou - Esperando %ds...", 
                         tentativa, max_retentativas, tempo_espera)
            if tentativa < max_retentativas:
                await asyncio.sleep(tempo_espera)
                continue
            else:
                logger.error("[EXTRATOR.ASYNC.API.TIMEOUT] Timeout persistente após %d tentativas", max_retentativas)
                raise

        except asyncio.CancelledError as exc:
            tempo_espera = 10 * tentativa
            logger.warning("[EXTRATOR.ASYNC.API.CANCELLED] CancelledError - Esperando %ss (tentativa %s)", tempo_espera, tentativa)
            if tentativa < max_retentativas:
                await asyncio.sleep(tempo_espera)
                continue
            else:
                raise

        except aiohttp.ClientResponseError as exc:
            if exc.status == 429:
                tempo_espera = 2**tentativa
                logger.warning(
                    "[EXTRATOR.ASYNC.API.RATE_LIMIT] 429 Rate Limit - Esperando %ss (tentativa %s)", tempo_espera, tentativa
                )
                await asyncio.sleep(tempo_espera)
            
            elif exc.status == 403:
                logger.error("[EXTRATOR.ASYNC.API.FORBIDDEN] Permissão negada (403 Forbidden): %s", exc)
                raise RuntimeError(
                    "Permissão negada pela API Omie (403 Forbidden). "
                    "Verifique app_key, app_secret, permissões do app e se o endpoint está correto."
                ) from exc    
            
            elif exc.status == 404:
                logger.error("[API] Recurso não encontrado: %s", exc)
                raise
            elif exc.status >= 500:
                tempo_espera = min(30 + (10 * tentativa), 120)  # Max 2 minutos
                logger.warning(
                    "[RETRY] %s - Erro servidor. Tentativa %s/%s - Esperando %ds", 
                    exc.status, tentativa, max_retentativas, tempo_espera
                )
                if tentativa < max_retentativas:
                    await asyncio.sleep(tempo_espera)
                    continue
                else:
                    raise
            else:
                logger.error("[API] Falha irreversivel: %s", exc)
                raise

        except Exception as exc:
            logger.error("[API] Erro inesperado: %s", exc)
            if tentativa < max_retentativas:
                tempo_espera = 2 * tentativa
                logger.warning("[RETRY] Erro inesperado - Tentativa %s/%s - Esperando %ds", 
                             tentativa, max_retentativas, tempo_espera)
                await asyncio.sleep(tempo_espera)
                continue
            else:
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
                logger.info("[EXTRATOR.ASYNC.ANOMESDIA.VAZIO] Nenhum registro para atualizar")
                return 0
            
            registros_list = list(registros)  # Converte para lista para usar len()
            logger.info(f"[EXTRATOR.ASYNC.ANOMESDIA.INICIO] Processando {len(registros_list):,} registros...")
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
                        logger.warning(f"[EXTRATOR.ASYNC.ANOMESDIA.DATA] Data inválida para chave {chave}: {dEmi}")
                        erros += 1
                except Exception as e:
                    logger.warning(f"[EXTRATOR.ASYNC.ANOMESDIA.ERRO] Erro ao processar {chave}: {e}")
                    erros += 1
            if atualizacoes:
                await conn.executemany(f"""
                    UPDATE {table_name} 
                    SET anomesdia = ?, anomes = ?
                    WHERE cChaveNFe = ?
                """, atualizacoes)
                await conn.commit()
                atualizados = len(atualizacoes)
                logger.info(f"[EXTRATOR.ASYNC.ANOMESDIA.SUCESSO] ✓ {atualizados:,} registros atualizados")
                if erros > 0:
                    logger.warning(f"[EXTRATOR.ASYNC.ANOMESDIA.ALERTAS] ⚠ {erros:,} registros com erro")
                return atualizados
            else:
                logger.info("[EXTRATOR.ASYNC.ANOMESDIA.RESULTADO] Nenhuma atualização válida encontrada")
                return 0
    except aiosqlite.Error as e:
        logger.error(f"[EXTRATOR.ASYNC.ANOMESDIA.DB.ERRO] Erro de banco: {e}")
        return 0
    except Exception as e:
        logger.error(f"[EXTRATOR.ASYNC.ANOMESDIA.INESPERADO] Erro inesperado: {e}")
        return 0


async def listar_nfs(client: OmieClient, config: Dict[str, Any], db_name: str) -> None:
    def _formatar_tempo_total(segundos: float) -> str:
        """Converte segundos em formato legível."""
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
    
    logger.info("[EXTRATOR.ASYNC.NFS.INICIO] Iniciando listagem de notas fiscais...")
    
    # Log das configurações de timeout para debug
    logger.info(f"[EXTRATOR.ASYNC.NFS.CONFIG] Timeout configurado: {_config_extrator.get('timeout_total', 600):,}s total")
    logger.info(f"[EXTRATOR.ASYNC.NFS.CONFIG] Max retries: {_config_extrator.get('max_retries', 5)}")
    logger.info(f"[EXTRATOR.ASYNC.NFS.CONFIG] Período: {config.get('start_date')} a {config.get('end_date')}")
    logger.info(f"[EXTRATOR.ASYNC.NFS.CONFIG] Registros por página: {config.get('records_per_page', 200):,}")

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
                data = await call_api(client, session, "ListarNF", payload)
                if data is None:
                    logger.warning("[EXTRATOR.ASYNC.NFS.API] Resposta nula da API para página %s", pagina)
                    return 0
                
                notas = data.get("nfCadastro", [])
                if not notas:
                    logger.warning("[EXTRATOR.ASYNC.NFS.API] Nenhuma nota encontrada para página %s", pagina)
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
                logger.info("[EXTRATOR.ASYNC.NFS.PAGINA] ✓ Página %s processada - %s registros salvos", pagina, total_registros_processados)
                inseridos = resultado_salvamento.get('inseridos', len(registros))
                return inseridos if isinstance(inseridos, int) else len(registros)
            except Exception as exc:
                logger.error("[EXTRATOR.ASYNC.NFS.ERRO] Erro na listagem página %s: %s", pagina, exc)
                return 0

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=600, connect=30, sock_read=300)  # 10 min total, 5 min leitura
    ) as session:
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
        data_inicial = await call_api(client, session, "ListarNF", payload_inicial)
        if data_inicial is None:
            logger.error("[EXTRATOR.ASYNC.NFS.API.ERRO] Falha ao obter informações iniciais da API")
            return
        
        total_paginas = data_inicial.get("total_de_paginas", 1)
        total_registros_esperados = data_inicial.get("total_de_registros", 0)
        logger.info(f"[EXTRATOR.ASYNC.NFS.DESCOBERTA] Total de páginas a processar: {total_paginas:,}")
        logger.info(f"[EXTRATOR.ASYNC.NFS.DESCOBERTA] Total de registros esperados: {total_registros_esperados:,}")

        semaphore = asyncio.Semaphore(4)  # Limite de 4 requisições concorrentes
        logger.info("[EXTRATOR.ASYNC.NFS.PROCESSAMENTO] Iniciando processamento paralelo das páginas...")
        
        inicio_processamento = time.time()
        tasks = [processar_pagina(p, semaphore, session) for p in range(1, total_paginas + 1)]
        resultados = await asyncio.gather(*tasks)
        fim_processamento = time.time()
        
        total_registros_salvos = sum(r for r in resultados if isinstance(r, int))
        tempo_processamento = fim_processamento - inicio_processamento

    logger.info(f"[EXTRATOR.ASYNC.NFS.SUCESSO] ✅ Listagem concluída com sucesso")
    logger.info(f"[EXTRATOR.ASYNC.NFS.RESULTADO] • Total de registros processados: {total_registros_salvos:,}")
    logger.info(f"[EXTRATOR.ASYNC.NFS.TEMPO] • Tempo de processamento: {_formatar_tempo_total(tempo_processamento)} ({tempo_processamento:.2f}s)")
    if tempo_processamento > 0:
        velocidade = total_registros_salvos / tempo_processamento
        logger.info(f"[EXTRATOR.ASYNC.NFS.PERFORMANCE] • Velocidade média: {velocidade:.0f} registros/s")
    
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

            data = await call_api(client, session, "ObterNfe", {"nIdNfe": nIdNF})
            if data is None:
                logger.warning(f"[EXTRATOR.ASYNC.XML.API] Resposta nula da API para chave {chave}")
                return
            
            xml_str = html.unescape(data.get("cXmlNfe", ""))

            if not xml_str.strip():
                logger.warning(f"[EXTRATOR.ASYNC.XML.VAZIO] XML vazio recebido para chave {chave} - não será salvo")
                atualizar_status_xml(db_name, chave, caminho, xml_str, baixado_novamente, xml_vazio=1)
            else:
                async with aiofiles.open(caminho, "w", encoding="utf-8") as f:
                    await f.write(xml_str)
                atualizar_status_xml(db_name, chave, caminho, xml_str, baixado_novamente)
                logger.debug(f"[EXTRATOR.ASYNC.XML.SUCESSO] ✓ XML salvo: {chave}")
                logger.info("[XML] XML salvo: %s", caminho)
        except Exception as exc:
            logger.error("[EXTRATOR.ASYNC.XML.ERRO] Falha ao baixar XML %s: %s", chave, exc)


async def baixar_xmls(client: OmieClient, db_name: str, db_path: str = "omie.db"):
    def _formatar_tempo_total(segundos: float) -> str:
        """Converte segundos em formato legível."""
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
    
    logger.info("[EXTRATOR.ASYNC.XML.INICIO] Iniciando download de XMLs pendentes...")
    
    # Importa função de otimização do utils.py
    try:
        from utils import _verificar_views_e_indices_disponiveis, SQLITE_PRAGMAS
        usar_otimizacoes_avancadas = True
        logger.debug("[EXTRATOR.ASYNC.XML.CONFIG] Usando otimizações avançadas disponíveis")
    except ImportError:
        logger.warning("[EXTRATOR.ASYNC.XML.CONFIG] Funções de otimização não disponíveis - usando método padrão")
        usar_otimizacoes_avancadas = False
        SQLITE_PRAGMAS = {
            "journal_mode": "WAL",
            "synchronous": "NORMAL", 
            "temp_store": "MEMORY"
        }
    
    inicio_download = time.time()
    
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
        logger.error("[EXTRATOR.ASYNC.XML.DB.ERRO] Erro ao conectar ao banco de dados: %s", e)
        return
    
    total_pendentes = len(rows)
    logger.info(f"[EXTRATOR.ASYNC.XML.DESCOBERTA] {total_pendentes:,} XMLs pendentes encontrados para download")
    
    if not rows:
        logger.info("[EXTRATOR.ASYNC.XML.VAZIO] Nenhum XML pendente para download - processo concluído")
        return
        return

    semaphore = asyncio.Semaphore(client.semaphore._value)
    concorrencia = client.semaphore._value
    logger.info(f"[EXTRATOR.ASYNC.XML.CONFIG] Concorrência configurada: {concorrencia} downloads paralelos")
    
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=600, connect=30, sock_read=300)  # 10 min total, 5 min leitura
    ) as session:
        logger.info("[EXTRATOR.ASYNC.XML.PROCESSAMENTO] Iniciando downloads paralelos...")
        await asyncio.gather(*[baixar_xml_individual(session, client, row, semaphore, db_name) for row in rows])
        
    fim_download = time.time()
    tempo_total = fim_download - inicio_download
    
    logger.info("[EXTRATOR.ASYNC.XML.SUCESSO] ✅ Download de XMLs concluído com sucesso")
    logger.info(f"[EXTRATOR.ASYNC.XML.RESULTADO] • XMLs processados: {total_pendentes:,}")
    logger.info(f"[EXTRATOR.ASYNC.XML.TEMPO] • Tempo total: {_formatar_tempo_total(tempo_total)} ({tempo_total:.2f}s)")
    if tempo_total > 0:
        velocidade = total_pendentes / tempo_total
        logger.info(f"[EXTRATOR.ASYNC.XML.PERFORMANCE] • Velocidade média: {velocidade:.1f} XMLs/s")
    
# ---------------------------------------------------------------------------


async def main():
    def _formatar_tempo_total(segundos: float) -> str:
        """Converte segundos em formato legível."""
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
    
    inicio_execucao = time.time()
    logger.info("[EXTRATOR.ASYNC.MAIN.INICIO] Iniciando execução assíncrona completa")

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
    logger.info(f"[EXTRATOR.ASYNC.MAIN.CONFIG] Logging configurado - arquivo: {log_file}")
    
    # Use explicitamente o carregar_configuracoes do omie_client_async
    config = carregar_configuracoes_client()

    # Log das credenciais para debug
    logger.info(f"[EXTRATOR.ASYNC.MAIN.CREDENCIAIS] Configuração carregada - app_key: {bool(config.get('app_key'))}, app_secret: {bool(config.get('app_secret'))}")
    if not config.get('app_key') or not config.get('app_secret'):
        logger.error("[EXTRATOR.ASYNC.MAIN.ERRO] ❌ app_key ou app_secret estão vazios! Verifique o arquivo configuracao.ini")

    db_name = config.get("db_name", "omie.db")
    logger.info(f"[EXTRATOR.ASYNC.MAIN.DB] Banco de dados: {db_name}")

    client = OmieClient(
        app_key=config["app_key"],
        app_secret=config["app_secret"],
        calls_per_second=config["calls_per_second"],
        base_url_nf=config["base_url_nf"],
        base_url_xml=config["base_url_xml"],
    )

    logger.info("[EXTRATOR.ASYNC.MAIN.PIPELINE] Iniciando pipeline de extração completo...")
    
    # Etapa 1: Inicializar banco
    logger.info("[EXTRATOR.ASYNC.MAIN.ETAPA1] Inicializando banco de dados...")
    iniciar_db(db_name, TABLE_NAME)
    
    # Etapa 2: Listar notas fiscais
    logger.info("[EXTRATOR.ASYNC.MAIN.ETAPA2] Executando listagem de notas fiscais...")
    await listar_nfs(client, config, db_name)
    
    # Etapa 3: Atualizar indexação temporal
    logger.info("[EXTRATOR.ASYNC.MAIN.ETAPA3] Atualizando indexação temporal (anomesdia)...")
    await atualizar_anomesdia(db_name)
    
    # Etapa 4: Baixar XMLs
    logger.info("[EXTRATOR.ASYNC.MAIN.ETAPA4] Executando download de XMLs...")
    await baixar_xmls(client, db_name)
    
    fim_execucao = time.time()
    tempo_total_execucao = fim_execucao - inicio_execucao
    
    logger.info("[EXTRATOR.ASYNC.MAIN.SUCESSO] ✅ Pipeline de extração finalizado com sucesso")
    logger.info(f"[EXTRATOR.ASYNC.MAIN.TEMPO] Tempo total de execução: {_formatar_tempo_total(tempo_total_execucao)} ({tempo_total_execucao:.2f}s)")


if __name__ == "__main__":
    asyncio.run(main())
