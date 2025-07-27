#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para testar as melhorias de erro 425 em ambiente real.

Este script faz algumas tentativas reais na API para verificar se:
1. Erros 425 são capturados corretamente  
2. Backoff agressivo funciona conforme esperado
3. Métricas são registradas adequadamente
4. Logs mostram mensagens melhoradas
"""
import asyncio
import aiohttp
import logging
import sys
import os

# Adiciona o diretório src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.omie_client_async import OmieClient, carregar_configuracoes

# Configurar logging detalhado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def testar_api_real_com_melhorias():
    """Testa melhorias de erro 425 com API real."""
    print("🧪 Testando melhorias de erro 425 com API real...")
    print("=" * 60)
    
    try:
        # Carrega configurações reais
        config = carregar_configuracoes()
        
        # Cria cliente com melhorias
        client = OmieClient(
            app_key=config["app_key"],
            app_secret=config["app_secret"],
            calls_per_second=2  # Reduzido para evitar sobrecarregar API
        )
        
        print(f"✅ Cliente criado com app_key: {config['app_key'][:10]}...")
        
        # Teste 1: Fazer algumas chamadas que podem gerar erro 425
        print("\\n📞 Fazendo chamadas de teste...")
        
        async with aiohttp.ClientSession() as session:
            # Parâmetros para obter NFe (pode gerar erro 425 se API estiver instável)
            params_teste = {
                "cChaveNFe": "35250559152594000176550010000186371834321559",  # Exemplo
                "dRetXML": "1"
            }
            
            sucesso_count = 0
            erro_425_count = 0
            erro_outros_count = 0
            
            # Faz 3 tentativas para simular uso real (reduzido para teste rápido)
            for i in range(1, 4):
                try:
                    print(f"\\nTentativa {i}/3...")
                    
                    resultado = await client.call_api(session, "ObterNfe", params_teste)
                    print(f"   ✅ Sucesso: {len(str(resultado))} chars de resposta")
                    sucesso_count += 1
                    
                    # Pequena pausa entre chamadas
                    await asyncio.sleep(1)
                    
                except RuntimeError as e:
                    if "425" in str(e) or "Too Early" in str(e):
                        print(f"   ⚠️  Erro 425 capturado: {str(e)[:50]}...")
                        erro_425_count += 1
                    else:
                        print(f"   ❌ Outro erro: {str(e)[:50]}...")
                        erro_outros_count += 1
                
                except Exception as e:
                    print(f"   💥 Erro inesperado: {str(e)[:50]}...")
                    erro_outros_count += 1
        
        # Mostra estatísticas
        print("\\n📊 Estatísticas do teste:")
        print(f"   Sucessos: {sucesso_count}")
        print(f"   Erros 425: {erro_425_count}")
        print(f"   Outros erros: {erro_outros_count}")
        
        # Mostra métricas de saúde do cliente
        health = client.get_health_status()
        print("\\n🏥 Métricas de saúde da API:")
        for key, value in health.items():
            if isinstance(value, float):
                print(f"   {key}: {value:.2f}")
            else:
                print(f"   {key}: {value}")
        
        # Teste específico das funcionalidades
        print("\\n Teste de funcionalidades específicas:")
        
        # Simula erro 425 nas métricas
        print("   Simulando 3 erros 425 consecutivos...")
        for i in range(3):
            client.health_metrics.record_425_error()
        
        print(f"   Instabilidade detectada: {client.health_metrics.instability_detected}")
        print(f"   Erros 425 consecutivos: {client.health_metrics.consecutive_425_errors}")
        print(f"   Deve usar backoff agressivo: {client.health_metrics.should_use_aggressive_backoff()}")
        
        # Simula sucesso para reset
        print("   Simulando sucesso para reset...")
        client.health_metrics.record_success()
        print(f"   Instabilidade após reset: {client.health_metrics.instability_detected}")
        
        print("\\n" + "=" * 60)
        print("✅ Teste completado! Verifique os logs acima.")
        
        # Recomendações baseadas no teste
        if erro_425_count > 0:
            print("\\n💡 Recomendações:")
            print("   - Erros 425 foram detectados, indicando que API estava instável")
            print("   - As melhorias devem ajudar com backoff mais agressivo")
            print("   - Monitore logs em produção para ver mensagens melhoradas")
        else:
            print("\\n💡 Observação:")
            print("   - Nenhum erro 425 detectado neste teste")
            print("   - API pode estar estável no momento")
            print("   - Melhorias estão prontas para quando erros 425 ocorrerem")
    
    except Exception as e:
        print(f"\\n❌ Erro durante teste: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Executa o teste principal."""
    await testar_api_real_com_melhorias()

if __name__ == "__main__":
    asyncio.run(main())
