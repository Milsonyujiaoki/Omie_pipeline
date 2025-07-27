#!/usr/bin/env python3
"""Teste super simples da estrutura"""

import sqlite3

conn = sqlite3.connect('omie.db')
cursor = conn.cursor()

print("=== TESTE SIMPLES ===")

# Contagem básica
cursor.execute("SELECT COUNT(*) FROM notas")
total = cursor.fetchone()[0]
print(f"Total: {total:,}")

# Formatos simples
cursor.execute("""
    SELECT 
        CASE 
            WHEN dEmi LIKE '__/__/____' THEN 'DD/MM/YYYY'
            WHEN dEmi LIKE '____-__-__' THEN 'YYYY-MM-DD'
            ELSE 'OUTROS'
        END as formato,
        COUNT(*) as total
    FROM notas 
    GROUP BY formato
    ORDER BY total DESC
    LIMIT 5
""")

formatos = cursor.fetchall()
for formato, total_formato in formatos:
    print(f"{formato}: {total_formato:,}")

conn.close()
print("✅ Teste concluído")
