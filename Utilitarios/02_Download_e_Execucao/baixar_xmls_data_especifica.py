#!/usr/bin/env python3
"""
Script para baixar XMLs pendentes da data 01/05/2025
"""

import sqlite3
import sys
import os
from pathlib import Path
from datetime import datetime
import asyncio

# Adiciona o diretório src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def baixar_xmls_pendentes_01_05_2025():
    """Baixa os XMLs pendentes para a data 01/05/2025"""
    
    print("=" * 70)
    print("BAIXANDO XMLs PENDENTES - 01/05/2025")
    print("=" * 70)
    
    # Conecta ao banco e busca os IDs
    with sqlite3.connect('omie.db') as conn:
        cursor = conn.cursor()
        
        # Busca todos os IDs pendentes
        cursor.execute("""
            SELECT nIdNF, cChaveNFe, nNF, cRazao 
            FROM notas 
            WHERE xml_baixado = 0 AND dEmi = '01/05/2025'
            ORDER BY nIdNF
        """)
        
        registros = cursor.fetchall()
        total = len(registros)
        
        print(f"Encontrados {total:,} registros pendentes para download")
        
        if total == 0:
            print("❌ Nenhum registro pendente encontrado!")
            return
        
        # Extrai apenas os IDs
        ids_pendentes = [reg[0] for reg in registros]
        
        print(f"IDs a serem baixados: {ids_pendentes[:5]}... (mostrando primeiros 5)")
        
    # Importa o módulo extrator
    try:
        from extrator_async import ExtractorOmieAsync
        from omie_client_async import OmieClientAsync
        
        print("✅ Módulos importados com sucesso")
        
        # Cria instância do extrator
        extrator = ExtractorOmieAsync()
        
        # Baixa os XMLs
        print(f"\nIniciando download de {total:,} XMLs...")
        
        # Executa o download assíncrono
        asyncio.run(baixar_xmls_por_ids(ids_pendentes))
        
    except ImportError as e:
        print(f"❌ Erro ao importar módulos: {e}")
        print("Tentando método alternativo...")
        
        # Método alternativo usando o main.py
        usar_main_para_baixar(ids_pendentes)
    except Exception as e:
        print(f"❌ Erro durante o download: {e}")
        import traceback
        traceback.print_exc()

async def baixar_xmls_por_ids(ids_pendentes):
    """Baixa XMLs pelos IDs usando o extrator assíncrono"""
    
    try:
        from omie_client_async import OmieClientAsync
        from utils import iniciar_db, atualizar_status_xml, gerar_xml_path
        
        # Inicializa o cliente Omie
        client = OmieClientAsync()
        
        # Cria diretório para a data
        data_dir = Path("resultado/2025/05/01")
        data_dir.mkdir(parents=True, exist_ok=True)
        print(f"✅ Diretório criado: {data_dir}")
        
        # Processa em lotes
        batch_size = 100
        total_baixados = 0
        total_erros = 0
        
        for i in range(0, len(ids_pendentes), batch_size):
            batch = ids_pendentes[i:i+batch_size]
            print(f"\nProcessando lote {i//batch_size + 1}: {len(batch)} registros")
            
            for j, nid_nf in enumerate(batch):
                try:
                    # Baixa o XML
                    xml_content = await client.baixar_xml_nfe(nid_nf)
                    
                    if xml_content and xml_content.strip():
                        # Busca dados do registro no banco
                        with sqlite3.connect('omie.db') as conn:
                            cursor = conn.cursor()
                            cursor.execute("""
                                SELECT cChaveNFe, nNF, dEmi 
                                FROM notas 
                                WHERE nIdNF = ?
                            """, (nid_nf,))
                            
                            result = cursor.fetchone()
                            if result:
                                chave, num_nf, data_emissao = result
                                
                                # Gera caminho do arquivo
                                pasta, caminho_xml = gerar_xml_path(chave, data_emissao, num_nf)
                                
                                # Cria pasta se não existir
                                pasta.mkdir(parents=True, exist_ok=True)
                                
                                # Salva o XML
                                caminho_xml.write_text(xml_content, encoding='utf-8')
                                
                                # Atualiza status no banco
                                atualizar_status_xml('omie.db', chave, caminho_xml, xml_content)
                                
                                total_baixados += 1
                                
                                if (j + 1) % 10 == 0:
                                    print(f"  Baixados: {j + 1}/{len(batch)}")
                    
                    else:
                        print(f"  ❌ XML vazio para ID {nid_nf}")
                        total_erros += 1
                
                except Exception as e:
                    print(f"  ❌ Erro ao baixar ID {nid_nf}: {e}")
                    total_erros += 1
                    continue
        
        print(f"\n✅ Download concluído!")
        print(f"   Baixados: {total_baixados:,}")
        print(f"   Erros: {total_erros:,}")
        
        # Verifica quantos ainda estão pendentes
        with sqlite3.connect('omie.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 0 AND dEmi = '01/05/2025'")
            ainda_pendentes = cursor.fetchone()[0]
            print(f"   Ainda pendentes: {ainda_pendentes:,}")
        
    except Exception as e:
        print(f"❌ Erro durante download assíncrono: {e}")
        import traceback
        traceback.print_exc()

def usar_main_para_baixar(ids_pendentes):
    """Usa o main.py para baixar os XMLs (método alternativo)"""
    
    print("Usando método alternativo via main.py...")
    
    # Cria arquivo temporário com os IDs
    ids_file = Path("ids_pendentes_01_05_2025.txt")
    
    with open(ids_file, 'w') as f:
        for id_nf in ids_pendentes:
            f.write(f"{id_nf}\n")
    
    print(f"✅ Arquivo criado: {ids_file} com {len(ids_pendentes):,} IDs")
    
    # Instruções para o usuário
    print("\n📋 INSTRUÇÕES PARA BAIXAR OS XMLs:")
    print("=" * 50)
    print("1. Execute o comando:")
    print("   python main.py --reprocessar ids_pendentes_01_05_2025.txt")
    print()
    print("2. Ou edite o arquivo configuracao.ini:")
    print("   [DOWNLOAD]")
    print("   data_especifica = 01/05/2025")
    print("   E execute: python main.py")
    print()
    print("3. Ou use o extrator diretamente:")
    print("   python src/extrator_async.py --ids ids_pendentes_01_05_2025.txt")
    print()
    print("4. Após o download, execute novamente:")
    print("   python Utilitarios/resolver_pendentes.py")
    print("   Para verificar se os registros foram processados.")

if __name__ == "__main__":
    baixar_xmls_pendentes_01_05_2025()
