#!/usr/bin/env python3
"""
Teste do extrator simples para diagnosticar problemas do pipeline atual.
Baseado no extrator.py que funciona corretamente.
"""

import os
import time
import html
import json
import sqlite3
import requests
import configparser
from datetime import datetime
from pathlib import Path
import logging

# Configurar logging
os.makedirs('log', exist_ok=True)
log_file = f"log/teste_extrator_simples_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Carregar configurações - usar o mesmo arquivo do pipeline atual
config = configparser.ConfigParser()
config.read('configuracao.ini')

APP_KEY = config['omie_api']['app_key']
APP_SECRET = config['omie_api']['app_secret']
START_DATE = config['query_params']['start_date']
END_DATE = config['query_params']['end_date']
RECORDS_PER_PAGE = int(config['query_params']['records_per_page'])
CALLS_PER_SECOND = int(config['api_speed']['calls_per_second'])

# SQLite
DB_NAME = 'omie_teste.db'
TABLE_NAME = 'notas_teste'

logging.info(f"Configurações carregadas:")
logging.info(f"- START_DATE: {START_DATE}")
logging.info(f"- END_DATE: {END_DATE}")
logging.info(f"- CALLS_PER_SECOND: {CALLS_PER_SECOND}")
logging.info(f"- RECORDS_PER_PAGE: {RECORDS_PER_PAGE}")

def chamada_com_retries(url, headers, payload, max_tentativas=3, espera_curta=5, espera_longa=300):
    """Função de retry simples - exatamente como no extrator.py que funciona"""
    for tentativa in range(1, max_tentativas + 1):
        try:
            logging.info(f"Tentativa {tentativa} - URL: {url}")
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            logging.info(f"Status da resposta: {response.status_code}")
            response.raise_for_status()
            return response
        except Exception as e:
            logging.warning(f"Tentativa {tentativa} falhou: {e}")
            if tentativa < max_tentativas:
                logging.info(f"Aguardando {espera_curta}s antes da próxima tentativa...")
                time.sleep(espera_curta)
            else:
                logging.warning(f"Todas as {max_tentativas} tentativas falharam. Aguardando {espera_longa} segundos antes de tentar novamente.")
                time.sleep(espera_longa)
                return chamada_com_retries(url, headers, payload, max_tentativas, espera_curta, espera_longa)

def iniciar_db():
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
        logging.info("Banco de dados teste inicializado")

def testar_listar_uma_pagina():
    """Testa apenas uma página da listagem para diagnóstico"""
    logging.info("=== TESTE: Listagem de uma página ===")
    
    payload = {
        'call': 'ListarNF',
        'app_key': APP_KEY,
        'app_secret': APP_SECRET,
        'param': [{
            'pagina': 1,
            'registros_por_pagina': 10,  # Apenas 10 registros para teste
            'apenas_importado_api': 'N',
            'dEmiInicial': START_DATE,
            'dEmiFinal': END_DATE,
            'tpNF': 1,
            'tpAmb': 1,
            'cDetalhesPedido': 'N',
            'cApenasResumo': 'S',
            'ordenar_por': 'CODIGO',
        }]
    }

    try:
        response = chamada_com_retries(
            url='https://app.omie.com.br/api/v1/produtos/nfconsultar/',
            headers={'Content-Type': 'application/json'},
            payload=payload
        )
        data = response.json()
        
        if 'nfCadastro' not in data:
            logging.error(f"Erro na resposta: {data}")
            return False
            
        logging.info(f"Sucesso! Encontradas {len(data['nfCadastro'])} notas fiscais")
        logging.info(f"Total de páginas: {data.get('total_de_paginas', 1)}")
        return data['nfCadastro']
        
    except Exception as e:
        logging.error(f"Erro ao listar notas: {e}")
        return False

def testar_download_xml(nIdNF, chave_nfe):
    """Testa o download de um XML específico"""
    logging.info(f"=== TESTE: Download XML - nIdNF: {nIdNF}, Chave: {chave_nfe} ===")
    
    payload = {
        'call': 'ObterNfe',
        'app_key': APP_KEY,
        'app_secret': APP_SECRET,
        'param': [{'nIdNfe': nIdNF}]
    }

    try:
        response = chamada_com_retries(
            url='https://app.omie.com.br/api/v1/produtos/dfedocs/',
            headers={'Content-Type': 'application/json'},
            payload=payload
        )
        data = response.json()
        
        if 'cXmlNfe' not in data:
            logging.error(f"Erro na resposta XML: {data}")
            return False
            
        xml_str = html.unescape(data['cXmlNfe'])
        logging.info(f"XML obtido com sucesso! Tamanho: {len(xml_str)} caracteres")
        
        # Salvar em arquivo de teste
        pasta_teste = Path("teste_xml")
        pasta_teste.mkdir(exist_ok=True)
        caminho_teste = pasta_teste / f"teste_{chave_nfe}.xml"
        
        with open(caminho_teste, 'w', encoding='utf-8') as f:
            f.write(xml_str)
        logging.info(f"XML salvo em: {caminho_teste}")
        return True
        
    except Exception as e:
        logging.error(f"Erro ao baixar XML: {e}")
        return False

def main():
    """Função principal de teste"""
    logging.info("========================================")
    logging.info("INICIANDO TESTE DO EXTRATOR SIMPLES")
    logging.info("========================================")
    
    # Inicializar banco
    iniciar_db()
    
    # Teste 1: Listar notas
    notas = testar_listar_uma_pagina()
    if not notas:
        logging.error("Falha no teste de listagem. Encerrando.")
        return
    
    # Aguardar um pouco entre chamadas
    logging.info(f"Aguardando {1/CALLS_PER_SECOND:.2f}s entre chamadas...")
    time.sleep(1 / CALLS_PER_SECOND)
    
    # Teste 2: Download de XML da primeira nota
    if notas:
        primeira_nota = notas[0]
        nIdNF = primeira_nota['compl'].get('nIdNF')
        chave_nfe = primeira_nota['compl'].get('cChaveNFe')
        
        if nIdNF and chave_nfe:
            sucesso_xml = testar_download_xml(nIdNF, chave_nfe)
            if sucesso_xml:
                logging.info("✅ TESTE CONCLUÍDO COM SUCESSO!")
            else:
                logging.error("❌ FALHA NO DOWNLOAD DO XML")
        else:
            logging.error("Dados da nota incompletos para teste XML")
    
    logging.info("========================================")
    logging.info("TESTE CONCLUÍDO")
    logging.info("========================================")

if __name__ == '__main__':
    main()
