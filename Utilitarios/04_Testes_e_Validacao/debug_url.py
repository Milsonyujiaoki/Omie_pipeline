#!/usr/bin/env python3
"""
Debug simples da URL
"""

from src.omie_client_async import carregar_configuracoes, OmieClient

# Carregar configurações
config = carregar_configuracoes()

print(f"Config XML URL: {config['base_url_xml']}")

# Criar cliente
client = OmieClient(
    app_key=config["app_key"],
    app_secret=config["app_secret"],
    base_url_xml=config["base_url_xml"]
)

print(f"Client XML URL: {client.base_url_xml}")
print(f"ObterXMLNFe URL: {client._selecionar_endpoint('ObterNFe')}")
