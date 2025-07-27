#!/usr/bin/env python3
"""
Teste com o extrator funcional mas baixando apenas 1 XML para validar a abordagem.
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
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Carregar configurações
config = configparser.ConfigParser()
config.read('configuracao.ini')

APP_KEY = config['omie_api']['app_key']
APP_SECRET = config['omie_api']['app_secret']
START_DATE = config['query_params']['start_date']
END_DATE = config['query_params']['end_date']

logging.info("🔧 TESTE FUNCIONAL - DOWNLOAD DE 1 XML")
logging.info("=" * 50)

def chamada_com_retries(url, headers, payload, max_tentativas=3):
    """Função de retry conservadora"""
    for tentativa in range(1, max_tentativas + 1):
        try:
            logging.info(f"⏳ Tentativa {tentativa}/{max_tentativas}...")
            response = requests.post(url, headers=headers, json=payload, timeout=180)
            response.raise_for_status()
            logging.info(f"✅ Sucesso na tentativa {tentativa}")
            return response
        except Exception as e:
            logging.warning(f"❌ Tentativa {tentativa} falhou: {e}")
            if tentativa < max_tentativas:
                espera = 60 * tentativa  # 60s, 120s, 180s
                logging.info(f"⏳ Aguardando {espera}s antes da próxima tentativa...")
                time.sleep(espera)
            else:
                logging.error(f"💥 Todas as {max_tentativas} tentativas falharam")
                raise

def teste_download_unico():
    """Testa download de um único XML usando abordagem sequencial"""
    
    # 1. Primeiro buscar uma nota fiscal
    logging.info("📋 Buscando uma nota fiscal para testar...")
    
    payload_lista = {
        'call': 'ListarNF',
        'app_key': APP_KEY,
        'app_secret': APP_SECRET,
        'param': [{
            'pagina': 1,
            'registros_por_pagina': 1,
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

    response = chamada_com_retries(
        url='https://app.omie.com.br/api/v1/produtos/nfconsultar/',
        headers={'Content-Type': 'application/json'},
        payload=payload_lista
    )
    data = response.json()
    
    if not data.get('nfCadastro'):
        logging.error("❌ Nenhuma nota fiscal encontrada")
        return False
        
    nf = data['nfCadastro'][0]
    nf_id = nf['compl'].get('nIdNF')
    chave = nf['compl'].get('cChaveNFe')
    num_nfe = nf['ide'].get('nNF')
    
    logging.info(f"✅ NF encontrada - ID: {nf_id}, Chave: {chave[:10]}..., Número: {num_nfe}")
    
    # 2. Aguardar entre chamadas (EXTREMAMENTE conservador)
    logging.info("⏳ Aguardando 60 segundos antes do download do XML...")
    time.sleep(60)  # 1 minuto completo entre chamadas
    
    # 3. Tentar baixar o XML
    logging.info("📥 Iniciando download do XML...")
    
    payload_xml = {
        'call': 'ObterNfe',
        'app_key': APP_KEY,
        'app_secret': APP_SECRET,
        'param': [{'nIdNfe': nf_id}]
    }

    inicio = time.time()
    response = chamada_com_retries(
        url='https://app.omie.com.br/api/v1/produtos/dfedocs/',
        headers={'Content-Type': 'application/json'},
        payload=payload_xml
    )
    tempo_total = time.time() - inicio
    
    data = response.json()
    
    # 4. Verificar resposta
    if 'cXmlNfe' in data:
        xml_str = html.unescape(data['cXmlNfe'])
        tamanho = len(xml_str)
        
        logging.info(f"✅ XML baixado com sucesso!")
        logging.info(f" Tempo total: {tempo_total:.2f}s")
        logging.info(f"📏 Tamanho: {tamanho:,} caracteres")
        
        # Salvar para testar
        caminho_teste = Path("teste_xml_download.xml")
        with open(caminho_teste, 'w', encoding='utf-8') as f:
            f.write(xml_str)
        logging.info(f"💾 XML salvo em: {caminho_teste}")
        
        return True
    else:
        erro = data.get('faultstring', 'Erro desconhecido')
        logging.error(f"❌ Erro na resposta da API: {erro}")
        return False

def main():
    try:
        sucesso = teste_download_unico()
        
        if sucesso:
            logging.info("\n TESTE PASSOU!")
            logging.info("💡 Abordagem sequencial funciona para XMLs")
            logging.info("💡 Rate limiting de 10s entre chamadas parece adequado")
        else:
            logging.error("\n💥 TESTE FALHOU!")
            logging.error("💡 Pode precisar de ajustes adicionais")
            
    except Exception as e:
        logging.error(f"💥 Erro no teste: {e}")
        logging.exception("Stack trace:")

if __name__ == "__main__":
    main()
