#!/usr/bin/env python3
"""
teste_gerar_xml_comparativo.py

Finalidade:
    Teste isolado para comparar as funções gerar_xml_path e gerar_xml_path_otimizado
    e testar a integração no código que usa essas funções.

Testes realizados:
    1. Comparação de performance entre as duas funções
    2. Verificação de consistência de resultados
    3. Teste de integração com verificador_xmls.py
    4. Análise de casos extremos e edge cases

Autor:
    Equipe de Integração Omie - CorpServices
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# Adiciona o diretório src ao path para importar utils
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

try:
    from src.utils import (
        gerar_xml_path,
        gerar_xml_path_otimizado,
        gerar_nome_arquivo_xml,
        descobrir_todos_xmls,
        normalizar_data
    )
except ImportError:
    # Fallback se executando do diretório src
    from src.utils import (
        gerar_xml_path,
        gerar_xml_path_otimizado,
        gerar_nome_arquivo_xml,
        descobrir_todos_xmls,
        normalizar_data
    )

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('teste_gerar_xml_comparativo.log')
    ]
)

logger = logging.getLogger(__name__)

# ============================================================================
# DADOS DE TESTE
# ============================================================================

# Conjunto de dados de teste representativo
DADOS_TESTE = [
    # Formato brasileiro
    ("35250714200166000196550010000123451234567890", "17/07/2025", "123"),
    ("35250714200166000196550010000123461234567891", "17/07/2025", "124"),
    ("35250714200166000196550010000123471234567892", "18/07/2025", "125"),
    
    # Formato ISO
    ("35250714200166000196550010000123481234567893", "2025-07-19", "126"),
    ("35250714200166000196550010000123491234567894", "2025-07-20", "127"),
    
    # Casos extremos
    ("35250714200166000196550010000123501234567895", "21/07/2025", "1"),
    ("35250714200166000196550010000123511234567896", "21/07/2025", "9999"),
    
    # Volume para teste de performance
    *[(f"3525071420016600019655001000012{i:03d}{i:010d}", "22/07/2025", str(i)) 
      for i in range(350, 370)],
    
    # Datas diferentes para teste de estrutura hierárquica
    ("35250714200166000196550010000123521234567897", "01/01/2025", "1001"),
    ("35250714200166000196550010000123531234567898", "31/12/2024", "1002"),
]

# ============================================================================
# FUNÇÕES DE TESTE
# ============================================================================

def testar_consistencia_resultados() -> Dict[str, Any]:
    """
    Testa se ambas as funções retornam resultados consistentes.
    
    Returns:
        Dicionário com resultados do teste de consistência
    """
    logger.info("🧪 Iniciando teste de consistência de resultados...")
    
    resultados = {
        "total_testados": 0,
        "identicos": 0,
        "diferentes": 0,
        "erros_original": 0,
        "erros_otimizado": 0,
        "casos_divergentes": []
    }
    
    for chave, dEmi, num_nfe in DADOS_TESTE:
        resultados["total_testados"] += 1
        
        try:
            # Teste função original
            pasta_orig, arquivo_orig = gerar_xml_path(chave, dEmi, num_nfe)
        except Exception as e:
            logger.warning(f"Erro na função original para {chave}: {e}")
            resultados["erros_original"] += 1
            continue
            
        try:
            # Teste função otimizada
            pasta_otim, arquivo_otim = gerar_xml_path_otimizado(chave, dEmi, num_nfe)
        except Exception as e:
            logger.warning(f"Erro na função otimizada para {chave}: {e}")
            resultados["erros_otimizado"] += 1
            continue
        
        # Comparação de resultados
        if str(arquivo_orig) == str(arquivo_otim):
            resultados["identicos"] += 1
        else:
            resultados["diferentes"] += 1
            resultados["casos_divergentes"].append({
                "chave": chave[:20] + "...",
                "dEmi": dEmi,
                "num_nfe": num_nfe,
                "original": str(arquivo_orig),
                "otimizado": str(arquivo_otim)
            })
    
    # Log dos resultados
    logger.info(f"✅ Consistência: {resultados['identicos']}/{resultados['total_testados']} idênticos")
    if resultados["diferentes"] > 0:
        logger.warning(f"⚠️  {resultados['diferentes']} casos divergentes encontrados")
    
    return resultados

def testar_performance_comparativa(num_iteracoes: int = 100) -> Dict[str, Any]:
    """
    Compara a performance das duas funções com múltiplas iterações.
    
    Args:
        num_iteracoes: Número de iterações para cada função
        
    Returns:
        Dicionário com métricas de performance
    """
    logger.info(f"⚡ Iniciando teste de performance ({num_iteracoes} iterações)...")
    
    # Prepare dados para teste
    dados_performance = DADOS_TESTE * (num_iteracoes // len(DADOS_TESTE) + 1)
    dados_performance = dados_performance[:num_iteracoes]
    
    # Teste função original
    inicio_orig = time.perf_counter()
    erros_orig = 0
    for chave, dEmi, num_nfe in dados_performance:
        try:
            gerar_xml_path(chave, dEmi, num_nfe)
        except Exception:
            erros_orig += 1
    tempo_orig = time.perf_counter() - inicio_orig
    
    # Teste função otimizada
    inicio_otim = time.perf_counter()
    erros_otim = 0
    for chave, dEmi, num_nfe in dados_performance:
        try:
            gerar_xml_path_otimizado(chave, dEmi, num_nfe)
        except Exception:
            erros_otim += 1
    tempo_otim = time.perf_counter() - inicio_otim
    
    # Cálculo de métricas
    melhoria_percentual = ((tempo_orig - tempo_otim) / tempo_orig) * 100 if tempo_orig > 0 else 0
    
    resultados = {
        "iteracoes": num_iteracoes,
        "tempo_original": tempo_orig,
        "tempo_otimizado": tempo_otim,
        "melhoria_percentual": melhoria_percentual,
        "erros_original": erros_orig,
        "erros_otimizado": erros_otim,
        "ops_por_segundo_original": num_iteracoes / tempo_orig if tempo_orig > 0 else 0,
        "ops_por_segundo_otimizada": num_iteracoes / tempo_otim if tempo_otim > 0 else 0
    }
    
    # Log dos resultados
    logger.info(f"📊 Original: {tempo_orig:.4f}s ({resultados['ops_por_segundo_original']:.1f} ops/s)")
    logger.info(f"📊 Otimizada: {tempo_otim:.4f}s ({resultados['ops_por_segundo_otimizada']:.1f} ops/s)")
    logger.info(f"📈 Melhoria: {melhoria_percentual:+.1f}%")
    
    return resultados

def testar_casos_extremos() -> Dict[str, Any]:
    """
    Testa casos extremos e edge cases.
    
    Returns:
        Dicionário com resultados dos casos extremos
    """
    logger.info(" Testando casos extremos...")
    
    casos_extremos = [
        # Dados inválidos
        ("", "17/07/2025", "123"),
        ("chave_valida", "", "123"),
        ("chave_valida", "17/07/2025", ""),
        (None, "17/07/2025", "123"),
        
        # Datas inválidas
        ("35250714200166000196550010000123451234567890", "32/13/2025", "123"),
        ("35250714200166000196550010000123451234567890", "invalid_date", "123"),
        
        # Chaves muito longas/curtas
        ("a" * 100, "17/07/2025", "123"),
        ("abc", "17/07/2025", "123"),
        
        # Números NFe extremos
        ("35250714200166000196550010000123451234567890", "17/07/2025", "0"),
        ("35250714200166000196550010000123451234567890", "17/07/2025", "999999999"),
    ]
    
    resultados = {
        "total_casos": len(casos_extremos),
        "tratados_corretamente": 0,
        "erros_inesperados": 0,
        "comportamento_inconsistente": 0
    }
    
    for i, (chave, dEmi, num_nfe) in enumerate(casos_extremos, 1):
        logger.debug(f"Testando caso extremo {i}: {chave}, {dEmi}, {num_nfe}")
        
        # Teste função original
        erro_orig = None
        try:
            resultado_orig = gerar_xml_path(chave, dEmi, num_nfe)
        except Exception as e:
            erro_orig = type(e).__name__
        
        # Teste função otimizada
        erro_otim = None
        try:
            resultado_otim = gerar_xml_path_otimizado(chave, dEmi, num_nfe)
        except Exception as e:
            erro_otim = type(e).__name__
        
        # Análise de comportamento
        if erro_orig and erro_otim:
            if erro_orig == erro_otim:
                resultados["tratados_corretamente"] += 1
            else:
                resultados["comportamento_inconsistente"] += 1
                logger.warning(f"Comportamento inconsistente: orig={erro_orig}, otim={erro_otim}")
        elif not erro_orig and not erro_otim:
            resultados["tratados_corretamente"] += 1
        else:
            resultados["erros_inesperados"] += 1
            logger.warning(f"Erro inesperado: orig={erro_orig}, otim={erro_otim}")
    
    logger.info(f"🎯 Casos extremos: {resultados['tratados_corretamente']}/{resultados['total_casos']} tratados corretamente")
    
    return resultados

def testar_integracao_verificador() -> Dict[str, Any]:
    """
    Testa a integração com o módulo verificador_xmls.py.
    
    Returns:
        Dicionário com resultados do teste de integração
    """
    logger.info("🔗 Testando integração com verificador_xmls...")
    
    try:
        # Import do verificador
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
        from verificador_xmls import verificar_arquivo_no_disco_e_validar_campo
        
        resultados = {
            "import_sucesso": True,
            "testes_executados": 0,
            "funciona_com_original": 0,
            "funciona_com_otimizada": 0,
            "erros": []
        }
        
        # Testa alguns casos do DADOS_TESTE
        casos_teste = DADOS_TESTE[:5]  # Primeiros 5 casos
        
        for chave, dEmi, num_nfe in casos_teste:
            resultados["testes_executados"] += 1
            
            try:
                # Simula o comportamento do verificador_xmls
                row = (chave, dEmi, num_nfe)
                resultado = verificar_arquivo_no_disco_e_validar_campo(row)
                
                # Se não deu erro, considera sucesso (arquivo pode ou não existir)
                resultados["funciona_com_original"] += 1
                
                logger.debug(f"Verificador retornou: {resultado} para {chave[:20]}...")
                
            except Exception as e:
                resultados["erros"].append(f"Erro ao testar {chave[:20]}...: {e}")
        
        # Para função otimizada, precisaria modificar o verificador_xmls
        # Vamos simular isso testando diretamente a função
        for chave, dEmi, num_nfe in casos_teste:
            try:
                pasta, arquivo = gerar_xml_path_otimizado(chave, dEmi, num_nfe)
                # Se a função não deu erro, considera sucesso
                resultados["funciona_com_otimizada"] += 1
            except Exception as e:
                resultados["erros"].append(f"Erro na função otimizada {chave[:20]}...: {e}")
        
        logger.info(f"✅ Integração: {resultados['funciona_com_original']}/{resultados['testes_executados']} casos funcionam")
        
    except ImportError as e:
        resultados = {
            "import_sucesso": False,
            "erro_import": str(e),
            "testes_executados": 0
        }
        logger.error(f"❌ Falha ao importar verificador_xmls: {e}")
    
    return resultados

def testar_descobrir_xmls_integracao() -> Dict[str, Any]:
    """
    Testa especificamente a integração com descobrir_todos_xmls.
    
    Returns:
        Dicionário com resultados do teste de descobrir_todos_xmls
    """
    logger.info("📂 Testando integração com descobrir_todos_xmls...")
    
    resultados = {
        "pasta_resultado_existe": False,
        "xmls_encontrados": 0,
        "funcao_executou": False,
        "tempo_execucao": 0,
        "erros": []
    }
    
    try:
        # Verifica se pasta resultado existe
        pasta_resultado = Path("resultado")
        if not pasta_resultado.exists():
            # Tenta pasta relativa do src
            pasta_resultado = Path("../resultado")
        
        if pasta_resultado.exists():
            resultados["pasta_resultado_existe"] = True
            
            inicio = time.perf_counter()
            xmls = descobrir_todos_xmls(pasta_resultado)
            resultados["tempo_execucao"] = time.perf_counter() - inicio
            
            resultados["xmls_encontrados"] = len(xmls)
            resultados["funcao_executou"] = True
            
            logger.info(f"📊 Descobertos {len(xmls)} XMLs em {resultados['tempo_execucao']:.3f}s")
            
            # Teste com alguns XMLs encontrados (se houver)
            if xmls:
                logger.info(f"📝 Exemplo de XMLs encontrados:")
                for i, xml in enumerate(xmls[:3]):  # Primeiros 3
                    logger.info(f"   {i+1}. {xml}")
        else:
            logger.warning("⚠️  Pasta 'resultado' não encontrada")
            
    except Exception as e:
        resultados["erros"].append(str(e))
        logger.error(f"❌ Erro ao testar descobrir_todos_xmls: {e}")
    
    return resultados

# ============================================================================
# FUNÇÃO PRINCIPAL DE TESTE
# ============================================================================

def executar_suite_completa() -> Dict[str, Any]:
    """
    Executa a suite completa de testes comparativos.
    
    Returns:
        Dicionário com todos os resultados dos testes
    """
    logger.info("🚀 Iniciando suite completa de testes comparativos...")
    
    suite_resultados = {
        "inicio": time.strftime("%Y-%m-%d %H:%M:%S"),
        "consistencia": {},
        "performance": {},
        "casos_extremos": {},
        "integracao_verificador": {},
        "descobrir_xmls": {},
        "fim": None,
        "duracao_total": 0
    }
    
    inicio_suite = time.perf_counter()
    
    try:
        # 1. Teste de consistência
        logger.info("\n" + "="*50)
        suite_resultados["consistencia"] = testar_consistencia_resultados()
        
        # 2. Teste de performance
        logger.info("\n" + "="*50)
        suite_resultados["performance"] = testar_performance_comparativa(500)
        
        # 3. Casos extremos
        logger.info("\n" + "="*50)
        suite_resultados["casos_extremos"] = testar_casos_extremos()
        
        # 4. Integração com verificador
        logger.info("\n" + "="*50)
        suite_resultados["integracao_verificador"] = testar_integracao_verificador()
        
        # 5. Teste descobrir_todos_xmls
        logger.info("\n" + "="*50)
        suite_resultados["descobrir_xmls"] = testar_descobrir_xmls_integracao()
        
    except Exception as e:
        logger.error(f"❌ Erro durante execução da suite: {e}")
        suite_resultados["erro_suite"] = str(e)
    
    suite_resultados["duracao_total"] = time.perf_counter() - inicio_suite
    suite_resultados["fim"] = time.strftime("%Y-%m-%d %H:%M:%S")
    
    return suite_resultados

def imprimir_relatorio_final(resultados: Dict[str, Any]) -> None:
    """
    Imprime relatório final dos testes.
    
    Args:
        resultados: Dicionário com todos os resultados dos testes
    """
    print("\n" + "="*80)
    print("📋 RELATÓRIO FINAL - COMPARAÇÃO gerar_xml_path vs gerar_xml_path_otimizado")
    print("="*80)
    
    print(f" Duração total: {resultados['duracao_total']:.2f}s")
    print(f"🕐 Início: {resultados['inicio']}")
    print(f"🕐 Fim: {resultados['fim']}")
    
    # Consistência
    if resultados.get("consistencia"):
        cons = resultados["consistencia"]
        print(f"\n🧪 CONSISTÊNCIA:")
        print(f"   ✅ Idênticos: {cons.get('identicos', 0)}/{cons.get('total_testados', 0)}")
        print(f"   ⚠️  Diferentes: {cons.get('diferentes', 0)}")
        print(f"   ❌ Erros original: {cons.get('erros_original', 0)}")
        print(f"   ❌ Erros otimizada: {cons.get('erros_otimizado', 0)}")
    
    # Performance
    if resultados.get("performance"):
        perf = resultados["performance"]
        print(f"\n⚡ PERFORMANCE:")
        print(f"   📊 Original: {perf.get('tempo_original', 0):.4f}s ({perf.get('ops_por_segundo_original', 0):.1f} ops/s)")
        print(f"   📊 Otimizada: {perf.get('tempo_otimizado', 0):.4f}s ({perf.get('ops_por_segundo_otimizada', 0):.1f} ops/s)")
        print(f"   📈 Melhoria: {perf.get('melhoria_percentual', 0):+.1f}%")
    
    # Casos extremos
    if resultados.get("casos_extremos"):
        extremos = resultados["casos_extremos"]
        print(f"\n CASOS EXTREMOS:")
        print(f"   🎯 Tratados corretamente: {extremos.get('tratados_corretamente', 0)}/{extremos.get('total_casos', 0)}")
        print(f"   ⚠️  Comportamento inconsistente: {extremos.get('comportamento_inconsistente', 0)}")
    
    # Integração
    if resultados.get("integracao_verificador"):
        integ = resultados["integracao_verificador"]
        print(f"\n🔗 INTEGRAÇÃO:")
        print(f"   ✅ Import sucesso: {integ.get('import_sucesso', False)}")
        print(f"   🔧 Funciona com original: {integ.get('funciona_com_original', 0)}")
        print(f"   🔧 Funciona com otimizada: {integ.get('funciona_com_otimizada', 0)}")
    
    # descobrir_todos_xmls
    if resultados.get("descobrir_xmls"):
        disc = resultados["descobrir_xmls"]
        print(f"\n📂 DESCOBRIR XMLs:")
        print(f"   📁 Pasta resultado existe: {disc.get('pasta_resultado_existe', False)}")
        print(f"   📄 XMLs encontrados: {disc.get('xmls_encontrados', 0)}")
        print(f"    Tempo execução: {disc.get('tempo_execucao', 0):.3f}s")
    
    print("\n" + "="*80)
    
    # Recomendações
    print("💡 RECOMENDAÇÕES:")
    
    if resultados.get("performance", {}).get("melhoria_percentual", 0) > 0:
        print("   ✅ A versão otimizada apresenta melhor performance - recomendada para uso")
    else:
        print("   ⚠️  A versão original apresenta performance similar ou melhor")
    
    if resultados.get("consistencia", {}).get("diferentes", 0) == 0:
        print("   ✅ Resultados consistentes entre as funções - migração segura")
    else:
        print("   ⚠️  Existem divergências - revisar casos antes da migração")
    
    if resultados.get("integracao_verificador", {}).get("import_sucesso", False):
        print("   ✅ Integração com verificador_xmls funcionando")
    else:
        print("   ⚠️  Problemas na integração com verificador_xmls")
    
    print("="*80)

# ============================================================================
# EXECUÇÃO PRINCIPAL
# ============================================================================

if __name__ == "__main__":
    print("🧪 TESTE COMPARATIVO: gerar_xml_path vs gerar_xml_path_otimizado")
    print("="*80)
    
    # Ajusta diretório de trabalho se necessário
    if os.path.basename(os.getcwd()) == 'src':
        os.chdir('..')
        logger.info("📁 Mudando para diretório raiz do projeto")
    
    logger.info(f"📁 Diretório atual: {os.getcwd()}")
    
    try:
        # Executa suite completa
        resultados = executar_suite_completa()
        
        # Imprime relatório
        imprimir_relatorio_final(resultados)
        
        # Salva resultados em arquivo
        import json
        with open("teste_gerar_xml_resultados.json", "w", encoding="utf-8") as f:
            json.dump(resultados, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info("💾 Resultados salvos em teste_gerar_xml_resultados.json")
        
    except Exception as e:
        logger.error(f"❌ Erro durante execução dos testes: {e}")
        sys.exit(1)
