#!/usr/bin/env python3
"""
Solução para registros pendentes - 01/05/2025
"""

import sqlite3
from pathlib import Path
from datetime import datetime

def resolver_registros_pendentes():
    """Resolve o problema dos registros pendentes"""
    
    print("=" * 70)
    print("SOLUÇÃO PARA REGISTROS PENDENTES - 01/05/2025")
    print("=" * 70)
    
    # Conecta ao banco
    with sqlite3.connect('omie.db') as conn:
        cursor = conn.cursor()
        
        # Verifica o problema
        cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 0 AND dEmi = '01/05/2025'")
        total_problema = cursor.fetchone()[0]
        print(f"Registros pendentes para 01/05/2025: {total_problema:,}")
        
        # Verifica se há registros baixados para essa data
        cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 1 AND dEmi = '01/05/2025'")
        baixados_mesma_data = cursor.fetchone()[0]
        print(f"Registros baixados para 01/05/2025: {baixados_mesma_data:,}")
        
        if baixados_mesma_data == 0:
            print("✅ CONFIRMADO: Essa data nunca foi processada")
            
            # Opções de solução
            print("\n" + "=" * 50)
            print("OPÇÕES DE SOLUÇÃO:")
            print("=" * 50)
            print("1. BAIXAR XMLs para a data 01/05/2025")
            print("2. REMOVER registros (se não são necessários)")
            print("3. MARCAR como inválidos para reprocessamento")
            print("4. VERIFICAR se há erro na data")
            
            # Mostra amostra dos dados
            print("\nAmostra dos registros:")
            cursor.execute("""
                SELECT cChaveNFe, nNF, cRazao, cnpj_cpf, nIdNF, nIdPedido
                FROM notas 
                WHERE xml_baixado = 0 AND dEmi = '01/05/2025'
                LIMIT 5
            """)
            
            for i, (chave, nNF, cRazao, cnpj, nIdNF, nIdPedido) in enumerate(cursor.fetchall(), 1):
                print(f"\n{i}. Chave: {chave}")
                print(f"   NFe: {nNF}")
                print(f"   Razão: {cRazao}")
                print(f"   CNPJ/CPF: {cnpj}")
                print(f"   nIdNF: {nIdNF}, nIdPedido: {nIdPedido}")
            
            # Verifica se os IDs são válidos
            print("\n" + "=" * 50)
            print("VERIFICAÇÃO DE VALIDADE DOS IDs:")
            print("=" * 50)
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN nIdNF IS NOT NULL AND nIdNF > 0 THEN 1 END) as com_nIdNF,
                    COUNT(CASE WHEN nIdPedido IS NOT NULL AND nIdPedido > 0 THEN 1 END) as com_nIdPedido
                FROM notas 
                WHERE xml_baixado = 0 AND dEmi = '01/05/2025'
            """)
            
            total, com_nIdNF, com_nIdPedido = cursor.fetchone()
            print(f"Total de registros: {total:,}")
            print(f"Com nIdNF válido: {com_nIdNF:,}")
            print(f"Com nIdPedido válido: {com_nIdPedido:,}")
            
            if com_nIdNF > 0:
                print("✅ Os registros têm IDs válidos - podem ser baixados")
            else:
                print("❌ Registros sem IDs válidos - provavelmente inválidos")
    
    # Oferece soluções automáticas
    print("\n" + "=" * 50)
    print("SOLUÇÕES AUTOMÁTICAS DISPONÍVEIS:")
    print("=" * 50)
    
    opcao = input("""
Escolha uma opção:
1. Tentar baixar XMLs para 01/05/2025
2. Marcar registros como inválidos
3. Remover registros (CUIDADO!)
4. Apenas mostrar relatório
5. Sair

Opção: """)
    
    if opcao == "1":
        print("Tentando baixar XMLs...")
        tentar_baixar_xmls_pendentes()
    elif opcao == "2":
        print("Marcando registros como inválidos...")
        marcar_como_invalidos()
    elif opcao == "3":
        confirmar = input("⚠️  ATENÇÃO: Isso removerá 21,586 registros! Confirma? (digite 'SIM'): ")
        if confirmar == "SIM":
            remover_registros_pendentes()
        else:
            print("❌ Operação cancelada")
    elif opcao == "4":
        print("✅ Relatório mostrado acima")
    else:
        print("👋 Saindo...")

def tentar_baixar_xmls_pendentes():
    """Tenta baixar os XMLs pendentes usando o extrator"""
    
    print("Preparando para baixar XMLs para 01/05/2025...")
    
    # Verifica se há configuração para baixar por data específica
    print("Para baixar esses XMLs, você pode:")
    print("1. Executar: python src/extrator_async.py --data 01/05/2025")
    print("2. Ou adicionar a data no arquivo de configuração")
    print("3. Ou usar a função de reprocessamento")
    
    print("\nScript para baixar esses XMLs:")
    print("-" * 30)
    print("""
# Criar script para baixar XMLs pendentes
import sqlite3
from src.extrator_async import baixar_xmls_por_data

# Busca os IDs dos registros pendentes
with sqlite3.connect('omie.db') as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT nIdNF FROM notas WHERE xml_baixado = 0 AND dEmi = '01/05/2025'")
    ids = [row[0] for row in cursor.fetchall()]

print(f"Baixando {len(ids)} XMLs...")
# baixar_xmls_por_ids(ids)
""")

def marcar_como_invalidos():
    """Marca os registros como inválidos"""
    
    with sqlite3.connect('omie.db') as conn:
        cursor = conn.cursor()
        
        # Marca como inválidos (se a coluna existir)
        try:
            cursor.execute("""
                UPDATE notas 
                SET status = 'INVALIDO' 
                WHERE xml_baixado = 0 AND dEmi = '01/05/2025'
            """)
            affected = cursor.rowcount
            conn.commit()
            print(f"✅ {affected:,} registros marcados como inválidos")
        except sqlite3.OperationalError as e:
            print(f"❌ Erro: {e}")
            print("Coluna 'status' não existe. Adicionando...")
            
            cursor.execute("ALTER TABLE notas ADD COLUMN status TEXT DEFAULT NULL")
            cursor.execute("""
                UPDATE notas 
                SET status = 'INVALIDO' 
                WHERE xml_baixado = 0 AND dEmi = '01/05/2025'
            """)
            affected = cursor.rowcount
            conn.commit()
            print(f"✅ {affected:,} registros marcados como inválidos")

def remover_registros_pendentes():
    """Remove os registros pendentes (CUIDADO!)"""
    
    with sqlite3.connect('omie.db') as conn:
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM notas WHERE xml_baixado = 0 AND dEmi = '01/05/2025'")
        affected = cursor.rowcount
        conn.commit()
        print(f"✅ {affected:,} registros removidos")

if __name__ == "__main__":
    resolver_registros_pendentes()
