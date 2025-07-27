#!/usr/bin/env python3
"""
Análise detalhada dos registros pendentes no banco de dados
"""

import sqlite3
import sys
from pathlib import Path

def analisar_registros_pendentes():
    """Analisa os registros pendentes no banco de dados"""
    
    db_path = "omie.db"
    if not Path(db_path).exists():
        print(f"ERRO: Banco de dados não encontrado: {db_path}")
        return
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            print("=" * 60)
            print("ANÁLISE DE REGISTROS PENDENTES")
            print("=" * 60)
            
            # 1. Estatísticas gerais
            cursor.execute("SELECT COUNT(*) FROM notas")
            total = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 0")
            pendentes = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 1")
            baixados = cursor.fetchone()[0]
            
            print(f"Total de registros no banco: {total:,}")
            print(f"Registros pendentes: {pendentes:,} ({pendentes/total*100:.1f}%)")
            print(f"Registros baixados: {baixados:,} ({baixados/total*100:.1f}%)")
            print()
            
            # 2. Análise de campos vazios
            print("ANÁLISE DE CAMPOS ESSENCIAIS VAZIOS")
            print("-" * 40)
            
            campos = {
                'dEmi': 'Data de emissão',
                'nNF': 'Número da NFe',
                'cRazao': 'Razão social',
                'cnpj_cpf': 'CNPJ/CPF',
                'nIdNF': 'ID da NFe',
                'nIdPedido': 'ID do pedido'
            }
            
            for campo, descricao in campos.items():
                cursor.execute(f"""
                    SELECT COUNT(*) FROM notas 
                    WHERE xml_baixado = 0 AND ({campo} IS NULL OR {campo} = '')
                """)
                vazios = cursor.fetchone()[0]
                print(f"{descricao:20} vazio: {vazios:,} registros")
            
            print()
            
            # 3. Registros com caminho_arquivo NULL
            cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 0 AND caminho_arquivo IS NULL")
            sem_caminho = cursor.fetchone()[0]
            print(f"Registros sem caminho_arquivo: {sem_caminho:,}")
            
            # 4. Registros com erro
            try:
                cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 0 AND erro = 1")
                com_erro = cursor.fetchone()[0]
                print(f"Registros com erro: {com_erro:,}")
            except:
                print("Coluna 'erro' não existe no banco")
            
            print()
            
            # 5. Distribuição por data de emissão
            print("DISTRIBUIÇÃO POR DATA DE EMISSÃO (TOP 10)")
            print("-" * 40)
            cursor.execute("""
                SELECT dEmi, COUNT(*) as qtd 
                FROM notas 
                WHERE xml_baixado = 0 AND dEmi IS NOT NULL AND dEmi != ''
                GROUP BY dEmi 
                ORDER BY qtd DESC 
                LIMIT 10
            """)
            
            for row in cursor.fetchall():
                data, qtd = row
                print(f"{data}: {qtd:,} registros")
            
            # 6. Registros sem data de emissão
            cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 0 AND (dEmi IS NULL OR dEmi = '')")
            sem_data = cursor.fetchone()[0]
            print(f"\nRegistros sem data de emissão: {sem_data:,}")
            
            print()
            
            # 7. Amostra de registros pendentes
            print("AMOSTRA DE REGISTROS PENDENTES")
            print("-" * 40)
            cursor.execute("""
                SELECT cChaveNFe, dEmi, nNF, cRazao, cnpj_cpf, caminho_arquivo
                FROM notas 
                WHERE xml_baixado = 0 
                LIMIT 5
            """)
            
            for i, row in enumerate(cursor.fetchall(), 1):
                chave, dEmi, nNF, cRazao, cnpj_cpf, caminho = row
                print(f"{i}. Chave: {chave}")
                print(f"   dEmi: {dEmi}")
                print(f"   nNF: {nNF}")
                print(f"   cRazao: {cRazao}")
                print(f"   cnpj_cpf: {cnpj_cpf}")
                print(f"   caminho_arquivo: {caminho}")
                print()
            
            # 8. Análise de possíveis causas
            print("POSSÍVEIS CAUSAS DOS REGISTROS PENDENTES")
            print("-" * 40)
            
            # Campos completamente vazios
            cursor.execute("""
                SELECT COUNT(*) FROM notas 
                WHERE xml_baixado = 0 
                AND (dEmi IS NULL OR dEmi = '') 
                AND (nNF IS NULL OR nNF = '')
                AND (cRazao IS NULL OR cRazao = '')
            """)
            completamente_vazios = cursor.fetchone()[0]
            print(f"Registros com múltiplos campos vazios: {completamente_vazios:,}")
            
            # Registros com chave mas sem dados
            cursor.execute("""
                SELECT COUNT(*) FROM notas 
                WHERE xml_baixado = 0 
                AND cChaveNFe IS NOT NULL 
                AND cChaveNFe != ''
                AND (dEmi IS NULL OR dEmi = '')
            """)
            chave_sem_dados = cursor.fetchone()[0]
            print(f"Registros com chave mas sem dEmi: {chave_sem_dados:,}")
            
            # Registros antigos
            cursor.execute("""
                SELECT COUNT(*) FROM notas 
                WHERE xml_baixado = 0 
                AND dEmi IS NOT NULL 
                AND dEmi != ''
                AND dEmi < '2025-01-01'
            """)
            antigos = cursor.fetchone()[0]
            print(f"Registros com dEmi anterior a 2025: {antigos:,}")
            
            print()
            print("=" * 60)
            print("ANÁLISE CONCLUÍDA")
            print("=" * 60)
            
    except Exception as e:
        print(f"ERRO durante análise: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analisar_registros_pendentes()
