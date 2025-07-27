"""
Versoo refatorada de `extrator_async.py` com melhorias propostas:
- Timeout e cabecalhos configuraveis
- Logging para console e arquivo
- Uso de `pathlib` e separacoo de responsabilidades
- Melhoria no tratamento de excecões
- Validacoo de resposta JSON
"""

import os
import html
import sqlite3
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Any

import aiohttp
from src.omie_client_async import OmieClient, carregar_configuracoes

DB_NAME = 'omie.db'
TABLE_NAME = 'notas'


def configurar_logging():
    Path("log").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f"log/extrator_async_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
            logging.StreamHandler()
        ]
    )

def iniciar_db():
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

def salvar_nota(registro: dict):
    with sqlite3.connect(DB_NAME) as conn:
        try:
            conn.execute(f'''
                INSERT INTO {TABLE_NAME} (
                    cChaveNFe, nIdNF, nIdPedido, dCan, dEmi, dInut, dReg, dSaiEnt, hEmi, hSaiEnt,
                    mod, nNF, serie, tpAmb, tpNF, cnpj_cpf, cRazao, vNF
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    registro.get('cChaveNFe'),
                    registro.get('nIdNF'),
                    registro.get('nIdPedido'),
                    registro.get('dCan'),
                    registro.get('dEmi'),
                    registro.get('dInut'),
                    registro.get('dReg'),
                    registro.get('dSaiEnt'),
                    registro.get('hEmi'),
                    registro.get('hSaiEnt'),
                    registro.get('mod'),
                    registro.get('nNF'),
                    registro.get('serie'),
                    registro.get('tpAmb'),
                    registro.get('tpNF'),
                    registro.get('cnpj_cpf'),
                    registro.get('cRazao'),
                    registro.get('vNF')
                )
            )
            conn.commit()
        except sqlite3.IntegrityError:
            logging.debug(f"Nota duplicada ignorada: {registro.get('cChaveNFe')}")

async def listar_nfs(client: OmieClient, config: dict[str, Any]):
    pagina = 1
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90)) as session:
        while True:
            payload = {
                'pagina': pagina,
                'registros_por_pagina': config["records_per_page"],
                'apenas_importado_api': 'N',
                'dEmiInicial': config["start_date"],
                'dEmiFinal': config["end_date"],
                'tpNF': 1,
                'tpAmb': 1,
                'cDetalhesPedido': 'N',
                'cApenasResumo': 'S',
                'ordenar_por': 'CODIGO',
            }
            try:
                data = await client.call_api(session, "ListarNF", payload)
                notas = data.get('nfCadastro', [])
                if not notas:
                    logging.warning(f"Pagina {pagina} sem notas: {data}")
                    break

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
                        'vNF': nf['total']['ICMSTot'].get('vNF'),
                    })
                total_paginas = data.get("total_de_paginas", 1)
                logging.info(f"Pagina {pagina} processada. Total: {total_paginas}")
                if pagina >= total_paginas:
                    break
                pagina += 1
            except Exception as e:
                logging.exception(f"Erro ao listar pagina {pagina}: {e}")
                break

async def baixar_xml_individual(session: aiohttp.ClientSession, client: OmieClient, row: tuple, atualizados: list):
    nIdNF, chave, data_emissao, num_nfe = row
    try:
        data_dt = datetime.strptime(data_emissao, '%d/%m/%Y')
        nome_arquivo = f"{num_nfe}_{data_dt.strftime('%Y%m%d')}_{chave}.xml"
        pasta = Path("resultado") / data_dt.strftime('%Y') / data_dt.strftime('%m') / data_dt.strftime('%d')
        caminho = pasta / nome_arquivo

        if caminho.exists():
            atualizados.append((chave,))
            return

        data = await client.call_api(session, "ObterNfe", {"nIdNfe": nIdNF})
        xml_str = html.unescape(data.get("cXmlNfe", ""))

        pasta.mkdir(parents=True, exist_ok=True)
        caminho.write_text(xml_str, encoding='utf-8')

        atualizados.append((chave,))
        logging.info(f"✅ XML salvo: {caminho}")
    except Exception as e:
        logging.error(f"Erro ao baixar {chave}: {e}")

async def baixar_xmls(client: OmieClient):
    with sqlite3.connect(DB_NAME) as conn:
        rows = conn.execute(f"SELECT nIdNF, cChaveNFe, dEmi, nNF FROM {TABLE_NAME} WHERE xml_baixado = 0").fetchall()

    atualizados = []
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        await asyncio.gather(*[
            baixar_xml_individual(session, client, row, atualizados) for row in rows
        ])

    if atualizados:
        with sqlite3.connect(DB_NAME) as conn:
            conn.executemany(
                f"UPDATE {TABLE_NAME} SET xml_baixado = 1 WHERE cChaveNFe = ?",
                atualizados
            )
            conn.commit()
        logging.info(f"{len(atualizados)} registros atualizados no banco.")

def main():
    configurar_logging()
    config = carregar_configuracoes()
    client = OmieClient(config["app_key"], config["app_secret"], config["calls_per_second"])

    iniciar_db()
    asyncio.run(listar_nfs(client, config))
    asyncio.run(baixar_xmls(client))

if __name__ == "__main__":
    main()
