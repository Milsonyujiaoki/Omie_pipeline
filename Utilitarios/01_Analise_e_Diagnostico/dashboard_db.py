#!/usr/bin/env python3
"""
📊 DASHBOARD RÁPIDO DO BANCO DE DADOS OMIE V3
============================================

Script simplificado para análise rápida e visualização das métricas principais.
Baseado nos utilitários existentes e otimizado para execução rápida.
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# Configuração
DB_PATH = "omie.db"
TABLE_NAME = "notas"

def limpar_tela():
    """Limpa a tela do terminal"""
    os.system('cls' if os.name == 'nt' else 'clear')

def formatar_numero(n):
    """Formata número com separadores"""
    return f"{n:,}".replace(",", ".")

def obter_estatisticas_basicas():
    """Obtém estatísticas básicas do banco"""
    if not Path(DB_PATH).exists():
        print(f"❌ Banco não encontrado: {DB_PATH}")
        return None
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Otimizações básicas
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.execute("PRAGMA cache_size = -64000")
            
            cursor = conn.cursor()
            
            # Contadores principais
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
            total = cursor.fetchone()[0]
            
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE xml_baixado = 1")
            baixados = cursor.fetchone()[0]
            
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE xml_baixado = 0 OR xml_baixado IS NULL")
            pendentes = cursor.fetchone()[0]
            
            # Verificar coluna de erro
            cursor.execute("PRAGMA table_info(notas)")
            colunas = [col[1] for col in cursor.fetchall()]
            
            erros = 0
            if 'erro_xml' in colunas:
                cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE erro_xml IS NOT NULL AND erro_xml != ''")
                erros = cursor.fetchone()[0]
            elif 'erro' in colunas:
                cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE erro = 1")
                erros = cursor.fetchone()[0]
            
            # Datas extremas (ordenadas cronologicamente)
            cursor.execute(f"""
                SELECT 
                    MIN(
                        CASE 
                            WHEN dEmi LIKE '__/__/____' THEN 
                                substr(dEmi, 7, 4) || '-' || 
                                substr(dEmi, 4, 2) || '-' || 
                                substr(dEmi, 1, 2)
                            ELSE dEmi 
                        END
                    ),
                    MAX(
                        CASE 
                            WHEN dEmi LIKE '__/__/____' THEN 
                                substr(dEmi, 7, 4) || '-' || 
                                substr(dEmi, 4, 2) || '-' || 
                                substr(dEmi, 1, 2)
                            ELSE dEmi 
                        END
                    )
                FROM {TABLE_NAME} 
                WHERE dEmi IS NOT NULL AND dEmi != ''
            """)
            resultado = cursor.fetchone()
            
            # Converter de volta para formato DD/MM/YYYY
            data_inicio_iso = resultado[0] or "N/A"
            data_fim_iso = resultado[1] or "N/A"
            
            try:
                if data_inicio_iso != "N/A" and len(data_inicio_iso) == 10:
                    data_inicio = f"{data_inicio_iso[8:10]}/{data_inicio_iso[5:7]}/{data_inicio_iso[0:4]}"
                else:
                    data_inicio = "N/A"
                    
                if data_fim_iso != "N/A" and len(data_fim_iso) == 10:
                    data_fim = f"{data_fim_iso[8:10]}/{data_fim_iso[5:7]}/{data_fim_iso[0:4]}"
                else:
                    data_fim = "N/A"
            except:
                data_inicio = data_inicio_iso
                data_fim = data_fim_iso
            
            # Top 10 dias com mais registros
            cursor.execute(f"""
                SELECT dEmi, COUNT(*) as total
                FROM {TABLE_NAME} 
                WHERE dEmi IS NOT NULL AND dEmi != ''
                GROUP BY dEmi 
                ORDER BY total DESC 
                LIMIT 10
            """)
            top_dias = cursor.fetchall()
            
            # Distribuição por status
            cursor.execute(f"""
                SELECT 
                    CASE 
                        WHEN xml_baixado = 1 THEN 'Baixado'
                        WHEN erro_xml IS NOT NULL AND erro_xml != '' THEN 'Com Erro'
                        ELSE 'Pendente'
                    END as status,
                    COUNT(*) as total
                FROM {TABLE_NAME}
                GROUP BY status
                ORDER BY total DESC
            """)
            distribuicao_status = cursor.fetchall()
            
            # Campos vazios importantes
            campos_vazios = {}
            for campo in ['dEmi', 'nNF', 'cRazao', 'cnpj_cpf', 'cChaveNFe']:
                cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE {campo} IS NULL OR {campo} = ''")
                campos_vazios[campo] = cursor.fetchone()[0]
            
            # Análise de progresso por período
            cursor.execute(f"""
                SELECT 
                    substr(dEmi, 4, 7) as mes_ano,
                    COUNT(*) as total,
                    SUM(CASE WHEN xml_baixado = 1 THEN 1 ELSE 0 END) as baixados
                FROM {TABLE_NAME}
                WHERE dEmi IS NOT NULL AND dEmi != '' AND dEmi LIKE '__/__/____'
                GROUP BY mes_ano
                ORDER BY substr(dEmi, 7, 4), substr(dEmi, 4, 2)
                LIMIT 12
            """)
            progresso_mensal = cursor.fetchall()
            
            # Velocidade de download (últimas 24h se houver timestamps)
            velocidade_estimada = 0
            if baixados > 0 and pendentes > 0:
                # Estimativa simples baseada na proporção atual
                velocidade_estimada = baixados / max(1, total) * 100
            
            return {
                'total': total,
                'baixados': baixados,
                'pendentes': pendentes,
                'erros': erros,
                'data_inicio': data_inicio,
                'data_fim': data_fim,
                'top_dias': top_dias,
                'distribuicao_status': distribuicao_status,
                'campos_vazios': campos_vazios,
                'progresso_mensal': progresso_mensal,
                'velocidade_estimada': velocidade_estimada,
                'percentual_concluido': (baixados / max(1, total)) * 100,
                'percentual_erro': (erros / max(1, total)) * 100
            }
            
    except Exception as e:
        print(f"❌ Erro ao acessar banco: {e}")
        return None

def exibir_dashboard(stats):
    """Exibe dashboard formatado"""
    limpar_tela()
    
    print("=" * 80)
    print("📊 DASHBOARD DO BANCO DE DADOS OMIE V3")
    print("=" * 80)
    print(f"🕒 Atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"💾 Banco: {DB_PATH}")
    print()
    
    # Estatísticas principais
    print("📈 ESTATÍSTICAS PRINCIPAIS")
    print("-" * 40)
    print(f"📋 Total de registros: {formatar_numero(stats['total'])}")
    print(f"✅ XMLs baixados: {formatar_numero(stats['baixados'])} ({stats['percentual_concluido']:.1f}%)")
    print(f"⏳ Pendentes: {formatar_numero(stats['pendentes'])}")
    print(f"❌ Com erro: {formatar_numero(stats['erros'])} ({stats['percentual_erro']:.1f}%)")
    print()
    
    # Período
    print("📅 PERÍODO DOS DADOS")
    print("-" * 40)
    print(f"🗓️  Data início: {stats['data_inicio']}")
    print(f"🗓️  Data fim: {stats['data_fim']}")
    print()
    
    # Distribuição por status
    print("📊 DISTRIBUIÇÃO POR STATUS")
    print("-" * 40)
    for status, total in stats['distribuicao_status']:
        percentual = (total / max(1, stats['total'])) * 100
        print(f"{status:12}: {formatar_numero(total):>10} ({percentual:5.1f}%)")
    print()
    
    # Top dias
    print("🔥 TOP 10 DIAS COM MAIS REGISTROS")
    print("-" * 40)
    for i, (data, total) in enumerate(stats['top_dias'], 1):
        print(f"{i:2}. {data}: {formatar_numero(total):>8} registros")
    print()
    
    # Campos vazios
    print("⚠️  CAMPOS OBRIGATÓRIOS VAZIOS")
    print("-" * 40)
    if any(total > 0 for total in stats['campos_vazios'].values()):
        for campo, total in stats['campos_vazios'].items():
            if total > 0:
                percentual = (total / max(1, stats['total'])) * 100
                print(f"{campo:12}: {formatar_numero(total):>8} ({percentual:5.1f}%)")
    else:
        print("✅ Todos os campos obrigatórios estão preenchidos!")
    print()
    
    # Progresso mensal
    if 'progresso_mensal' in stats and stats['progresso_mensal']:
        print("📈 PROGRESSO POR MÊS/ANO")
        print("-" * 40)
        for mes_ano, total, baixados in stats['progresso_mensal'][:6]:  # Top 6
            percentual = (baixados / max(1, total)) * 100
            print(f"{mes_ano:8}: {formatar_numero(baixados):>8}/{formatar_numero(total):>8} ({percentual:5.1f}%)")
        print()
    
    # Estimativas melhoradas
    if stats['pendentes'] > 0 and stats['baixados'] > 0:
        print("🎯 ESTIMATIVAS E PERFORMANCE")
        print("-" * 40)
        
        # Progresso atual
        print(f"📈 Progresso atual: {stats['percentual_concluido']:.1f}%")
        
        # Estimativa mais realista
        if stats['percentual_concluido'] > 90:
            tempo_estimado = "< 1 dia (fase final)"
        elif stats['percentual_concluido'] > 50:
            dias_estimados = (stats['pendentes'] / max(stats['baixados'] / 30, 1000))  # Assume 30 dias de processamento
            tempo_estimado = f"~{dias_estimados:.1f} dias"
        else:
            tempo_estimado = "Calculando..."
        
        print(f" Tempo estimado restante: {tempo_estimado}")
        
        # Taxa de sucesso
        taxa_sucesso = ((stats['total'] - stats['erros']) / max(1, stats['total'])) * 100
        print(f"✨ Taxa de sucesso: {taxa_sucesso:.1f}%")
        
        # Velocidade estimada
        if stats['baixados'] > 100000:  # Se já baixou muitos arquivos
            print(f"🚀 Performance: Excelente (>100k XMLs processados)")
        elif stats['baixados'] > 10000:
            print(f"🚀 Performance: Boa (>10k XMLs processados)")
        else:
            print(f"🚀 Performance: Inicial")
    elif stats['pendentes'] == 0:
        print(" PROCESSAMENTO CONCLUÍDO!")
        print("-" * 40)
        print("✅ Todos os XMLs foram baixados com sucesso!")
        taxa_sucesso = ((stats['total'] - stats['erros']) / max(1, stats['total'])) * 100
        print(f"✨ Taxa de sucesso final: {taxa_sucesso:.1f}%")
    
    print()
    print("=" * 80)

def menu_opcoes():
    """Menu de opções adicionais"""
    print("\n🔧 OPÇÕES ADICIONAIS:")
    print("1. Atualizar dados")
    print("2. 📄 Exportar relatório")
    print("3.  Análise detalhada")
    print("4. ❌ Sair")
    
    try:
        opcao = input("\nEscolha uma opção (1-4): ").strip()
        return opcao
    except KeyboardInterrupt:
        return "4"

def exportar_relatorio_simples(stats):
    """Exporta relatório simples"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    arquivo = f"relatorio_simples_{timestamp}.txt"
    
    try:
        with open(arquivo, 'w', encoding='utf-8') as f:
            f.write("RELATÓRIO DO BANCO DE DADOS OMIE V3\n")
            f.write("=" * 50 + "\n")
            f.write(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write(f"Banco: {DB_PATH}\n\n")
            
            f.write("ESTATÍSTICAS PRINCIPAIS\n")
            f.write("-" * 30 + "\n")
            f.write(f"Total de registros: {formatar_numero(stats['total'])}\n")
            f.write(f"XMLs baixados: {formatar_numero(stats['baixados'])} ({stats['percentual_concluido']:.1f}%)\n")
            f.write(f"Pendentes: {formatar_numero(stats['pendentes'])}\n")
            f.write(f"Com erro: {formatar_numero(stats['erros'])} ({stats['percentual_erro']:.1f}%)\n")
            f.write(f"Período: {stats['data_inicio']} até {stats['data_fim']}\n\n")
            
            f.write("TOP 10 DIAS COM MAIS REGISTROS\n")
            f.write("-" * 30 + "\n")
            for i, (data, total) in enumerate(stats['top_dias'], 1):
                f.write(f"{i}. {data}: {formatar_numero(total)} registros\n")
        
        print(f"✅ Relatório exportado: {arquivo}")
        
    except Exception as e:
        print(f"❌ Erro ao exportar: {e}")

def main():
    """Função principal"""
    while True:
        print("\nCarregando dados...")
        stats = obter_estatisticas_basicas()
        
        if not stats:
            print("❌ Não foi possível carregar os dados.")
            break
        
        exibir_dashboard(stats)
        opcao = menu_opcoes()
        
        if opcao == "1":
            continue  # Recarrega os dados
        elif opcao == "2":
            exportar_relatorio_simples(stats)
            input("\nPressione Enter para continuar...")
        elif opcao == "3":
            print("\n Para análise detalhada, execute: python analise_completa_db.py")
            input("Pressione Enter para continuar...")
        elif opcao == "4":
            print("\n👋 Saindo...")
            break
        else:
            print("\n❌ Opção inválida!")
            input("Pressione Enter para continuar...")

if __name__ == "__main__":
    main()
