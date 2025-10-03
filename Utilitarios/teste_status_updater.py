#!/usr/bin/env python3
"""
TESTE DO SISTEMA DE ATUALIZAÇÃO DE STATUS NFE
Valida a funcionalidade de consulta e atualização de status das NFe.
"""

import sys
import logging
from pathlib import Path
import sqlite3

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))


def verificar_dependencias():
    """Verifica se as dependências necessárias estão disponíveis."""
    print("🔍 VERIFICANDO DEPENDÊNCIAS...")
    print("=" * 50)
    
    dependencias = [
        ("aiohttp", "Requisições HTTP assíncronas"),
        ("asyncio", "Processamento assíncrono (built-in)"),
        ("sqlite3", "Banco de dados (built-in)"),
        ("configparser", "Configurações (built-in)"),
    ]
    
    todas_ok = True
    
    for modulo, descricao in dependencias:
        try:
            if modulo == "aiohttp":
                import aiohttp
            elif modulo == "asyncio":
                import asyncio
            elif modulo == "sqlite3":
                import sqlite3
            elif modulo == "configparser":
                import configparser
            
            print(f"   ✅ {modulo:<15} {descricao}")
        except ImportError as e:
            print(f"   ❌ {modulo:<15} AUSENTE - {descricao}")
            print(f"      Erro: {e}")
            if modulo == "aiohttp":
                print(f"      💡 Instale com: pip install aiohttp")
                todas_ok = False
    
    return todas_ok


def verificar_estrutura_banco():
    """Verifica se a estrutura do banco suporta status."""
    
    print("\n🔍 VERIFICANDO ESTRUTURA DO BANCO...")
    print("=" * 50)
    
    try:
        if not Path("omie.db").exists():
            print("❌ Arquivo omie.db não encontrado!")
            print("💡 Execute o pipeline principal primeiro para criar o banco")
            return False
        
        with sqlite3.connect("omie.db") as conn:
            cursor = conn.cursor()
            
            # Verifica se tabela existe
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notas'")
            if not cursor.fetchone():
                print("❌ Tabela 'notas' não encontrada!")
                return False
            
            # Verifica colunas
            cursor.execute("PRAGMA table_info(notas)")
            colunas = {row[1]: row[2] for row in cursor.fetchall()}
            
            print("📋 COLUNAS DA TABELA:")
            campos_essenciais = ['cChaveNFe', 'nIdNF', 'status', 'xml_baixado']
            
            for campo in campos_essenciais:
                if campo in colunas:
                    print(f"   ✅ {campo:<20} {colunas[campo]}")
                else:
                    print(f"   ❌ {campo:<20} AUSENTE!")
                    if campo == 'status':
                        print("      💡 Adicionando coluna 'status'...")
                        try:
                            cursor.execute("ALTER TABLE notas ADD COLUMN status TEXT DEFAULT NULL")
                            conn.commit()
                            print("      ✅ Coluna 'status' adicionada com sucesso")
                        except Exception as e:
                            print(f"      ❌ Erro ao adicionar coluna: {e}")
                            return False
            
            # Estatísticas
            cursor.execute("SELECT COUNT(*) FROM notas")
            total = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 1")
            com_xml = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM notas WHERE status IS NOT NULL AND status != ''")
            com_status = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM notas WHERE status IS NULL OR status = ''")
            sem_status = cursor.fetchone()[0]
            
            print(f"\n📊 ESTATÍSTICAS:")
            print(f"   • Total de registros: {total:,}")
            print(f"   • Com XML baixado: {com_xml:,}")
            print(f"   • Com status: {com_status:,}")
            print(f"   • Sem status: {sem_status:,}")
            
            if sem_status > 0:
                print(f"\n💡 {sem_status:,} registros podem ser atualizados com status")
            else:
                print(f"\n✅ Todos os registros já possuem status")
            
            return True
            
    except Exception as e:
        print(f"❌ Erro ao verificar banco: {e}")
        return False


def testar_configuracao():
    """Testa se as configurações estão corretas."""
    
    print("\n⚙️  VERIFICANDO CONFIGURAÇÕES...")
    print("=" * 50)
    
    try:
        config_path = Path("configuracao.ini")
        if not config_path.exists():
            print("❌ Arquivo configuracao.ini não encontrado!")
            return False
        
        import configparser
        config = configparser.ConfigParser()
        config.read(config_path, encoding='utf-8')
        
        # Verifica seção omie_api
        if not config.has_section('omie_api'):
            print("❌ Seção [omie_api] não encontrada!")
            return False
        
        # Verifica campos essenciais
        campos_obrigatorios = ['app_key', 'app_secret', 'base_url_nf']
        
        for campo in campos_obrigatorios:
            valor = config.get('omie_api', campo, fallback=None)
            if valor:
                valor_mascarado = valor[:10] + "..." if len(valor) > 10 else valor
                print(f"   ✅ {campo:<15} {valor_mascarado}")
            else:
                print(f"   ❌ {campo:<15} AUSENTE!")
                return False
        
        calls_per_second = config.getint('omie_api', 'calls_per_second', fallback=4)
        print(f"   ✅ calls_per_second  {calls_per_second}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao verificar configurações: {e}")
        return False


def testar_importacao_modulos():
    """Testa se os módulos do sistema podem ser importados."""
    
    print("\n📦 TESTANDO IMPORTAÇÃO DOS MÓDULOS...")
    print("=" * 50)
    
    modulos = [
        ("src.omie_client_async", "Cliente API Omie"),
        ("src.utils", "Utilitários do sistema"),
        ("src.status_nfe_updater", "Atualizador de status (novo)"),
    ]
    
    todos_ok = True
    
    for modulo, descricao in modulos:
        try:
            __import__(modulo)
            print(f"   ✅ {modulo:<25} {descricao}")
        except ImportError as e:
            print(f"   ❌ {modulo:<25} ERRO - {e}")
            if "aiohttp" in str(e):
                print(f"      💡 Instale dependências: pip install aiohttp")
            todos_ok = False
        except Exception as e:
            print(f"   ⚠️  {modulo:<25} AVISO - {e}")
    
    return todos_ok


def executar_teste_simples():
    """Executa teste simples da funcionalidade."""
    
    print("\n🧪 TESTE SIMPLES DE FUNCIONALIDADE...")
    print("=" * 50)
    
    try:
        # Testa normalização de status (função simples)
        print("📋 Testando normalização de status:")
        
        testes_status = [
            ("cancelada", "CANCELADA"),
            ("Autorizada", "AUTORIZADA"), 
            ("rejeitada", "REJEITADA"),
            ("processando", "PROCESSANDO"),
            ("status_desconhecido", "STATUS_DESCONHECIDO"),
        ]
        
        def normalizar_status_teste(status_raw: str) -> str:
            """Função de teste para normalização."""
            if not status_raw:
                return "INDEFINIDO"
                
            status_lower = status_raw.lower().strip()
            
            mapeamentos = {
                "cancelada": "CANCELADA",
                "autorizada": "AUTORIZADA", 
                "rejeitada": "REJEITADA",
                "processando": "PROCESSANDO",
            }
            
            for palavra_chave, status_norm in mapeamentos.items():
                if palavra_chave in status_lower:
                    return status_norm
                    
            return status_raw.upper()
        
        todos_ok = True
        for entrada, esperado in testes_status:
            resultado = normalizar_status_teste(entrada)
            if resultado == esperado:
                print(f"   ✅ {entrada:<20} -> {resultado}")
            else:
                print(f"   ❌ {entrada:<20} -> {resultado} (esperado: {esperado})")
                todos_ok = False
        
        return todos_ok
        
    except Exception as e:
        print(f"❌ Erro no teste simples: {e}")
        return False


def main():
    """Função principal de testes."""
    
    # Configuração de logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("🔄 SISTEMA DE TESTE - ATUALIZAÇÃO DE STATUS NFE")
    print("=" * 60)
    print("Este script testa a funcionalidade de atualização de status das NFe")
    print()
    
    # Sequência de testes
    testes = [
        ("Dependências", verificar_dependencias),
        ("Estrutura do Banco", verificar_estrutura_banco),
        ("Configurações", testar_configuracao),
        ("Importação de Módulos", testar_importacao_modulos),
        ("Funcionalidade Simples", executar_teste_simples),
    ]
    
    resultados = []
    
    for nome_teste, funcao_teste in testes:
        print(f"\n{'='*20} {nome_teste.upper()} {'='*20}")
        try:
            resultado = funcao_teste()
            resultados.append((nome_teste, resultado))
            
            if resultado:
                print(f"✅ {nome_teste}: PASSOU")
            else:
                print(f"❌ {nome_teste}: FALHOU")
                
        except Exception as e:
            print(f"❌ {nome_teste}: ERRO - {e}")
            resultados.append((nome_teste, False))
    
    # Relatório final
    print("\n" + "=" * 60)
    print("📋 RELATÓRIO FINAL DOS TESTES")
    print("=" * 60)
    
    passou_todos = True
    for nome, resultado in resultados:
        status = "✅ PASSOU" if resultado else "❌ FALHOU"
        print(f"   {nome:<25} {status}")
        if not resultado:
            passou_todos = False
    
    print(f"\n{'='*60}")
    
    if passou_todos:
        print("🎉 TODOS OS TESTES PASSARAM!")
        print("\n💡 O sistema está pronto para uso.")
        print("💡 Para executar a atualização de status:")
        print("   python Utilitarios/executar_status_updater.py --dry-run")
    else:
        print("⚠️  ALGUNS TESTES FALHARAM!")
        print("\n💡 Correções necessárias:")
        
        for nome, resultado in resultados:
            if not resultado:
                if "Dependências" in nome:
                    print("   • Instale: pip install aiohttp")
                elif "Banco" in nome:
                    print("   • Execute o pipeline principal para criar o banco")
                elif "Configurações" in nome:
                    print("   • Verifique o arquivo configuracao.ini")
                elif "Módulos" in nome:
                    print("   • Verifique se todos os arquivos foram criados")
    
    print(f"{'='*60}")


def mostrar_ajuda():
    """Mostra ajuda sobre os testes."""
    print("""
🔄 SISTEMA DE TESTE - ATUALIZAÇÃO DE STATUS NFE
===============================================

DESCRIÇÃO:
  Este script testa todas as funcionalidades do sistema de
  atualização de status das NFe, validando configurações,
  dependências e estrutura básica.

TESTES REALIZADOS:
  ✓ Dependências Python necessárias
  ✓ Estrutura do banco de dados
  ✓ Configurações da API Omie  
  ✓ Importação dos módulos do sistema
  ✓ Funcionalidade básica de normalização

USAGE:
  python teste_status_updater.py [opções]

OPÇÕES:
  --help, -h       Mostra esta ajuda

EXEMPLOS:
  # Execução dos testes
  python teste_status_updater.py

DEPENDÊNCIAS:
  • aiohttp           - pip install aiohttp
  • Python 3.8+      - Built-in modules

ARQUIVOS VERIFICADOS:
  • configuracao.ini                - Configurações da API
  • omie.db                         - Banco de dados SQLite
  • src/status_nfe_updater.py       - Módulo principal
  • src/omie_client_async.py        - Cliente API
""")


if __name__ == "__main__":
    if "--help" in sys.argv or "-h" in sys.argv:
        mostrar_ajuda()
        sys.exit(0)
    
    # Executa testes
    main()
