#!/usr/bin/env python3
"""
Script para executar e monitorar o atualizador de caminhos dos arquivos XML.
"""

import sys
import logging
import sqlite3
import time
from pathlib import Path
from configparser import ConfigParser

# Configurar logging detalhado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('atualizar_caminhos.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def verificar_estrutura():
    """Verifica a estrutura de arquivos e banco."""
    logger.info("[VERIFICACAO] Verificando estrutura do sistema")
    
    # 1. Verificar configuração
    config_path = Path("configuracao.ini")
    if not config_path.exists():
        logger.error("[VERIFICACAO.CONFIG] Arquivo configuracao.ini não encontrado")
        return False
    
    config = ConfigParser()
    config.read(config_path)
    resultado_dir = Path(config.get('paths', 'resultado_dir', fallback='resultado'))
    logger.info(f"[VERIFICACAO.CONFIG] Diretório resultado configurado: {resultado_dir}")
    
    # 2. Verificar diretório resultado
    if not resultado_dir.exists():
        logger.error(f"[VERIFICACAO.DIR] Diretório {resultado_dir} não existe")
        return False
    
    # 3. Contar arquivos XML
    arquivos_xml = list(resultado_dir.rglob("*.xml"))
    logger.info(f"[VERIFICACAO.ARQUIVOS] Arquivos XML encontrados: {len(arquivos_xml):,}")
    
    if len(arquivos_xml) == 0:
        logger.warning("[VERIFICACAO.ARQUIVOS] Nenhum arquivo XML encontrado")
    else:
        # Mostra alguns exemplos
        for i, xml in enumerate(arquivos_xml[:5]):
            logger.debug(f"[VERIFICACAO.ARQUIVOS] {xml.relative_to(resultado_dir)}")
        if len(arquivos_xml) > 5:
            logger.debug(f"[VERIFICACAO.ARQUIVOS] ... e mais {len(arquivos_xml) - 5} arquivos")
    
    # 4. Verificar banco de dados
    db_path = Path("omie.db")
    if not db_path.exists():
        logger.error("[VERIFICACAO.DB] Banco omie.db não encontrado")
        return False
    
    # 5. Verificar estrutura do banco
    try:
        with sqlite3.connect("omie.db") as conn:
            cursor = conn.cursor()
            
            # Verifica se tabela notas existe
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notas'")
            if not cursor.fetchone():
                logger.error("[VERIFICACAO.DB.TABELA] Tabela 'notas' não encontrada no banco")
                return False
            
            # Conta registros total
            cursor.execute("SELECT COUNT(*) FROM notas")
            total_notas = cursor.fetchone()[0]
            logger.info(f"[VERIFICACAO.DB.TOTAL] Total de registros no banco: {total_notas:,}")
            
            # Conta registros com XML baixado
            cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 1")
            com_xml = cursor.fetchone()[0]
            logger.info(f"[VERIFICACAO.DB.BAIXADOS] Registros com XML baixado: {com_xml:,}")
            
            # Conta registros sem caminho
            cursor.execute("SELECT COUNT(*) FROM notas WHERE caminho_arquivo IS NULL OR caminho_arquivo = ''")
            sem_caminho = cursor.fetchone()[0]
            logger.info(f"[VERIFICACAO.DB.SEM_CAMINHO] Registros sem caminho: {sem_caminho:,}")
            
            # Adiciona estatísticas úteis para contexto
            cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_vazio = 1")
            xml_vazios = cursor.fetchone()[0]
            if xml_vazios > 0:
                logger.warning(f"[VERIFICACAO.DB.VAZIOS] XMLs vazios detectados: {xml_vazios:,}")
            
            cursor.execute("SELECT COUNT(*) FROM notas WHERE erro = 1")
            com_erro = cursor.fetchone()[0]
            if com_erro > 0:
                logger.warning(f"[VERIFICACAO.DB.ERROS] Registros com erro: {com_erro:,}")
            
            # Calcula percentuais úteis
            if total_notas > 0:
                percentual_baixados = (com_xml / total_notas) * 100
                percentual_sem_caminho = (sem_caminho / total_notas) * 100
                logger.info(f"[VERIFICACAO.DB.PERCENTUAIS] {percentual_baixados:.1f}% baixados, {percentual_sem_caminho:.1f}% sem caminho")
            
    except Exception as e:
        logger.error(f"[VERIFICACAO.DB] Erro ao verificar banco: {e}")
        return False
    
    logger.info("[VERIFICACAO] Estrutura verificada com sucesso")
    return True

def executar_atualizador():
    """Executa o atualizador de caminhos."""
    logger.info("[EXECUTAR] Executando atualizador otimizado de caminhos")
    
    tempo_inicio = time.time()
    
    try:
        from src.atualizar_caminhos_arquivos import atualizar_caminhos_no_banco
        
        logger.info("[EXECUTAR] Iniciando atualização otimizada de caminhos")
        logger.info("[EXECUTAR.OTIMIZACOES] OTIMIZAÇÕES ATIVAS:")
        logger.info("[EXECUTAR.OTIMIZACOES] - Views otimizadas para consulta de pendentes")
        logger.info("[EXECUTAR.OTIMIZACOES] - Índices compostos para performance")
        logger.info("[EXECUTAR.OTIMIZACOES] - PRAGMAs avançados (WAL, cache 128MB, mmap 512MB)")
        logger.info("[EXECUTAR.OTIMIZACOES] - Processamento em lotes de 1000 registros")
        logger.info("[EXECUTAR.OTIMIZACOES] - Verificação inteligente de arquivos vazios")
        
        # Log do estado antes da execução
        try:
            with sqlite3.connect("omie.db") as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM notas WHERE caminho_arquivo IS NULL OR caminho_arquivo = ''")
                pendentes_antes = cursor.fetchone()[0]
                logger.info(f"[EXECUTAR.CONTEXTO] Registros sem caminho (antes): {pendentes_antes:,}")
        except Exception as ctx_error:
            logger.debug(f"[EXECUTAR.CONTEXTO] Erro ao obter contexto inicial: {ctx_error}")
        
        atualizar_caminhos_no_banco('omie.db')
        
        tempo_execucao = time.time() - tempo_inicio
        
        # Log do estado após a execução
        try:
            with sqlite3.connect("omie.db") as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM notas WHERE caminho_arquivo IS NULL OR caminho_arquivo = ''")
                pendentes_depois = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM notas WHERE caminho_arquivo IS NOT NULL")
                com_caminho_depois = cursor.fetchone()[0]
                
                atualizados = pendentes_antes - pendentes_depois if 'pendentes_antes' in locals() else 0
                
                logger.info(f"[EXECUTAR.RESULTADO] Registros sem caminho (depois): {pendentes_depois:,}")
                logger.info(f"[EXECUTAR.RESULTADO] Registros com caminho (total): {com_caminho_depois:,}")
                logger.info(f"[EXECUTAR.RESULTADO] Registros atualizados: {atualizados:,}")
                
        except Exception as result_error:
            logger.debug(f"[EXECUTAR.RESULTADO] Erro ao obter resultados: {result_error}")
        
        velocidade = atualizados / tempo_execucao if tempo_execucao > 0 and 'atualizados' in locals() else 0
        logger.info(f"[EXECUTAR.PERFORMANCE] Tempo: {tempo_execucao:.2f}s, Velocidade: {velocidade:.1f} registros/s")
        logger.info("[EXECUTAR] Atualização otimizada concluída")
        
        return True
        
    except Exception as e:
        logger.exception(f"[EXECUTAR] Erro durante atualização: {e}")
        return False

def verificar_resultados():
    """Verifica os resultados da atualização."""
    logger.info("[RESULTADOS] Verificando resultados da atualização")
    
    try:
        with sqlite3.connect("omie.db") as conn:
            cursor = conn.cursor()
            
            # Estatísticas após atualização
            cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 1")
            com_xml_depois = cursor.fetchone()[0]
            logger.info(f"[RESULTADOS.BAIXADOS] Registros com XML baixado (após): {com_xml_depois:,}")
            
            cursor.execute("SELECT COUNT(*) FROM notas WHERE caminho_arquivo IS NOT NULL AND caminho_arquivo != ''")
            com_caminho_depois = cursor.fetchone()[0]
            logger.info(f"[RESULTADOS.CAMINHOS] Registros com caminho (após): {com_caminho_depois:,}")
            
            cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_vazio = 1")
            xml_vazios = cursor.fetchone()[0]
            if xml_vazios > 0:
                logger.warning(f"[RESULTADOS.VAZIOS] Arquivos XML vazios detectados: {xml_vazios:,}")
            
            # Exemplos de caminhos atualizados
            cursor.execute("SELECT cChaveNFe, caminho_arquivo FROM notas WHERE caminho_arquivo IS NOT NULL LIMIT 5")
            exemplos = cursor.fetchall()
            
            if exemplos:
                logger.info("[RESULTADOS.EXEMPLOS] Exemplos de caminhos atualizados:")
                for chave, caminho in exemplos:
                    caminho_short = str(Path(caminho).name) if caminho else "N/A"
                    logger.debug(f"[RESULTADOS.EXEMPLOS] {chave[:10]}... -> {caminho_short}")
        
        return True
        
    except Exception as e:
        logger.exception(f"[RESULTADOS] Erro durante verificação: {e}")
        return False

def main():
    """Função principal."""
    logger.info("[MAIN] ATUALIZADOR DE CAMINHOS - INÍCIO")
    logger.info("=" * 60)
    
    # 1. Verificar estrutura
    if not verificar_estrutura():
        logger.error("[MAIN] Falha na verificação da estrutura - abortando")
        sys.exit(1)
    
    # 2. Executar atualizador
    if not executar_atualizador():
        logger.error("[MAIN] Falha na atualização - abortando")
        sys.exit(1)
    
    # 3. Verificar resultados
    if not verificar_resultados():
        logger.error("[MAIN] Falha na verificação dos resultados")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("[MAIN] ATUALIZADOR DE CAMINHOS - CONCLUÍDO COM SUCESSO")

if __name__ == "__main__":
    main()
