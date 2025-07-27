#!/usr/bin/env python3
"""
Script simples para baixar XMLs pendentes da data 01/05/2025
"""

import sqlite3
import sys
import os
from pathlib import Path

def criar_arquivo_ids_pendentes():
    """Cria arquivo com IDs pendentes para download"""
    
    print("=" * 70)
    print("PREPARANDO DOWNLOAD DE XMLs PENDENTES - 01/05/2025")
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
        ids_pendentes = [str(reg[0]) for reg in registros]
        
        # Cria arquivo com os IDs
        ids_file = Path("ids_pendentes_01_05_2025.txt")
        
        with open(ids_file, 'w') as f:
            for id_nf in ids_pendentes:
                f.write(f"{id_nf}\n")
        
        print(f"✅ Arquivo criado: {ids_file}")
        print(f"📝 Contém {len(ids_pendentes):,} IDs para download")
        
        # Mostra amostra dos IDs
        print(f"\nPrimeiros 10 IDs:")
        for i, id_nf in enumerate(ids_pendentes[:10]):
            print(f"  {i+1:2d}. {id_nf}")
        
        if len(ids_pendentes) > 10:
            print(f"  ... e mais {len(ids_pendentes) - 10:,} IDs")
    
    # Instruções para download
    print("\n" + "=" * 70)
    print("INSTRUÇÕES PARA DOWNLOAD")
    print("=" * 70)
    
    print("MÉTODO 1 - Usando o pipeline principal:")
    print("   Edite o arquivo 'configuracao.ini' e adicione:")
    print("   [DOWNLOAD]")
    print("   data_especifica = 01/05/2025")
    print("   ")
    print("   Depois execute: python main.py")
    print()
    
    print("MÉTODO 2 - Usando o extrator diretamente:")
    print("   python src/extrator_async.py --data 01/05/2025")
    print()
    
    print("MÉTODO 3 - Baixar por lotes específicos:")
    print("   Execute o script de download em lotes (recomendado)")
    print()
    
    print("📋 VERIFICAÇÃO PÓS-DOWNLOAD:")
    print("   Após o download, execute:")
    print("   python Utilitarios/resolver_pendentes.py")
    print("   Para verificar se os registros foram processados.")
    
    return ids_file

def configurar_download_automatico():
    """Configura o download automático no arquivo de configuração"""
    
    config_file = Path("configuracao.ini")
    
    if not config_file.exists():
        print("❌ Arquivo configuracao.ini não encontrado!")
        return
    
    # Lê o arquivo de configuração
    with open(config_file, 'r', encoding='utf-8') as f:
        linhas = f.readlines()
    
    # Procura pela seção [DOWNLOAD] ou a adiciona
    tem_secao_download = False
    tem_data_especifica = False
    novas_linhas = []
    
    for linha in linhas:
        if linha.strip() == "[DOWNLOAD]":
            tem_secao_download = True
            novas_linhas.append(linha)
        elif linha.strip().startswith("data_especifica"):
            tem_data_especifica = True
            novas_linhas.append("data_especifica = 01/05/2025\n")
        else:
            novas_linhas.append(linha)
    
    # Adiciona seção se não existir
    if not tem_secao_download:
        novas_linhas.append("\n[DOWNLOAD]\n")
        novas_linhas.append("data_especifica = 01/05/2025\n")
    elif not tem_data_especifica:
        # Adiciona data_especifica após [DOWNLOAD]
        for i, linha in enumerate(novas_linhas):
            if linha.strip() == "[DOWNLOAD]":
                novas_linhas.insert(i+1, "data_especifica = 01/05/2025\n")
                break
    
    # Salva o arquivo
    with open(config_file, 'w', encoding='utf-8') as f:
        f.writelines(novas_linhas)
    
    print(f"✅ Configuração atualizada em {config_file}")
    print("   Adicionado: data_especifica = 01/05/2025")

def executar_download():
    """Executa o download usando o pipeline principal"""
    
    print("\nEXECUTANDO DOWNLOAD...")
    print("=" * 50)
    
    # Configura o arquivo de configuração
    configurar_download_automatico()
    
    # Instrui o usuário
    print("\n📋 PRÓXIMOS PASSOS:")
    print("1. Execute o comando:")
    print("   python main.py")
    print()
    print("2. Aguarde o download completar")
    print("3. Verifique se não há mais registros pendentes:")
    print("   python Utilitarios/resolver_pendentes.py")
    
    # Pergunta se deve executar automaticamente
    resposta = input("\nDeseja executar o download automaticamente? (s/n): ").lower().strip()
    
    if resposta in ['s', 'sim', 'y', 'yes']:
        print("🚀 Executando main.py...")
        import subprocess
        try:
            result = subprocess.run([sys.executable, 'main.py'], 
                                  capture_output=True, text=True, cwd='.')
            print("STDOUT:")
            print(result.stdout)
            if result.stderr:
                print("STDERR:")
                print(result.stderr)
        except Exception as e:
            print(f"❌ Erro ao executar main.py: {e}")
    else:
        print("✅ Configuração pronta. Execute 'python main.py' quando estiver pronto.")

if __name__ == "__main__":
    print("Escolha uma opção:")
    print("1. Criar arquivo com IDs pendentes")
    print("2. Configurar e executar download automático")
    print("3. Apenas mostrar estatísticas")
    
    opcao = input("Opção (1-3): ").strip()
    
    if opcao == "1":
        criar_arquivo_ids_pendentes()
    elif opcao == "2":
        criar_arquivo_ids_pendentes()
        executar_download()
    elif opcao == "3":
        # Mostra apenas estatísticas
        with sqlite3.connect('omie.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 0 AND dEmi = '01/05/2025'")
            pendentes = cursor.fetchone()[0]
            print(f"Registros pendentes para 01/05/2025: {pendentes:,}")
    else:
        print("❌ Opção inválida!")
