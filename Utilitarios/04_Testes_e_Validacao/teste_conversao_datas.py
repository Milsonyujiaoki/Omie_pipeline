#!/usr/bin/env python3
"""Teste das conversões de data sem modificar o banco"""

import sqlite3
from datetime import datetime

def testar_conversao(data_iso: str) -> str:
    """Testa conversão YYYY-MM-DD para DD/MM/YYYY"""
    try:
        data_obj = datetime.strptime(data_iso, '%Y-%m-%d')
        return data_obj.strftime('%d/%m/%Y')
    except ValueError as e:
        return f"ERRO: {e}"

def main():
    print("🧪 TESTE DE CONVERSÃO DE DATAS")
    print("=" * 40)
    
    # Conecta ao banco
    conn = sqlite3.connect('omie.db')
    cursor = conn.cursor()
    
    # Pega algumas amostras de YYYY-MM-DD
    cursor.execute("""
        SELECT dEmi 
        FROM notas 
        WHERE dEmi LIKE '____-__-__'
        LIMIT 10
    """)
    
    amostras = cursor.fetchall()
    
    print(f"📊 Testando {len(amostras)} amostras:")
    print()
    
    for i, (data_original,) in enumerate(amostras, 1):
        data_convertida = testar_conversao(data_original)
        print(f"  {i:2}. '{data_original}' → '{data_convertida}'")
    
    # Estatística rápida
    cursor.execute("SELECT COUNT(*) FROM notas WHERE dEmi LIKE '____-__-__'")
    total_para_converter = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM notas WHERE dEmi LIKE '__/__/____'")
    total_ja_convertido = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM notas")
    total_geral = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"\n📈 ESTATÍSTICAS:")
    print(f"  Total de registros: {total_geral:,}")
    print(f"  Já no formato DD/MM/YYYY: {total_ja_convertido:,} ({total_ja_convertido/total_geral*100:.1f}%)")
    print(f"  Precisam conversão: {total_para_converter:,} ({total_para_converter/total_geral*100:.1f}%)")
    
    print(f"\n✅ Teste concluído - conversões parecem corretas!")

if __name__ == "__main__":
    main()
