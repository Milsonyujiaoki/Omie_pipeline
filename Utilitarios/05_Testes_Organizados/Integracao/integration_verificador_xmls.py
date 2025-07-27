#!/usr/bin/env python3
"""
Testes isolados para verificar a veracidade dos dados do verificador_xmls.py

Finalidade:
- Validar se os arquivos encontrados realmente existem
- Verificar se há arquivos não detectados (falsos negativos)
- Analisar padrões nos arquivos encontrados vs não encontrados
- Diagnosticar possíveis problemas na lógica de verificação
"""

import os
import sqlite3
import logging
from pathlib import Path
import sys
from typing import List, Tuple, Dict

# Adicionar path para importar utils
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

try:
    from src.utils import gerar_xml_path, gerar_xml_path_otimizado
except ImportError:
    # Fallback se executando do diretório src ou raiz
    try:
        from src.utils import gerar_xml_path, gerar_xml_path_otimizado
    except ImportError:
        logger.error("Não foi possível importar as funções de utils")
        sys.exit(1)

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def testar_amostra_aleatoria(db_path: str = "omie.db", amostra: int = 20) -> None:
    """
    Testa uma amostra aleatória de registros para verificar se o algoritmo está funcionando.
    
    Args:
        db_path: Caminho do banco SQLite
        amostra: Quantidade de registros para testar
    """
    logger.info(f"=== TESTE 1: AMOSTRA ALEATÓRIA ({amostra} registros) ===")
    
    with sqlite3.connect(db_path) as conn:
        # Busca amostra aleatória de registros pendentes
        cursor = conn.execute(f"""
            SELECT cChaveNFe, dEmi, nNF 
            FROM notas 
            WHERE xml_baixado = 0 
            ORDER BY RANDOM() 
            LIMIT {amostra}
        """)
        rows = cursor.fetchall()
    
    logger.info(f"Testando {len(rows)} registros aleatórios...")
    
    encontrados = 0
    nao_encontrados = 0
    
    for i, (chave, dEmi, nNF) in enumerate(rows, 1):
        try:
            _, caminho = gerar_xml_path(chave, dEmi, nNF)
            existe = caminho.exists()
            tamanho = caminho.stat().st_size if existe else 0
            
            status = "✓ ENCONTRADO" if existe and tamanho > 0 else "✗ NÃO ENCONTRADO"
            if existe and tamanho > 0:
                encontrados += 1
            else:
                nao_encontrados += 1
                
            logger.info(f"  {i:2d}. {status} | {chave[:20]}... | {nNF} | {tamanho:,} bytes")
            
            # Mostra detalhes do primeiro arquivo encontrado
            if i == 1 and existe:
                logger.info(f"       Caminho: {caminho}")
                
        except Exception as e:
            logger.error(f"  {i:2d}. ERRO ao verificar {chave}: {e}")
            nao_encontrados += 1
    
    percentual = (encontrados / len(rows)) * 100 if rows else 0
    logger.info(f"\nResultado da amostra:")
    logger.info(f"  Encontrados: {encontrados}/{len(rows)} ({percentual:.1f}%)")
    logger.info(f"  Não encontrados: {nao_encontrados}/{len(rows)} ({100-percentual:.1f}%)")


def testar_registros_baixados(db_path: str = "omie.db", amostra: int = 10) -> None:
    """
    Testa registros que já foram marcados como baixados para verificar consistência.
    
    Args:
        db_path: Caminho do banco SQLite
        amostra: Quantidade de registros para testar
    """
    logger.info(f"\n=== TESTE 2: REGISTROS JÁ BAIXADOS ({amostra} registros) ===")
    
    with sqlite3.connect(db_path) as conn:
        # Busca amostra de registros já marcados como baixados
        cursor = conn.execute(f"""
            SELECT cChaveNFe, dEmi, nNF 
            FROM notas 
            WHERE xml_baixado = 1 
            ORDER BY RANDOM() 
            LIMIT {amostra}
        """)
        rows = cursor.fetchall()
    
    if not rows:
        logger.warning("Nenhum registro marcado como baixado encontrado!")
        return
        
    logger.info(f"Testando {len(rows)} registros já marcados como baixados...")
    
    consistentes = 0
    inconsistentes = 0
    
    for i, (chave, dEmi, nNF) in enumerate(rows, 1):
        try:
            _, caminho = gerar_xml_path(chave, dEmi, nNF)
            existe = caminho.exists()
            tamanho = caminho.stat().st_size if existe else 0
            
            if existe and tamanho > 0:
                status = "✓ CONSISTENTE"
                consistentes += 1
            else:
                status = "✗ INCONSISTENTE"
                inconsistentes += 1
                
            logger.info(f"  {i:2d}. {status} | {chave[:20]}... | {nNF} | {tamanho:,} bytes")
                
        except Exception as e:
            logger.error(f"  {i:2d}. ERRO ao verificar {chave}: {e}")
            inconsistentes += 1
    
    percentual = (consistentes / len(rows)) * 100 if rows else 0
    logger.info(f"\nConsistência dos registros baixados:")
    logger.info(f"  Consistentes: {consistentes}/{len(rows)} ({percentual:.1f}%)")
    logger.info(f"  Inconsistentes: {inconsistentes}/{len(rows)} ({100-percentual:.1f}%)")


def analisar_diretorios_resultado() -> None:
    """
    Analisa os diretórios de resultado para entender a estrutura dos arquivos.
    Considera subpastas numeradas dentro de cada dia (limitadas a 10.000 arquivos).
    """
    logger.info(f"\n=== TESTE 3: ANÁLISE DE DIRETÓRIOS (COM SUBPASTAS) ===")
    
    resultado_dir = Path("resultado")
    
    if not resultado_dir.exists():
        logger.error(f"Diretório 'resultado' não encontrado: {resultado_dir.absolute()}")
        return
    
    # Conta arquivos XML por diretório incluindo subpastas
    total_xmls = 0
    diretorios_com_xml = 0
    subpastas_encontradas = 0
    
    logger.info("Analisando estrutura de diretórios com subpastas...")
    
    for ano_dir in resultado_dir.iterdir():
        if not ano_dir.is_dir():
            continue
            
        for mes_dir in ano_dir.iterdir():
            if not mes_dir.is_dir():
                continue
                
            for dia_dir in mes_dir.iterdir():
                if not dia_dir.is_dir():
                    continue
                
                # Primeiro verifica XMLs diretos no diretório do dia
                xmls_diretos = list(dia_dir.glob("*.xml"))
                xmls_neste_dia = len(xmls_diretos)
                
                # Agora verifica subpastas com padrão {dia}_pasta_{numero}
                # Exemplo: 21_pasta_1, 21_pasta_2, etc.
                subpastas_neste_dia = 0
                dia_atual = dia_dir.name  # Extrai o dia (ex: "21")
                
                for item in dia_dir.iterdir():
                    # Verifica se é uma subpasta com padrão {dia}_pasta_{numero}
                    if (item.is_dir() and 
                        item.name.startswith(f"{dia_atual}_pasta_") and
                        item.name.count('_') >= 2):
                        
                        subpastas_neste_dia += 1
                        subpastas_encontradas += 1
                        xmls_na_subpasta = list(item.glob("*.xml"))
                        xmls_neste_dia += len(xmls_na_subpasta)
                        
                        # Log detalhado das primeiras subpastas
                        if diretorios_com_xml < 3 and len(xmls_na_subpasta) > 0:
                            logger.info(f"    Subpasta {item}: {len(xmls_na_subpasta)} XMLs")
                            if xmls_na_subpasta:
                                exemplo = xmls_na_subpasta[0]
                                tamanho = exemplo.stat().st_size
                                logger.info(f"      Exemplo: {exemplo.name} ({tamanho:,} bytes)")
                
                if xmls_neste_dia > 0:
                    total_xmls += xmls_neste_dia
                    diretorios_com_xml += 1
                    
                    # Log apenas dos primeiros 3 diretórios com arquivos
                    if diretorios_com_xml <= 3:
                        logger.info(f"  {dia_dir}: {xmls_neste_dia} XMLs total")
                        if xmls_diretos:
                            logger.info(f"    Diretos no dia: {len(xmls_diretos)} XMLs")
                        if subpastas_neste_dia > 0:
                            logger.info(f"    Subpastas encontradas: {subpastas_neste_dia}")
                        
                        # Mostra exemplo de arquivo direto se existir
                        if xmls_diretos:
                            exemplo = xmls_diretos[0]
                            tamanho = exemplo.stat().st_size
                            logger.info(f"    Exemplo direto: {exemplo.name} ({tamanho:,} bytes)")
    
    logger.info(f"\nEstatísticas dos diretórios:")
    logger.info(f"  Total de XMLs encontrados: {total_xmls:,}")
    logger.info(f"  Diretórios (dias) com XMLs: {diretorios_com_xml}")
    logger.info(f"  Subpastas numeradas encontradas: {subpastas_encontradas}")
    logger.info(f"  Média por diretório de dia: {total_xmls/diretorios_com_xml:.1f}" if diretorios_com_xml > 0 else "  Média: 0")
    logger.info(f"  Média por subpasta: {total_xmls/subpastas_encontradas:.1f}" if subpastas_encontradas > 0 else "  Sem subpastas ou média: 0")


def testar_funcao_gerar_xml_path() -> None:
    """
    Testa a função gerar_xml_path com dados conhecidos.
    Verifica se está considerando subpastas numeradas corretamente.
    """
    logger.info(f"\n=== TESTE 4: FUNÇÃO GERAR_XML_PATH (COM SUBPASTAS) ===")
    
    # Busca alguns registros reais do banco para testar
    with sqlite3.connect("omie.db") as conn:
        cursor = conn.execute("""
            SELECT cChaveNFe, dEmi, nNF 
            FROM notas 
            WHERE xml_baixado = 1 
            LIMIT 3
        """)
        rows = cursor.fetchall()
    
    if not rows:
        logger.warning("Nenhum registro baixado encontrado para teste")
        return
    
    logger.info(f"Testando função gerar_xml_path com {len(rows)} registros...")
    
    for i, (chave, dEmi, nNF) in enumerate(rows, 1):
        logger.info(f"\nTeste {i}:")
        logger.info(f"  cChaveNFe: {chave}")
        logger.info(f"  dEmi: {dEmi}")
        logger.info(f"  nNF: {nNF}")
        
        try:
            pasta, caminho = gerar_xml_path(chave, dEmi, nNF)
            logger.info(f"  Pasta gerada: {pasta}")
            logger.info(f"  Caminho gerado: {caminho}")
            
            # Verifica se o arquivo existe no caminho gerado
            existe_no_caminho = caminho.exists()
            logger.info(f"  Arquivo existe no caminho gerado: {existe_no_caminho}")
            
            if existe_no_caminho:
                tamanho = caminho.stat().st_size
                logger.info(f"  Tamanho: {tamanho:,} bytes")
            else:
                # Se não existe no caminho gerado, vamos procurar manualmente
                # para ver se está em alguma subpasta
                logger.info("  Procurando em subpastas...")
                
                # Extrai ano, mês, dia do caminho
                parts = caminho.parts
                if len(parts) >= 4:  # resultado/ano/mes/dia/arquivo.xml
                    dia_dir = Path(*parts[:-1])  # diretório do dia
                    nome_arquivo = parts[-1]  # nome do arquivo
                    
                    encontrado_em_subpasta = False
                    if dia_dir.exists():
                        # Extrai o dia do caminho para formar o padrão da subpasta
                        dia_str = dia_dir.name  # Ex: "21"
                        
                        # Procura em subpastas com padrão {dia}_pasta_{numero}
                        for subitem in dia_dir.iterdir():
                            if (subitem.is_dir() and 
                                subitem.name.startswith(f"{dia_str}_pasta_") and
                                subitem.name.count('_') >= 2):
                                
                                arquivo_na_subpasta = subitem / nome_arquivo
                                if arquivo_na_subpasta.exists():
                                    tamanho = arquivo_na_subpasta.stat().st_size
                                    logger.info(f"  ✓ ENCONTRADO na subpasta {subitem.name}: {tamanho:,} bytes")
                                    logger.info(f"    Caminho real: {arquivo_na_subpasta}")
                                    encontrado_em_subpasta = True
                                    break
                    
                    if not encontrado_em_subpasta:
                        logger.info("  ✗ Não encontrado nem no caminho gerado nem em subpastas")
            
        except Exception as e:
            logger.error(f"  ERRO na função gerar_xml_path: {e}")
    
    # Teste adicional: verifica se a função está preparada para subpastas
    logger.info(f"\n=== VERIFICAÇÃO DA LÓGICA DE SUBPASTAS ===")
    logger.info("Analisando se gerar_xml_path considera subpastas...")
    
    # Importa e examina a função
    try:
        import inspect
        fonte = inspect.getsource(gerar_xml_path)
        tem_logica_subpasta = any(palavra in fonte.lower() for palavra in ['subpasta', 'subdirectory', 'folder', '10000', 'limit'])
        logger.info(f"Função parece ter lógica de subpastas: {'SIM' if tem_logica_subpasta else 'PROVAVELMENTE NÃO'}")
        
        # Mostra parte relevante do código se encontrar
        linhas = fonte.split('\n')
        for i, linha in enumerate(linhas):
            if any(palavra in linha.lower() for palavra in ['pasta', 'dir', 'folder', 'path']):
                logger.info(f"  Linha {i+1}: {linha.strip()}")
                
    except Exception as e:
        logger.warning(f"Não foi possível analisar o código da função: {e}")


def comparar_com_resultado_verificador() -> None:
    """
    Compara os resultados com o que o verificador encontrou.
    """
    logger.info(f"\n=== TESTE 5: COMPARAÇÃO COM VERIFICADOR ===")
    
    # Executa a mesma lógica do verificador para alguns registros
    with sqlite3.connect("omie.db") as conn:
        # Busca 100 registros pendentes
        cursor = conn.execute("""
            SELECT cChaveNFe, dEmi, nNF 
            FROM notas 
            WHERE xml_baixado = 0 
            LIMIT 100
        """)
        rows = cursor.fetchall()
    
    logger.info(f"Testando lógica do verificador com {len(rows)} registros...")
    
    encontrados_aqui = 0
    
    for chave, dEmi, nNF in rows:
        try:
            _, caminho = gerar_xml_path(chave, dEmi, nNF)
            if caminho.exists() and caminho.stat().st_size > 0:
                encontrados_aqui += 1
        except Exception:
            pass
    
    percentual = (encontrados_aqui / len(rows)) * 100 if rows else 0
    logger.info(f"Resultado da replicação:")
    logger.info(f"  Encontrados: {encontrados_aqui}/{len(rows)} ({percentual:.1f}%)")
    logger.info(f"  Taxa similar ao verificador original (3/5761 = 0.05%): {'SIM' if percentual < 1 else 'NÃO'}")


def comparar_funcoes_gerar_xml_path(db_path: str = "omie.db", amostra: int = 10) -> None:
    """
    Compara diretamente as funções gerar_xml_path e gerar_xml_path_otimizado.
    
    Args:
        db_path: Caminho do banco SQLite
        amostra: Quantidade de registros para testar
    """
    logger.info(f"\n=== TESTE EXTRA: COMPARAÇÃO DIRETA DAS FUNÇÕES ===")
    
    with sqlite3.connect(db_path) as conn:
        # Busca amostra de registros
        cursor = conn.execute(f"""
            SELECT cChaveNFe, dEmi, nNF 
            FROM notas 
            WHERE xml_baixado = 0 
            ORDER BY RANDOM() 
            LIMIT {amostra}
        """)
        rows = cursor.fetchall()
    
    if not rows:
        logger.warning("Nenhum registro encontrado para comparação")
        return
        
    logger.info(f"Comparando {len(rows)} registros entre as duas funções...")
    
    import time
    
    # Performance tracking
    tempo_original = 0
    tempo_otimizada = 0
    
    resultados_identicos = 0
    resultados_diferentes = 0
    original_encontra = 0
    otimizada_encontra = 0
    
    for i, (chave, dEmi, nNF) in enumerate(rows, 1):
        logger.info(f"\n--- Teste {i}: {chave[:20]}... ---")
        
        # Teste função original
        try:
            inicio = time.perf_counter()
            pasta_orig, caminho_orig = gerar_xml_path(chave, dEmi, nNF)
            tempo_original += time.perf_counter() - inicio
            
            existe_orig = caminho_orig.exists() and caminho_orig.stat().st_size > 0
            if existe_orig:
                original_encontra += 1
                
            logger.info(f"  Original: {caminho_orig}")
            logger.info(f"  Original existe: {existe_orig}")
            
        except Exception as e:
            logger.error(f"  Original ERRO: {e}")
            continue
        
        # Teste função otimizada
        try:
            inicio = time.perf_counter()
            pasta_otim, caminho_otim = gerar_xml_path_otimizado(chave, dEmi, nNF)
            tempo_otimizada += time.perf_counter() - inicio
            
            existe_otim = caminho_otim.exists() and caminho_otim.stat().st_size > 0
            if existe_otim:
                otimizada_encontra += 1
                
            logger.info(f"  Otimizada: {caminho_otim}")
            logger.info(f"  Otimizada existe: {existe_otim}")
            
        except Exception as e:
            logger.error(f"  Otimizada ERRO: {e}")
            continue
        
        # Comparação
        if str(caminho_orig) == str(caminho_otim):
            resultados_identicos += 1
            logger.info(f"  ✅ Caminhos IDÊNTICOS")
        else:
            resultados_diferentes += 1
            logger.info(f"  ⚠️  Caminhos DIFERENTES")
            
            # Analisa qual está correto
            if existe_orig and not existe_otim:
                logger.info(f"     → Original está correto")
            elif not existe_orig and existe_otim:
                logger.info(f"     → Otimizada está correto")
            elif existe_orig and existe_otim:
                logger.info(f"     → Ambos encontram arquivos (possível duplicação)")
            else:
                logger.info(f"     → Nenhum encontra arquivo")
    
    # Resumo
    logger.info(f"\n=== RESUMO DA COMPARAÇÃO ===")
    logger.info(f"Performance:")
    logger.info(f"  Original: {tempo_original:.4f}s")
    logger.info(f"  Otimizada: {tempo_otimizada:.4f}s")
    if tempo_original > 0:
        melhoria = ((tempo_original - tempo_otimizada) / tempo_original) * 100
        logger.info(f"  Melhoria: {melhoria:+.1f}%")
    
    logger.info(f"\nPrecisão na localização:")
    logger.info(f"  Original encontra: {original_encontra}/{len(rows)}")
    logger.info(f"  Otimizada encontra: {otimizada_encontra}/{len(rows)}")
    
    logger.info(f"\nConsistência:")
    logger.info(f"  Caminhos idênticos: {resultados_identicos}/{len(rows)}")
    logger.info(f"  Caminhos diferentes: {resultados_diferentes}/{len(rows)}")
    
    # Recomendação
    if otimizada_encontra > original_encontra:
        logger.info(f"\n💡 RECOMENDAÇÃO: Usar função OTIMIZADA (encontra mais arquivos)")
    elif original_encontra > otimizada_encontra:
        logger.info(f"\n💡 RECOMENDAÇÃO: Usar função ORIGINAL (encontra mais arquivos)")
    else:
        logger.info(f"\n💡 RECOMENDAÇÃO: Ambas equivalentes em precisão, usar OTIMIZADA (mais rápida)")


def main():
    """Executa todos os testes de verificação."""
    logger.info("INICIANDO TESTES DE VERIFICAÇÃO DO VERIFICADOR_XMLS.PY")
    logger.info("=" * 60)
    
    # Verifica se o banco existe
    if not os.path.exists("omie.db"):
        logger.error("Banco 'omie.db' não encontrado!")
        return
    
    try:
        # Executa todos os testes
        testar_amostra_aleatoria()
        testar_registros_baixados()
        analisar_diretorios_resultado()
        testar_funcao_gerar_xml_path()
        comparar_com_resultado_verificador()
        
        # NOVO: Teste de comparação direta
        comparar_funcoes_gerar_xml_path()
        
        logger.info("\n" + "=" * 60)
        logger.info("TESTES CONCLUÍDOS")
        
    except Exception as e:
        logger.exception(f"Erro durante os testes: {e}")

if __name__ == "__main__":
    main()
