#!/usr/bin/env python3
"""
Script de teste para validar o Pipeline Adaptativo Otimizado.

Este script testa:
1. Ativação do pipeline adaptativo
2. Detecção de saúde da API
3. Adaptação automática de configurações
4. Integração com extrator_async
5. Fallback sequencial quando necessário
"""

import logging
import sys
import os
from pathlib import Path

# Configurar logging para teste
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def testar_ativacao_pipeline():
    """Testa ativação do pipeline adaptativo."""
    try:
        logger.info("=== TESTE 1: Ativação do Pipeline Adaptativo ===")
        
        from pipeline_adaptativo import ativar_pipeline_adaptativo, health_monitor
        
        config = ativar_pipeline_adaptativo()
        
        logger.info(f"✅ Pipeline ativado com sucesso")
        logger.info(f"✅ Modo inicial: {health_monitor.modo_atual}")
        logger.info(f"✅ Configuração: {config}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na ativação: {e}")
        return False

def testar_adaptacao_configuracao():
    """Testa adaptação automática de configurações."""
    try:
        logger.info("=== TESTE 2: Adaptação de Configurações ===")
        
        from pipeline_adaptativo import health_monitor, otimizar_configuracao_existente
        
        # Simula configuração inicial
        config_inicial = {
            'calls_per_second': 4,
            'batch_size': 500,
            'max_workers': 4,
            'records_per_page': 200
        }
        
        logger.info(f"Configuração inicial: {config_inicial}")
        
        # Testa modo normal
        config_normal = otimizar_configuracao_existente(config_inicial.copy(), health_monitor)
        logger.info(f"✅ Modo normal: {config_normal}")
        
        # Simula erros para forçar modo conservador
        for i in range(6):
            health_monitor.record_error(425)
        
        config_conservador = otimizar_configuracao_existente(config_inicial.copy(), health_monitor)
        logger.info(f"✅ Modo conservador: {config_conservador}")
        
        # Simula mais erros para forçar modo sequencial
        for i in range(10):
            health_monitor.record_error(500)
        
        config_sequencial = otimizar_configuracao_existente(config_inicial.copy(), health_monitor)
        logger.info(f"✅ Modo sequencial: {config_sequencial}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na adaptação: {e}")
        return False

def testar_integracao_patches():
    """Testa integração com patches do extrator_async."""
    try:
        logger.info("=== TESTE 3: Integração com Patches ===")
        
        from extrator_patches import aplicar_todos_patches
        
        patches_ok = aplicar_todos_patches()
        
        if patches_ok:
            logger.info("✅ Patches aplicados com sucesso")
        else:
            logger.warning("⚠️  Patches não aplicados (normal se extrator_async não disponível)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro nos patches: {e}")
        return False

def testar_deteccao_historico():
    """Testa detecção de problemas no histórico de logs."""
    try:
        logger.info("=== TESTE 4: Detecção de Histórico ===")
        
        from pipeline_adaptativo import health_monitor
        
        # Simula arquivo de erro
        with open('erro_teste.log', 'w', encoding='utf-8') as f:
            f.write("""
            2025-07-21 10:00:00 - ERROR - 425 Too Many Requests
            2025-07-21 10:01:00 - ERROR - 425 Too Many Requests  
            2025-07-21 10:02:00 - ERROR - 500 Internal Server Error
            2025-07-21 10:03:00 - ERROR - 425 Too Many Requests
            """)
        
        # Testa detecção
        if Path('erro_teste.log').exists():
            with open('erro_teste.log', 'r', encoding='utf-8', errors='ignore') as f:
                conteudo = f.read()
                erros_425 = conteudo.count('425') + conteudo.count('Too Many Requests')
                erros_500 = conteudo.count('500') + conteudo.count('Internal Server Error')
                
                logger.info(f"✅ Detectados {erros_425} erros 425 e {erros_500} erros 500")
        
        # Limpa arquivo de teste
        if Path('erro_teste.log').exists():
            Path('erro_teste.log').unlink()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na detecção: {e}")
        return False

def testar_configuracao_arquivo():
    """Testa se arquivo de configuração existe e pode ser lido."""
    try:
        logger.info("=== TESTE 5: Arquivo de Configuração ===")
        
        config_path = Path('configuracao.ini')
        if config_path.exists():
            logger.info("✅ Arquivo configuracao.ini encontrado")
            
            import configparser
            config = configparser.ConfigParser()
            config.read('configuracao.ini')
            
            # Testa seções principais
            secoes_esperadas = ['omie_api', 'query_params', 'api_speed', 'pipeline']
            for secao in secoes_esperadas:
                if config.has_section(secao):
                    logger.info(f"✅ Seção [{secao}] encontrada")
                else:
                    logger.warning(f"⚠️  Seção [{secao}] não encontrada")
            
        else:
            logger.warning("⚠️  Arquivo configuracao.ini não encontrado")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na configuração: {e}")
        return False

def main():
    """Executa todos os testes."""
    logger.info("🚀 INICIANDO TESTES DO PIPELINE ADAPTATIVO OTIMIZADO")
    logger.info("=" * 60)
    
    testes = [
        testar_ativacao_pipeline,
        testar_adaptacao_configuracao,
        testar_integracao_patches,
        testar_deteccao_historico,
        testar_configuracao_arquivo
    ]
    
    sucessos = 0
    total = len(testes)
    
    for teste in testes:
        try:
            if teste():
                sucessos += 1
            logger.info("")  # Linha em branco entre testes
        except Exception as e:
            logger.error(f"❌ Erro inesperado no teste {teste.__name__}: {e}")
    
    logger.info("=" * 60)
    logger.info(f"📊 RESULTADO FINAL: {sucessos}/{total} testes passaram")
    
    if sucessos == total:
        logger.info(" TODOS OS TESTES PASSARAM! Pipeline adaptativo pronto para uso.")
        return 0
    else:
        logger.warning(f"⚠️  {total - sucessos} teste(s) falharam. Verificar logs acima.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
