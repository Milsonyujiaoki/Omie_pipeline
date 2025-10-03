#!/usr/bin/env python3
"""
TESTE SIMPLES DE STATUS NFE
Teste com apenas algumas notas e logging detalhado.
"""

import sys
import asyncio
import aiohttp
import sqlite3
import logging
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.omie_client_async import carregar_configuracoes_client
from src.utils import conexao_otimizada

# Configura logging detalhado
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def teste_simples_status():
    """Teste simples com 3 notas específicas."""
    
    print("🧪 TESTE SIMPLES - STATUS NFE")
    print("=" * 50)
    
    try:
        # Pega 3 notas do banco
        with conexao_otimizada("omie.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT cChaveNFe, nIdNF, nNF, dEmi
                FROM notas 
                WHERE xml_baixado = 1 
                  AND erro = 0
                  AND cChaveNFe IS NOT NULL
                  AND nIdNF IS NOT NULL
                  AND (status IS NULL OR status = '' OR status = 'INDEFINIDO')
                ORDER BY dEmi DESC 
                LIMIT 3
            """)
            
            notas = cursor.fetchall()
        
        if not notas:
            print("❌ Nenhuma nota elegível encontrada")
            return False
        
        print(f"📋 Testando {len(notas)} notas:")
        for i, (chave, nid, num, data) in enumerate(notas, 1):
            print(f"   {i}. NFe {num} - ID {nid} - {data}")
        
        # Carrega configurações
        config = carregar_configuracoes_client()
        logger.info(f"Config carregada: app_key={config['app_key'][:10]}...")
        
        # Processa cada nota individualmente
        resultados = []
        
        async with aiohttp.ClientSession() as session:
            for i, (chave_nfe, nid_nf, num_nf, data_emi) in enumerate(notas, 1):
                print(f"\n🔸 Processando nota {i}/3:")
                print(f"   NFe: {num_nf}")
                print(f"   ID: {nid_nf}")
                print(f"   Chave: {chave_nfe[:20]}...")
                
                try:
                    # Monta payload
                    payload = {
                        "app_key": config["app_key"],
                        "app_secret": config["app_secret"],
                        "call": "ObterNfe",
                        "param": [{"nIdNF": nid_nf}]
                    }
                    
                    logger.debug(f"Payload: {payload}")
                    
                    # Faz requisição
                    print(f"   📡 Fazendo requisição...")
                    async with session.post(
                        config["base_url_nf"],
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        
                        print(f"   Status HTTP: {response.status}")
                        logger.debug(f"Headers: {dict(response.headers)}")
                        
                        if response.status == 200:
                            data = await response.json()
                            logger.debug(f"Resposta: {data}")
                            
                            if "faultstring" in data:
                                print(f"   ❌ Erro API: {data['faultstring']}")
                                print(f"   Código: {data.get('faultcode', 'N/A')}")
                                resultados.append((nid_nf, "ERRO_API", data['faultstring']))
                            else:
                                print(f"   ✅ Dados recebidos!")
                                
                                # Analisa campos de status
                                campos_status = {}
                                for campo in ["situacao", "cSitNFe", "xMotivo", "tpNF", "tpAmb"]:
                                    if campo in data:
                                        campos_status[campo] = data[campo]
                                        print(f"   {campo}: {data[campo]}")
                                
                                # Extrai status
                                status_encontrado = None
                                if "situacao" in data:
                                    status_encontrado = data["situacao"]
                                elif "xMotivo" in data:
                                    status_encontrado = data["xMotivo"]
                                
                                status_normalizado = normalizar_status_simples(status_encontrado)
                                print(f"   Status extraído: {status_encontrado}")
                                print(f"   Status normalizado: {status_normalizado}")
                                
                                # Testa atualização no banco
                                sucesso_update = await atualizar_banco_teste(chave_nfe, status_normalizado)
                                print(f"   Atualização banco: {'✅' if sucesso_update else '❌'}")
                                
                                resultados.append((nid_nf, status_normalizado, campos_status))
                        else:
                            print(f"   ❌ Status HTTP {response.status}")
                            text = await response.text()
                            logger.debug(f"Resposta: {text}")
                            resultados.append((nid_nf, "ERRO_HTTP", response.status))
                
                except Exception as e:
                    print(f"   ❌ Erro: {e}")
                    logger.exception(f"Erro detalhado para NFe {nid_nf}")
                    resultados.append((nid_nf, "ERRO_EXCECAO", str(e)))
                
                # Pausa entre requisições
                await asyncio.sleep(2)
        
        # Relatório final
        print(f"\n📊 RELATÓRIO FINAL:")
        print("=" * 50)
        
        sucessos = 0
        for i, resultado in enumerate(resultados, 1):
            nid, status, extra = resultado
            print(f"   {i}. ID {nid}: {status}")
            if not status.startswith("ERRO"):
                sucessos += 1
                if isinstance(extra, dict):
                    print(f"      Campos: {list(extra.keys())}")
        
        print(f"\n✅ Sucessos: {sucessos}/{len(resultados)}")
        print(f"❌ Erros: {len(resultados) - sucessos}/{len(resultados)}")
        
        return sucessos > 0
        
    except Exception as e:
        print(f"❌ Erro geral: {e}")
        logger.exception("Erro geral no teste")
        return False


def normalizar_status_simples(status_raw):
    """Normalização simples de status."""
    if not status_raw:
        return "INDEFINIDO"
        
    status_lower = status_raw.lower().strip()
    
    if "cancelada" in status_lower:
        return "CANCELADA"
    elif "autorizada" in status_lower:
        return "AUTORIZADA"
    elif "rejeitada" in status_lower:
        return "REJEITADA"
    else:
        return status_raw.upper()


async def atualizar_banco_teste(chave_nfe, status):
    """Teste de atualização no banco."""
    try:
        with conexao_otimizada("omie.db") as conn:
            cursor = conn.cursor()
            
            # Verifica se registro existe
            cursor.execute("SELECT COUNT(*) FROM notas WHERE cChaveNFe = ?", (chave_nfe,))
            exists = cursor.fetchone()[0] > 0
            
            if not exists:
                logger.warning(f"Registro não encontrado para chave {chave_nfe[:20]}...")
                return False
            
            # Atualiza status
            cursor.execute("""
                UPDATE notas 
                SET status = ?
                WHERE cChaveNFe = ?
            """, (status, chave_nfe))
            
            rows_affected = cursor.rowcount
            conn.commit()
            
            logger.debug(f"Linhas afetadas: {rows_affected}")
            return rows_affected > 0
            
    except Exception as e:
        logger.error(f"Erro ao atualizar banco: {e}")
        return False


if __name__ == "__main__":
    asyncio.run(teste_simples_status())
