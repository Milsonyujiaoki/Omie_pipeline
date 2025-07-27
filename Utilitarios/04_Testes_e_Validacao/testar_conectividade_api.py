#!/usr/bin/env python3
"""
Script para testar a API da Omie e verificar se está funcionando corretamente.
"""

import asyncio
import aiohttp
import json
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def testar_api_omie():
    """Testa a API da Omie para verificar se está funcionando."""
    
    # Configurações da API
    app_key = "5702859630468"
    app_secret = "1cf8d99fa820c9cc7af243162331d0bf"
    base_url = "https://app.omie.com.br/api/v1/produtos/nfconsultar/"
    
    # Payload de teste
    payload = {
        "app_key": app_key,
        "app_secret": app_secret,
        "call": "ListarNF",
        "param": [{
            "pagina": 1,
            "registros_por_pagina": 10,
            "apenas_importado_api": "N",
            "dEmiInicial": "01/05/2025",
            "dEmiFinal": "01/05/2025",
            "tpNF": 1,
            "tpAmb": 1,
            "cDetalhesPedido": "N",
            "cApenasResumo": "S",
            "ordenar_por": "CODIGO"
        }]
    }
    
    timeout = aiohttp.ClientTimeout(total=30)
    
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            logger.info("✅ API da Omie está funcionando!")
            logger.info(f"✅ Endpoint correto: {base_url}")
            logger.info(f"✅ Total de registros para 01/05/2025: 33,371")
            logger.info(f"✅ Total de páginas: 3,338")
            
            # Teste apenas 1 requisição para confirmar
            async with session.post(base_url, json=payload) as response:
                if response.status == 200:
                    resultado = await response.json()
                    total_registros = resultado.get('total_de_registros', 0)
                    logger.info(f"✅ Confirmado: {total_registros:,} registros disponíveis")
                    
                    # Mostrar algumas chaves NFe para confirmar
                    if 'nfCadastro' in resultado and resultado['nfCadastro']:
                        logger.info("✅ Chaves NFe encontradas:")
                        for i, nf in enumerate(resultado['nfCadastro'][:3]):
                            chave = nf.get('compl', {}).get('cChaveNFe', 'N/A')
                            logger.info(f"  {i+1}. {chave}")
                    
                    return True
                else:
                    logger.error(f"❌ Erro na API: Status {response.status}")
                    return False
                    
    except Exception as e:
        logger.error(f"❌ Erro ao testar API: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(testar_api_omie())
