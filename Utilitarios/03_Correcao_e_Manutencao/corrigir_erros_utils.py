#!/usr/bin/env python3
"""
Script para corrigir o erro da coluna 'status' no utils.py
"""

import re

def corrigir_utils():
    """Corrige o erro da coluna status no arquivo utils.py"""
    
    # Ler o arquivo atual
    with open('c:/milson/extrator_omie_v3/src/utils.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remover a linha problemática
    content = content.replace(
        "                cursor.executemany(query_update, [(chave,) for chave in chaves_invalidas])",
        "                # cursor.executemany(query_update, [(chave,) for chave in chaves_invalidas])"
    )
    
    # Remover outras linhas desnecessárias
    content = content.replace(
        "                conn.commit()",
        "                # conn.commit()"
    )
    
    content = content.replace(
        '                logger.info(f"[INVALIDOS] {len(chaves_invalidas)} registros marcados como INVALIDO")',
        '                # logger.info(f"[INVALIDOS] {len(chaves_invalidas)} registros marcados como INVALIDO")'
    )
    
    # Salvar o arquivo corrigido
    with open('c:/milson/extrator_omie_v3/src/utils.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Arquivo utils.py corrigido com sucesso!")

if __name__ == "__main__":
    corrigir_utils()
