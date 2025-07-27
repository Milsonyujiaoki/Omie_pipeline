"""
Versoo refatorada e independente de `baixar_parallel.py`:
- Agora inclui a etapa de listagem de NFs (`ListarNF`) e salva no banco
- Executa a extracoo e download dos XMLs
- Comportamento completo e isolado do modo assincrono
"""

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

# === Carrega configuracões do INI ===
config = configparser.ConfigParser()
config.read('configuracao.ini')

APP_KEY = config['omie_api']['app_key']
APP_SECRET = config['omie_api']['app_secret']
START_DATE = config['query_params']['start_date']
END_DATE = config['query_params']['end_date']
RECORDS_PER_PAGE = int(config['query_params']['records_per_page'])

DB_NAME = 'omie.db'
TABLE_NAME = 'notas'
TIMEOUT = int(config['api_speed'].get('timeout', 60))
MAX_WORKERS = int(config['api_speed'].get('parallel_workers', 4))

URL_LISTAR = 'https://app.omie.com.br/api/v1/produtos/nfconsultar/'
URL_XML = 'https://app.omie.com.br/api/v1/produtos/dfedocs/'


def iniciar_db() -> None:
    Path("log").mkdir(exist_ok=True)
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(f'''
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                cChaveNFe TEXT PRIMARY KEY,
                nIdNF INTEGER,
                nIdPedido INTEGER,
                dCan TEXT,
                dEmi TEXT,
                dInut TEXT,
                dReg TEXT,
                dSaiEnt TEXT,
                hEmi TEXT,
                hSaiEnt TEXT,
                mod TEXT,
                nNF TEXT,
                serie TEXT,
                tpAmb TEXT,
                tpNF TEXT,
                cnpj_cpf TEXT,
                cRazao TEXT,
                vNF REAL,
                xml_baixado BOOLEAN DEFAULT 0
            )''')
        conn.commit()


def salvar_nota(registro: dict) -> None:
    with sqlite3.connect(DB_NAME) as conn:
        try:
            conn.execute(f'''
                INSERT INTO {TABLE_NAME} (
                    cChaveNFe, nIdNF, nIdPedido, dCan, dEmi, dInut, dReg, dSaiEnt, hEmi, hSaiEnt,
                    mod, nNF, serie, tpAmb, tpNF, cnpj_cpf, cRazao, vNF
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    registro.get('cChaveNFe'), registro.get('nIdNF'), registro.get('nIdPedido'),
                    registro.get('dCan'), registro.get('dEmi'), registro.get('dInut'), registro.get('dReg'),
                    registro.get('dSaiEnt'), registro.get('hEmi'), registro.get('hSaiEnt'), registro.get('mod'),
                    registro.get('nNF'), registro.get('serie'), registro.get('tpAmb'), registro.get('tpNF'),
                    registro.get('cnpj_cpf'), registro.get('cRazao'), registro.get('vNF')
                ))
            conn.commit()
        except sqlite3.IntegrityError:
            pass


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
            response = requests.post(URL_LISTAR, json=payload, timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json()
            notas = data.get('nfCadastro', [])
            for nf in notas:
                salvar_nota({
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
            total_paginas = data.get('total_de_paginas', 1)
            logging.info(f"📄 Pagina {pagina}/{total_paginas} importada.")
            if pagina >= total_paginas:
                break
            pagina += 1
        except Exception as e:
            logging.error(f"Erro ao listar pagina {pagina}: {e}")
            break


def baixar_uma_nota(registro: tuple) -> Optional[str]:
    nIdNF, chave, data_emissao, num_nfe = registro
    try:
        data_dt = datetime.strptime(data_emissao, '%d/%m/%Y')
        nome_arquivo = f"{num_nfe}_{data_dt.strftime('%Y%m%d')}_{chave}.xml"
        pasta = Path("resultado") / data_dt.strftime('%Y') / data_dt.strftime('%m') / data_dt.strftime('%d')
        caminho = pasta / nome_arquivo

        if caminho.exists():
            logging.debug(f"🔁 XML ja existe: {caminho}")
            return chave

        payload = {
            'call': 'ObterNfe',
            'app_key': APP_KEY,
            'app_secret': APP_SECRET,
            'param': [{'nIdNfe': nIdNF}]
        }

        response = requests.post(URL_XML, headers={'Content-Type': 'application/json'}, json=payload, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()

        xml_str = html.unescape(data['cXmlNfe'])
        pasta.mkdir(parents=True, exist_ok=True)
        caminho.write_text(xml_str, encoding='utf-8')

        logging.info(f"✅ XML salvo: {caminho}")
        return chave

    except Exception as e:
        logging.warning(f"❌ Erro ao baixar nota {chave}: {e}")
        return None


def baixar_xmls_em_parallel() -> None:
    with sqlite3.connect(DB_NAME) as conn:
        rows = conn.execute(f"SELECT nIdNF, cChaveNFe, dEmi, nNF FROM {TABLE_NAME} WHERE xml_baixado = 0").fetchall()

    logging.info(f"🚀 Iniciando download paralelo de {len(rows)} XMLs com {MAX_WORKERS} workers...")

    registros_atualizados = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(baixar_uma_nota, row): row for row in rows}
        for future in as_completed(futures):
            resultado = future.result()
            if resultado:
                registros_atualizados.append((resultado,))

    if registros_atualizados:
        with sqlite3.connect(DB_NAME) as conn:
            conn.executemany(f"UPDATE {TABLE_NAME} SET xml_baixado = 1 WHERE cChaveNFe = ?", registros_atualizados)
            conn.commit()
        logging.info(f"{len(registros_atualizados)} registros atualizados no banco.")
    else:
        logging.warning("⚠️ Nenhum XML foi baixado com sucesso.")


def main():
    Path("log").mkdir(exist_ok=True)
    logging.basicConfig(filename=f"log/baixar_parallel_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log", level=logging.INFO, format='%(asctime)s - %(message)s')

    logging.info("🧩 Iniciando execucao completa do modo paralelo: Listagem + Download")
    iniciar_db()
    listar_nfs()
    baixar_xmls_em_parallel()
    logging.info("✅ execucao finalizada com sucesso.")


if __name__ == '__main__':
    main()
