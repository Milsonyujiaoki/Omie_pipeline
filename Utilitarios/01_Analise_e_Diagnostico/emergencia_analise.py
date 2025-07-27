#!/usr/bin/env python3
"""
Script para interromper processos Python travados e executar analise rapida
"""

import os
import sys
import time
import psutil
from pathlib import Path

def encontrar_processos_python():
    """Encontra todos os processos Python em execução"""
    processos = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            if proc.info['name'] and 'python' in proc.info['name'].lower():
                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                if 'main.py' in cmdline or 'extrator' in cmdline:
                    tempo_execucao = time.time() - proc.info['create_time']
                    processos.append({
                        'pid': proc.info['pid'],
                        'cmdline': cmdline,
                        'tempo_execucao': tempo_execucao
                    })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    return processos

def interromper_processos_travados():
    """Interrompe processos que estão executando ha mais de 30 minutos"""
    processos = encontrar_processos_python()
    
    if not processos:
        print("✅ Nenhum processo Python relacionado encontrado")
        return
    
    print(f" Encontrados {len(processos)} processos Python:")
    
    for proc in processos:
        tempo_min = proc['tempo_execucao'] / 60
        print(f"  PID {proc['pid']}: {proc['cmdline'][:80]}... (executando ha {tempo_min:.1f} min)")
        
        if tempo_min > 30:  # Mais de 30 minutos
            print(f"⚠️  Processo travado detectado! Interrompendo PID {proc['pid']}")
            try:
                os.kill(proc['pid'], 9)  # SIGKILL
                print(f"✅ Processo {proc['pid']} interrompido")
            except Exception as e:
                print(f"❌ Erro ao interromper processo {proc['pid']}: {e}")

def executar_analise_rapida():
    """Executa analise rapida do relatorio"""
    print("\n🏃 Executando analise rapida...")
    
    # Importa e executa analise rapida
    sys.path.insert(0, str(Path(__file__).parent))
    
    try:
        from src.report_arquivos_vazios import encontrar_arquivos_vazios_ou_zero_otimizado
        import logging
        
        # Configura logging
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
        
        # Executa analise limitada
        root_path = "C:\\milson\\extrator_omie_v3\\resultado"
        
        print(f"📂 Analisando: {root_path}")
        
        # Limita a analise a 50k arquivos
        from pathlib import Path
        import datetime
        
        root = Path(root_path)
        if not root.exists():
            print(f"❌ Diretorio não encontrado: {root_path}")
            return
        
        # So analisa arquivos modificados nos ultimos 3 dias
        tres_dias_atras = datetime.datetime.now() - datetime.timedelta(days=3)
        timestamp_limite = tres_dias_atras.timestamp()
        
        arquivos_recentes = []
        contador = 0
        
        for arquivo in root.rglob("*"):
            if arquivo.is_file():
                try:
                    if arquivo.stat().st_mtime > timestamp_limite:
                        arquivos_recentes.append(arquivo)
                        contador += 1
                        
                        # Limite para evitar travamento
                        if contador > 5000:
                            print(f"⚠️  Limitando analise a {contador} arquivos recentes")
                            break
                            
                except (OSError, PermissionError):
                    continue
        
        print(f"📊 Processando {len(arquivos_recentes)} arquivos recentes...")
        
        if not arquivos_recentes:
            print("✅ Nenhum arquivo recente para analisar")
            return
        
        # Analisa arquivos
        from src.report_arquivos_vazios import verificar_arquivo_rapido
        
        problemas = []
        for i, arquivo in enumerate(arquivos_recentes):
            if i % 1000 == 0:
                print(f"  Processando arquivo {i+1}/{len(arquivos_recentes)}")
            
            resultado = verificar_arquivo_rapido(str(arquivo))
            if resultado:
                problemas.append(resultado)
        
        print(f"📝 Analise concluida: {len(problemas)} problemas encontrados")
        
        # Salva relatorio se houver problemas
        if problemas:
            import pandas as pd
            df = pd.DataFrame(problemas)
            relatorio_path = "relatorio_arquivos_vazios_rapido.xlsx"
            df.to_excel(relatorio_path, index=False)
            print(f"💾 Relatorio salvo: {relatorio_path}")
        
    except Exception as e:
        print(f"❌ Erro na analise rapida: {e}")

def main():
    """Função principal"""
    print("🚨 Script de Emergência - Analise Rapida de Arquivos")
    print("=" * 50)
    
    # Verifica processos travados
    print("\n1. Verificando processos Python em execução...")
    interromper_processos_travados()
    
    # Executa analise rapida
    print("\n2. Executando analise rapida...")
    executar_analise_rapida()
    
    print("\n✅ Script concluido!")

if __name__ == "__main__":
    main()
