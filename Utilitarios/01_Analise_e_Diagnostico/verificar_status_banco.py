#!/usr/bin/env python3
"""
Verificação rápida dos registros pendentes
"""

import sqlite3

def verificar_pendentes():
    """Verifica registros pendentes no banco"""
    
    with sqlite3.connect('omie.db') as conn:
        cursor = conn.cursor()
        
        # Total de registros
        cursor.execute("SELECT COUNT(*) FROM notas")
        total = cursor.fetchone()[0]
        
        # Registros pendentes
        cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 0")
        pendentes_total = cursor.fetchone()[0]
        
        # Registros pendentes de 01/05/2025
        cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 0 AND dEmi = '01/05/2025'")
        pendentes_0105 = cursor.fetchone()[0]
        
        # Registros baixados
        cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 1")
        baixados = cursor.fetchone()[0]
        
        print("=" * 60)
        print("RELATÓRIO DE STATUS DO BANCO DE DADOS")
        print("=" * 60)
        print(f"Total de registros no banco: {total:,}")
        print(f"Registros com XML baixado:   {baixados:,}")
        print(f"Registros pendentes (total): {pendentes_total:,}")
        print(f"Registros pendentes 01/05:   {pendentes_0105:,}")
        print(f"Percentual pendente:         {(pendentes_total/total)*100:.1f}%")
        
        if pendentes_0105 > 0:
            print("\n⚠️  AINDA HÁ REGISTROS PENDENTES PARA 01/05/2025")
            print("   Execute o script de download para resolver.")
        else:
            print("\n✅ Todos os registros de 01/05/2025 foram processados!")
        
        # Verifica se há outros registros pendentes
        cursor.execute("""
            SELECT dEmi, COUNT(*) as total
            FROM notas 
            WHERE xml_baixado = 0 AND dEmi != '01/05/2025'
            GROUP BY dEmi
            ORDER BY total DESC
            LIMIT 5
        """)
        
        outros_pendentes = cursor.fetchall()
        
        if outros_pendentes:
            print("\n📋 Outras datas com registros pendentes:")
            for data, qtd in outros_pendentes:
                print(f"   {data}: {qtd:,} registros")

if __name__ == "__main__":
    verificar_pendentes()
