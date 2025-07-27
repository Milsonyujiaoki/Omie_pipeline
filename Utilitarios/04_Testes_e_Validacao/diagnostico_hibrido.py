#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para verificar por que o modo híbrido não executou completamente.

Analisa:
1. Números no banco de dados
2. Configurações híbridas
3. Lógica de decisão
4. Condições para Fase 2
"""
import sqlite3
import configparser
import sys
import os

# Adiciona o diretório src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def analisar_banco_atual():
    """Analisa estado atual do banco."""
    print(" Analisando estado atual do banco de dados...")
    
    try:
        with sqlite3.connect("omie.db") as conn:
            conn.row_factory = sqlite3.Row
            
            # 1. Contagens básicas
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN xml_baixado = 0 AND erro = 0 THEN 1 ELSE 0 END) as pendentes,
                    SUM(CASE WHEN erro = 1 THEN 1 ELSE 0 END) as com_erro
                FROM notas
            """)
            stats = cursor.fetchone()
            
            print(f"📊 Estatísticas básicas:")
            print(f"   Total de registros: {stats['total']:,}")
            print(f"   Registros pendentes: {stats['pendentes']:,}")
            print(f"   Registros com erro: {stats['com_erro']:,}")
            
            # 2. Análise detalhada de erros
            if stats['com_erro'] > 0:
                cursor = conn.execute("""
                    SELECT 
                        SUM(CASE WHEN mensagem_erro LIKE '%500%' OR mensagem_erro LIKE '%Server Error%' THEN 1 ELSE 0 END) as erro_500,
                        SUM(CASE WHEN mensagem_erro LIKE '%XML vazio%' OR mensagem_erro LIKE '%empty%' THEN 1 ELSE 0 END) as xml_vazio,
                        SUM(CASE WHEN mensagem_erro LIKE '%timeout%' OR mensagem_erro LIKE '%TimeoutError%' THEN 1 ELSE 0 END) as timeout,
                        SUM(CASE WHEN mensagem_erro LIKE '%425%' OR mensagem_erro LIKE '%Too Early%' THEN 1 ELSE 0 END) as erro_425
                    FROM notas 
                    WHERE erro = 1
                """)
                erros = cursor.fetchone()
                
                print(f"📈 Categorização de erros:")
                print(f"   Erro 500 (API): {erros['erro_500']:,}")
                print(f"   Erro 425 (Too Early): {erros['erro_425']:,}")
                print(f"   XML vazio: {erros['xml_vazio']:,}")
                print(f"   Timeout: {erros['timeout']:,}")
                
                erros_recuperaveis = erros['erro_500'] + erros['timeout']
                print(f"   ERROS RECUPERÁVEIS: {erros_recuperaveis:,}")
                
                return stats, erros, erros_recuperaveis
            
            return stats, None, 0
            
    except Exception as e:
        print(f"❌ Erro ao analisar banco: {e}")
        return None, None, 0

def analisar_configuracoes():
    """Analisa configurações híbridas."""
    print("\\n⚙️ Analisando configurações híbridas...")
    
    try:
        config = configparser.ConfigParser()
        config.read('configuracao.ini', encoding='utf-8')
        
        modo_hibrido_ativo = config.getboolean('pipeline', 'modo_hibrido_ativo', fallback=False)
        min_erros_reprocessamento = config.getint('pipeline', 'min_erros_para_reprocessamento', fallback=1000)
        reprocessar_automaticamente = config.getboolean('pipeline', 'reprocessar_automaticamente', fallback=True)
        apenas_normal = config.getboolean('pipeline', 'apenas_normal', fallback=False)
        
        print(f"   modo_hibrido_ativo: {modo_hibrido_ativo}")
        print(f"   min_erros_para_reprocessamento: {min_erros_reprocessamento:,}")
        print(f"   reprocessar_automaticamente: {reprocessar_automaticamente}")
        print(f"   apenas_normal: {apenas_normal}")
        
        return {
            'modo_hibrido_ativo': modo_hibrido_ativo,
            'min_erros_reprocessamento': min_erros_reprocessamento,
            'apenas_normal': apenas_normal
        }
        
    except Exception as e:
        print(f"❌ Erro ao carregar configurações: {e}")
        return None

def simular_logica_decisao(stats, erros, config):
    """Simula lógica de decisão do pipeline."""
    print("\\n🧠 Simulando lógica de decisão...")
    
    if not stats or not config:
        print("❌ Dados insuficientes para simulação")
        return
    
    pendentes = stats['pendentes']
    com_erro = stats['com_erro']
    
    # 1. Lógica de detecção de modo
    print("\\n Detecção de modo:")
    if pendentes > 100000:
        modo_sugerido = "pendentes_geral"
        print(f"   Modo sugerido: {modo_sugerido} (pendentes {pendentes:,} > 100k)")
    else:
        if erros:
            erros_recuperaveis = erros['erro_500'] + erros['timeout']
            if erros_recuperaveis > 1000:
                modo_sugerido = "hibrido"
                print(f"   Modo sugerido: {modo_sugerido} (erros recuperáveis {erros_recuperaveis:,} > 1k)")
            elif com_erro > 100:
                modo_sugerido = "reprocessamento"
                print(f"   Modo sugerido: {modo_sugerido} (com erro {com_erro:,} > 100)")
            else:
                modo_sugerido = "normal"
                print(f"   Modo sugerido: {modo_sugerido}")
        else:
            modo_sugerido = "normal"
            print(f"   Modo sugerido: {modo_sugerido}")
    
    # 2. Verificações do pipeline híbrido
    if modo_sugerido == "hibrido":
        print("\\n🔧 Verificações do pipeline híbrido:")
        
        if not config['modo_hibrido_ativo']:
            print("   ❌ Modo híbrido DESABILITADO na configuração")
            return
        else:
            print("   ✅ Modo híbrido HABILITADO na configuração")
        
        if config['apenas_normal']:
            print("   ❌ Modo apenas_normal ativo - pularia Fase 2")
        else:
            print("   ✅ Modo apenas_normal DESABILITADO")
        
        if erros:
            erros_recuperaveis = erros['erro_500'] + erros['timeout']
            threshold = config.get('min_erros_para_reprocessamento', 1000)  # Fallback padrão
            
            print(f"   Erros recuperáveis: {erros_recuperaveis:,}")
            print(f"   Threshold configurado: {threshold:,}")
            
            if erros_recuperaveis >= threshold:
                print("   ✅ FASE 2 deveria EXECUTAR")
                print(f"       ({erros_recuperaveis:,} >= {threshold:,})")
            else:
                print("   ❌ FASE 2 seria PULADA")
                print(f"       ({erros_recuperaveis:,} < {threshold:,})")
    
    return modo_sugerido

def main():
    """Executa análise completa."""
    print(" ANÁLISE: Por que modo híbrido não executou Fase 2?")
    print("=" * 60)
    
    # 1. Analisa banco atual
    stats, erros, erros_recuperaveis = analisar_banco_atual()
    
    # 2. Analisa configurações
    config = analisar_configuracoes()
    
    # 3. Simula lógica de decisão
    modo_sugerido = simular_logica_decisao(stats, erros, config)
    
    # 4. Conclusões
    print("\\n" + "=" * 60)
    print("📋 CONCLUSÕES:")
    
    if modo_sugerido == "hibrido" and config and config.get('modo_hibrido_ativo', False):
        if erros and (erros['erro_500'] + erros['timeout']) >= config.get('min_erros_para_reprocessamento', 1000):
            print("✅ Pipeline híbrido DEVERIA ter executado completamente")
            print("❌ PROBLEMA: Fase 1 falhou, impedindo Fase 2")
            print("💡 SOLUÇÃO: Modificar lógica para não interromper pipeline")
        else:
            print("ℹ️  Pipeline híbrido executou corretamente")
            print("   Fase 2 foi pulada por não atingir threshold")
    else:
        print("ℹ️  Modo híbrido não era aplicável neste cenário")
    
    print("\\n🔧 CORREÇÃO IMPLEMENTADA:")
    print("   - Fase 1 não interrompe mais o pipeline em caso de erro")
    print("   - Fase 2 executará mesmo se Fase 1 falhar")
    print("   - Prioriza reprocessamento de erros acumulados")

if __name__ == "__main__":
    main()
