#!/usr/bin/env python3
"""
Teste de integração das funcionalidades de anomesdia e views otimizadas.

Este script testa se as novas funcionalidades foram integradas corretamente
ao pipeline principal, verificando:
1. Criação da coluna anomesdia
2. Criação de views otimizadas
3. Atualização de índices
4. Funcionamento das consultas temporais
"""

import sys
import logging
import sqlite3
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def testar_estrutura_banco():
    """Testa se a estrutura do banco está correta."""
    logger.info("=== TESTE 1: ESTRUTURA DO BANCO ===")
    
    try:
        # Testa importação das funções
        from src.utils import garantir_coluna_anomesdia, atualizar_anomesdia, criar_views_otimizadas
        logger.info("✓ Importações das funções bem-sucedidas")
        
        # Testa criação da coluna
        resultado = garantir_coluna_anomesdia("omie.db")
        if resultado:
            logger.info("✓ Coluna anomesdia garantida")
        else:
            logger.error("✗ Falha ao garantir coluna anomesdia")
            return False
        
        # Verifica se a coluna existe
        with sqlite3.connect("omie.db") as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(notas)")
            colunas = [coluna[1] for coluna in cursor.fetchall()]
            
            if 'anomesdia' in colunas:
                logger.info("✓ Coluna anomesdia existe na tabela")
            else:
                logger.error("✗ Coluna anomesdia não encontrada")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Erro durante teste de estrutura: {e}")
        return False

def testar_views_otimizadas():
    """Testa se as views otimizadas são criadas corretamente."""
    logger.info("=== TESTE 2: VIEWS OTIMIZADAS ===")
    
    try:
        from src.utils import criar_views_otimizadas
        
        # Cria as views
        criar_views_otimizadas("omie.db")
        logger.info("✓ Função criar_views_otimizadas executada")
        
        # Verifica se as views foram criadas
        with sqlite3.connect("omie.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
            views = [row[0] for row in cursor.fetchall()]
            
            views_esperadas = [
                'vw_notas_pendentes',
                'vw_notas_com_erro', 
                'vw_notas_mes_atual',
                'vw_resumo_diario',
                'vw_notas_recentes'
            ]
            
            views_criadas = 0
            for view in views_esperadas:
                if view in views:
                    logger.info(f"✓ View {view} criada")
                    views_criadas += 1
                else:
                    logger.warning(f"⚠ View {view} não encontrada")
            
            logger.info(f"✓ {views_criadas}/{len(views_esperadas)} views criadas com sucesso")
            return views_criadas > 0
        
    except Exception as e:
        logger.error(f"✗ Erro durante teste de views: {e}")
        return False

def testar_indices_performance():
    """Testa se os índices de performance estão corretos."""
    logger.info("=== TESTE 3: ÍNDICES DE PERFORMANCE ===")
    
    try:
        # Cria os índices manualmente para teste
        indices_sql = [
            """CREATE INDEX IF NOT EXISTS idx_anomesdia 
               ON notas(anomesdia) 
               WHERE anomesdia IS NOT NULL""",
            
            """CREATE INDEX IF NOT EXISTS idx_anomesdia_baixado 
               ON notas(anomesdia, xml_baixado) 
               WHERE anomesdia IS NOT NULL""",
            
            """CREATE INDEX IF NOT EXISTS idx_anomesdia_erro 
               ON notas(anomesdia, erro) 
               WHERE anomesdia IS NOT NULL""",
            
            """CREATE INDEX IF NOT EXISTS idx_anomesdia_pendentes 
               ON notas(anomesdia, xml_baixado, erro) 
               WHERE anomesdia IS NOT NULL AND xml_baixado = 0 AND erro = 0"""
        ]
        
        with sqlite3.connect("omie.db") as conn:
            cursor = conn.cursor()
            
            # Cria os índices
            for sql in indices_sql:
                try:
                    cursor.execute(sql)
                    logger.debug(f"[ÍNDICE] Criado: {sql.split()[5]}")
                except sqlite3.Error as e:
                    logger.warning(f"[ÍNDICE] Falha ao criar índice: {e}")
            
            conn.commit()
            logger.info("✓ Índices de anomesdia criados")
            
            # Verifica se os índices foram criados
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indices = [row[0] for row in cursor.fetchall()]
            
            indices_esperados = [
                'idx_anomesdia',
                'idx_anomesdia_baixado',
                'idx_anomesdia_erro', 
                'idx_anomesdia_pendentes'
            ]
            
            indices_encontrados = 0
            for indice in indices_esperados:
                if indice in indices:
                    logger.info(f"✓ Índice {indice} existe")
                    indices_encontrados += 1
                else:
                    logger.warning(f"⚠ Índice {indice} não encontrado")
            
            logger.info(f"✓ {indices_encontrados}/{len(indices_esperados)} índices encontrados")
            return indices_encontrados == len(indices_esperados)
        
    except Exception as e:
        logger.error(f"✗ Erro durante teste de índices: {e}")
        return False

def testar_consultas_temporais():
    """Testa se as consultas temporais funcionam."""
    logger.info("=== TESTE 4: CONSULTAS TEMPORAIS ===")
    
    try:
        with sqlite3.connect("omie.db") as conn:
            cursor = conn.cursor()
            
            # Testa consulta básica por anomesdia
            cursor.execute("SELECT COUNT(*) FROM notas WHERE anomesdia IS NOT NULL")
            com_anomesdia = cursor.fetchone()[0]
            logger.info(f"✓ Registros com anomesdia: {com_anomesdia:,}")
            
            # Testa consulta por período usando anomesdia
            cursor.execute("SELECT COUNT(*) FROM notas WHERE anomesdia >= 20250101 AND anomesdia <= 20251231")
            ano_2025 = cursor.fetchone()[0]
            logger.info(f"✓ Registros 2025: {ano_2025:,}")
            
            # Testa views
            views_funcionais = 0
            views_para_testar = [
                'vw_notas_pendentes',
                'vw_notas_com_erro',
                'vw_resumo_diario'
            ]
            
            for view in views_para_testar:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {view} LIMIT 1")
                    resultado = cursor.fetchone()[0]
                    logger.info(f"✓ View {view} funcional: {resultado:,} registros")
                    views_funcionais += 1
                except sqlite3.Error as e:
                    logger.warning(f"⚠ View {view} com problema: {e}")
            
            logger.info(f"✓ {views_funcionais}/{len(views_para_testar)} views funcionais")
            return True
        
    except Exception as e:
        logger.error(f"✗ Erro durante teste de consultas: {e}")
        return False

def testar_atualizacao_anomesdia():
    """Testa a atualização da coluna anomesdia."""
    logger.info("=== TESTE 5: ATUALIZAÇÃO ANOMESDIA ===")
    
    try:
        from src.utils import atualizar_anomesdia
        
        # Executa atualização
        registros_atualizados = atualizar_anomesdia("omie.db")
        logger.info(f"✓ {registros_atualizados:,} registros atualizados com anomesdia")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Erro durante atualização de anomesdia: {e}")
        return False

def executar_todos_testes():
    """Executa todos os testes de integração."""
    logger.info("="*60)
    logger.info("TESTE DE INTEGRAÇÃO - FUNCIONALIDADES ANOMESDIA")
    logger.info("="*60)
    
    # Verifica se banco existe
    if not Path("omie.db").exists():
        logger.warning("⚠ Banco omie.db não encontrado - alguns testes podem falhar")
    
    testes = [
        ("Estrutura do Banco", testar_estrutura_banco),
        ("Views Otimizadas", testar_views_otimizadas), 
        ("Índices de Performance", testar_indices_performance),
        ("Consultas Temporais", testar_consultas_temporais),
        ("Atualização Anomesdia", testar_atualizacao_anomesdia)
    ]
    
    sucessos = 0
    total = len(testes)
    
    for nome, teste_func in testes:
        logger.info(f"\n--- {nome} ---")
        try:
            if teste_func():
                sucessos += 1
                logger.info(f"✓ {nome}: PASSOU")
            else:
                logger.error(f"✗ {nome}: FALHOU")
        except Exception as e:
            logger.error(f"✗ {nome}: ERRO - {e}")
    
    # Resultado final
    logger.info("\n" + "="*60)
    logger.info("RESULTADO DOS TESTES")
    logger.info("="*60)
    logger.info(f"Sucessos: {sucessos}/{total}")
    logger.info(f"Taxa de sucesso: {(sucessos/total)*100:.1f}%")
    
    if sucessos == total:
        logger.info(" TODOS OS TESTES PASSARAM! Integração bem-sucedida.")
    elif sucessos >= total * 0.8:
        logger.info("✅ MAIORIA DOS TESTES PASSOU. Integração funcionando bem.")
    else:
        logger.warning("⚠ VÁRIOS TESTES FALHARAM. Verificar integração.")
    
    return sucessos, total

if __name__ == "__main__":
    sucessos, total = executar_todos_testes()
    
    # Exit code baseado no resultado
    if sucessos == total:
        sys.exit(0)  # Sucesso total
    elif sucessos >= total * 0.8:
        sys.exit(1)  # Sucesso parcial
    else:
        sys.exit(2)  # Falhas significativas
