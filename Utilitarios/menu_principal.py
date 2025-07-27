#!/usr/bin/env python3
"""
🎯 EXTRATOR OMIE V3 - MENU PRINCIPAL DE UTILITÁRIOS
==================================================

Script master para navegação e execução dos utilitários organizados.
Oferece interface interativa para acesso rápido a todas as funcionalidades.
"""

import os
import sys
import subprocess
from pathlib import Path

def limpar_tela():
    """Limpa a tela do terminal"""
    os.system('cls' if os.name == 'nt' else 'clear')

def exibir_header():
    """Exibe o cabeçalho do sistema"""
    print("=" * 70)
    print("🎯 EXTRATOR OMIE V3 - MENU PRINCIPAL DE UTILITÁRIOS")
    print("=" * 70)
    print()

def executar_script(caminho_script):
    """Executa um script Python"""
    try:
        if Path(caminho_script).exists():
            print(f"🚀 Executando: {Path(caminho_script).name}")
            print("-" * 50)
            result = subprocess.run([sys.executable, caminho_script], 
                                  capture_output=False, text=True)
            print("-" * 50)
            print(f"✅ Script concluído com código: {result.returncode}")
            input("\nPressione Enter para continuar...")
        else:
            print(f"❌ Erro: Script não encontrado: {caminho_script}")
            input("Pressione Enter para continuar...")
    except Exception as e:
        print(f"❌ Erro ao executar script: {e}")
        input("Pressione Enter para continuar...")

def menu_analise_diagnostico():
    """Menu para scripts de análise e diagnóstico"""
    while True:
        limpar_tela()
        exibir_header()
        print("📊 ANÁLISE E DIAGNÓSTICO")
        print("=" * 40)
        print("1.  Verificar Status do Banco (rápido)")
        print("2. 📋 Análise Detalhada de Registros Pendentes")
        print("3. 🏥 Diagnóstico Completo de Registros Pendentes")
        print("4. 📡 Monitor de Progresso do Pipeline")
        print("0. ⬅️ Voltar ao Menu Principal")
        print()
        
        escolha = input("Escolha uma opção: ").strip()
        
        if escolha == "1":
            executar_script("01_Analise_e_Diagnostico/verificar_status_banco.py")
        elif escolha == "2":
            executar_script("01_Analise_e_Diagnostico/analise_registros_pendentes.py")
        elif escolha == "3":
            executar_script("01_Analise_e_Diagnostico/diagnostico_registros_pendentes.py")
        elif escolha == "4":
            executar_script("01_Analise_e_Diagnostico/monitor_progresso_pipeline.py")
        elif escolha == "0":
            break
        else:
            print("❌ Opção inválida!")
            input("Pressione Enter para continuar...")

def menu_download_execucao():
    """Menu para scripts de download e execução"""
    while True:
        limpar_tela()
        exibir_header()
        print("🚀 DOWNLOAD E EXECUÇÃO")
        print("=" * 40)
        print("1. ⭐ Resolver Registros Pendentes (PRINCIPAL)")
        print("2. 📥 Baixar XMLs de Data Específica")
        print("3. 🤖 Executar Download Automático")
        print("0. ⬅️ Voltar ao Menu Principal")
        print()
        
        escolha = input("Escolha uma opção: ").strip()
        
        if escolha == "1":
            executar_script("02_Download_e_Execucao/resolver_registros_pendentes.py")
        elif escolha == "2":
            executar_script("02_Download_e_Execucao/baixar_xmls_data_especifica.py")
        elif escolha == "3":
            executar_script("02_Download_e_Execucao/executar_download_automatico.py")
        elif escolha == "0":
            break
        else:
            print("❌ Opção inválida!")
            input("Pressione Enter para continuar...")

def menu_correcao_manutencao():
    """Menu para scripts de correção e manutenção"""
    while True:
        limpar_tela()
        exibir_header()
        print("🔧 CORREÇÃO E MANUTENÇÃO")
        print("=" * 40)
        print("1. 🩹 Corrigir Erros do Utils.py")
        print("2. 📅 Padronizar Formato de Datas")
        print("3.  Verificar Integridade dos XMLs")
        print("0. ⬅️ Voltar ao Menu Principal")
        print()
        
        escolha = input("Escolha uma opção: ").strip()
        
        if escolha == "1":
            executar_script("03_Correcao_e_Manutencao/corrigir_erros_utils.py")
        elif escolha == "2":
            executar_script("03_Correcao_e_Manutencao/padronizar_formato_datas.py")
        elif escolha == "3":
            executar_script("03_Correcao_e_Manutencao/verificar_integridade_xmls.py")
        elif escolha == "0":
            break
        else:
            print("❌ Opção inválida!")
            input("Pressione Enter para continuar...")

def menu_testes_validacao():
    """Menu para scripts de testes e validação"""
    while True:
        limpar_tela()
        exibir_header()
        print("🧪 TESTES E VALIDAÇÃO")
        print("=" * 40)
        print("1. 🌐 Testar Conectividade com API")
        print("2. 📊 Verificar Status Simples")
        print("0. ⬅️ Voltar ao Menu Principal")
        print()
        
        escolha = input("Escolha uma opção: ").strip()
        
        if escolha == "1":
            executar_script("04_Testes_e_Validacao/testar_conectividade_api.py")
        elif escolha == "2":
            executar_script("04_Testes_e_Validacao/verificar_status_simples.py")
        elif escolha == "0":
            break
        else:
            print("❌ Opção inválida!")
            input("Pressione Enter para continuar...")

def exibir_guia_rapido():
    """Exibe um guia rápido de uso"""
    limpar_tela()
    exibir_header()
    print("📚 GUIA RÁPIDO DE USO")
    print("=" * 40)
    print()
    print("🎯 CENÁRIOS COMUNS:")
    print()
    print("1️⃣ PRIMEIRO USO / ANÁLISE INICIAL:")
    print("   • Análise → Verificar Status do Banco")
    print("   • Análise → Análise Detalhada de Registros Pendentes")
    print()
    print("2️⃣ RESOLVER REGISTROS PENDENTES:")
    print("   • Download → Resolver Registros Pendentes (PRINCIPAL)")
    print("   • Escolher opção 1 no menu que aparecer")
    print()
    print("3️⃣ PROBLEMAS TÉCNICOS:")
    print("   • Testes → Testar Conectividade com API")
    print("   • Correção → Corrigir Erros do Utils.py")
    print()
    print("4️⃣ MANUTENÇÃO REGULAR:")
    print("   • Correção → Verificar Integridade dos XMLs")
    print("   • Correção → Padronizar Formato de Datas")
    print()
    print("5️⃣ MONITORAMENTO DURANTE EXECUÇÃO:")
    print("   • Análise → Monitor de Progresso do Pipeline")
    print()
    print("💡 DICA: O script 'Resolver Registros Pendentes' resolve")
    print("   a maioria dos problemas automaticamente!")
    print()
    input("Pressione Enter para voltar ao menu...")

def menu_principal():
    """Menu principal do sistema"""
    while True:
        limpar_tela()
        exibir_header()
        print("📋 CATEGORIAS DISPONÍVEIS:")
        print()
        print("1. 📊 Análise e Diagnóstico")
        print("2. 🚀 Download e Execução")
        print("3. 🔧 Correção e Manutenção")
        print("4. 🧪 Testes e Validação")
        print()
        print("📚 Opções de Ajuda:")
        print("5. 📖 Guia Rápido de Uso")
        print("6. 📁 Abrir Pasta de Utilitários")
        print()
        print("0. 🚪 Sair")
        print()
        
        escolha = input("Escolha uma categoria: ").strip()
        
        if escolha == "1":
            menu_analise_diagnostico()
        elif escolha == "2":
            menu_download_execucao()
        elif escolha == "3":
            menu_correcao_manutencao()
        elif escolha == "4":
            menu_testes_validacao()
        elif escolha == "5":
            exibir_guia_rapido()
        elif escolha == "6":
            try:
                os.startfile(Path.cwd())  # Windows
            except:
                try:
                    subprocess.run(['open', Path.cwd()])  # macOS
                except:
                    subprocess.run(['xdg-open', Path.cwd()])  # Linux
        elif escolha == "0":
            print("\n👋 Até logo!")
            break
        else:
            print("❌ Opção inválida!")
            input("Pressione Enter para continuar...")

if __name__ == "__main__":
    # Verificar se está na pasta correta
    if not Path("01_Analise_e_Diagnostico").exists():
        print("❌ Erro: Execute este script na pasta Utilitarios/")
        print("   Pasta atual:", Path.cwd())
        input("Pressione Enter para sair...")
        sys.exit(1)
    
    try:
        menu_principal()
    except KeyboardInterrupt:
        print("\n\n👋 Execução interrompida pelo usuário. Até logo!")
    except Exception as e:
        print(f"\n❌ Erro inesperado: {e}")
        input("Pressione Enter para sair...")
