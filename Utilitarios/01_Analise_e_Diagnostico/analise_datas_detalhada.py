#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('omie.db')
cursor = conn.cursor()

# Verifica estrutura da tabela
print("=== ESTRUTURA DA TABELA ===")
cursor.execute("PRAGMA table_info(notas)")
colunas = cursor.fetchall()
for col in colunas:
    print(f"{col[1]:20} {col[2]:10} {'PK' if col[5] else ''}")

print("\n=== AMOSTRA DE DADOS ===")
cursor.execute("SELECT cChaveNFe, dEmi, nNF FROM notas LIMIT 5")
amostras = cursor.fetchall()
for amostra in amostras:
    print(f"Chave: {amostra[0][:20]}... Data: '{amostra[1]}' NFe: {amostra[2]}")

print("\n=== ANÁLISE DE DATAS ===")
# Verifica datas inválidas
cursor.execute("""
    SELECT COUNT(*) FROM notas 
    WHERE dEmi IS NULL 
       OR dEmi = '' 
       OR dEmi = '0000-00-00' 
       OR dEmi = '1900-01-01' 
       OR LENGTH(dEmi) < 8
""")
datas_invalidas = cursor.fetchone()[0]

# Total de registros
cursor.execute("SELECT COUNT(*) FROM notas")
total_registros = cursor.fetchone()[0]

print(f"Total de registros: {total_registros}")
print(f"Datas inválidas: {datas_invalidas}")
print(f"Percentual: {(datas_invalidas/total_registros*100):.2f}%")

# Exemplos de datas inválidas
cursor.execute("""
    SELECT cChaveNFe, dEmi, nNF 
    FROM notas 
    WHERE dEmi IS NULL 
       OR dEmi = '' 
       OR dEmi = '0000-00-00' 
       OR dEmi = '1900-01-01' 
       OR LENGTH(dEmi) < 8
    LIMIT 5
""")
exemplos = cursor.fetchall()

print("\nExemplos de datas inválidas:")
for ex in exemplos:
    print(f"  Chave: {ex[0][:20]}..., Data: '{ex[1]}', NFe: {ex[2]}")

# Verifica formatos de data existentes
print("\n=== FORMATOS DE DATA ENCONTRADOS ===")
cursor.execute("""
    SELECT DISTINCT 
        CASE 
            WHEN dEmi LIKE '__/__/____' THEN 'DD/MM/YYYY'
            WHEN dEmi LIKE '____-__-__' THEN 'YYYY-MM-DD'
            WHEN dEmi IS NULL THEN 'NULL'
            WHEN dEmi = '' THEN 'VAZIO'
            ELSE 'OUTRO: ' || dEmi
        END as formato,
        COUNT(*) as total
    FROM notas 
    GROUP BY formato
    ORDER BY total DESC
    LIMIT 10
""")
formatos = cursor.fetchall()
for fmt in formatos:
    print(f"{fmt[0]:20}: {fmt[1]:,} registros")

conn.close()
