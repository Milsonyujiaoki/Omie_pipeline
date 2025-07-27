#!/usr/bin/env python3
"""
🧪 TESTE MELHORIAS API - Erro 500
=================================

Script para testar as melhorias implementadas para lidar com erro 500 da API Omie.
"""

import asyncio
import aiohttp
import sys
import time
from pathlib import Path

# Adiciona src ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.omie_client_async import OmieClient, carregar_configuracoes
import logging

# Configurar logging

logger = logging.getLogger(__name__)

async def test_error_500_handling():
    """Testa o tratamento melhorado de erro 500"""
    
    logger.info("🧪 Testando melhorias para erro 500...")
    
    try:
        config = carregar_configuracoes()
        
        client = OmieClient(
            app_key=config["app_key"],
            app_secret=config["app_secret"],
            calls_per_second=2,  # Reduzido
            base_url_xml=config["base_url_xml"]
        )
        
        # Testa com algumas chaves que estavam falhando
        test_cases = [
            {
                'nIdNF': 10216888900,
                'cChaveNFe': '35250559162462000107550010000001821002527191',
                'tpAmb': 1
            },
            {
                'nIdNF': 10216888914,
                'cChaveNFe': '35250559279145000116550010006344041129463998',
                'tpAmb': 1
            }
        ]
        
        sucessos = 0
        erros_500 = 0
        outros_erros = 0
        
        async with aiohttp.ClientSession() as session:
            for i, payload in enumerate(test_cases, 1):
                logger.info(f"[{i}/{len(test_cases)}] Testando XML para NFe ID: {payload['nIdNF']}")
                
                try:
                    inicio = time.time()
                    result = await client.call_api(session, "ObterXMLNFe", payload)
                    fim = time.time()
                    
                    if result.get('cXmlNFe'):
                        sucessos += 1
                        logger.info(f"✅ Sucesso em {fim-inicio:.2f}s - XML obtido")
                    else:
                        logger.warning(f"⚠️  XML vazio retornado")
                        
                except Exception as e:
                    if hasattr(e, 'status') and e.status == 500:
                        erros_500 += 1
                        logger.warning(f"❌ Erro 500 (esperado durante instabilidade)")
                    else:
                        outros_erros += 1
                        logger.error(f"❌ Outro erro: {e}")
                
                # Pausa entre testes
                await asyncio.sleep(3)
        
        # Relatório final
        total = len(test_cases)
        logger.info("=" * 50)
        logger.info("📊 RESULTADOS DO TESTE:")
        logger.info(f"   • Total de testes: {total}")
        logger.info(f"   • Sucessos: {sucessos}")
        logger.info(f"   • Erros 500: {erros_500}")
        logger.info(f"   • Outros erros: {outros_erros}")
        logger.info(f"   • Taxa de sucesso: {(sucessos/total)*100:.1f}%")
        
        if erros_500 > 0:
            logger.info("ℹ️  Erros 500 indicam instabilidade da API Omie (normal)")
            logger.info("ℹ️  As melhorias implementadas devem lidar melhor com estes erros")
        
    except Exception as e:
        logger.error(f"❌ Erro crítico no teste: {e}")

if __name__ == "__main__":
    print("🧪 TESTE DE MELHORIAS - ERRO 500")
    print("=" * 40)
    asyncio.run(test_error_500_handling())
