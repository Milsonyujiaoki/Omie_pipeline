#!/usr/bin/env python3
"""
Script para corrigir a view vw_notas_pendentes adicionando a coluna nIdNF.
"""
import sqlite3

def corrigir_view_notas_pendentes():
    """Corrige a view vw_notas_pendentes para incluir a coluna nIdNF."""
    
    conn = sqlite3.connect('../../../omie.db')
    cursor = conn.cursor()
    
    print("=== CORREÇÃO DA VIEW VW_NOTAS_PENDENTES ===")
    
    # Verificar se a view existe
    print("\n1. Verificando view atual...")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='vw_notas_pendentes'")
    view_exists = cursor.fetchone()
    
    if view_exists:
        print("   ✓ View vw_notas_pendentes encontrada")
        
        # Verificar colunas atuais da view
        try:
            cursor.execute("PRAGMA table_info(vw_notas_pendentes)")
            current_columns = cursor.fetchall()
            print("   Colunas atuais:")
            for col in current_columns:
                print(f"     - {col[1]}")
            
            # Verificar se nIdNF já existe
            has_nidnf = any(col[1] == 'nIdNF' for col in current_columns)
            if has_nidnf:
                print("   ✓ View já contém a coluna nIdNF - nenhuma correção necessária")
                conn.close()
                return
                
        except Exception as e:
            print(f"   ⚠ Erro ao verificar colunas: {e}")
    else:
        print("   ⚠ View vw_notas_pendentes não encontrada")
    
    print("\n2. Recriando view com coluna nIdNF...")
    
    # Dropar view existente
    try:
        cursor.execute("DROP VIEW IF EXISTS vw_notas_pendentes")
        print("   ✓ View antiga removida")
    except Exception as e:
        print(f"   ⚠ Erro ao remover view: {e}")
    
    # Criar nova view com nIdNF
    create_view_sql = """
    CREATE VIEW IF NOT EXISTS vw_notas_pendentes AS
    SELECT 
        cChaveNFe,
        nIdNF,
        nNF,
        dEmi,
        cRazao,
        vNF,
        anomesdia,
        CASE 
            WHEN anomesdia IS NOT NULL THEN
                SUBSTR(CAST(anomesdia AS TEXT), 1, 4) || '-' ||
                SUBSTR(CAST(anomesdia AS TEXT), 5, 2) || '-' ||
                SUBSTR(CAST(anomesdia AS TEXT), 7, 2)
            ELSE dEmi
        END as data_formatada
    FROM notas
    WHERE xml_baixado = 0
    ORDER BY anomesdia DESC, nNF
    """
    
    try:
        cursor.execute(create_view_sql)
        print("   ✓ Nova view criada com sucesso")
    except Exception as e:
        print(f"   ✗ Erro ao criar view: {e}")
        conn.close()
        return
    
    print("\n3. Verificando nova view...")
    try:
        # Verificar estrutura da nova view
        cursor.execute("PRAGMA table_info(vw_notas_pendentes)")
        new_columns = cursor.fetchall()
        print("   Novas colunas:")
        for col in new_columns:
            print(f"     - {col[1]}")
        
        # Testar consulta com nIdNF
        cursor.execute("""
            SELECT nIdNF, cChaveNFe, dEmi, nNF, anomesdia
            FROM vw_notas_pendentes
            WHERE nIdNF IS NOT NULL
            LIMIT 3
        """)
        test_rows = cursor.fetchall()
        print(f"   ✓ Teste da consulta com nIdNF: {len(test_rows)} registros encontrados")
        
        if test_rows:
            print("   Exemplo de dados:")
            for row in test_rows[:1]:
                print(f"     nIdNF: {row[0]}, cChaveNFe: {row[1][:20]}..., nNF: {row[3]}")
                
    except Exception as e:
        print(f"   ✗ Erro ao verificar nova view: {e}")
    
    # Commit e close
    conn.commit()
    conn.close()
    
    print("\n=== CORREÇÃO CONCLUÍDA ===")
    print("A view vw_notas_pendentes agora inclui a coluna nIdNF")
    print("O extrator_async.py deve funcionar corretamente agora")

if __name__ == "__main__":
    corrigir_view_notas_pendentes()
