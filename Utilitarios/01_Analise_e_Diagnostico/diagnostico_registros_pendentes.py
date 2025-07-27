#!/usr/bin/env python3
"""
Diagnóstico completo dos registros pendentes
"""

import sqlite3
from pathlib import Path
from datetime import datetime

def diagnosticar_registros_pendentes():
    """Faz um diagnóstico completo dos registros pendentes"""
    
    print("=" * 70)
    print("DIAGNÓSTICO COMPLETO DOS REGISTROS PENDENTES")
    print("=" * 70)
    
    # 1. Análise do banco de dados
    with sqlite3.connect('omie.db') as conn:
        cursor = conn.cursor()
        
        # Total de registros pendentes
        cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 0")
        total_pendentes = cursor.fetchone()[0]
        print(f"Total de registros pendentes: {total_pendentes:,}")
        
        # Distribuição por data
        cursor.execute("""
            SELECT dEmi, COUNT(*) as qtd 
            FROM notas 
            WHERE xml_baixado = 0 
            GROUP BY dEmi 
            ORDER BY qtd DESC
        """)
        
        print("\nDistribuição por data:")
        for data, qtd in cursor.fetchall():
            print(f"  {data}: {qtd:,} registros")
        
        # Verifica se há padrão na data
        cursor.execute("SELECT dEmi FROM notas WHERE xml_baixado = 0 LIMIT 1")
        data_problema = cursor.fetchone()[0]
        print(f"\nData problemática: {data_problema}")
        
        # Converte para formato de diretório
        if data_problema:
            try:
                data_dt = datetime.strptime(data_problema, '%d/%m/%Y')
                ano = data_dt.strftime('%Y')
                mes = data_dt.strftime('%m')
                dia = data_dt.strftime('%d')
                print(f"Estrutura de diretório esperada: resultado/{ano}/{mes}/{dia}")
                
                # Verifica se o diretório existe
                dir_esperado = Path(f'resultado/{ano}/{mes}/{dia}')
                print(f"Diretório existe: {dir_esperado.exists()}")
                
                if not dir_esperado.exists():
                    print("❌ PROBLEMA IDENTIFICADO: Diretório não existe!")
                    
                    # Verifica se há arquivos em outros lugares
                    resultado_dir = Path('resultado')
                    padrao_data = data_dt.strftime('%Y%m%d')
                    arquivos_encontrados = list(resultado_dir.rglob(f"*{padrao_data}*.xml"))
                    
                    print(f"Arquivos com padrão {padrao_data}: {len(arquivos_encontrados)}")
                    
                    if arquivos_encontrados:
                        print("Locais onde foram encontrados:")
                        locais = set()
                        for arq in arquivos_encontrados[:10]:  # Primeiros 10
                            locais.add(str(arq.parent))
                        for local in sorted(locais):
                            print(f"  {local}")
                    else:
                        print("❌ CONFIRMADO: Não há arquivos XML para esta data!")
                        
                        # Verifica se há registros no banco com xml_baixado = 1 para essa data
                        cursor.execute("""
                            SELECT COUNT(*) FROM notas 
                            WHERE dEmi = ? AND xml_baixado = 1
                        """, (data_problema,))
                        baixados_mesma_data = cursor.fetchone()[0]
                        print(f"Registros baixados para a mesma data: {baixados_mesma_data}")
                        
                        if baixados_mesma_data == 0:
                            print("❌ CAUSA RAIZ: Essa data nunca foi processada!")
                            
                            # Sugere ações
                            print("\n" + "=" * 50)
                            print("AÇÕES SUGERIDAS:")
                            print("=" * 50)
                            print("1. Executar download para a data 01/05/2025")
                            print("2. Ou remover esses registros se não são necessários")
                            print("3. Verificar se há erro na data dos registros")
                            
                            # Mostra amostra dos registros problemáticos
                            print("\nAmostra dos registros problemáticos:")
                            cursor.execute("""
                                SELECT cChaveNFe, dEmi, nNF, cRazao 
                                FROM notas 
                                WHERE xml_baixado = 0 
                                LIMIT 3
                            """)
                            for chave, dEmi, nNF, cRazao in cursor.fetchall():
                                print(f"  Chave: {chave}")
                                print(f"  Data: {dEmi}, NFe: {nNF}")
                                print(f"  Razão: {cRazao}")
                                print()
                
            except ValueError as e:
                print(f"Erro ao converter data: {e}")
    
    # 2. Análise da estrutura de diretórios
    print("\n" + "=" * 50)
    print("ESTRUTURA DE DIRETÓRIOS DISPONÍVEIS")
    print("=" * 50)
    
    resultado_dir = Path('resultado')
    if resultado_dir.exists():
        # Lista anos disponíveis
        anos = [d.name for d in resultado_dir.iterdir() if d.is_dir() and d.name.isdigit()]
        print(f"Anos disponíveis: {sorted(anos)}")
        
        # Para 2025, lista meses
        if '2025' in anos:
            meses_2025 = [d.name for d in (resultado_dir / '2025').iterdir() if d.is_dir()]
            print(f"Meses em 2025: {sorted(meses_2025)}")
            
            # Para maio de 2025, lista dias
            if '05' in meses_2025:
                dias_maio = [d.name for d in (resultado_dir / '2025' / '05').iterdir() if d.is_dir()]
                print(f"Dias em maio/2025: {sorted(dias_maio)}")
            else:
                print("❌ Mês 05 (maio) não existe em 2025")
    
    print("\n" + "=" * 70)
    print("DIAGNÓSTICO CONCLUÍDO")
    print("=" * 70)

if __name__ == "__main__":
    diagnosticar_registros_pendentes()
