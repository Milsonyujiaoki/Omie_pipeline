#!/usr/bin/env python3
"""
Verifica se os XMLs dos registros pendentes existem no diretório
"""

import sqlite3
from pathlib import Path
import time

def verificar_existencia_xmls():
    """Verifica se os XMLs dos registros pendentes existem"""
    
    print("=== VERIFICANDO EXISTÊNCIA DOS XMLs DOS REGISTROS PENDENTES ===")
    
    # Busca registros pendentes
    with sqlite3.connect('omie.db') as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cChaveNFe, dEmi, nNF 
            FROM notas 
            WHERE xml_baixado = 0 
            LIMIT 20
        """)
        registros = cursor.fetchall()
    
    resultado_dir = Path('resultado')
    encontrados = 0
    nao_encontrados = 0
    
    print(f"Verificando {len(registros)} registros pendentes...")
    print()
    
    for i, (chave, dEmi, nNF) in enumerate(registros, 1):
        print(f"[{i:2d}] Verificando: {chave}")
        
        # Busca o XML no diretório (busca mais específica)
        xml_files = list(resultado_dir.rglob(f"*{chave}*.xml"))
        
        if xml_files:
            print(f"     ✓ ENCONTRADO: {xml_files[0]}")
            print(f"     ✓ Tamanho: {xml_files[0].stat().st_size} bytes")
            encontrados += 1
        else:
            print(f"     ✗ NÃO ENCONTRADO")
            print(f"     ✗ dEmi: {dEmi}, nNF: {nNF}")
            nao_encontrados += 1
        
        print()
    
    print(f"RESUMO:")
    print(f"Encontrados: {encontrados}")
    print(f"Não encontrados: {nao_encontrados}")
    
    # Verifica se há padrão na data
    if nao_encontrados > 0:
        print()
        print("=== ANÁLISE DA DATA DOS REGISTROS PENDENTES ===")
        
        with sqlite3.connect('omie.db') as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT dEmi, COUNT(*) as qtd 
                FROM notas 
                WHERE xml_baixado = 0 
                GROUP BY dEmi 
                ORDER BY qtd DESC
            """)
            
            for data, qtd in cursor.fetchall():
                print(f"{data}: {qtd:,} registros")
        
        # Verifica se há XMLs para essa data específica
        print()
        print("=== VERIFICANDO DIRETÓRIO PARA DATA 01/05/2025 ===")
        
        # Converte data para estrutura de diretório
        data_dir = resultado_dir / "2025" / "05" / "01"
        
        if data_dir.exists():
            xml_count = len(list(data_dir.glob("*.xml")))
            print(f"Diretório existe: {data_dir}")
            print(f"Arquivos XML encontrados: {xml_count}")
            
            if xml_count > 0:
                print("Primeiros 5 arquivos:")
                for i, xml_file in enumerate(data_dir.glob("*.xml")):
                    if i >= 5:
                        break
                    print(f"  {xml_file.name}")
        else:
            print(f"Diretório NÃO existe: {data_dir}")
            
            # Verifica se há arquivos em outros diretórios para essa data
            print("Buscando arquivos XML com data 01/05/2025 em outros diretórios...")
            found_files = list(resultado_dir.rglob("*20250501*.xml"))
            print(f"Arquivos encontrados com padrão de data: {len(found_files)}")
            
            if found_files:
                print("Primeiros 5 arquivos encontrados:")
                for i, xml_file in enumerate(found_files[:5]):
                    print(f"  {xml_file}")

if __name__ == "__main__":
    verificar_existencia_xmls()
