#!/usr/bin/env python3
"""
TESTE RÁPIDO - Verificação da estrutura do banco e script de correção

Este script verifica se a estrutura do banco está compatível com o script de correção.
"""

import sys
import os
import sqlite3
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def verificar_estrutura_banco(db_path: str = "omie.db"):
    """Verifica a estrutura atual do banco de dados."""
    
    if not Path(db_path).exists():
        print(f"❌ Banco {db_path} não encontrado")
        return False
    
    print(f" Verificando estrutura do banco: {db_path}")
    print("=" * 50)
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Verificar colunas da tabela notas
            cursor.execute("PRAGMA table_info(notas)")
            colunas = cursor.fetchall()
            
            print("📋 COLUNAS DA TABELA 'notas':")
            campos_encontrados = {}
            for col in colunas:
                nome = col[1]
                tipo = col[2]
                print(f"   {nome:<20} {tipo}")
                campos_encontrados[nome] = tipo
            
            # Verificar campos essenciais
            campos_essenciais = [
                'nIdNF', 'cChaveNFe', 'nNF', 'dEmi', 'cnpj_cpf', 'cRazao',
                'xml_baixado', 'xml_vazio', 'erro', 'caminho_arquivo', 'anomesdia'
            ]
            
            print(f"\n✅ VERIFICAÇÃO DE CAMPOS ESSENCIAIS:")
            campos_ok = 0
            for campo in campos_essenciais:
                if campo in campos_encontrados:
                    print(f"   ✓ {campo}")
                    campos_ok += 1
                else:
                    print(f"   ❌ {campo} - AUSENTE")
            
            print(f"\n📊 CAMPOS: {campos_ok}/{len(campos_essenciais)} encontrados")
            
            # Verificar índices
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='notas'")
            indices = cursor.fetchall()
            
            print(f"\n🔗 ÍNDICES EXISTENTES:")
            for idx in indices:
                print(f"   • {idx[0]}")
            
            # Verificar views
            cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
            views = cursor.fetchall()
            
            print(f"\n👁️ VIEWS EXISTENTES:")
            for view in views:
                print(f"   • {view[0]}")
            
            # Contar registros pendentes
            try:
                cursor.execute("""
                    SELECT COUNT(*) FROM notas 
                    WHERE xml_baixado = 0 AND erro = 0 
                    AND cChaveNFe IS NOT NULL AND cChaveNFe != ''
                """)
                pendentes = cursor.fetchone()[0]
                print(f"\n📈 ESTATÍSTICAS:")
                print(f"   Registros pendentes: {pendentes:,}")
                
                # Total de registros
                cursor.execute("SELECT COUNT(*) FROM notas")
                total = cursor.fetchone()[0]
                print(f"   Total de registros: {total:,}")
                
                if total > 0:
                    percentual = (pendentes / total) * 100
                    print(f"   Percentual pendente: {percentual:.1f}%")
                
            except Exception as e:
                print(f"   ❌ Erro ao contar registros: {e}")
            
            return campos_ok >= len(campos_essenciais) * 0.8  # 80% dos campos
            
    except Exception as e:
        print(f"❌ Erro ao verificar banco: {e}")
        return False

def testar_consulta_pendentes(db_path: str = "omie.db", limite: int = 5):
    """Testa a consulta de registros pendentes."""
    
    print(f"\n🧪 TESTE DE CONSULTA PENDENTES (máx {limite} registros)")
    print("=" * 50)
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Testar consulta principal
            sql = """
                SELECT nIdNF, cChaveNFe, nNF, dEmi, cnpj_cpf, cRazao
                FROM notas 
                WHERE xml_baixado = 0 
                  AND erro = 0 
                  AND cChaveNFe IS NOT NULL 
                  AND cChaveNFe != ''
                  AND cChaveNFe != 'NULL'
                ORDER BY nIdNF
                LIMIT ?
            """
            
            cursor.execute(sql, (limite,))
            resultados = cursor.fetchall()
            
            print(f"📋 RESULTADOS DA CONSULTA ({len(resultados)} registros):")
            
            for i, row in enumerate(resultados, 1):
                print(f"   {i}. ID: {row[0]}, Chave: {row[1][:10]}..., NF: {row[2]}")
                print(f"      Data: {row[3]}, CNPJ: {row[4]}")
                print(f"      Razão: {(row[5] or 'N/A')[:30]}...")
                print()
            
            if len(resultados) > 0:
                print("✅ Consulta funcionando corretamente!")
                return True
            else:
                print("⚠️ Nenhum registro pendente encontrado")
                return True
                
    except Exception as e:
        print(f"❌ Erro na consulta: {e}")
        return False

def main():
    """Função principal de teste."""
    
    print("🔧 TESTE DE ESTRUTURA E COMPATIBILIDADE")
    print("=" * 60)
    
    # Verificar se arquivo de configuração existe
    config_file = Path("configuracao.ini")
    if config_file.exists():
        print("✅ Arquivo configuracao.ini encontrado")
    else:
        print("❌ Arquivo configuracao.ini NÃO encontrado")
        print("   O script precisará deste arquivo para funcionar")
    
    # Verificar estrutura do banco
    estrutura_ok = verificar_estrutura_banco()
    
    # Testar consulta se estrutura OK
    if estrutura_ok:
        consulta_ok = testar_consulta_pendentes()
    else:
        consulta_ok = False
    
    # Resultado final
    print("\n" + "=" * 60)
    print("📊 RESULTADO FINAL DO TESTE")
    print("=" * 60)
    
    if estrutura_ok and consulta_ok:
        print(" ESTRUTURA COMPATÍVEL - Script pode ser executado!")
        print("\nPara executar o script de correção:")
        print("   python corrigir_base_pendentes.py --limite 10")
        return True
    else:
        print("❌ PROBLEMAS DETECTADOS - Verificar estrutura do banco")
        if not estrutura_ok:
            print("   • Campos da tabela não compatíveis")
        if not consulta_ok:
            print("   • Consulta de pendentes com erro")
        return False

if __name__ == "__main__":
    sucesso = main()
    sys.exit(0 if sucesso else 1)
