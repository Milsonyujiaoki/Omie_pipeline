#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script otimizado para padronização de datas no banco Omie V3
Converte apenas os 29.513 registros YYYY-MM-DD para DD/MM/YYYY
Baseado na análise real da estrutura de dados
"""

import sqlite3
import logging
from datetime import datetime
from typing import Dict, Any

# Configuração
DB_PATH = "omie.db"
TABLE_NAME = "notas"

# Logging otimizado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('padronizacao_datas.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def formatar_numero(n: int) -> str:
    """Formata número com separadores"""
    return f"{n:,}".replace(",", ".")

def conectar_db() -> sqlite3.Connection:
    """Conecta ao banco com otimizações"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Otimizações SQLite
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA cache_size = -64000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    
    return conn

def analisar_estrutura() -> Dict[str, Any]:
    """Analisa a estrutura atual das datas"""
    logger.info(" Analisando estrutura das datas...")
    
    conn = conectar_db()
    cursor = conn.cursor()
    
    # Total de registros
    cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
    total = cursor.fetchone()[0]
    
    # Formatos encontrados
    cursor.execute(f"""
        SELECT 
            CASE 
                WHEN dEmi LIKE '__/__/____' THEN 'DD/MM/YYYY'
                WHEN dEmi LIKE '____-__-__' THEN 'YYYY-MM-DD'
                ELSE 'OUTROS'
            END as formato,
            COUNT(*) as total
        FROM {TABLE_NAME} 
        GROUP BY formato
        ORDER BY total DESC
    """)
    
    formatos = cursor.fetchall()
    
    # Específico: quantos YYYY-MM-DD existem
    cursor.execute(f"""
        SELECT COUNT(*) FROM {TABLE_NAME} 
        WHERE dEmi LIKE '____-__-__'
    """)
    
    necessita_conversao = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total_registros': total,
        'formatos': formatos,
        'necessita_conversao': necessita_conversao
    }

def converter_yyyy_mm_dd_para_dd_mm_yyyy(data_iso: str) -> str:
    """
    Converte data de YYYY-MM-DD para DD/MM/YYYY
    Exemplo: '2025-04-11' → '11/04/2025'
    """
    try:
        # Parse da data ISO
        data_obj = datetime.strptime(data_iso, '%Y-%m-%d')
        
        # Valida range
        if 2020 <= data_obj.year <= 2025:
            return data_obj.strftime('%d/%m/%Y')
        else:
            logger.warning(f"Data fora do range esperado: {data_iso}")
            return data_iso  # Mantém original se suspeita
            
    except ValueError as e:
        logger.error(f"Erro ao converter data {data_iso}: {e}")
        return data_iso  # Mantém original em caso de erro

def padronizar_datas_yyyy_mm_dd() -> Dict[str, int]:
    """
    Converte especificamente os registros YYYY-MM-DD para DD/MM/YYYY
    """
    logger.info("🔧 Iniciando conversão YYYY-MM-DD → DD/MM/YYYY...")
    
    conn = conectar_db()
    cursor = conn.cursor()
    
    estatisticas = {
        'encontrados': 0,
        'convertidos': 0,
        'erros': 0,
        'processados': 0
    }
    
    try:
        # Busca todos os registros no formato YYYY-MM-DD
        cursor.execute(f"""
            SELECT cChaveNFe, dEmi 
            FROM {TABLE_NAME} 
            WHERE dEmi LIKE '____-__-__'
            ORDER BY cChaveNFe
        """)
        
        registros = cursor.fetchall()
        estatisticas['encontrados'] = len(registros)
        
        logger.info(f"📊 Encontrados {estatisticas['encontrados']:,} registros para conversão")
        
        # Processa em lotes
        batch_size = 1000
        for i in range(0, len(registros), batch_size):
            batch = registros[i:i+batch_size]
            
            for registro in batch:
                chave_nfe = registro['cChaveNFe']
                data_original = registro['dEmi']
                
                # Converte a data
                data_convertida = converter_yyyy_mm_dd_para_dd_mm_yyyy(data_original)
                
                if data_convertida != data_original:
                    # Atualiza no banco
                    cursor.execute(
                        f"UPDATE {TABLE_NAME} SET dEmi = ? WHERE cChaveNFe = ?",
                        (data_convertida, chave_nfe)
                    )
                    
                    estatisticas['convertidos'] += 1
                    logger.debug(f"✅ {chave_nfe[:8]}...: '{data_original}' → '{data_convertida}'")
                else:
                    estatisticas['erros'] += 1
                    logger.warning(f"⚠️ Não convertido: {chave_nfe[:8]}..., Data: '{data_original}'")
                
                estatisticas['processados'] += 1
            
            # Commit a cada batch
            conn.commit()
            
            # Log de progresso
            if (i + batch_size) % (batch_size * 5) == 0:
                logger.info(f"Processados {estatisticas['processados']:,}/{estatisticas['encontrados']:,} registros...")
        
        # Commit final
        conn.commit()
        conn.close()
        
        return estatisticas
        
    except Exception as e:
        conn.close()
        logger.error(f"Erro durante conversão: {e}")
        raise

def validar_resultado() -> Dict[str, Any]:
    """Valida o resultado da conversão"""
    logger.info("✅ Validando resultado...")
    
    conn = conectar_db()
    cursor = conn.cursor()
    
    # Conta formatos após conversão
    cursor.execute(f"""
        SELECT 
            CASE 
                WHEN dEmi LIKE '__/__/____' THEN 'DD/MM/YYYY'
                WHEN dEmi LIKE '____-__-__' THEN 'YYYY-MM-DD'
                ELSE 'OUTROS'
            END as formato,
            COUNT(*) as total
        FROM {TABLE_NAME} 
        GROUP BY formato
        ORDER BY total DESC
    """)
    
    formatos_final = cursor.fetchall()
    
    # Total de registros
    cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
    total = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total_registros': total,
        'formatos_final': formatos_final
    }

def main():
    """Função principal otimizada"""
    print("=" * 80)
    print("🔧 PADRONIZADOR OTIMIZADO DE DATAS - OMIE V3")
    print("=" * 80)
    print(f"🕒 Iniciado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"💾 Banco: {DB_PATH}")
    print(f"🎯 Objetivo: Converter YYYY-MM-DD → DD/MM/YYYY")
    print()
    
    try:
        # 1. Análise inicial
        print("📊 ANÁLISE INICIAL")
        print("-" * 40)
        analise = analisar_estrutura()
        
        print(f"📋 Total de registros: {formatar_numero(analise['total_registros'])}")
        print("\n📈 Distribuição atual:")
        for formato in analise['formatos']:
            nome_formato = formato[0]
            total = formato[1]
            percentual = (total / analise['total_registros']) * 100
            print(f"  {nome_formato:12}: {formatar_numero(total):>10} ({percentual:5.1f}%)")
        
        print(f"\n🎯 Registros a converter: {formatar_numero(analise['necessita_conversao'])}")
        
        if analise['necessita_conversao'] == 0:
            print("\n✅ NENHUMA CONVERSÃO NECESSÁRIA!")
            print("Todas as datas já estão no formato DD/MM/YYYY")
            return
        
        # 2. Confirmação
        print(f"\n⚠️ CONVERSÃO: {analise['necessita_conversao']:,} registros YYYY-MM-DD → DD/MM/YYYY")
        resposta = input("Deseja continuar? (s/N): ").strip().lower()
        
        if resposta not in ['s', 'sim', 'y', 'yes']:
            print("❌ Operação cancelada pelo usuário")
            return
        
        # 3. Backup recomendado
        print("\n💾 RECOMENDAÇÃO: Faça backup do banco antes de continuar!")
        input("Pressione ENTER após fazer o backup (ou Ctrl+C para cancelar)...")
        
        # 4. Conversão
        print("\n🔧 INICIANDO CONVERSÃO")
        print("-" * 40)
        estatisticas = padronizar_datas_yyyy_mm_dd()
        
        # 5. Resultados
        print("\n📈 RESULTADOS DA CONVERSÃO")
        print("-" * 40)
        print(f" Registros encontrados: {formatar_numero(estatisticas['encontrados'])}")
        print(f"✅ Convertidos com sucesso: {formatar_numero(estatisticas['convertidos'])}")
        print(f"❌ Erros na conversão: {formatar_numero(estatisticas['erros'])}")
        
        taxa_sucesso = (estatisticas['convertidos'] / max(1, estatisticas['encontrados'])) * 100
        print(f"📊 Taxa de sucesso: {taxa_sucesso:.1f}%")
        
        # 6. Validação final
        print("\n✅ VALIDAÇÃO FINAL")
        print("-" * 40)
        validacao = validar_resultado()
        
        print(f"📋 Total de registros: {formatar_numero(validacao['total_registros'])}")
        print("\n📈 Distribuição final:")
        
        dd_mm_yyyy_final = 0
        yyyy_mm_dd_final = 0
        
        for formato in validacao['formatos_final']:
            nome_formato = formato[0]
            total = formato[1]
            percentual = (total / validacao['total_registros']) * 100
            print(f"  {nome_formato:12}: {formatar_numero(total):>10} ({percentual:5.1f}%)")
            
            if nome_formato == 'DD/MM/YYYY':
                dd_mm_yyyy_final = total
            elif nome_formato == 'YYYY-MM-DD':
                yyyy_mm_dd_final = total
        
        # Resultado final
        if yyyy_mm_dd_final == 0:
            print("\n PERFEITO! Todas as datas estão agora no formato DD/MM/YYYY!")
        elif yyyy_mm_dd_final < analise['necessita_conversao']:
            print(f"\n✨ PROGRESSO! Restam apenas {yyyy_mm_dd_final:,} datas no formato antigo")
        else:
            print(f"\n⚠️ ATENÇÃO: {yyyy_mm_dd_final:,} datas ainda estão no formato YYYY-MM-DD")
        
        print(f"\n📝 Log detalhado salvo em: padronizacao_datas.log")
        print(f"🕒 Finalizado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        
    except KeyboardInterrupt:
        print("\n❌ Operação interrompida pelo usuário")
    except Exception as e:
        logger.error(f"Erro durante execução: {e}")
        print(f"\n❌ Erro: {e}")

if __name__ == "__main__":
    main()
