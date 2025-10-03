#!/usr/bin/env python3
"""
DIAGNÓSTICO DETALHADO - API STATUS NFE
Testa e diagnostica problemas na consulta de status da API Omie.
"""

import sys
import asyncio
import aiohttp
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.omie_client_async import carregar_configuracoes_client
from src.utils import conexao_otimizada


def configurar_logging_debug():
    """Configura logging em modo debug."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f'log/diagnostico_api_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        ]
    )


async def testar_api_individual():
    """Testa consulta individual de uma NFe específica."""
    
    print("🔍 TESTE 1: CONSULTA INDIVIDUAL DE NFE")
    print("=" * 60)
    
    try:
        # Pega uma nota do banco para testar
        with conexao_otimizada("omie.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT cChaveNFe, nIdNF 
                FROM notas 
                WHERE xml_baixado = 1 
                  AND erro = 0
                  AND cChaveNFe IS NOT NULL
                  AND nIdNF IS NOT NULL
                ORDER BY dEmi DESC 
                LIMIT 5
            """)
            
            registros = cursor.fetchall()
            
        if not registros:
            print("❌ Nenhum registro encontrado para teste")
            return False
        
        # Carrega configurações
        config = carregar_configuracoes_client()
        
        print(f"📋 Testando com {len(registros)} registros:")
        
        async with aiohttp.ClientSession() as session:
            for i, (chave_nfe, nid_nf) in enumerate(registros, 1):
                print(f"\n🔸 Teste {i}/5:")
                print(f"   Chave: {chave_nfe}")
                print(f"   ID: {nid_nf}")
                
                # Testa consulta por ID (preferencial)
                payload_id = {
                    "app_key": config["app_key"],
                    "app_secret": config["app_secret"],
                    "call": "ObterNfe",
                    "param": [{"nIdNF": nid_nf}]
                }
                
                try:
                    print(f"   📡 Consultando por ID...")
                    async with session.post(
                        config["base_url_nf"],
                        json=payload_id,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        print(f"   Status HTTP: {response.status}")
                        
                        if response.status == 200:
                            data = await response.json()
                            
                            if "faultstring" in data:
                                print(f"   ❌ Erro API: {data['faultstring']}")
                                print(f"   Código: {data.get('faultcode', 'N/A')}")
                                
                                # Tenta por chave se falhou por ID
                                print(f"   📡 Tentando por chave...")
                                payload_chave = {
                                    "app_key": config["app_key"],
                                    "app_secret": config["app_secret"],
                                    "call": "ObterNfe",
                                    "param": [{"cChaveNFe": chave_nfe}]
                                }
                                
                                async with session.post(
                                    config["base_url_nf"],
                                    json=payload_chave,
                                    timeout=aiohttp.ClientTimeout(total=30)
                                ) as response2:
                                    if response2.status == 200:
                                        data2 = await response2.json()
                                        if "faultstring" in data2:
                                            print(f"   ❌ Erro por chave: {data2['faultstring']}")
                                        else:
                                            print(f"   ✅ Sucesso por chave!")
                                            print(f"   Campos retornados: {list(data2.keys())}")
                                            
                                            # Mostra dados relevantes
                                            for campo in ["situacao", "cSitNFe", "xMotivo", "tpNF", "tpAmb"]:
                                                if campo in data2:
                                                    print(f"   {campo}: {data2[campo]}")
                                    
                            else:
                                print(f"   ✅ Sucesso por ID!")
                                print(f"   Campos retornados: {list(data.keys())}")
                                
                                # Mostra dados relevantes
                                for campo in ["situacao", "cSitNFe", "xMotivo", "tpNF", "tpAmb"]:
                                    if campo in data:
                                        print(f"   {campo}: {data[campo]}")
                        else:
                            print(f"   ❌ Status HTTP inválido: {response.status}")
                            
                except Exception as e:
                    print(f"   ❌ Erro na requisição: {e}")
                
                # Pausa entre testes
                await asyncio.sleep(2)
        
        return True
        
    except Exception as e:
        print(f"❌ Erro geral no teste: {e}")
        return False


async def testar_api_listagem():
    """Testa o endpoint de listagem de NFe."""
    
    print("\n🔍 TESTE 2: LISTAGEM DE NFES EMITIDAS")
    print("=" * 60)
    
    try:
        config = carregar_configuracoes_client()
        
        # Teste com período recente
        filtros = {
            "pagina": 1,
            "registros_por_pagina": 10,
            "data_inicial": "01/08/2025",
            "data_final": "31/08/2025"
        }
        
        payload = {
            "app_key": config["app_key"],
            "app_secret": config["app_secret"],
            "call": "ListarNFesEmitidas",
            "param": filtros
        }
        
        print(f"📋 Filtros de teste:")
        for k, v in filtros.items():
            print(f"   {k}: {v}")
        
        async with aiohttp.ClientSession() as session:
            print(f"\n📡 Enviando requisição...")
            
            async with session.post(
                "https://app.omie.com.br/api/v1/nfe/",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                print(f"Status HTTP: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    
                    if "faultstring" in data:
                        print(f"❌ Erro API: {data['faultstring']}")
                        print(f"Código: {data.get('faultcode', 'N/A')}")
                        return False
                    else:
                        print(f"✅ Sucesso na listagem!")
                        print(f"Campos principais: {list(data.keys())}")
                        
                        if "total_de_registros" in data:
                            print(f"Total de registros: {data['total_de_registros']:,}")
                        
                        if "nfes_emitidas" in data and data["nfes_emitidas"]:
                            print(f"NFes retornadas: {len(data['nfes_emitidas'])}")
                            
                            # Analisa primeira NFe
                            primeira_nfe = data["nfes_emitidas"][0]
                            print(f"\n📄 Primeira NFe:")
                            print(f"   Campos: {list(primeira_nfe.keys())}")
                            
                            for campo in ["cChaveNFe", "nIdNF", "situacao", "cSitNFe", "xMotivo"]:
                                if campo in primeira_nfe:
                                    valor = primeira_nfe[campo]
                                    if isinstance(valor, str) and len(valor) > 50:
                                        valor = valor[:50] + "..."
                                    print(f"   {campo}: {valor}")
                        else:
                            print("⚠️ Nenhuma NFe retornada no período")
                            
                        return True
                else:
                    print(f"❌ Status HTTP inválido: {response.status}")
                    text = await response.text()
                    print(f"Resposta: {text[:500]}...")
                    return False
        
    except Exception as e:
        print(f"❌ Erro no teste de listagem: {e}")
        return False


def verificar_estrutura_banco():
    """Verifica a estrutura do banco e dados."""
    
    print("\n🔍 TESTE 3: ESTRUTURA DO BANCO")
    print("=" * 60)
    
    try:
        with conexao_otimizada("omie.db") as conn:
            cursor = conn.cursor()
            
            # Verifica estrutura da tabela
            cursor.execute("PRAGMA table_info(notas)")
            colunas = cursor.fetchall()
            
            print("📋 Colunas da tabela 'notas':")
            for col in colunas:
                print(f"   {col[1]:<20} {col[2]:<10} {col[3]}")
            
            # Estatísticas gerais
            print(f"\n📊 Estatísticas:")
            
            queries_stats = [
                ("Total de registros", "SELECT COUNT(*) FROM notas"),
                ("Com XML baixado", "SELECT COUNT(*) FROM notas WHERE xml_baixado = 1"),
                ("Sem erro", "SELECT COUNT(*) FROM notas WHERE erro = 0"),
                ("Com chave NFe", "SELECT COUNT(*) FROM notas WHERE cChaveNFe IS NOT NULL AND cChaveNFe != ''"),
                ("Com ID NFe", "SELECT COUNT(*) FROM notas WHERE nIdNF IS NOT NULL"),
                ("Com status", "SELECT COUNT(*) FROM notas WHERE status IS NOT NULL AND status != ''"),
                ("Status NULL/vazio", "SELECT COUNT(*) FROM notas WHERE status IS NULL OR status = ''"),
            ]
            
            for descricao, query in queries_stats:
                cursor.execute(query)
                resultado = cursor.fetchone()[0]
                print(f"   {descricao:<20}: {resultado:,}")
            
            # Amostra de registros elegíveis
            print(f"\n📋 Amostra de registros elegíveis:")
            cursor.execute("""
                SELECT cChaveNFe, nIdNF, status, dEmi, nNF
                FROM notas 
                WHERE (status IS NULL OR status = '' OR status = 'INDEFINIDO')
                  AND xml_baixado = 1 
                  AND erro = 0
                  AND cChaveNFe IS NOT NULL
                  AND nIdNF IS NOT NULL
                ORDER BY dEmi DESC 
                LIMIT 5
            """)
            
            registros = cursor.fetchall()
            for i, reg in enumerate(registros, 1):
                chave = reg[0][:20] + "..." if reg[0] else "NULL"
                print(f"   {i}. Chave: {chave} | ID: {reg[1]} | Status: {reg[2]} | Data: {reg[3]} | Num: {reg[4]}")
            
            if not registros:
                print("   ⚠️ Nenhum registro elegível encontrado!")
                
                # Verifica por que não há registros elegíveis
                print(f"\n🔍 Diagnóstico de elegibilidade:")
                
                checks = [
                    ("Registros totais", "SELECT COUNT(*) FROM notas"),
                    ("XML não baixado", "SELECT COUNT(*) FROM notas WHERE xml_baixado != 1"),
                    ("Com erro", "SELECT COUNT(*) FROM notas WHERE erro != 0"),
                    ("Chave NFe nula", "SELECT COUNT(*) FROM notas WHERE cChaveNFe IS NULL OR cChaveNFe = ''"),
                    ("ID NFe nulo", "SELECT COUNT(*) FROM notas WHERE nIdNF IS NULL"),
                    ("Já tem status", "SELECT COUNT(*) FROM notas WHERE status IS NOT NULL AND status != '' AND status != 'INDEFINIDO'"),
                ]
                
                for desc, query in checks:
                    cursor.execute(query)
                    count = cursor.fetchone()[0]
                    print(f"   {desc}: {count:,}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao verificar banco: {e}")
        return False


async def main():
    """Executa todos os testes de diagnóstico."""
    
    print("🔧 DIAGNÓSTICO DETALHADO - API STATUS NFE")
    print("=" * 70)
    print("Este script identifica problemas na consulta de status da API Omie")
    print()
    
    # Configura logging detalhado
    from datetime import datetime
    configurar_logging_debug()
    
    resultados = []
    
    # Teste 1: Estrutura do banco
    print("INICIANDO TESTES...")
    resultado1 = verificar_estrutura_banco()
    resultados.append(("Estrutura do Banco", resultado1))
    
    # Teste 2: API Individual 
    resultado2 = await testar_api_individual()
    resultados.append(("API Individual", resultado2))
    
    # Teste 3: API Listagem
    resultado3 = await testar_api_listagem()
    resultados.append(("API Listagem", resultado3))
    
    # Relatório final
    print("\n" + "=" * 70)
    print("📋 RELATÓRIO FINAL DO DIAGNÓSTICO")
    print("=" * 70)
    
    todos_ok = True
    for teste, resultado in resultados:
        status = "✅ PASSOU" if resultado else "❌ FALHOU"
        print(f"   {teste:<20} {status}")
        if not resultado:
            todos_ok = False
    
    print(f"\n{'='*70}")
    
    if todos_ok:
        print("✅ TODOS OS TESTES PASSARAM!")
        print("\nO problema pode estar na lógica de processamento ou filtros.")
        print("Verifique se as condições de elegibilidade estão corretas.")
    else:
        print("❌ ALGUNS TESTES FALHARAM!")
        print("\nProblemas identificados que podem estar causando o erro:")
        
        for teste, resultado in resultados:
            if not resultado:
                if "Banco" in teste:
                    print("   • Verifique se há registros elegíveis para atualização")
                elif "Individual" in teste:
                    print("   • API individual não está retornando dados esperados")
                elif "Listagem" in teste:
                    print("   • API de listagem com problemas")
    
    print(f"{'='*70}")


if __name__ == "__main__":
    asyncio.run(main())
