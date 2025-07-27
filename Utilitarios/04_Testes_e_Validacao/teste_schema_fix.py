#!/usr/bin/env python3
"""
Teste rápido de correção do schema SQL.
"""

def testar_schema_sql():
    """Testa se o schema SQL está correto."""
    
    try:
        import sqlite3
        from src.utils import criar_schema_base
        
        # Teste em memória
        with sqlite3.connect(':memory:') as conn:
            criar_schema_base(conn, 'notas')
            
            # Verifica se tabela foi criada
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notas'")
            resultado = cursor.fetchone()
            
            if resultado:
                print("✅ Schema SQL corrigido com sucesso!")
                print("✅ Tabela 'notas' criada sem erros de sintaxe")
                return True
            else:
                print("❌ Tabela não foi criada")
                return False
                
    except Exception as e:
        print(f"❌ Erro no teste de schema: {e}")
        return False

if __name__ == "__main__":
    testar_schema_sql()
