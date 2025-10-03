#!/usr/bin/env python3
"""
EXEMPLO DE USO DO CÓDIGO DE VERIFICAÇÃO DE STATUS
Demonstra como usar os endpoints para verificar status das NFe.
"""

import sys
from pathlib import Path
from typing import Dict, Any
import requests
import asyncio
import aiohttp
import sqlite3

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.omie_client_async import carregar_configuracoes_client


def verificar_status_nfe_sincronos(auth: Dict[str, str], filtros: Dict[str, Any]) -> Dict[str, Any]:
    """
    Consulta o endpoint de NF-e emitidas e retorna a lista de notas com seus status.
    Versão síncrona usando requests (baseada no seu código).
    """
    payload = {
        **auth,
        "call": "ListarNFesEmitidas", 
        "param": filtros
    }
    
    resp = requests.post("https://app.omie.com.br/api/v1/nfe/", json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


def is_cancelada(nota: Dict[str, Any]) -> bool:
    """
    Identifica se a nota está com status 'Cancelada' (ou similar).
    Baseada no seu código original.
    """
    return nota.get("situacao", "").lower() == "cancelada"


async def verificar_status_nfe_async(auth: Dict[str, str], filtros: Dict[str, Any]) -> Dict[str, Any]:
    """
    Versão assíncrona usando aiohttp para melhor integração com o pipeline.
    """
    payload = {
        **auth,
        "call": "ListarNFesEmitidas",
        "param": filtros
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://app.omie.com.br/api/v1/nfe/", 
            json=payload,
            timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            response.raise_for_status()
            return await response.json()


def processar_notas_com_status(notas: list, salvar_banco: bool = False) -> Dict[str, int]:
    """
    Processa lista de notas e contabiliza por status.
    Opcionalmente salva no banco de dados.
    """
    estatisticas = {
        "canceladas": 0,
        "autorizadas": 0,
        "outras": 0,
        "total": len(notas)
    }
    
    notas_para_salvar = []
    
    for nota in notas:
        if is_cancelada(nota):
            estatisticas["canceladas"] += 1
            status = "CANCELADA"
        elif nota.get("situacao", "").lower() == "autorizada":
            estatisticas["autorizadas"] += 1
            status = "AUTORIZADA"
        else:
            estatisticas["outras"] += 1
            status = nota.get("situacao", "INDEFINIDO").upper()
        
        print(f"Nota {nota.get('chave_nfe', 'N/A')[:20]}... possui status: {status}")
        
        if salvar_banco:
            notas_para_salvar.append({
                'chave_nfe': nota.get('chave_nfe'),
                'status': status,
                'situacao_original': nota.get('situacao')
            })
    
    # Salva no banco se solicitado
    if salvar_banco and notas_para_salvar:
        salvar_status_banco(notas_para_salvar)
    
    return estatisticas


def salvar_status_banco(notas_status: list) -> int:
    """
    Salva status das notas no banco de dados.
    """
    try:
        with sqlite3.connect("omie.db") as conn:
            cursor = conn.cursor()
            
            # Verifica se coluna status existe
            cursor.execute("PRAGMA table_info(notas)")
            colunas = {row[1] for row in cursor.fetchall()}
            
            if 'status' not in colunas:
                print("⚠️  Coluna 'status' não encontrada. Criando...")
                cursor.execute("ALTER TABLE notas ADD COLUMN status TEXT DEFAULT NULL")
                conn.commit()
                print("✅ Coluna 'status' criada com sucesso")
            
            # Atualiza status das notas
            atualizados = 0
            for nota in notas_status:
                if nota['chave_nfe']:
                    cursor.execute("""
                        UPDATE notas 
                        SET status = ? 
                        WHERE cChaveNFe = ?
                    """, (nota['status'], nota['chave_nfe']))
                    
                    if cursor.rowcount > 0:
                        atualizados += 1
            
            conn.commit()
            print(f"📊 {atualizados} registros atualizados no banco")
            return atualizados
            
    except Exception as e:
        print(f"❌ Erro ao salvar no banco: {e}")
        return 0


def exemplo_uso_sincronos():
    """
    Exemplo de uso baseado no seu código original.
    """
    print("🔄 EXEMPLO DE USO - VERSÃO SÍNCRONA")
    print("=" * 50)
    
    try:
        # Carrega configurações
        config = carregar_configuracoes_client()
        
        auth = {
            "app_key": config["app_key"], 
            "app_secret": config["app_secret"]
        }
        
        filtros = {
            "pagina": 1, 
            "registros_por_pagina": 50, 
            "data_inicial": "01/09/2025", 
            "data_final": "03/09/2025"
        }
        
        print(f"🔍 Consultando NFe de {filtros['data_inicial']} a {filtros['data_final']}")
        
        # Chama API
        resultado = verificar_status_nfe_sincronos(auth, filtros)
        
        if "notas" in resultado:
            notas = resultado["notas"]
            print(f"📊 {len(notas)} notas encontradas")
            
            # Processa conforme seu código original
            estatisticas = processar_notas_com_status(notas)
            
            print(f"\n📈 ESTATÍSTICAS:")
            print(f"   • Total: {estatisticas['total']}")
            print(f"   • Canceladas: {estatisticas['canceladas']}")
            print(f"   • Autorizadas: {estatisticas['autorizadas']}")
            print(f"   • Outras: {estatisticas['outras']}")
            
        else:
            print("⚠️  Nenhuma nota encontrada na resposta")
            
    except Exception as e:
        print(f"❌ Erro: {e}")


async def exemplo_uso_async():
    """
    Exemplo usando versão assíncrona otimizada.
    """
    print("\n🚀 EXEMPLO DE USO - VERSÃO ASSÍNCRONA")
    print("=" * 50)
    
    try:
        # Carrega configurações
        config = carregar_configuracoes_client()
        
        auth = {
            "app_key": config["app_key"],
            "app_secret": config["app_secret"]
        }
        
        filtros = {
            "pagina": 1,
            "registros_por_pagina": 20,  # Menor para exemplo
            "data_inicial": "01/09/2025",
            "data_final": "03/09/2025"
        }
        
        print(f"🔍 Consultando NFe (async) de {filtros['data_inicial']} a {filtros['data_final']}")
        
        # Chama API assíncrona
        resultado = await verificar_status_nfe_async(auth, filtros)
        
        if "notas" in resultado:
            notas = resultado["notas"]
            print(f"📊 {len(notas)} notas encontradas")
            
            # Processa e salva no banco
            estatisticas = processar_notas_com_status(notas, salvar_banco=True)
            
            print(f"\n📈 ESTATÍSTICAS (SALVO NO BANCO):")
            print(f"   • Total: {estatisticas['total']}")
            print(f"   • Canceladas: {estatisticas['canceladas']}")
            print(f"   • Autorizadas: {estatisticas['autorizadas']}")
            print(f"   • Outras: {estatisticas['outras']}")
            
        else:
            print("⚠️  Nenhuma nota encontrada na resposta")
            
    except Exception as e:
        print(f"❌ Erro: {e}")


def exemplo_integração_sistema():
    """
    Exemplo de como seu código se integra com o sistema existente.
    """
    print("\n🔗 EXEMPLO DE INTEGRAÇÃO COM SISTEMA EXISTENTE")
    print("=" * 60)
    
    try:
        # Importa o sistema de atualização de status
        from src.status_nfe_updater import StatusNFeUpdater
        
        print("✅ Sistema de atualização de status importado com sucesso")
        print("💡 Seu código original pode ser usado junto com:")
        print("   • StatusNFeUpdater para processamento em lotes")
        print("   • Pipeline principal (main_old.py)")
        print("   • Utilitários standalone")
        
        # Mostra como usar junto
        updater = StatusNFeUpdater()
        
        print(f"\n⚙️  CONFIGURAÇÕES DO SISTEMA:")
        print(f"   • Limite de notas por execução: 500")
        print(f"   • Processamento em lotes: 100")
        print(f"   • Requisições simultâneas: 2")
        print(f"   • Base de dados: {updater.db_path}")
        
        print(f"\n🎯 ENDPOINTS UTILIZADOS:")
        print(f"   • ListarNFesEmitidas: https://app.omie.com.br/api/v1/nfe/")
        print(f"   • ObterNfe: {updater.client.base_url_nf}")
        
        print(f"\n💡 COMO EXECUTAR:")
        print("   1. Standalone: python Utilitarios/executar_status_updater.py")
        print("   2. Pipeline: python main_old.py (inclui atualização automática)")
        print("   3. Programático: StatusNFeUpdater().executar_atualizacao_status()")
        
    except ImportError as e:
        print(f"⚠️  Sistema não encontrado: {e}")
        print("💡 Execute primeiro: Certifique-se que todos os arquivos foram criados")


async def main():
    """Função principal que executa todos os exemplos."""
    
    print("🔄 EXEMPLOS DE USO - SISTEMA DE STATUS NFE")
    print("=" * 70)
    print("Baseado no código fornecido e integração com o sistema existente")
    print()
    
    # Exemplo 1: Versão síncrona (seu código original)
    exemplo_uso_sincronos()
    
    # Exemplo 2: Versão assíncrona otimizada
    await exemplo_uso_async()
    
    # Exemplo 3: Integração com sistema
    exemplo_integração_sistema()
    
    print(f"\n{'='*70}")
    print("🎉 EXEMPLOS CONCLUÍDOS COM SUCESSO!")
    print("💡 Agora você pode usar qualquer uma das abordagens:")
    print("   • Código original (requests síncrono)")
    print("   • Versão assíncrona otimizada") 
    print("   • Sistema completo integrado")
    print(f"{'='*70}")


if __name__ == "__main__":
    print("Executando exemplos de uso do sistema de status...")
    asyncio.run(main())
