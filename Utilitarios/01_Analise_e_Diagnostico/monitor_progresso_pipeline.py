#!/usr/bin/env python3
"""
Script para monitorar o progresso do pipeline e os registros pendentes.
"""

import sqlite3
import time
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def verificar_status_banco():
    """Verifica o status atual dos registros no banco."""
    try:
        db_path = "omie.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Contar registros por status
        cursor.execute("""
            SELECT 
                xml_baixado,
                COUNT(*) as total
            FROM notas 
            WHERE strftime('%d/%m/%Y', data_emissao) = '01/05/2025'
            GROUP BY xml_baixado
        """)
        
        resultados = cursor.fetchall()
        logger.info("=" * 50)
        logger.info("STATUS DOS REGISTROS - 01/05/2025")
        logger.info("=" * 50)
        
        for xml_baixado, total in resultados:
            status = "BAIXADO" if xml_baixado == 1 else "PENDENTE"
            logger.info(f"{status}: {total:,} registros")
        
        # Verificar se há registros processados recentemente
        cursor.execute("""
            SELECT COUNT(*) as processados_recentemente
            FROM notas 
            WHERE strftime('%d/%m/%Y', data_emissao) = '01/05/2025'
            AND xml_baixado = 1
            AND datetime(data_processamento) > datetime('now', '-10 minutes')
        """)
        
        recentes = cursor.fetchone()[0]
        if recentes > 0:
            logger.info(f"PROCESSADOS RECENTEMENTE: {recentes:,} registros")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Erro ao verificar status: {e}")

def verificar_arquivos_resultado():
    """Verifica quantos arquivos XML existem no diretório resultado."""
    try:
        import os
        resultado_dir = "C:/milson/extrator_omie_v3/resultado"
        
        if not os.path.exists(resultado_dir):
            logger.warning(f"Diretório resultado não encontrado: {resultado_dir}")
            return
            
        # Contar arquivos XML
        xml_count = 0
        for root, dirs, files in os.walk(resultado_dir):
            xml_count += len([f for f in files if f.endswith('.xml')])
        
        logger.info(f"ARQUIVOS XML NO RESULTADO: {xml_count:,}")
        
    except Exception as e:
        logger.error(f"Erro ao verificar arquivos: {e}")

def main():
    """Função principal de monitoramento."""
    logger.info("Iniciando monitoramento do progresso...")
    
    while True:
        try:
            verificar_status_banco()
            verificar_arquivos_resultado()
            
            # Aguardar 2 minutos antes da próxima verificação
            time.sleep(120)
            
        except KeyboardInterrupt:
            logger.info("Monitoramento interrompido pelo usuário.")
            break
        except Exception as e:
            logger.error(f"Erro durante monitoramento: {e}")
            time.sleep(30)  # Aguardar menos tempo em caso de erro

if __name__ == "__main__":
    main()
