#!/usr/bin/env python3
"""
Teste com detecção de redirecionamento
"""

import asyncio
import aiohttp
import logging
from src.omie_client_async import OmieClient, carregar_configuracoes

# Configurar logging
logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

async def test_redirect():
    """Testa redirecionamentos da API"""
    try:
        config = carregar_configuracoes()
        
        client = OmieClient(
            app_key=config["app_key"],
            app_secret=config["app_secret"],
            calls_per_second=config["calls_per_second"],
            base_url_nf=config["base_url_nf"],
            base_url_xml=config["base_url_xml"]
        )
        
        print("Testando API com detecção de redirecionamento...")
        
        async with aiohttp.ClientSession() as session:
            payload = {
                'nIdNF': 10216888900,
                'cChaveNFe': '35250559162462000107550010000001821002527191',
                'tpAmb': 1
            }
            
            result = await client.call_api(session, "ObterXMLNFe", payload)
            print(f"Sucesso: {result}")
            
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    asyncio.run(test_redirect())
