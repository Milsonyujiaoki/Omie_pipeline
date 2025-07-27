#!/usr/bin/env python3
"""
Teste de download de um único XML para identificar rate limiting específico.
"""

import asyncio
import aiohttp
import time
from src.omie_client_async import carregar_configuracoes, OmieClient

async def testar_download_xml():
    """Testa download de um único XML com rate limiting ultra conservador."""
    print("🔧 Testando download específico de XML...")
    
    try:
        # Carrega configurações
        config = carregar_configuracoes()
        
        # Cria cliente com rate limiting MUITO conservador para XML
        client = OmieClient(
            app_key=config["app_key"],
            app_secret=config["app_secret"],
            calls_per_second=0.2  # 1 call a cada 5 segundos!
        )
        
        print("📋 Primeiro: Buscando um ID de NF para testar...")
        
        # Primeiro, obter um ID de nota fiscal válido
        payload_lista = {
            'pagina': 1,
            'registros_por_pagina': 1,
            'apenas_importado_api': 'N',
            'dEmiInicial': '21/07/2025',
            'dEmiFinal': '31/07/2025',
            'tpNF': 1,
            'tpAmb': 1,
            'cDetalhesPedido': 'N',
            'cApenasResumo': 'S',
            'ordenar_por': 'CODIGO',
        }
        
        timeout_config = aiohttp.ClientTimeout(total=180, connect=20)
        
        async with aiohttp.ClientSession(timeout=timeout_config) as session:
            # 1. Buscar um ID válido
            print(" Buscando nota fiscal...")
            resposta_lista = await client.call_api(session, "ListarNF", payload_lista)
            
            if not resposta_lista.get('nfCadastro'):
                print("❌ Nenhuma nota fiscal encontrada no período")
                return False
                
            nf = resposta_lista['nfCadastro'][0]
            nf_id = nf.get('nIdNfe')
            chave_nfe = nf.get('cChaveNFe', 'Não informada')
            
            print(f"✅ NF encontrada - ID: {nf_id}, Chave: {chave_nfe[:10]}...")
            
            # 2. Aguardar antes do download do XML (ultra conservador)
            print("⏳ Aguardando 10 segundos antes do download do XML...")
            await asyncio.sleep(10)
            
            # 3. Tentar baixar o XML
            print("📥 Baixando XML...")
            payload_xml = {'nIdNfe': nf_id}
            
            inicio = time.time()
            resposta_xml = await client.call_api(session, "ObterNfe", payload_xml)
            tempo_total = time.time() - inicio
            
            # 4. Validar resposta
            xml_content = resposta_xml.get('cXmlNFe')
            if xml_content:
                tamanho_xml = len(xml_content)
                print(f"✅ XML baixado com sucesso!")
                print(f" Tempo: {tempo_total:.2f}s")
                print(f"📏 Tamanho: {tamanho_xml:,} caracteres")
                return True
            else:
                print("❌ XML não retornado na resposta")
                return False
            
    except Exception as e:
        print(f"❌ Falha: {e}")
        return False

async def main():
    """Execução principal do teste."""
    print("🚀 TESTE DE DOWNLOAD DE XML INDIVIDUAL")
    print("=" * 50)
    
    sucesso = await testar_download_xml()
    
    if sucesso:
        print("\n✅ Download de XML funcionou!")
        print("💡 Rate limiting de 0.2 req/s (5s entre calls) pode ser adequado")
    else:
        print("\n❌ Falha no download de XML")
        print("💡 Pode precisar de rate limiting ainda mais conservador")

if __name__ == "__main__":
    asyncio.run(main())
