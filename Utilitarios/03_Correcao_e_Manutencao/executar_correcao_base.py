#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para executar correção da base usando extrator_async.

Este script executa o pipeline de download de XMLs pendentes 
respeitando o limite de 4 req/s da API Omie.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Adiciona o diretório src ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.extrator_async import baixar_xmls, main as async_main
from src.omie_client_async import OmieClient, carregar_configuracoes
from src.utils import inicializar_banco_e_indices

def configurar_logging():
    """Configura logging para acompanhar o progresso."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('log_correcao_base.txt', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

async def executar_correcao_base():
    """
    Executa correção da base baixando XMLs pendentes.
    """
    print("🔧 INICIANDO CORREÇÃO DA BASE OMIE")
    print("=" * 50)
    
    tempo_inicio = time.time()
    
    try:
        # 1. Carrega configurações
        print("📋 Carregando configurações...")
        config = carregar_configuracoes()
        db_name = config.get("db_name", "omie.db")
        
        # 2. Inicializa cliente Omie
        print("🔌 Inicializando cliente Omie...")
        client = OmieClient(
            app_key=config["app_key"],
            app_secret=config["app_secret"],
            calls_per_second=config["calls_per_second"],
            base_url_nf=config["base_url_nf"],
            base_url_xml=config["base_url_xml"]
        )
        
        # 3. Inicializa banco de dados
        print("💾 Inicializando banco de dados...")
        inicializar_banco_e_indices(db_name)
        
        # 4. Verifica registros pendentes
        import sqlite3
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado IS NULL OR xml_baixado = 0")
        pendentes = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM notas")
        total = cursor.fetchone()[0]
        conn.close()
        
        print(f"📊 Status da base:")
        print(f"   Total de registros: {total:,}")
        print(f"   Registros pendentes: {pendentes:,}")
        print(f"   Percentual pendente: {(pendentes/total)*100:.1f}%")
        
        if pendentes == 0:
            print("✅ Nenhum registro pendente encontrado. Base já está corrigida!")
            return
        
        # 5. Executa download de XMLs
        print(f"\n🚀 Iniciando download de {pendentes:,} XMLs pendentes...")
        print("⚙️  Configuração: 4 req/s, lotes de 20 registros")
        print(" Tempo estimado: ~{:.1f} minutos".format(pendentes / 4 / 60))
        print("-" * 50)
        
        metricas = await baixar_xmls(
            client=client,
            config=config,
            db_name=db_name,
            max_concurrent=4,  # Respeitando limite da API
            base_dir="resultado"
        )
        
        # 6. Relatório final
        tempo_total = time.time() - tempo_inicio
        print("\n" + "=" * 50)
        print("📈 RELATÓRIO FINAL DA CORREÇÃO")
        print("=" * 50)
        print(f"✅ Downloads concluídos: {metricas.downloads_concluidos:,}")
        print(f"❌ Downloads com erro: {metricas.downloads_com_erro:,}")
        print(f"📊 Taxa de sucesso: {metricas.taxa_sucesso:.1f}%")
        print(f" Tempo total: {tempo_total/60:.1f} minutos")
        print(f"🚀 Throughput: {metricas.throughput:.1f} downloads/s")
        print(f"⚠️  Erros 500 (API): {metricas.erros_500}")
        print(f"🌡️  Instabilidades detectadas: {metricas.instabilidades_detectadas}")
        
        if metricas.taxa_sucesso >= 95:
            print("\n CORREÇÃO CONCLUÍDA COM SUCESSO!")
        elif metricas.taxa_sucesso >= 80:
            print("\n⚠️  CORREÇÃO PARCIALMENTE CONCLUÍDA")
            print("   Recomenda-se executar novamente para os registros restantes.")
        else:
            print("\n❌ CORREÇÃO COM MUITOS ERROS")
            print("   Verifique logs e conectividade da API.")
        
    except Exception as e:
        print(f"\n❌ ERRO CRÍTICO: {e}")
        logging.exception("Erro durante execução")
        raise

def main():
    """Função principal."""
    configurar_logging()
    
    try:
        asyncio.run(executar_correcao_base())
    except KeyboardInterrupt:
        print("\n⏹️  Execução interrompida pelo usuário")
    except Exception as e:
        print(f"\n💥 Falha na execução: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
