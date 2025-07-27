"""
Versoo refatorada de `verificador_xmls.py` integrada ao pipeline com melhorias:
- Uso de pathlib para caminhos
- Logging estruturado
- Melhor tratamento de excecões
- Validacoo robusta de datas e arquivos
"""

import sqlite3
from datetime import datetime
from pathlib import Path
import logging

DB_NAME = 'omie.db'
TABLE_NAME = 'notas'


def verificar_arquivos_existentes_e_corrigir_campos() -> None:
    """
    Verifica a existência dos arquivos XML no disco e atualiza registros no banco.
    """
    atualizacoes = []
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute(f"SELECT cChaveNFe, dEmi, nNF FROM {TABLE_NAME} WHERE xml_baixado = 0")
            rows = c.fetchall()

            for chave, data_emissao, num_nfe in rows:
                try:
                    data_dt = datetime.strptime(data_emissao, '%d/%m/%Y')
                    nome_arquivo = f"{num_nfe}_{data_dt.strftime('%Y%m%d')}_{chave}.xml"
                    pasta = Path("resultado") / data_dt.strftime('%Y') / data_dt.strftime('%m') / data_dt.strftime('%d')
                    caminho = pasta / nome_arquivo

                    if caminho.exists():
                        atualizacoes.append((chave,))
                        logging.debug(f"📁 Arquivo existe: {caminho}")

                except Exception as e:
                    logging.warning(f"Erro ao verificar arquivo para chave {chave} ({data_emissao}): {e}")

            if atualizacoes:
                c.executemany(f"UPDATE {TABLE_NAME} SET xml_baixado = 1 WHERE cChaveNFe = ?", atualizacoes)
                conn.commit()
                logging.info(f"{len(atualizacoes)} registros atualizados com sucesso.")
            else:
                logging.info("✅ Nenhum novo arquivo encontrado para atualizar.")

    except Exception as e:
        logging.exception(f"Erro ao conectar ao banco de dados ou executar consulta: {e}")


def verificar() -> None:
    """
    funcao principal para ser chamada pelo pipeline.
    """
    logging.info(" Iniciando verificador de XMLs existentes no disco...")
    verificar_arquivos_existentes_e_corrigir_campos()
    logging.info(" verificacao finalizada.")
