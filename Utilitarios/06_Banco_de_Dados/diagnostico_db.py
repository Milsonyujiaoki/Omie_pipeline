import sqlite3

# Conectar ao banco
conn = sqlite3.connect('../../../omie.db')

print("=== DIAGNÓSTICO DO BANCO ===")

# Verificar colunas da tabela notas
print("\n1. Colunas da tabela 'notas':")
cursor = conn.execute("PRAGMA table_info(notas)")
columns = cursor.fetchall()
for col in columns:
    print(f"  {col[1]} ({col[2]})")

# Verificar se há dados na tabela
print("\n2. Contagem de registros:")
cursor = conn.execute("SELECT COUNT(*) FROM notas")
total = cursor.fetchone()[0]
print(f"  Total de registros: {total}")

# Verificar registros com nIdNF
print("\n3. Registros com nIdNF:")
cursor = conn.execute("SELECT COUNT(*) FROM notas WHERE nIdNF IS NOT NULL")
com_nidnf = cursor.fetchone()[0]
print(f"  Com nIdNF: {com_nidnf}")

# Verificar registros pendentes
print("\n4. XMLs pendentes:")
cursor = conn.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 0")
pendentes = cursor.fetchone()[0]
print(f"  Pendentes: {pendentes}")

# Testar consulta problemática
print("\n5. Testando consulta problemática:")
try:
    cursor = conn.execute("""
        SELECT nIdNF, cChaveNFe, dEmi, nNF
        FROM notas 
        WHERE xml_baixado = 0 AND nIdNF IS NOT NULL
        LIMIT 5
    """)
    rows = cursor.fetchall()
    print(f"  Sucesso! {len(rows)} registros encontrados")
    for row in rows[:3]:
        print(f"    {row}")
except Exception as e:
    print(f"  ERRO: {e}")

# Verificar views
print("\n6. Views disponíveis:")
try:
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='view'")
    views = cursor.fetchall()
    if views:
        for view in views:
            print(f"  - {view[0]}")
    else:
        print("  Nenhuma view encontrada")
except Exception as e:
    print(f"  ERRO: {e}")

# Verificar função de otimização
print("\n7. Testando função de otimização:")
try:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from src.utils import _verificar_views_e_indices_disponiveis
    
    otimizacoes = _verificar_views_e_indices_disponiveis('../../../omie.db')
    print(f"  Otimizações disponíveis: {otimizacoes}")
except Exception as e:
    print(f"  ERRO: {e}")

# Testar a consulta específica da view vw_notas_pendentes
print("\n8. Testando consulta da view vw_notas_pendentes:")
try:
    cursor = conn.execute("""
        SELECT nIdNF, cChaveNFe, dEmi, nNF, anomesdia
        FROM vw_notas_pendentes
        WHERE nIdNF IS NOT NULL
        LIMIT 3
    """)
    rows = cursor.fetchall()
    print(f"  Sucesso! {len(rows)} registros encontrados na view")
    for row in rows:
        print(f"    {row}")
except Exception as e:
    print(f"  ERRO na consulta da view: {e}")

# Verificar estrutura da view
print("\n9. Verificando estrutura da view vw_notas_pendentes:")
try:
    cursor = conn.execute("PRAGMA table_info(vw_notas_pendentes)")
    view_columns = cursor.fetchall()
    print("  Colunas da view:")
    for col in view_columns:
        print(f"    {col[1]} ({col[2]})")
except Exception as e:
    print(f"  ERRO: {e}")

# Testar consulta exata do erro
print("\n10. Testando consulta exata que está falhando:")
try:
    cursor = conn.execute("""
        SELECT nIdNF, cChaveNFe, dEmi, nNF, anomesdia
        FROM vw_notas_pendentes
        WHERE nIdNF IS NOT NULL
        ORDER BY anomesdia DESC, cChaveNFe
        LIMIT 1
    """)
    rows = cursor.fetchall()
    print(f"  Sucesso! Consulta exata funcionou: {len(rows)} registros")
    if rows:
        print(f"    Exemplo: {rows[0]}")
except Exception as e:
    print(f"  ERRO na consulta exata: {e}")

conn.close()
print("\n=== FIM DO DIAGNÓSTICO ===")
