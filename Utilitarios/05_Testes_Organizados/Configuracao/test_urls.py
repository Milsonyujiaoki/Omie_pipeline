#!/usr/bin/env python3
"""
Teste para verificar URLs exatas usadas pelo cliente
"""
import os
import sys
from pathlib import Path

# Adiciona o diretório pai ao path para importar src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from src.omie_client_async import carregar_configuracoes, OmieClient

async def test_urls():
    """Testa as URLs que estão sendo usadas pelo cliente"""
    
    # Carregar configurações
    config = carregar_configuracoes()
    
    print("=== CONFIGURAÇÕES CARREGADAS ===")
    print(f"base_url_nf: {config['base_url_nf']}")
    print(f"base_url_xml: {config['base_url_xml']}")
    
    # Criar cliente
    client = OmieClient(
        app_key=config["app_key"],
        app_secret=config["app_secret"],
        calls_per_second=config["calls_per_second"],
        base_url_nf=config["base_url_nf"],
        base_url_xml=config["base_url_xml"]
    )
    
    print("\n=== URLs NO CLIENTE ===")
    print(f"client.base_url_nf: {client.base_url_nf}")
    print(f"client.base_url_xml: {client.base_url_xml}")
    
    print("\n=== TESTE DE SELEÇÃO DE ENDPOINT ===")
    url_listar = client._selecionar_endpoint("ListarNF")
    url_xml = client._selecionar_endpoint("ObterNFe")
    
    print(f"ListarNF endpoint: {url_listar}")
    print(f"ObterNFe endpoint: {url_xml}")

    print("\n=== VERIFICAÇÃO HTTPS ===")
    print(f"ListarNF usa HTTPS: {url_listar.startswith('https://')}")
    print(f"ObterNFe usa HTTPS: {url_xml.startswith('https://')}")

if __name__ == "__main__":
    asyncio.run(test_urls())
