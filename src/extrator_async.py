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
from typing import Any, Dict
from threading import Lock

import aiohttp

# Adicionar o diretório raiz ao path para importações
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import (
    atualizar_status_xml,
    iniciar_db,
    salvar_varias_notas,
    gerar_xml_path_otimizado,
    conexao_otimizada,
    gerar_pasta_xml_path,
    atualizar_anomesdia,
    normalizar_data
)
from src.omie_client_async import OmieClient, carregar_configuracoes
from main_old import executar_atualizacao_anomesdia


# ---------------------------------------------------------------------------
# Configuracoo de logging centralizado
# ---------------------------------------------------------------------------
# logger = logging.getLogger(__name__)

# Configuração básica de logging para acompanhar execução
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('log/extrator_async.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

TABLE_NAME = "notas"

# === Controle de limite de requisicões (4 por segundo) ===
ULTIMA_REQUISICAO = 0.0
LOCK = Lock()

# Configurações de otimização SQLite
SQLITE_PRAGMAS: Dict[str, str] = {
    "journal_mode": "WAL",
    "synchronous": "NORMAL",
    "temp_store": "MEMORY",
    "cache_size": "-64000",  # 64MB cache
    "mmap_size": "268435456"  # 256MB mmap
}


def respeitar_limite_requisicoes() -> None:
    global ULTIMA_REQUISICAO
    with LOCK:
        agora = time.monotonic()
        tempo_decorrido = agora - ULTIMA_REQUISICAO
        if tempo_decorrido < 0.25:
            time.sleep(0.25 - tempo_decorrido)
        ULTIMA_REQUISICAO = time.monotonic()


def normalizar_nota(nf: dict[str, Any]) -> dict[str, Any]:
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


async def call_api_com_retentativa(
    client: OmieClient,
    session: aiohttp.ClientSession,
    metodo: str,
    payload: dict[str, Any],
):
    max_retentativas = 3
    for tentativa in range(1, max_retentativas + 1):
        try:
            respeitar_limite_requisicoes()
            return await client.call_api(session, metodo, payload)
        
        except asyncio.TimeoutError as exc:
            logger.warning("[RETRY] Timeout - Esperando %ss (tentativa %s)", 10 * tentativa, tentativa)
            await asyncio.sleep(10 * tentativa)
        except asyncio.CancelledError as exc:
            logger.warning("[RETRY] CancelledError - Esperando %ss (tentativa %s)", 10 * tentativa, tentativa)
            await asyncio.sleep(10 * tentativa)

        except aiohttp.ClientResponseError as exc:
            if exc.status == 429:
                tempo_espera = 2**tentativa
                logger.warning(
                    "[RETRY] 429 - Esperando %ss (tentativa %s)", tempo_espera, tentativa
                )
                await asyncio.sleep(tempo_espera)
            elif exc.status >= 500:
                tempo_espera = 1 + tentativa
                logger.warning(
                    "[RETRY] %s - Erro servidor. Tentativa %s", exc.status, tentativa
                )
                await asyncio.sleep(tempo_espera)
            else:
                logger.error("[API] Falha irreversivel: %s", exc)
                raise

        except Exception as exc:
            logger.error("[API] Erro inesperado: %s", exc)
            raise

    raise RuntimeError(f"[API] Falha apos {max_retentativas} tentativas para {metodo}")

import aiosqlite

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
                AND (anomesdia IS NULL OR anomesdia = 0)
            """)
            registros = await cursor.fetchall()
            await cursor.close()
            if not registros:
                logger.info("[ANOMESDIA] Nenhum registro para atualizar")
                return 0
            logger.info(f"[ANOMESDIA] Processando {len(registros)} registros...")
            atualizacoes = []
            erros = 0
            for chave, dEmi in registros:
                try:
                    data_normalizada = normalizar_data(dEmi)
                    if data_normalizada:
                        # Converte para YYYYMMDD
                        dia, mes, ano = data_normalizada.split('/')
                        anomesdia = int(f"{ano}{mes}{dia}")
                        atualizacoes.append((anomesdia, chave))
                    else:
                        logger.warning(f"[ANOMESDIA] Data inválida para chave {chave}: {dEmi}")
                        erros += 1
                except Exception as e:
                    logger.warning(f"[ANOMESDIA] Erro ao processar {chave}: {e}")
                    erros += 1
            if atualizacoes:
                await conn.executemany(f"""
                    UPDATE {table_name} 
                    SET anomesdia = ? 
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


async def listar_nfs(client: OmieClient, config: dict[str, Any], db_name: str):
    logger.info("[NFS] Iniciando listagem de notas fiscais...")
    
    
    # Verifica otimizações disponíveis para relatórios de progresso
    try:
        from src.utils import _verificar_views_e_indices_disponiveis
        db_otimizacoes = _verificar_views_e_indices_disponiveis(db_name)
        usar_views = True
    except ImportError:
        db_otimizacoes = {}
        usar_views = False
    
    pagina = 1
    total_registros_salvos = 0
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=360)) as session:
        while True:
            payload = {
                "pagina": pagina,
                "registros_por_pagina": config["records_per_page"],
                "apenas_importado_api": "N",
                "dEmiInicial": config["start_date"],
                "dEmiFinal": config["end_date"],
                "tpNF": 1,
                "tpAmb": 1,
                "cDetalhesPedido": "N",
                "cApenasResumo": "S",
                "ordenar_por": "CODIGO",
            }
            try:
                data = await call_api_com_retentativa(client, session, "ListarNF", payload)
                notas = data.get("nfCadastro", [])
                if not notas:
                    logger.info("[NFS] Pagina %s sem notas.", pagina)
                    break

                registros = [r for nf in notas if (r := normalizar_nota(nf))]
                resultado_salvamento = salvar_varias_notas(registros, db_name)
                total_registros_salvos += resultado_salvamento.get('inseridos', len(registros))
                total_registros_processados = resultado_salvamento.get('total_processados', len(registros))

                total_paginas = data.get("total_de_paginas", 1)
                logger.info("[NFS] Pagina %s/%s processada (%s registros).", pagina, total_paginas, total_registros_processados)
                
                
                if pagina >= total_paginas:
                    break
                pagina += 1

            except Exception as exc:
                logger.exception("[NFS] Erro na listagem pagina %s: %s", pagina, exc)
                break
    
    logger.info(f"[NFS] Listagem concluida. {total_registros_salvos} registros processados.")
    



async def baixar_xml_individual(
    session: aiohttp.ClientSession,
    client: OmieClient,
    row: tuple,
    semaphore: asyncio.Semaphore,
    db_name: str,
):
    async with semaphore:
        # Adaptação para suportar tanto 4 quanto 5 campos (com anomesdia da consulta otimizada)
        if len(row) > 4:
            chave, dEmi, num_nfe,nIdNF, anomesdia = row
            #cChaveNFe, dEmi, nNF, nIdNF, anomesdia
        else:
            chave, dEmi, num_nfe,nIdNF = row
            anomesdia = None
            
        try:
            pasta, caminho = gerar_pasta_xml_path(chave, dEmi, num_nfe)
            
            
            pasta.mkdir(parents=True, exist_ok=True)
            rebaixado = caminho.exists()

            data = await call_api_com_retentativa(
                client, session, "ObterNfe", {"nIdNfe": nIdNF}
            )
            xml_str = html.unescape(data.get("cXmlNfe", ""))

            caminho.write_text(xml_str, encoding="utf-8")
            atualizar_status_xml(db_name, chave, caminho, xml_str, rebaixado)
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
    config = carregar_configuracoes()
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
    await atualizar_anomesdia(client, db_name)
    await baixar_xmls(client, db_name)
    logger.info("[MAIN] Processo finalizado com sucesso")


if __name__ == "__main__":
    asyncio.run(main())
