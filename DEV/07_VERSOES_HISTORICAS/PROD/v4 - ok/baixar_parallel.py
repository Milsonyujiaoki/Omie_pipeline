# baixar_parallel.py

import os
import html
import sqlite3
import logging
import requests
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import configparser

# === Carrega configuracões do INI ===
config = configparser.ConfigParser()
config.read('configuracao.ini')

APP_KEY = config['omie_api']['app_key']
APP_SECRET = config['omie_api']['app_secret']
DB_NAME = 'omie.db'
TABLE_NAME = 'notas'


def baixar_uma_nota(registro: tuple, app_key: str, app_secret: str) -> str | None:
    """
    Baixa e salva um XML individualmente. Retorna a chave da nota se sucesso.
    """
    nIdNF, chave, data_emissao, num_nfe = registro
    try:
        data_dt = datetime.strptime(data_emissao, '%d/%m/%Y')
        data_formatada = data_dt.strftime('%Y%m%d')
        nome_arquivo = f"{num_nfe}_{data_formatada}_{chave}.xml"
        pasta = Path(f"resultado/{data_dt.year}/{data_dt.strftime('%m')}/{data_dt.strftime('%d')}")
        caminho = pasta / nome_arquivo

        if caminho.exists():
            logging.info(f"🔁 XML ja existe: {caminho}")
            return chave

        payload = {
            'call': 'ObterNfe',
            'app_key': app_key,
            'app_secret': app_secret,
            'param': [{'nIdNfe': nIdNF}]
        }

        response = requests.post(
            url='https://app.omie.com.br/api/v1/produtos/dfedocs/',
            headers={'Content-Type': 'application/json'},
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        data = response.json()

        xml_str = html.unescape(data['cXmlNfe'])
        pasta.mkdir(parents=True, exist_ok=True)

        with open(caminho, 'w', encoding='utf-8') as f:
            f.write(xml_str)

        logging.info(f"✅ XML salvo: {caminho}")
        return chave

    except Exception as e:
        logging.error(f"❌ Erro ao processar nota {chave}: {str(e)}")
        return None


def baixar_xmls_em_parallel(max_workers: int = 4) -> None:
    """
    Realiza o download paralelo dos XMLs com controle de erros e atualizacao do banco.
    """
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute(f"SELECT nIdNF, cChaveNFe, dEmi, nNF FROM {TABLE_NAME} WHERE xml_baixado = 0")
        rows = c.fetchall()

    logging.info(f"🚀 Iniciando download paralelo de {len(rows)} XMLs com {max_workers} workers...")

    registros_atualizados = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(baixar_uma_nota, row, APP_KEY, APP_SECRET)
            for row in rows
        ]

        for future in as_completed(futures):
            resultado = future.result()
            if resultado:
                registros_atualizados.append((resultado,))

    if registros_atualizados:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.executemany(
                f"UPDATE {TABLE_NAME} SET xml_baixado = 1 WHERE cChaveNFe = ?",
                registros_atualizados
            )
            conn.commit()
            logging.info(f"{len(registros_atualizados)} registros atualizados no banco.")
    else:
        logging.info("⚠️ Nenhum XML foi baixado com sucesso.")


if __name__ == '__main__':
    os.makedirs("log", exist_ok=True)
    log_file = f"log/baixar_parallel_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(message)s')

    baixar_xmls_em_parallel()
