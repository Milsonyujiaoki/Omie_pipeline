#!/usr/bin/env python3
"""
Script para padronizar o formato da coluna dEmi no banco de dados.
Converte todas as datas para o formato dd/mm/yyyy.
"""

import sqlite3
import re
from datetime import datetime
from pathlib import Path

def normalizar_data_para_ddmmyyyy(data_str):
    """
    Normaliza uma string de data para o formato dd/mm/yyyy.
    
    Args:
        data_str: String de data em varios formatos possiveis
        
    Returns:
        String no formato dd/mm/yyyy ou None se invalida
    """
    if not data_str or data_str.strip() == '':
        return None
    
    data_str = data_str.strip()
    
    # Padrões suportados
    padroes = [
        r'^(\d{2})/(\d{2})/(\d{4})$',  # dd/mm/yyyy
        r'^(\d{4})-(\d{2})-(\d{2})$',  # yyyy-mm-dd
        r'^(\d{2})-(\d{2})-(\d{4})$',  # dd-mm-yyyy
        r'^(\d{4})/(\d{2})/(\d{2})$',  # yyyy/mm/dd
        r'^(\d{1,2})/(\d{1,2})/(\d{4})$',  # d/m/yyyy ou dd/m/yyyy
    ]
    
    for padrao in padroes:
        match = re.match(padrao, data_str)
        if match:
            g1, g2, g3 = match.groups()
            
            # Detecta formato pela posicoo do ano
            if len(g1) == 4:  # yyyy-mm-dd ou yyyy/mm/dd
                ano, mes, dia = g1, g2, g3
            elif len(g3) == 4:  # dd/mm/yyyy ou dd-mm-yyyy
                dia, mes, ano = g1, g2, g3
            else:
                continue
            
            # Valida e formata
            try:
                dia = int(dia)
                mes = int(mes)
                ano = int(ano)
                
                # Validacoo basica
                if not (1 <= dia <= 31 and 1 <= mes <= 12 and 1900 <= ano <= 2100):
                    continue
                
                # Formato final: dd/mm/yyyy
                return f"{dia:02d}/{mes:02d}/{ano}"
                
            except (ValueError, TypeError):
                continue
    
    return None

def atualizar_formato_demi(db_path):
    """
    Atualiza o formato da coluna dEmi no banco de dados.
    
    Args:
        db_path: Caminho para o banco SQLite
    """
    print(f"Iniciando padronizacoo de datas em: {db_path}")
    
    try:
        with sqlite3.connect(db_path) as conn:
            # Busca todos os registros com dEmi
            cursor = conn.execute("SELECT cChaveNFe, dEmi FROM notas WHERE dEmi IS NOT NULL AND dEmi != ''")
            registros = cursor.fetchall()
            
            print(f"Encontrados {len(registros)} registros com dEmi para processar")
            
            atualizados = 0
            problemas = 0
            
            for chave, demi_atual in registros:
                nova_demi = normalizar_data_para_ddmmyyyy(demi_atual)
                
                if nova_demi and nova_demi != demi_atual:
                    try:
                        conn.execute(
                            "UPDATE notas SET dEmi = ? WHERE cChaveNFe = ?",
                            (nova_demi, chave)
                        )
                        atualizados += 1
                        if atualizados % 1000 == 0:
                            print(f"Processados {atualizados} registros...")
                    except Exception as e:
                        print(f"Erro ao atualizar {chave}: {e}")
                        problemas += 1
                elif not nova_demi:
                    print(f"Data invalida para {chave}: '{demi_atual}'")
                    problemas += 1
            
            conn.commit()
            print(f"Padronizacoo concluida:")
            print(f"  - Registros atualizados: {atualizados}")
            print(f"  - Problemas encontrados: {problemas}")
            print(f"  - Total processado: {len(registros)}")
            
    except Exception as e:
        print(f"Erro durante padronizacoo: {e}")
        raise

if __name__ == "__main__":
    db_path = Path("omie.db")
    
    if not db_path.exists():
        print(f"Banco de dados noo encontrado: {db_path}")
        exit(1)
    
    # Faz backup do banco
    backup_path = db_path.with_suffix('.backup')
    print(f"Criando backup em: {backup_path}")
    
    import shutil
    shutil.copy2(db_path, backup_path)
    
    # Executa padronizacoo
    atualizar_formato_demi(db_path)
    
    print("Padronizacoo concluida com sucesso!")
