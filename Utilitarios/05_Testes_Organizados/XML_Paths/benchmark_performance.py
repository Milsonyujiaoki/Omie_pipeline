#!/usr/bin/env python3
"""
teste_final_performance.py

Teste final de performance entre as funções gerar_xml_path.
Usa dados reais existentes no banco (xml_baixado = 1).
"""

import sys
import time
import sqlite3
import random
from pathlib import Path

# Setup do path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

try:
    from src.utils import gerar_xml_path, gerar_xml_path_otimizado
except ImportError:
    print("❌ Erro: Não foi possível importar as funções. Execute do diretório raiz do projeto.")
    sys.exit(1)

def teste_performance_final():
    """Teste de performance definitivo com dados reais"""
    print("🚀 TESTE FINAL DE PERFORMANCE")
    print("="*50)
    
    # Conecta ao banco e pega amostra aleatória
    try:
        with sqlite3.connect("omie.db") as conn:
            # Pega uma amostra aleatória de 200 registros
            cursor = conn.execute("""
                SELECT cChaveNFe, dEmi, nNF 
                FROM notas 
                WHERE xml_baixado = 1 
                ORDER BY RANDOM() 
                LIMIT 200
            """)
            dados = cursor.fetchall()
    except Exception as e:
        print(f"❌ Erro ao acessar banco: {e}")
        return
    
    print(f"📊 Testando com {len(dados)} registros aleatórios com XMLs baixados...")
    
    # Função para testar uma implementação
    def testar_funcao(nome, funcao, dados):
        print(f"\n🧪 Testando {nome}...")
        inicio = time.perf_counter()
        resultados = []
        arquivos_encontrados = 0
        erros = 0
        
        for chave, dEmi, nNF in dados:
            try:
                pasta, arquivo = funcao(chave, dEmi, nNF)
                resultados.append(str(arquivo))
                
                # Verifica se o arquivo existe e tem conteúdo
                if arquivo.exists() and arquivo.stat().st_size > 0:
                    arquivos_encontrados += 1
                    
            except Exception as e:
                resultados.append(f"ERRO: {e}")
                erros += 1
        
        tempo = time.perf_counter() - inicio
        
        return {
            'nome': nome,
            'tempo': tempo,
            'resultados': resultados,
            'encontrados': arquivos_encontrados,
            'erros': erros,
            'total': len(dados)
        }
    
    # Testa ambas as funções
    resultado_original = testar_funcao("FUNÇÃO ORIGINAL", gerar_xml_path, dados)
    resultado_otimizada = testar_funcao("FUNÇÃO OTIMIZADA", gerar_xml_path_otimizado, dados)
    
    # Análise comparativa
    print(f"\n📈 RESULTADO COMPARATIVO:")
    print("="*50)
    
    for resultado in [resultado_original, resultado_otimizada]:
        taxa_sucesso = (resultado['encontrados'] / resultado['total']) * 100
        print(f"\n{resultado['nome']}:")
        print(f"    Tempo de execução: {resultado['tempo']:.4f}s")
        print(f"   ✅ Arquivos encontrados: {resultado['encontrados']}/{resultado['total']} ({taxa_sucesso:.1f}%)")
        print(f"   ❌ Erros: {resultado['erros']}")
    
    # Comparação de performance
    tempo_orig = resultado_original['tempo']
    tempo_otim = resultado_otimizada['tempo']
    
    if tempo_orig > 0:
        melhoria = ((tempo_orig - tempo_otim) / tempo_orig) * 100
        velocidade = tempo_orig / tempo_otim if tempo_otim > 0 else float('inf')
        
        print(f"\n🔥 GANHO DE PERFORMANCE:")
        print(f"   📈 Melhoria: {melhoria:+.1f}%")
        print(f"   🏃 Velocidade relativa: {velocidade:.1f}x mais rápida")
        
        # Economia de tempo em escala
        total_registros = 869515  # Total do banco
        tempo_economia = (tempo_orig - tempo_otim) * (total_registros / len(dados))
        print(f"   💰 Economia para {total_registros:,} registros: {tempo_economia:.1f}s ({tempo_economia/60:.1f} min)")
    
    # Comparação de eficácia
    encontrados_orig = resultado_original['encontrados']
    encontrados_otim = resultado_otimizada['encontrados']
    
    print(f"\n🎯 EFICÁCIA NA LOCALIZAÇÃO:")
    if encontrados_otim > encontrados_orig:
        diferenca = encontrados_otim - encontrados_orig
        print(f"    Otimizada encontra {diferenca} arquivos A MAIS ({(diferenca/len(dados)*100):.1f}%)")
    elif encontrados_orig > encontrados_otim:
        diferenca = encontrados_orig - encontrados_otim
        print(f"   ⚠️  Original encontra {diferenca} arquivos a mais ({(diferenca/len(dados)*100):.1f}%)")
    else:
        print(f"   🤝 Ambas encontram a mesma quantidade")
    
    # Análise de consistência
    resultados_orig = resultado_original['resultados']
    resultados_otim = resultado_otimizada['resultados']
    
    identicos = sum(1 for a, b in zip(resultados_orig, resultados_otim) if a == b)
    diferentes = len(dados) - identicos
    
    print(f"\nCONSISTÊNCIA DOS RESULTADOS:")
    print(f"   ✅ Caminhos idênticos: {identicos}/{len(dados)} ({(identicos/len(dados)*100):.1f}%)")
    print(f"   Caminhos diferentes: {diferentes}/{len(dados)} ({(diferentes/len(dados)*100):.1f}%)")
    
    # Mostra exemplos de diferenças (apenas se houver)
    if diferentes > 0:
        print(f"\n ANÁLISE DAS DIFERENÇAS:")
        exemplos = 0
        melhor_detectados = 0
        
        for i, (orig, otim) in enumerate(zip(resultados_orig, resultados_otim)):
            if orig != otim and exemplos < 5:
                chave = dados[i][0]
                
                # Verifica qual arquivo realmente existe
                existe_orig = Path(orig).exists() and Path(orig).stat().st_size > 0 if not orig.startswith("ERRO") else False
                existe_otim = Path(otim).exists() and Path(otim).stat().st_size > 0 if not otim.startswith("ERRO") else False
                
                if existe_otim and not existe_orig:
                    melhor_detectados += 1
                
                print(f"   {exemplos + 1}. {chave[:20]}...")
                print(f"      Original:  {'✅' if existe_orig else '❌'} {Path(orig).name if not orig.startswith('ERRO') else 'ERRO'}")
                print(f"      Otimizada: {'✅' if existe_otim else '❌'} {Path(otim).name if not otim.startswith('ERRO') else 'ERRO'}")
                
                exemplos += 1
        
        if melhor_detectados > 0:
            print(f"   🎯 Otimizada detecta melhor: {melhor_detectados} casos analisados")
    
    # Recomendação final
    print(f"\n💡 RECOMENDAÇÃO FINAL:")
    print("="*30)
    
    vantagens_otimizada = []
    if tempo_otim < tempo_orig:
        vantagens_otimizada.append(f"🚀 {melhoria:.1f}% mais rápida")
    if encontrados_otim >= encontrados_orig:
        vantagens_otimizada.append(f"🎯 Encontra ≥ arquivos ({encontrados_otim} vs {encontrados_orig})")
    
    if vantagens_otimizada:
        print(f"   ✅ USE A FUNÇÃO OTIMIZADA:")
        for vantagem in vantagens_otimizada:
            print(f"      {vantagem}")
        print(f"   🔧 Configure USE_OPTIMIZED_VERSION = True no verificador_xmls.py")
    else:
        print(f"   ⚠️  Mantenha a função original por ora")
    
    return resultado_original, resultado_otimizada

def main():
    print("🎯 TESTE FINAL - COMPARAÇÃO DE PERFORMANCE")
    print("="*60)
    print("Análise definitiva das funções gerar_xml_path")
    print("="*60)
    
    # Verifica pré-requisitos
    if not Path("omie.db").exists():
        print("❌ Banco omie.db não encontrado")
        return
    
    try:
        resultado_orig, resultado_otim = teste_performance_final()
        
        print(f"\n" + "="*60)
        print("✅ ANÁLISE CONCLUÍDA")
        print("\nResumo executivo:")
        print(f"- Função otimizada executou {resultado_otim['tempo']:.3f}s vs {resultado_orig['tempo']:.3f}s")
        print(f"- Encontrou {resultado_otim['encontrados']} vs {resultado_orig['encontrados']} arquivos")
        print(f"- Performance: {((resultado_orig['tempo'] - resultado_otim['tempo'])/resultado_orig['tempo']*100):+.1f}% melhor")
        print("="*60)
        
    except Exception as e:
        print(f"❌ Erro durante análise: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
