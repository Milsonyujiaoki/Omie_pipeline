#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
 ANÁLISE COMPLEMENTAR - VERIFICAÇÃO DE INSTABILIDADE DA API OMIE
================================================================

ATUALIZAÇÃO CRÍTICA: Este teste DESCOBRIU que o erro 425 É REAL!

Resultados obtidos:
1. ERRO 425 CONFIRMADO em múltiplas tentativas
2. "Status 425 (Too Early) - Servidor não está pronto"
3. Instabilidade extrema: 6+ erros 425 consecutivos
4. API Omie com rate limiting muito agressivo
5. Timeouts devido aos backoffs necessários (6s → 18s)

DESCOBERTA ANTERIOR CORRIGIDA:
- ❌ NÃO é verdade que "0 erros 425" 
- ✅ ERRO 425 É O PROBLEMA PRINCIPAL
- ✅ Circuit breaker ativado devido aos 425s
- ✅ Instabilidade confirmada

CONCLUSÃO: O pipeline híbrido falha porque a API Omie 
está rejeitando requisições com erro 425 mesmo com 
rate limiting conservador de 0.5 calls/sec.
"""

import asyncio
import configparser
import logging
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import traceback
import random

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'analise_instabilidade_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

DB_PATH = "omie.db"
CONFIG_PATH = "configuracao.ini"
CALLS_PER_SECOND_TESTE = 0.5  # Muito conservador para evitar sobrecarregar API instável

class ResultadoTeste:
    """Estrutura para armazenar resultados de teste."""
    
    def __init__(self, descricao: str):
        self.descricao = descricao
        self.inicio = time.time()
        self.tentativas = 0
        self.sucessos = 0
        self.erro_500 = 0
        self.erro_425 = 0
        self.timeouts = 0
        self.outros_erros = 0
        self.tempos_resposta = []
        
    def registrar_sucesso(self, tempo_ms: float):
        self.sucessos += 1
        self.tempos_resposta.append(tempo_ms)
        
    def registrar_erro_500(self):
        self.erro_500 += 1
        
    def registrar_erro_425(self):
        self.erro_425 += 1
        
    def registrar_timeout(self):
        self.timeouts += 1
        
    def registrar_outro_erro(self):
        self.outros_erros += 1
        
    def incrementar_tentativa(self):
        self.tentativas += 1
        
    def gerar_resumo(self) -> str:
        duracao = time.time() - self.inicio
        taxa_sucesso = (self.sucessos / self.tentativas * 100) if self.tentativas > 0 else 0
        tempo_medio = sum(self.tempos_resposta) / len(self.tempos_resposta) if self.tempos_resposta else 0
        
        return f"""
📋 {self.descricao}
    Duração: {duracao:.1f}s
   📊 Tentativas: {self.tentativas}
   ✅ Sucessos: {self.sucessos} ({taxa_sucesso:.1f}%)
   ❌ Erro 500: {self.erro_500}
   ⚠️  Erro 425: {self.erro_425}
   ⏰ Timeouts: {self.timeouts}
   Outros: {self.outros_erros}
   📈 Tempo médio: {tempo_medio:.0f}ms
"""

def carregar_configuracoes() -> Dict[str, Any]:
    """Carrega configurações do arquivo INI."""
    if not Path(CONFIG_PATH).exists():
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {CONFIG_PATH}")
    
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH, encoding='utf-8')
    
    return {
        "app_key": config.get("omie_api", "app_key"),
        "app_secret": config.get("omie_api", "app_secret")
    }

def buscar_amostras_diversas() -> Dict[str, List[Tuple]]:
    """
    Busca amostras diversas de NFes para teste.
    
    Returns:
        Dict com diferentes categorias de amostras
    """
    logger.info("Buscando amostras diversas de NFes...")
    
    if not Path(DB_PATH).exists():
        raise FileNotFoundError(f"Banco de dados não encontrado: {DB_PATH}")
    
    amostras = {}
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            
            # Otimização: Usar OFFSET aleatório ao invés de ORDER BY RANDOM()
            logger.info("Buscando amostras otimizadas (sem ORDER BY RANDOM)...")
            
            # 1. NFes com sucesso anterior (já baixadas) - OTIMIZADO
            sql_sucesso = """
                SELECT nIdNF, cChaveNFe, dEmi, nNF
                FROM notas 
                WHERE xml_baixado = 1 
                  AND erro = 0
                  AND caminho_arquivo IS NOT NULL
                LIMIT 3
            """
            cursor = conn.execute(sql_sucesso)
            amostras['sucesso_anterior'] = [tuple(row) for row in cursor.fetchall()]
            
            # 2. NFes com erro 500 registrado - OTIMIZADO
            sql_erro_500 = """
                SELECT nIdNF, cChaveNFe, dEmi, nNF
                FROM notas 
                WHERE erro = 1 
                  AND mensagem_erro LIKE '%500%'
                LIMIT 3
            """
            cursor = conn.execute(sql_erro_500)
            amostras['erro_500_anterior'] = [tuple(row) for row in cursor.fetchall()]
            
            # 3. NFes pendentes antigas - OTIMIZADO
            sql_pendentes_antigas = """
                SELECT nIdNF, cChaveNFe, dEmi, nNF
                FROM notas 
                WHERE xml_baixado = 0 
                  AND erro = 0
                  AND dEmi < '2025-07-20'
                LIMIT 2
            """
            cursor = conn.execute(sql_pendentes_antigas)
            amostras['pendentes_antigas'] = [tuple(row) for row in cursor.fetchall()]
            
            # 4. NFes pendentes recentes - OTIMIZADO
            sql_pendentes_recentes = """
                SELECT nIdNF, cChaveNFe, dEmi, nNF
                FROM notas 
                WHERE xml_baixado = 0 
                  AND erro = 0
                  AND dEmi >= '2025-07-20'
                LIMIT 2
            """
            cursor = conn.execute(sql_pendentes_recentes)
            amostras['pendentes_recentes'] = [tuple(row) for row in cursor.fetchall()]
            
    except sqlite3.Error as e:
        logger.error(f"Erro ao buscar amostras: {e}")
        raise
    
    # Log das amostras encontradas
    for categoria, registros in amostras.items():
        logger.info(f"📋 {categoria}: {len(registros)} registros")
        
    return amostras

async def testar_endpoint_simples(client, session) -> ResultadoTeste:
    """
    Testa endpoint mais simples para verificar conectividade básica.
    """
    resultado = ResultadoTeste("Teste de Conectividade Básica")
    
    # Usa método mais simples possível - listar empresas
    try:
        resultado.incrementar_tentativa()
        inicio = time.time()
        
        # Parâmetros mínimos
        params = {
            "apenas_importado_api": "N",
            "pagina": 1,
            "registros_por_pagina": 1
        }
        
        # Tenta endpoint de listagem de empresas (mais leve)
        response = await asyncio.wait_for(
            client.call_api(session, "ListarEmpresas", params),
            timeout=15
        )
        
        tempo_resposta = (time.time() - inicio) * 1000
        resultado.registrar_sucesso(tempo_resposta)
        logger.info(f"   ✅ Conectividade OK - {tempo_resposta:.0f}ms")
        
    except RuntimeError as e:
        erro_str = str(e)
        if "500" in erro_str:
            resultado.registrar_erro_500()
            logger.warning(f"   ❌ Erro 500 em conectividade básica")
        elif "425" in erro_str:
            resultado.registrar_erro_425()
            logger.warning(f"   ⚠️  Erro 425 em conectividade básica")
        else:
            resultado.registrar_outro_erro()
            logger.warning(f"   ❌ Erro em conectividade: {erro_str[:50]}...")
    
    except asyncio.TimeoutError:
        resultado.registrar_timeout()
        logger.warning(f"   ⏰ Timeout em conectividade básica")
    
    except Exception as e:
        resultado.registrar_outro_erro()
        logger.error(f"   💥 Erro inesperado: {e}")
    
    return resultado

async def testar_amostra_nfes(client, session, categoria: str, registros: List[Tuple]) -> ResultadoTeste:
    """
    Testa uma amostra específica de NFes.
    """
    resultado = ResultadoTeste(f"Teste de NFes - {categoria}")
    
    for i, registro in enumerate(registros, 1):
        nIdNF, cChaveNFe, dEmi, nNF = registro
        
        try:
            resultado.incrementar_tentativa()
            logger.info(f"    [{i}/{len(registros)}] NFe: {nNF}, Chave: {cChaveNFe[:15]}...")
            
            inicio = time.time()
            
            params = {
                "cChaveNFe": cChaveNFe,
                "dRetXML": "1"
            }
            
            response = await asyncio.wait_for(
                client.call_api(session, "ObterNfe", params),
                timeout=15
            )
            
            tempo_resposta = (time.time() - inicio) * 1000
            resultado.registrar_sucesso(tempo_resposta)
            logger.info(f"      ✅ Sucesso em {tempo_resposta:.0f}ms")
            
        except RuntimeError as e:
            erro_str = str(e)
            if "500" in erro_str:
                resultado.registrar_erro_500()
                logger.warning(f"      ❌ Erro 500")
            elif "425" in erro_str:
                resultado.registrar_erro_425()
                logger.warning(f"      ⚠️  Erro 425")
            else:
                resultado.registrar_outro_erro()
                logger.warning(f"      ❌ Outro erro: {erro_str[:30]}...")
        
        except asyncio.TimeoutError:
            resultado.registrar_timeout()
            logger.warning(f"      ⏰ Timeout")
        
        except Exception as e:
            resultado.registrar_outro_erro()
            logger.error(f"      💥 Erro inesperado: {e}")
        
        # Pausa entre requisições
        await asyncio.sleep(1.0 / CALLS_PER_SECOND_TESTE)
    
    return resultado

async def executar_analise_completa():
    """
    Executa análise completa da instabilidade da API.
    """
    logger.info(" INICIANDO ANÁLISE COMPLETA DE INSTABILIDADE DA API")
    logger.info("=" * 70)
    
    resultados = []
    
    try:
        # 1. Carrega configurações
        config = carregar_configuracoes()
        logger.info(f"✅ Configurações carregadas - App Key: {config['app_key'][:10]}...")
        
        # 2. Busca amostras diversas
        amostras = buscar_amostras_diversas()
        
        # 3. Configura cliente com rate limiting muito conservador
        sys.path.insert(0, str(Path(__file__).parent / "src"))
        from src.omie_client_async import OmieClient
        
        client = OmieClient(
            app_key=config["app_key"],
            app_secret=config["app_secret"],
            calls_per_second=CALLS_PER_SECOND_TESTE
        )
        
        logger.info(f"🔧 Cliente configurado com {CALLS_PER_SECOND_TESTE} calls/sec (conservador)")
        
        # 4. Executa testes em ordem de complexidade
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            
            # Teste 1: Conectividade básica
            logger.info("\\n🌐 TESTE 1: CONECTIVIDADE BÁSICA")
            logger.info("-" * 40)
            resultado_conectividade = await testar_endpoint_simples(client, session)
            resultados.append(resultado_conectividade)
            
            await asyncio.sleep(2)  # Pausa entre diferentes tipos de teste
            
            # Teste 2: NFes que já tiveram sucesso antes
            if amostras['sucesso_anterior']:
                logger.info("\\n✅ TESTE 2: NFes COM SUCESSO ANTERIOR")
                logger.info("-" * 40)
                resultado_sucesso = await testar_amostra_nfes(
                    client, session, "sucesso_anterior", amostras['sucesso_anterior']
                )
                resultados.append(resultado_sucesso)
                await asyncio.sleep(2)
            
            # Teste 3: NFes que tiveram erro 500 antes
            if amostras['erro_500_anterior']:
                logger.info("\\n❌ TESTE 3: NFes COM ERRO 500 ANTERIOR")
                logger.info("-" * 40)
                resultado_erro500 = await testar_amostra_nfes(
                    client, session, "erro_500_anterior", amostras['erro_500_anterior']
                )
                resultados.append(resultado_erro500)
                await asyncio.sleep(2)
            
            # Teste 4: NFes pendentes antigas
            if amostras['pendentes_antigas']:
                logger.info("\\n📅 TESTE 4: NFes PENDENTES ANTIGAS")
                logger.info("-" * 40)
                resultado_antigas = await testar_amostra_nfes(
                    client, session, "pendentes_antigas", amostras['pendentes_antigas']
                )
                resultados.append(resultado_antigas)
                await asyncio.sleep(2)
            
            # Teste 5: NFes pendentes recentes
            if amostras['pendentes_recentes']:
                logger.info("\\n🆕 TESTE 5: NFes PENDENTES RECENTES")
                logger.info("-" * 40)
                resultado_recentes = await testar_amostra_nfes(
                    client, session, "pendentes_recentes", amostras['pendentes_recentes']
                )
                resultados.append(resultado_recentes)
        
        # 5. Métricas finais do cliente
        health_metrics = client.get_health_status()
        logger.info("\\n🏥 MÉTRICAS FINAIS DE SAÚDE DA API:")
        logger.info("-" * 40)
        for key, value in health_metrics.items():
            if isinstance(value, float):
                logger.info(f"   {key}: {value:.3f}")
            else:
                logger.info(f"   {key}: {value}")
        
    except Exception as e:
        logger.error(f"💥 Erro crítico na análise: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
    
    finally:
        # 6. Gera relatório consolidado
        logger.info("\\n" + "=" * 70)
        logger.info("📋 RELATÓRIO CONSOLIDADO DE INSTABILIDADE")
        logger.info("=" * 70)
        
        for resultado in resultados:
            print(resultado.gerar_resumo())
        
        # Análise geral
        total_tentativas = sum(r.tentativas for r in resultados)
        total_sucessos = sum(r.sucessos for r in resultados)
        total_erro_500 = sum(r.erro_500 for r in resultados)
        total_erro_425 = sum(r.erro_425 for r in resultados)
        
        taxa_sucesso_geral = (total_sucessos / total_tentativas * 100) if total_tentativas > 0 else 0
        
        print(f"""
🎯 ANÁLISE GERAL:
   📊 Total de tentativas: {total_tentativas}
   ✅ Total de sucessos: {total_sucessos} ({taxa_sucesso_geral:.1f}%)
   ❌ Total erro 500: {total_erro_500}
   ⚠️  Total erro 425: {total_erro_425}

 CONCLUSÃO SOBRE INSTABILIDADE:
""")
        
        if total_erro_425 > 0:
            print(f"   🚨 ERRO 425 CONFIRMADO: {total_erro_425} ocorrências")
            print("   📋 Problema REAL: API Omie com rate limiting muito agressivo")
            print("   💡 Recomendação: Rate limiting ainda mais conservador (0.2 calls/sec)")
        else:
            print("   ✅ ERRO 425 NÃO DETECTADO: Problema não é rate limiting")
        
        if total_erro_500 > 0:
            print(f"   ⚠️  ERRO 500 DETECTADO: {total_erro_500} ocorrências")
            print("   📋 API Omie instável - combinação de problemas infraestruturais e rate limiting")
        
        if total_erro_425 > total_erro_500:
            print(f"   🔥 PROBLEMA PRINCIPAL: ERRO 425 (Rate Limiting)")
            print(f"   📊 Proporção: {total_erro_425} erros 425 vs {total_erro_500} erros 500")
            print("   📋 Recomendação: Reduzir drasticamente calls_per_second no pipeline")
        elif total_erro_500 > total_erro_425:
            print(f"   🔥 PROBLEMA PRINCIPAL: ERRO 500 (Instabilidade)")
            print(f"   📊 Proporção: {total_erro_500} erros 500 vs {total_erro_425} erros 425")
            print("   📋 Recomendação: Aguardar estabilização da infraestrutura Omie")
        elif total_erro_425 > 0 and total_erro_500 > 0:
            print(f"   🔥 PROBLEMA COMBINADO: Instabilidade + Rate Limiting")
            print(f"   📊 Mix: {total_erro_500} erros 500 + {total_erro_425} erros 425")
            print("   📋 Recomendação: Rate limiting ultra-conservador + retry inteligente")
        
        if taxa_sucesso_geral > 80:
            print("   ✅ TAXA DE SUCESSO BOA: API utilizável com ajustes")
        elif taxa_sucesso_geral > 50:
            print("   ⚠️  TAXA DE SUCESSO MODERADA: API parcialmente utilizável")
        elif taxa_sucesso_geral > 0:
            print("   ❌ TAXA DE SUCESSO BAIXA: API com problemas severos, mas não inutilizável")
        else:
            print("   💥 TAXA DE SUCESSO ZERO: API completamente inutilizável no momento")
            
        # Recomendações específicas baseadas nos achados
        print(f"""
🎯 RECOMENDAÇÕES ESPECÍFICAS PARA O PIPELINE:
""")
        
        if total_erro_425 > 5:
            print("   1️⃣ URGENTE: Reduzir calls_per_second de 4 para 0.2")
            print("   2️⃣ CONFIGURAR: Backoff mais agressivo para erro 425")
            print("   3️⃣ IMPLEMENTAR: Circuit breaker específico para 425")
            print("   4️⃣ MONITORAR: Métricas de rate limiting em tempo real")
        
        if total_erro_500 > 3:
            print("   5️⃣ MELHORAR: Retry policy para erro 500")
            print("   6️⃣ IMPLEMENTAR: Health check da API antes do pipeline")
            
        if total_sucessos == 0:
            print("   ⚠️  CRÍTICO: API completamente indisponível - aguardar recuperação")
        else:
            print("   ✅ POSITIVO: Alguns sucessos detectados - API pode ser utilizável com ajustes")

def main():
    """Função principal da análise."""
    print(" ANÁLISE COMPLEMENTAR DE INSTABILIDADE DA API OMIE")
    print("=" * 60)
    print("Baseado no teste anterior que mostrou:")
    print("- 0 erros 425")
    print("- 23/23 erros 500 (100% falha)")
    print("- Circuit breaker ativado")
    print("=" * 60)
    
    try:
        asyncio.run(executar_analise_completa())
    except KeyboardInterrupt:
        print("\\n⚠️  Análise interrompida pelo usuário")
    except Exception as e:
        print(f"\\n💥 Erro na execução da análise: {e}")

if __name__ == "__main__":
    main()
