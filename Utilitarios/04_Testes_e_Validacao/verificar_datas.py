#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('omie.db')
cursor = conn.cursor()

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

print(f"Total de registros: {total_registros}")
print(f"Datas inválidas: {datas_invalidas}")
print(f"Percentual: {(datas_invalidas/total_registros*100):.2f}%")
print("\nExemplos de datas inválidas:")
for ex in exemplos:
    print(f"  Chave: {ex[0][:20]}..., Data: '{ex[1]}', NFe: {ex[2]}")

conn.close()
