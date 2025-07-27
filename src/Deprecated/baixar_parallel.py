# baixar_parallel_v8.py
# Requer: Python 3.9+
# Dependências: requests, sqlite3, pathlib, logging, datetime, concurrent.futures

import os
import html
import sqlite3
import logging
import requests
import configparser
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from time import time, sleep
from threading import Lock

from utils import atualizar_status_xml, iniciar_db, salvar_varias_notas

# Logger centralizado
logger = logging.getLogger(__name__)

# === Leitura de configuracões do arquivo INI ===
config = configparser.ConfigParser()
config.read('configuracao.ini')

# Parâmetros da API
APP_KEY = config['omie_api']['app_key']
APP_SECRET = config['omie_api']['app_secret']
START_DATE = config['query_params']['start_date']
END_DATE = config['query_params']['end_date']
RECORDS_PER_PAGE = int(config['query_params']['records_per_page'])

# Parâmetros do ambiente
DB_NAME = config['paths'].get('db_name', 'omie.db')
TABLE_NAME = 'notas'
TIMEOUT = int(config['api_speed'].get('timeout', 60))
MAX_WORKERS = int(config['api_speed'].get('parallel_workers', 4))

# URLs das APIs Omie
URL_LISTAR = config['omie_api'].get('base_url_nf', 'https://app.omie.com.br/api/v1/produtos/nfconsultar/')
URL_XML = config['omie_api'].get('base_url_xml', 'https://app.omie.com.br/api/v1/produtos/dfedocs/')

# === Controle de taxa ===
rate_lock = Lock()
last_request_time = 0.0

def respeitar_limite_requisicoes():
    global last_request_time
    with rate_lock:
        elapsed = time() - last_request_time
        if elapsed < 0.25:
            sleep(0.25 - elapsed)
        last_request_time = time()

def listar_nfs() -> None:
    pagina = 1
    while True:
        payload = {
            'app_key': APP_KEY,
            'app_secret': APP_SECRET,
            'call': 'ListarNF',
            'param': [{
                'pagina': pagina,
                'registros_por_pagina': RECORDS_PER_PAGE,
                'apenas_importado_api': 'N',
                'dEmiInicial': START_DATE,
                'dEmiFinal': END_DATE,
                'tpNF': 1,
                'tpAmb': 1,
                'cDetalhesPedido': 'N',
                'cApenasResumo': 'S',
                'ordenar_por': 'CODIGO'
            }]
        }
        try:
            respeitar_limite_requisicoes()
            response = requests.post(URL_LISTAR, json=payload, timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json()
            notas = data.get('nfCadastro', [])

            registros = []
            for nf in notas:
                registros.append({
                    'cChaveNFe': nf['compl'].get('cChaveNFe'),
                    'nIdNF': nf['compl'].get('nIdNF'),
                    'nIdPedido': nf['compl'].get('nIdPedido'),
                    'dCan': nf['ide'].get('dCan'),
                    'dEmi': nf['ide'].get('dEmi'),
                    'dInut': nf['ide'].get('dInut'),
                    'dReg': nf['ide'].get('dReg'),
                    'dSaiEnt': nf['ide'].get('dSaiEnt'),
                    'hEmi': nf['ide'].get('hEmi'),
                    'hSaiEnt': nf['ide'].get('hSaiEnt'),
                    'mod': nf['ide'].get('mod'),
                    'nNF': nf['ide'].get('nNF'),
                    'serie': nf['ide'].get('serie'),
                    'tpAmb': nf['ide'].get('tpAmb'),
                    'tpNF': nf['ide'].get('tpNF'),
                    'cnpj_cpf': nf['nfDestInt'].get('cnpj_cpf'),
                    'cRazao': nf['nfDestInt'].get('cRazao'),
                    'vNF': nf['total']['ICMSTot'].get('vNF')
                })

            salvar_varias_notas(registros, DB_NAME)

            total_paginas = data.get('total_de_paginas', 1)
            logging.info(f"Pagina {pagina}/{total_paginas} importada.")
            if pagina >= total_paginas:
                break
            pagina += 1

        except Exception as e:
            logging.error(f"Erro ao listar pagina {pagina}: {e}")
            break

def baixar_uma_nota(registro: tuple) -> Optional[str]:
    nIdNF, chave, dEmi, num_nfe = registro
    try:
        data_dt = datetime.strptime(dEmi, '%d/%m/%Y')
        nome_arquivo = f"{num_nfe}_{data_dt.strftime('%Y%m%d')}_{chave}.xml"
        pasta = Path("resultado") / data_dt.strftime('%Y') / data_dt.strftime('%m') / data_dt.strftime('%d')
        caminho = pasta / nome_arquivo

        pasta.mkdir(parents=True, exist_ok=True)
        rebaixado = caminho.exists()

        payload = {
            'call': 'ObterNfe',
            'app_key': APP_KEY,
            'app_secret': APP_SECRET,
            'param': [{'nIdNfe': nIdNF}]
        }

        respeitar_limite_requisicoes()
        response = requests.post(URL_XML, headers={'Content-Type': 'application/json'}, json=payload, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()

        xml_str = html.unescape(data['cXmlNfe'])
        caminho.write_text(xml_str, encoding='utf-8')

        atualizar_status_xml(DB_NAME, chave, caminho, xml_str, rebaixado)
        logging.info(f"XML salvo: {caminho}")
        return chave

    except Exception as e:
        logging.warning(f"Erro ao baixar nota {chave}: {e}")
        return None

def baixar_xmls_em_parallel() -> None:
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_baixado ON notas (xml_baixado)")
        rows = conn.execute(
            f"SELECT nIdNF, cChaveNFe, dEmi, nNF FROM {TABLE_NAME} WHERE xml_baixado = 0"
        ).fetchall()

    logging.info(f" Iniciando download paralelo de {len(rows)} XMLs com {MAX_WORKERS} workers...")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(baixar_uma_nota, row): row for row in rows}
        for future in as_completed(futures):
            future.result()

def main():
    Path("log").mkdir(exist_ok=True)
    logging.basicConfig(
        filename=f"log/baixar_parallel_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
        level=logging.INFO,
        format='%(asctime)s - %(message)s'
    )

    logging.info(" Iniciando execucao completa do modo paralelo: Listagem + Download")
    iniciar_db(DB_NAME, TABLE_NAME)
    listar_nfs()
    baixar_xmls_em_parallel()
    logging.info("execucao finalizada com sucesso.")

if __name__ == '__main__':
    main()
