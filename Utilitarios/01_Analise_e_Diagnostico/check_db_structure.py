#!/usr/bin/env python3
import sqlite3

def check_database_structure():
    conn = sqlite3.connect('omie.db')
    cursor = conn.cursor()
    
    print("=== ESTRUTURA DA TABELA NOTAS ===")
    cursor.execute("PRAGMA table_info(notas)")
    cols = cursor.fetchall()
    for col in cols:
        print(f"{col[1]:20} {col[2]:15} {'PRIMARY KEY' if col[5] else ''} {'NOT NULL' if col[3] else ''}")
    
    print("\n=== VIEWS EXISTENTES ===")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
    views = cursor.fetchall()
    for view in views:
        print(view[0])
    
    print("\n=== ÍNDICES EXISTENTES ===")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indices = cursor.fetchall()
    for index in indices:
        if not index[0].startswith('sqlite_'):
            print(index[0])
    
    print("\n=== ESTATÍSTICAS RÁPIDAS ===")
    cursor.execute("SELECT COUNT(*) FROM notas")
    total = cursor.fetchone()[0]
    print(f"Total de registros: {total:,}")
    
    cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 1")
    baixados = cursor.fetchone()[0]
    print(f"XMLs baixados: {baixados:,}")
    
    cursor.execute("SELECT COUNT(*) FROM notas WHERE anomesdia IS NOT NULL")
    com_anomesdia = cursor.fetchone()[0]
    print(f"Registros com anomesdia: {com_anomesdia:,}")
    
    conn.close()

if __name__ == "__main__":
    check_database_structure()
