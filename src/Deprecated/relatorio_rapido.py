#!/usr/bin/env python3
"""
Script para executar relatorio de arquivos vazios com limite de tempo
"""

import sys
import os
import time
import signal
from pathlib import Path
from threading import Thread, Event

# Adiciona o diretorio raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

from src.report_arquivos_vazios import gerar_relatorio
import logging

# Configurar logging
logger = logging.getLogger(__name__)

# Evento para controlar a interrupção
stop_event = Event()

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    """Handler para timeout"""
    logger.warning("Timeout atingido! Interrompendo execução...")
    stop_event.set()
    raise TimeoutException("Tempo limite excedido")

def gerar_relatorio_com_timeout(root_path: str, timeout_seconds: int = 300):
    """
    Gera relatorio com timeout para evitar execução infinita.
    
    Args:
        root_path: Caminho para analise
        timeout_seconds: Tempo limite em segundos (padrão: 5 minutos)
    """
    logger.info(f"Iniciando relatorio com timeout de {timeout_seconds} segundos...")
    
    # Configura handler de timeout
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_seconds)
    
    try:
        start_time = time.time()
        gerar_relatorio(root_path)
        elapsed = time.time() - start_time
        logger.info(f"Relatorio concluido em {elapsed:.2f}s")
        
    except TimeoutException:
        logger.error(" Relatorio interrompido por timeout")
        logger.info("Sugestão: Execute uma analise rapida apenas dos arquivos mais recentes")
        
    except Exception as e:
        logger.error(f"Erro na geração do relatorio: {e}")
        
    finally:
        signal.alarm(0)  # Cancela o timeout

def gerar_relatorio_rapido(root_path: str):
    """
    Gera relatorio rapido focando apenas em arquivos modificados recentemente.
    
    Args:
        root_path: Caminho para analise
    """
    logger.info("Executando analise rapida (ultimos 7 dias)...")
    
    import datetime
    from pathlib import Path
    
    root = Path(root_path)
    if not root.exists():
        logger.error(f"Diretorio não encontrado: {root_path}")
        return
    
    # So analisa arquivos modificados nos ultimos 7 dias
    sete_dias_atras = datetime.datetime.now() - datetime.timedelta(days=7)
    timestamp_limite = sete_dias_atras.timestamp()
    
    arquivos_recentes = []
    for arquivo in root.rglob("*"):
        if arquivo.is_file():
            try:
                if arquivo.stat().st_mtime > timestamp_limite:
                    arquivos_recentes.append(arquivo)
            except (OSError, PermissionError):
                continue

    logger.info(f"Encontrados {len(arquivos_recentes)} arquivos modificados recentemente")

    if not arquivos_recentes:
        logger.info("Nenhum arquivo recente para analisar")
        return
    
    # Analisa apenas os arquivos recentes
    from src.report_arquivos_vazios import verificar_arquivo_rapido, salvar_relatorio_otimizado
    
    problemas = []
    for arquivo in arquivos_recentes:
        resultado = verificar_arquivo_rapido(str(arquivo))
        if resultado:
            problemas.append(resultado)
    
    if problemas:
        salvar_relatorio_otimizado(problemas)
        logger.info(f"Relatorio salvo com {len(problemas)} problemas encontrados")
    else:
        logger.info("Nenhum problema encontrado nos arquivos recentes")

def main():
    """Função principal"""
    root_path = "C:\\milson\\extrator_omie_v3\\resultado"
    
    print("Escolha o tipo de analise:")
    print("1. Analise completa (pode demorar muito)")
    print("2. Analise rapida (ultimos 7 dias)")
    print("3. Analise com timeout (5 minutos)")
    
    try:
        escolha = input("\nDigite sua escolha (1, 2 ou 3): ").strip()
        
        if escolha == "1":
            gerar_relatorio(root_path)
        elif escolha == "2":
            gerar_relatorio_rapido(root_path)
        elif escolha == "3":
            gerar_relatorio_com_timeout(root_path, 300)  # 5 minutos
        else:
            print("Opção invalida. Executando analise rapida...")
            gerar_relatorio_rapido(root_path)
            
    except KeyboardInterrupt:
        logger.info("Execução interrompida pelo usuario")
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")

if __name__ == "__main__":
    main()
