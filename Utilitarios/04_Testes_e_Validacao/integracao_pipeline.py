#!/usr/bin/env python3
"""
INTEGRAÇÃO EXTRATOR FUNCIONAL COM PIPELINE PRINCIPAL
=======================================================

Script para integrar os resultados do extrator funcional com o pipeline
principal, sincronizando os dados e preparando para retomar a automação.

Funcionalidades:
- Sincronização de dados entre bancos
- Validação de integridade dos XMLs baixados
- Atualização de status no banco principal
- Preparação para retomada do pipeline automatizado
- Relatório de integração detalhado
"""

import sqlite3
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import shutil

# Configurações
DB_PRINCIPAL = "omie.db"
DB_BACKUP = "omie_backup.db"
RESULTADO_DIR = "resultado"
LOG_DIR = "log"

def criar_backup_banco():
    """Cria backup do banco principal antes da integração"""
    try:
        if Path(DB_PRINCIPAL).exists():
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f"backup_integracao_{timestamp}.db"
            shutil.copy2(DB_PRINCIPAL, backup_path)
            print(f"✅ Backup criado: {backup_path}")
            return backup_path
        return None
    except Exception as e:
        print(f"❌ Erro ao criar backup: {e}")
        return None

def obter_estatisticas_integracao():
    """Obtém estatísticas para análise de integração"""
    if not Path(DB_PRINCIPAL).exists():
        print(f"❌ Banco principal não encontrado: {DB_PRINCIPAL}")
        return None
    
    try:
        with sqlite3.connect(DB_PRINCIPAL) as conn:
            cursor = conn.cursor()
            
            # Estatísticas gerais
            cursor.execute("SELECT COUNT(*) FROM notas")
            total = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 1")
            baixados = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 0 OR xml_baixado IS NULL")
            pendentes = cursor.fetchone()[0]
            
            # Registros com caminho_arquivo preenchido
            cursor.execute("SELECT COUNT(*) FROM notas WHERE caminho_arquivo IS NOT NULL AND caminho_arquivo != ''")
            com_caminho = cursor.fetchone()[0]
            
            # Registros baixados hoje (pelo extrator funcional)
            hoje = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT COUNT(*) FROM notas 
                WHERE xml_baixado = 1 
                AND caminho_arquivo LIKE '%resultado%'
                AND (
                    caminho_arquivo LIKE '%2025/07/21%' OR
                    caminho_arquivo LIKE '%2025\\07\\21%'
                )
            """)
            baixados_hoje = cursor.fetchone()[0]
            
            # Verificar integridade dos XMLs
            cursor.execute("""
                SELECT COUNT(*) FROM notas 
                WHERE xml_baixado = 1 
                AND caminho_arquivo IS NOT NULL 
                AND caminho_arquivo != ''
            """)
            com_caminho_baixado = cursor.fetchone()[0]
            
            return {
                'total': total,
                'baixados': baixados,
                'pendentes': pendentes,
                'com_caminho': com_caminho,
                'baixados_hoje': baixados_hoje,
                'com_caminho_baixado': com_caminho_baixado,
                'percentual_concluido': (baixados / max(1, total)) * 100
            }
            
    except Exception as e:
        print(f"❌ Erro ao obter estatísticas: {e}")
        return None

def validar_integridade_xmls(limite: int = 1000) -> Dict[str, int]:
    """Valida integridade dos XMLs baixados"""
    print(f"\n Validando integridade dos XMLs (amostra de {limite})...")
    
    resultados = {
        'validados': 0,
        'validos': 0,
        'invalidos': 0,
        'nao_encontrados': 0,
        'vazios': 0
    }
    
    try:
        with sqlite3.connect(DB_PRINCIPAL) as conn:
            cursor = conn.cursor()
            
            # Pegar amostra de registros baixados
            cursor.execute(f"""
                SELECT cChaveNFe, caminho_arquivo 
                FROM notas 
                WHERE xml_baixado = 1 
                AND caminho_arquivo IS NOT NULL 
                AND caminho_arquivo != ''
                LIMIT {limite}
            """)
            
            registros = cursor.fetchall()
            
            for i, (chave, caminho) in enumerate(registros):
                if i % 100 == 0:
                    print(f"  Validando {i}/{len(registros)}...")
                
                resultados['validados'] += 1
                
                # Verificar se arquivo existe
                if not Path(caminho).exists():
                    resultados['nao_encontrados'] += 1
                    continue
                
                # Verificar se não está vazio
                if Path(caminho).stat().st_size == 0:
                    resultados['vazios'] += 1
                    continue
                
                # Verificar se contém XML válido (verificação básica)
                try:
                    with open(caminho, 'r', encoding='utf-8') as f:
                        conteudo = f.read(100)  # Ler apenas o início
                        if '<' in conteudo and '>' in conteudo:
                            resultados['validos'] += 1
                        else:
                            resultados['invalidos'] += 1
                except:
                    resultados['invalidos'] += 1
            
            print(f"✅ Validação concluída: {resultados['validados']} arquivos verificados")
            
    except Exception as e:
        print(f"❌ Erro na validação: {e}")
    
    return resultados

def atualizar_campos_faltantes():
    """Atualiza campos que possam estar faltando após integração"""
    print("\nAtualizando campos faltantes...")
    
    try:
        with sqlite3.connect(DB_PRINCIPAL) as conn:
            cursor = conn.cursor()
            
            # Contar registros que precisam de atualização
            cursor.execute("""
                SELECT COUNT(*) FROM notas 
                WHERE xml_baixado = 1 
                AND (caminho_arquivo IS NULL OR caminho_arquivo = '')
            """)
            precisam_atualizacao = cursor.fetchone()[0]
            
            if precisam_atualizacao > 0:
                print(f"  📝 {precisam_atualizacao} registros precisam de atualização de caminho...")
                
                # Atualizar caminhos baseado no padrão
                cursor.execute("""
                    UPDATE notas 
                    SET caminho_arquivo = 
                        'resultado/' || 
                        substr(dEmi, 7, 4) || '/' ||
                        substr(dEmi, 4, 2) || '/' ||
                        substr(dEmi, 1, 2) || '/' ||
                        nNF || '_' ||
                        substr(dEmi, 7, 4) || substr(dEmi, 4, 2) || substr(dEmi, 1, 2) || '_' ||
                        cChaveNFe || '.xml'
                    WHERE xml_baixado = 1 
                    AND (caminho_arquivo IS NULL OR caminho_arquivo = '')
                    AND dEmi IS NOT NULL 
                    AND nNF IS NOT NULL 
                    AND cChaveNFe IS NOT NULL
                """)
                
                atualizados = cursor.rowcount
                conn.commit()
                
                print(f"  ✅ {atualizados} caminhos atualizados")
            else:
                print("  ✅ Todos os registros já têm caminhos atualizados")
            
            # Verificar e limpar registros duplicados
            cursor.execute("""
                SELECT cChaveNFe, COUNT(*) 
                FROM notas 
                GROUP BY cChaveNFe 
                HAVING COUNT(*) > 1
            """)
            duplicados = cursor.fetchall()
            
            if duplicados:
                print(f"  ⚠️  Encontrados {len(duplicados)} registros duplicados")
                # Aqui você pode implementar lógica de desduplicação se necessário
            else:
                print("  ✅ Nenhum registro duplicado encontrado")
                
    except Exception as e:
        print(f"❌ Erro na atualização: {e}")

def preparar_pipeline_principal():
    """Prepara configurações para retomar o pipeline principal"""
    print("\n⚙️  Preparando configurações do pipeline principal...")
    
    try:
        # Verificar arquivo de configuração
        config_path = Path("configuracao.ini")
        if config_path.exists():
            print("  ✅ Arquivo configuracao.ini encontrado")
            
            # Ler configurações atuais
            with open(config_path, 'r', encoding='utf-8') as f:
                config_content = f.read()
                
            # Verificar se modo híbrido está ativo
            if 'modo_hibrido_ativo = true' in config_content:
                print("  ✅ Modo híbrido está ativo")
            else:
                print("  ⚠️  Modo híbrido não está ativo - pode ser necessário ativar")
                
            # Verificar configurações de reprocessamento
            if 'reprocessar_automaticamente = true' in config_content:
                print("  ✅ Reprocessamento automático ativo")
            else:
                print("  ⚠️  Reprocessamento automático não está ativo")
                
        else:
            print("  ❌ Arquivo configuracao.ini não encontrado")
            
        # Verificar se há registros suficientes para modo híbrido
        stats = obter_estatisticas_integracao()
        if stats and stats['pendentes'] < 100000:  # Menos de 100k pendentes
            print(f"  ✅ Registros pendentes: {stats['pendentes']:,} (adequado para finalização)")
            return "finalizacao"
        elif stats and stats['pendentes'] > 0:
            print(f"  ⚠️  Registros pendentes: {stats['pendentes']:,} (modo híbrido recomendado)")
            return "hibrido"
        else:
            print("   Processamento aparentemente concluído!")
            return "concluido"
            
    except Exception as e:
        print(f"❌ Erro na preparação: {e}")
        return "erro"

def gerar_relatorio_integracao():
    """Gera relatório completo da integração"""
    print("\n📄 Gerando relatório de integração...")
    
    try:
        stats = obter_estatisticas_integracao()
        if not stats:
            return
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        relatorio_path = f"relatorio_integracao_{timestamp}.txt"
        
        with open(relatorio_path, 'w', encoding='utf-8') as f:
            f.write("RELATÓRIO DE INTEGRAÇÃO - EXTRATOR FUNCIONAL → PIPELINE PRINCIPAL\n")
            f.write("=" * 70 + "\n")
            f.write(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write(f"Banco analisado: {DB_PRINCIPAL}\n\n")
            
            f.write("ESTATÍSTICAS GERAIS\n")
            f.write("-" * 30 + "\n")
            f.write(f"Total de registros: {stats['total']:,}\n")
            f.write(f"XMLs baixados: {stats['baixados']:,} ({stats['percentual_concluido']:.1f}%)\n")
            f.write(f"Registros pendentes: {stats['pendentes']:,}\n")
            f.write(f"Registros com caminho: {stats['com_caminho']:,}\n")
            f.write(f"Baixados hoje: {stats['baixados_hoje']:,}\n\n")
            
            # Validação de integridade
            if stats['baixados'] > 0:
                f.write("VALIDAÇÃO DE INTEGRIDADE\n")
                f.write("-" * 30 + "\n")
                validacao = validar_integridade_xmls(1000)
                for tipo, quantidade in validacao.items():
                    f.write(f"{tipo.replace('_', ' ').title()}: {quantidade}\n")
                f.write("\n")
            
            # Recomendações
            f.write("RECOMENDAÇÕES\n")
            f.write("-" * 30 + "\n")
            
            if stats['percentual_concluido'] > 95:
                f.write("✅ Processamento quase concluído - executar pipeline normal\n")
                f.write("✅ Considerar compactação e upload dos resultados\n")
            elif stats['percentual_concluido'] > 80:
                f.write("⚠️  Executar pipeline híbrido para finalizar registros restantes\n")
                f.write("✅ Manter extrator funcional como backup\n")
            else:
                f.write("⚠️  Considerar execução prolongada do extrator funcional\n")
                f.write("⚠️  Investigar possíveis problemas no pipeline principal\n")
            
            f.write(f"\nStatus do pipeline: Pronto para integração\n")
            f.write(f"Próximos passos: {preparar_pipeline_principal()}\n")
        
        print(f"✅ Relatório salvo: {relatorio_path}")
        
    except Exception as e:
        print(f"❌ Erro ao gerar relatório: {e}")

def main():
    """Função principal de integração"""
    print("=" * 70)
    print("INTEGRAÇÃO EXTRATOR FUNCIONAL → PIPELINE PRINCIPAL")
    print("=" * 70)
    print(f"🕒 Iniciado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print()
    
    # 1. Criar backup
    backup_path = criar_backup_banco()
    
    # 2. Análise inicial
    print("\n📊 Análise inicial do banco...")
    stats = obter_estatisticas_integracao()
    
    if not stats:
        print("❌ Não foi possível analisar o banco.")
        return
    
    print(f"  📋 Total: {stats['total']:,} registros")
    print(f"  ✅ Baixados: {stats['baixados']:,} ({stats['percentual_concluido']:.1f}%)")
    print(f"  ⏳ Pendentes: {stats['pendentes']:,}")
    print(f"  📁 Com caminho: {stats['com_caminho']:,}")
    print(f"  🆕 Baixados hoje: {stats['baixados_hoje']:,}")
    
    # 3. Validação de integridade
    validacao = validar_integridade_xmls(500)  # Amostra menor para execução rápida
    
    # 4. Atualização de campos
    atualizar_campos_faltantes()
    
    # 5. Preparação do pipeline
    modo_recomendado = preparar_pipeline_principal()
    
    # 6. Relatório final
    gerar_relatorio_integracao()
    
    # 7. Resumo e recomendações
    print("\n" + "=" * 70)
    print("✅ INTEGRAÇÃO CONCLUÍDA")
    print("=" * 70)
    
    if stats['percentual_concluido'] > 95:
        print(" Status: QUASE CONCLUÍDO")
        print("📋 Próxima ação: Executar pipeline normal para finalização")
        print("💡 Comando sugerido: python main.py")
    elif stats['percentual_concluido'] > 80:
        print("⚡ Status: FASE FINAL")
        print("📋 Próxima ação: Pipeline híbrido para registros restantes")
        print("💡 O extrator funcional pode continuar em paralelo")
    else:
        print("Status: EM ANDAMENTO")
        print("📋 Próxima ação: Continuar com extrator funcional")
        print("💡 Considerar investigar problemas no pipeline principal")
    
    print(f"\n📄 Relatório detalhado disponível nos arquivos gerados")
    print(f"💾 Backup criado: {backup_path}")
    print("=" * 70)

if __name__ == "__main__":
    main()
