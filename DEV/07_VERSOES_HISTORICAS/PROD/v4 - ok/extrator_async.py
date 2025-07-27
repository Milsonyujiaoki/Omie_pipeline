# extrator_async.py

import os
import html
import sqlite3
import asyncio
import logging
from pathlib import Path
from datetime import datetime

import aiohttp
from omie_client_async import OmieClient, carregar_configuracoes

DB_NAME = 'omie.db'
TABLE_NAME = 'notas'


def iniciar_db():
    os.makedirs("log", exist_ok=True)
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute(f'''
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
        )
        ''')
        conn.commit()


def salvar_nota(registro: dict):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        try:
            c.execute(f'''
                INSERT INTO {TABLE_NAME} (
                    cChaveNFe, nIdNF, nIdPedido, dCan, dEmi, dInut, dReg, dSaiEnt, hEmi, hSaiEnt,
                    mod, nNF, serie, tpAmb, tpNF, cnpj_cpf, cRazao, vNF
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
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
            ))
            conn.commit()
        except sqlite3.IntegrityError:
            pass


async def listar_nfs(client: OmieClient, config: dict):
    pagina = 1
    async with aiohttp.ClientSession() as session:
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
            data = await client.call_api(session, "ListarNF", payload)

            if 'nfCadastro' not in data:
                logging.warning(f"Erro na pagina {pagina}: {data}")
                break

            for nf in data['nfCadastro']:
                registro = {
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
                }
                salvar_nota(registro)

            total_paginas = data.get("total_de_paginas", 1)
            logging.info(f"Pagina {pagina} processada. Total: {total_paginas}")
            if pagina >= total_paginas:
                break
            pagina += 1


async def baixar_xml_individual(session: aiohttp.ClientSession, client: OmieClient, row: tuple, atualizados: list):
    nIdNF, chave, data_emissao, num_nfe = row
    try:
        data_dt = datetime.strptime(data_emissao, '%d/%m/%Y')
        data_formatada = data_dt.strftime('%Y%m%d')
        nome_arquivo = f"{num_nfe}_{data_formatada}_{chave}.xml"
        pasta = Path(f"resultado/{data_dt.year}/{data_dt.strftime('%m')}/{data_dt.strftime('%d')}")
        caminho = pasta / nome_arquivo

        if caminho.exists():
            atualizados.append((chave,))
            return

        payload = {"nIdNfe": nIdNF}
        data = await client.call_api(session, "ObterNfe", payload)
        xml_str = html.unescape(data["cXmlNfe"])

        pasta.mkdir(parents=True, exist_ok=True)
        with open(caminho, 'w', encoding='utf-8') as f:
            f.write(xml_str)

        atualizados.append((chave,))
        logging.info(f"✅ XML salvo: {caminho}")
    except Exception as e:
        logging.error(f"Erro ao baixar {chave}: {e}")


async def baixar_xmls(client: OmieClient):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute(f"SELECT nIdNF, cChaveNFe, dEmi, nNF FROM {TABLE_NAME} WHERE xml_baixado = 0")
        rows = c.fetchall()

    atualizados = []
    async with aiohttp.ClientSession() as session:
        tarefas = [
            baixar_xml_individual(session, client, row, atualizados)
            for row in rows
        ]
        await asyncio.gather(*tarefas)

    if atualizados:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.executemany(
                f"UPDATE {TABLE_NAME} SET xml_baixado = 1 WHERE cChaveNFe = ?",
                atualizados
            )
            conn.commit()
        logging.info(f"{len(atualizados)} registros atualizados no banco.")


async def main():
    logging.basicConfig(
        filename=f"log/extrator_async_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    config = carregar_configuracoes()
    client = OmieClient(config["app_key"], config["app_secret"], config["calls_per_second"])

    iniciar_db()
    await listar_nfs(client, config)
    await baixar_xmls(client)

if __name__ == "__main__":
    asyncio.run(main())
