#!/usr/bin/env python3
"""
Teste simples da API Omie para verificar conectividade básica.
"""

import asyncio
import aiohttp
import time
from src.omie_client_async import carregar_configuracoes, OmieClient

async def testar_api_simples():
    """Testa uma única chamada à API Omie de forma ultra conservadora."""
    print("🔧 Testando conectividade básica com a API Omie...")
    
    try:
        # Carrega configurações
        config = carregar_configuracoes()
        
        # Cria cliente
        client = OmieClient(
            app_key=config["app_key"],
            app_secret=config["app_secret"],
            calls_per_second=1  # Ultra conservador
        )
        
        print("📋 Fazendo uma única chamada de teste...")
        
        # Teste com uma única requisição de listagem (menos restritiva que XML)
        payload = {
            'pagina': 1,
            'registros_por_pagina': 1,
            'apenas_importado_api': 'N',
            'dEmiInicial': '18/07/2025',  # Usando as datas do config
            'dEmiFinal': '31/07/2025',
            'tpNF': 1,
            'tpAmb': 1,
            'cDetalhesPedido': 'N',
            'cApenasResumo': 'S',
            'ordenar_por': 'CODIGO',
        }
        
        timeout_config = aiohttp.ClientTimeout(total=120, connect=15)
        
        async with aiohttp.ClientSession(timeout=timeout_config) as session:
            inicio = time.time()
            resposta = await client.call_api(session, "ListarNF", payload)
            tempo_total = time.time() - inicio
            
            print(f"✅ Sucesso! Tempo: {tempo_total:.2f}s")
            print(f"📊 Resposta contém {len(resposta.get('nfCadastro', []))} registros")
            return True
            
    except Exception as e:
        print(f"❌ Falha: {e}")
        return False

async def main():
    """Execução principal do teste."""
    print("🚀 TESTE DE CONECTIVIDADE API OMIE")
    print("=" * 50)
    
    sucesso = await testar_api_simples()
    
    if sucesso:
        print("\n✅ API está respondendo normalmente!")
        print("💡 Problema pode estar no rate limiting específico para XMLs")
    else:
        print("\n❌ API não está respondendo")
        print("💡 Pode haver instabilidade temporária no servidor Omie")

if __name__ == "__main__":
    asyncio.run(main())
