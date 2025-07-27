#!/usr/bin/env python3
"""
Script de teste para o compactador de resultados.
"""

import sys
import logging
from pathlib import Path

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # Testar pasta específica
    pasta_teste = Path('resultado/2025/07/20')
    logger.info(f"Testando pasta: {pasta_teste}")
    logger.info(f"Existe: {pasta_teste.exists()}")
    
    if not pasta_teste.exists():
        logger.error("Pasta não encontrada!")
        return
    
    # Verificar XMLs
    xmls = list(pasta_teste.glob('*.xml'))
    logger.info(f"XMLs encontrados: {len(xmls)}")
    
    if len(xmls) == 0:
        logger.warning("Nenhum XML encontrado!")
        return
    
    # Testar importação
    try:
        from src_novo.application.services.compactador_resultado import compactar_pasta_otimizada
        logger.info("Importação bem-sucedida!")
    except ImportError as e:
        logger.error(f"Erro na importação: {e}")
        return
    
    # Testar compactação
    try:
        logger.info("Iniciando teste de compactação...")
        zips = compactar_pasta_otimizada(pasta_teste, limite=5)  # Limite baixo para teste
        
        logger.info(f"ZIPs criados: {len(zips)}")
        for zip_path in zips:
            logger.info(f"  - {zip_path.name} ({zip_path.stat().st_size} bytes)")
            
    except Exception as e:
        logger.error(f"Erro na compactação: {e}", exc_info=True)

if __name__ == "__main__":
    main()
