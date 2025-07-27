#!/usr/bin/env python3
"""
 ANÁLISE COMPLETA E MÉTRICAS DETALHADAS DO BANCO DE DADOS OMIE V3
===================================================================

Script avançado para análise detalhada do banco de dados com:
- Estatísticas gerais e específicas
- Análise temporal e distribuições
- Verificação de integridade e qualidade dos dados
- Métricas de performance e progresso
- Análise de erros e problemas
- Projeções e estimativas
- Visualizações em tabelas formatadas
- Exportação de relatórios

Características técnicas:
- Utiliza índices existentes para performance máxima
- Análise em lotes para evitar sobrecarga de memória
- Formatação rica com cores e tabelas
- Suporte a múltiplos formatos de saída
- Cálculos estatísticos avançados
"""

import os
import sys
import sqlite3
import json
import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, NamedTuple
from dataclasses import dataclass
from collections import defaultdict, Counter
import time

# Adiciona src ao path para importar utils
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from src.utils import (
        SQLITE_PRAGMAS,
        normalizar_data,
        formatar_data_iso_para_br,
        sanitizar_cnpj
    )
    from main import criar_indices_performance
    HAS_UTILS = True
except ImportError:
    print("⚠ Módulos utils não encontrados - executando com funcionalidades básicas")
    HAS_UTILS = False
    SQLITE_PRAGMAS = {
        "journal_mode": "WAL",
        "synchronous": "NORMAL",
        "temp_store": "MEMORY",
        "cache_size": "-64000"
    }

# =============================================================================
# CONFIGURAÇÃO E CONSTANTES
# =============================================================================

DB_PATH = "omie.db"
TABLE_NAME = "notas"
RESULTADO_DIR = "resultado"

# Cores para output no terminal - desabilitadas para compatibilidade
class Cores:
    ''' '''
    VERDE = ''
    AZUL = ''
    AMARELO = ''
    VERMELHO = ''
    MAGENTA = ''
    CIANO = ''
    BRANCO = ''
    RESET = ''
    NEGRITO = ''

# =============================================================================
# ESTRUTURAS DE DADOS
# =============================================================================

@dataclass
class EstatisticasGerais:
    """Estatísticas gerais do banco de dados"""
    total_registros: int
    xml_baixados: int
    xml_pendentes: int
    com_erro: int
    sem_erro: int
    percentual_concluido: float
    percentual_erro: float
    data_inicio: str
    data_fim: str
    total_dias: int

@dataclass
class AnaliseDetalhada:
    """Análise detalhada dia a dia"""
    dados_por_dia: List[Dict[str, Any]]  # Lista completa de dados diários
    resumo_mensal: Dict[str, Dict[str, Any]]  # Resumo detalhado por mês
    top_dias_problematicos: List[Tuple[str, Dict[str, int]]]  # Dias com mais problemas
    distribuicao_horarios: Dict[str, int]  # Se tivermos dados de hora
    padroes_sazonais: Dict[str, Any]  # Padrões por dia da semana, etc.

@dataclass
class EstatisticasTemporais:
    """Estatísticas temporais e distribuições"""
    distribuicao_por_dia: Dict[str, int]
    distribuicao_por_mes: Dict[str, int]
    distribuicao_por_ano: Dict[str, int]
    dias_com_mais_registros: List[Tuple[str, int]]
    dias_com_mais_erros: List[Tuple[str, int]]
    periodo_mais_ativo: Tuple[str, str, int]
    analise_detalhada: AnaliseDetalhada  # Nova análise detalhada

@dataclass
class QualidadeDados:
    """Métricas otimizadas de qualidade dos dados"""
    total_registros: int
    registros_validos: int
    registros_com_erro: int
    registros_sem_erro: int
    arquivos_baixados: int
    arquivos_nao_baixados: int
    com_anomesdia: int
    sem_anomesdia: int
    campos_nulos: Dict[str, int]
    campos_obrigatorios_vazios: Dict[str, int]
    registros_duplicados: int
    registros_inconsistentes: int
    cnpjs_invalidos: int
    datas_invalidas: int
    valores_fora_padrao: Dict[str, int]
    top_inconsistencias: List[Tuple[str, int]]
    percentual_completos: float
    percentual_baixados: float
    percentual_com_anomesdia: float
    percentual_sem_erro: float

@dataclass
class MetricasPerformance:
    """Métricas otimizadas de performance e velocidade"""
    velocidade_media_por_dia: float
    dias_mais_rapidos: List[Tuple[str, float]]
    dias_mais_lentos: List[Tuple[str, float]]
    projecao_conclusao: str
    tempo_restante_estimado: str
    eficiencia_geral: float
    tendencia_performance: str
    variabilidade_performance: float
    total_registros: int
    registros_baixados: int
    registros_pendentes: int

@dataclass
class AnaliseErros:
    """Análise otimizada e detalhada de erros"""
    tipos_erro: Dict[str, int]
    distribuicao_erro_temporal: Dict[str, int]
    erros_por_cnpj: Dict[str, int]
    erros_por_faixa_nf: Dict[str, int]
    detalhes_erros: List[Dict[str, Any]]
    top_tipos_erro: List[Tuple[str, int]]
    top_cnpj_erro: List[Tuple[str, int]]
    top_faixa_nf_erro: List[Tuple[str, int]]
    total_erros: int
    taxa_erro_geral: float
    taxa_sucesso: float
    ultimos_30_dias_erros: Dict[str, int]

# =============================================================================
# UTILITÁRIOS DE FORMATAÇÃO
# =============================================================================

def formatar_numero(numero: int) -> str:
    """Formata número com separadores de milhares"""
    return f"{numero:,}".replace(",", ".")

def formatar_percentual(valor: float) -> str:
    """Formata percentual simples"""
    return f"{valor:.1f}%"

def formatar_duracao(segundos: float) -> str:
    """Formata duração em formato legível"""
    if segundos < 60:
        return f"{segundos:.1f}s"
    elif segundos < 3600:
        return f"{segundos/60:.1f}min"
    elif segundos < 86400:
        return f"{segundos/3600:.1f}h"
    else:
        return f"{segundos/86400:.1f}dias"

def criar_tabela(titulo: str, colunas: List[str], dados: List[List[str]], 
                 largura_total: int = 80) -> str:
    """Cria tabela formatada para exibição"""
    resultado = []
    
    # Cabeçalho
    resultado.append("=" * largura_total)
    resultado.append(f"{titulo:^{largura_total}}")
    resultado.append("=" * largura_total)
    
    if not dados:
        resultado.append(f"{'Nenhum dado disponível':^{largura_total}}")
        resultado.append("=" * largura_total)
        return "\n".join(resultado)
    
    # Calcular larguras das colunas
    num_colunas = len(colunas)
    largura_coluna = (largura_total - (num_colunas + 1)) // num_colunas
    
    # Cabeçalho das colunas
    linha_cabecalho = "|"
    for coluna in colunas:
        linha_cabecalho += f" {coluna[:largura_coluna-1].ljust(largura_coluna-1)} |"
    resultado.append(linha_cabecalho)
    resultado.append("-" * largura_total)
    
    # Dados
    for linha in dados[:20]:  # Limita a 20 linhas
        linha_dados = "|"
        for i, valor in enumerate(linha):
            texto = str(valor)[:largura_coluna-1].ljust(largura_coluna-1)
            linha_dados += f" {texto} |"
        resultado.append(linha_dados)
    
    if len(dados) > 20:
        resultado.append(f"... e mais {len(dados) - 20} registros")
    
    resultado.append("=" * largura_total)
    return "\n".join(resultado)

def exibir_header():
    """Exibe cabeçalho principal"""
    print(f"\n{'='*80}")
    print(f" ANÁLISE COMPLETA DO BANCO DE DADOS OMIE V3")
    print(f"{'='*80}")
    print(f"Timestamp: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print()

# =============================================================================
# CONEXÃO E OTIMIZAÇÃO DO BANCO
# =============================================================================

def conectar_banco_otimizado(db_path: str) -> sqlite3.Connection:
    """Conecta ao banco com otimizações de performance"""
    if not Path(db_path).exists():
        raise FileNotFoundError(f"Banco de dados não encontrado: {db_path}")
    
    conn = sqlite3.connect(db_path)
    
    # Aplicar otimizações SQLite
    for pragma, valor in SQLITE_PRAGMAS.items():
        conn.execute(f"PRAGMA {pragma} = {valor}")
    
    # Criar índices se não existirem (usando utils se disponível)
    if HAS_UTILS:
        try:
            with criar_indices_performance(db_path):
                pass
        except:
            pass
    
    return conn

# =============================================================================
# ANÁLISES ESPECÍFICAS
# =============================================================================

def obter_estatisticas_gerais(conn: sqlite3.Connection) -> EstatisticasGerais:
    """Obtém estatísticas gerais do banco de dados"""
    cursor = conn.cursor()
    
    # Contadores principais
    cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
    total_registros = cursor.fetchone()[0]
    
    cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE xml_baixado = 1")
    xml_baixados = cursor.fetchone()[0]
    
    cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE xml_baixado = 0 OR xml_baixado IS NULL")
    xml_pendentes = cursor.fetchone()[0]
    
    # Verificar se existe coluna erro
    cursor.execute("PRAGMA table_info(notas)")
    colunas = [col[1] for col in cursor.fetchall()]
    
    if 'erro' in colunas:
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE erro = 1")
        com_erro = cursor.fetchone()[0]
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE erro = 0 OR erro IS NULL")
        sem_erro = cursor.fetchone()[0]
    elif 'erro_xml' in colunas:
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE erro_xml IS NOT NULL AND erro_xml != ''")
        com_erro = cursor.fetchone()[0]
        sem_erro = total_registros - com_erro
    else:
        com_erro = 0
        sem_erro = total_registros
    
    # Calcular percentuais
    percentual_concluido = (xml_baixados / max(1, total_registros)) * 100
    percentual_erro = (com_erro / max(1, total_registros)) * 100
    
    # Período de dados - usando conversão SQL para ordenação cronológica correta
    cursor.execute(f"""
        SELECT MIN(date(substr(dEmi, 7, 4) || '-' || substr(dEmi, 4, 2) || '-' || substr(dEmi, 1, 2))),
               MAX(date(substr(dEmi, 7, 4) || '-' || substr(dEmi, 4, 2) || '-' || substr(dEmi, 1, 2)))
        FROM {TABLE_NAME} 
        WHERE dEmi IS NOT NULL AND dEmi != '' AND dEmi LIKE '__/__/____'
    """)
    resultado = cursor.fetchone()
    
    # Converter de volta para formato brasileiro se encontrou datas válidas
    if resultado[0] and resultado[1]:
        try:
            data_inicio_iso = resultado[0]
            data_fim_iso = resultado[1]
            # Converter ISO (YYYY-MM-DD) para BR (DD/MM/YYYY)
            data_inicio = datetime.strptime(data_inicio_iso, '%Y-%m-%d').strftime('%d/%m/%Y')
            data_fim = datetime.strptime(data_fim_iso, '%Y-%m-%d').strftime('%d/%m/%Y')
        except ValueError:
            data_inicio = "N/A"
            data_fim = "N/A"
    else:
        data_inicio = "N/A"
        data_fim = "N/A"
    
    # Calcular total de dias
    total_dias = 0
    if data_inicio != "N/A" and data_fim != "N/A":
        try:
            inicio = datetime.strptime(data_inicio, '%d/%m/%Y')
            fim = datetime.strptime(data_fim, '%d/%m/%Y')
            total_dias = (fim - inicio).days + 1
        except ValueError:
            total_dias = 0
    
    return EstatisticasGerais(
        total_registros=total_registros,
        xml_baixados=xml_baixados,
        xml_pendentes=xml_pendentes,
        com_erro=com_erro,
        sem_erro=sem_erro,
        percentual_concluido=percentual_concluido,
        percentual_erro=percentual_erro,
        data_inicio=data_inicio,
        data_fim=data_fim,
        total_dias=total_dias
    )

def obter_analise_detalhada_por_dia(conn: sqlite3.Connection) -> AnaliseDetalhada:
    """Obtém análise detalhada dia a dia"""
    cursor = conn.cursor()
    
    # Dados completos por dia
    cursor.execute(f"""
        SELECT 
            dEmi as data,
            COUNT(*) as total_registros,
            SUM(CASE WHEN xml_baixado = 1 THEN 1 ELSE 0 END) as xml_baixados,
            SUM(CASE WHEN xml_baixado = 0 OR xml_baixado IS NULL THEN 1 ELSE 0 END) as xml_pendentes,
            SUM(CASE WHEN erro = 1 THEN 1 ELSE 0 END) as com_erro_flag,
            SUM(CASE WHEN erro_xml IS NOT NULL AND erro_xml != '' THEN 1 ELSE 0 END) as com_erro_xml,
            COUNT(DISTINCT cChaveNFe) as chaves_unicas,
            COUNT(DISTINCT cnpj_cpf) as cnpjs_unicos,
            AVG(CAST(nNF AS FLOAT)) as media_numero_nf,
            MIN(nNF) as menor_nf,
            MAX(nNF) as maior_nf
        FROM {TABLE_NAME} 
        WHERE dEmi IS NOT NULL AND dEmi != '' AND dEmi LIKE '__/__/____'
        GROUP BY dEmi 
        ORDER BY date(substr(dEmi, 7, 4) || '-' || substr(dEmi, 4, 2) || '-' || substr(dEmi, 1, 2))
    """)
    
    dados_por_dia = []
    for row in cursor.fetchall():
        data, total, baixados, pendentes, erro_flag, erro_xml, chaves, cnpjs, media_nf, min_nf, max_nf = row
        
        # Calcular métricas derivadas
        taxa_sucesso = (baixados / max(1, total)) * 100
        taxa_erro = ((erro_flag + erro_xml) / max(1, total)) * 100
        duplicatas = total - chaves if chaves else 0
        
        dados_por_dia.append({
            'data': data,
            'total_registros': total,
            'xml_baixados': baixados,
            'xml_pendentes': pendentes,
            'erros_flag': erro_flag,
            'erros_xml': erro_xml,
            'total_erros': erro_flag + erro_xml,
            'taxa_sucesso': taxa_sucesso,
            'taxa_erro': taxa_erro,
            'chaves_unicas': chaves,
            'cnpjs_unicos': cnpjs,
            'duplicatas': duplicatas,
            'media_nf': media_nf or 0,
            'faixa_nf': f"{min_nf or 0}-{max_nf or 0}"
        })
    
    # Resumo mensal detalhado
    resumo_mensal = {}
    for item in dados_por_dia:
        try:
            dt = datetime.strptime(item['data'], '%d/%m/%Y')
            mes_ano = dt.strftime('%m/%Y')
            mes_nome = dt.strftime('%B/%Y')
            
            if mes_ano not in resumo_mensal:
                resumo_mensal[mes_ano] = {
                    'mes_nome': mes_nome,
                    'total_dias': 0,
                    'total_registros': 0,
                    'total_baixados': 0,
                    'total_pendentes': 0,
                    'total_erros': 0,
                    'melhor_dia': {'data': '', 'registros': 0},
                    'pior_dia': {'data': '', 'erros': 0},
                    'media_diaria': 0,
                    'dias_sem_atividade': 0,
                    'eficiencia_media': 0
                }
            
            resumo = resumo_mensal[mes_ano]
            resumo['total_dias'] += 1
            resumo['total_registros'] += item['total_registros']
            resumo['total_baixados'] += item['xml_baixados']
            resumo['total_pendentes'] += item['xml_pendentes']
            resumo['total_erros'] += item['total_erros']
            
            # Melhor e pior dia
            if item['total_registros'] > resumo['melhor_dia']['registros']:
                resumo['melhor_dia'] = {'data': item['data'], 'registros': item['total_registros']}
            
            if item['total_erros'] > resumo['pior_dia']['erros']:
                resumo['pior_dia'] = {'data': item['data'], 'erros': item['total_erros']}
            
        except ValueError:
            continue
    
    # Calcular médias mensais
    for mes_ano, resumo in resumo_mensal.items():
        resumo['media_diaria'] = resumo['total_registros'] / max(1, resumo['total_dias'])
        resumo['eficiencia_media'] = (resumo['total_baixados'] / max(1, resumo['total_registros'])) * 100
    
    # Top dias problemáticos (mais erros relativos)
    top_dias_problematicos = []
    for item in dados_por_dia:
        if item['total_registros'] > 100:  # Só considerar dias com volume significativo
            peso_problema = (item['taxa_erro'] * 0.7) + (item['xml_pendentes'] / item['total_registros'] * 100 * 0.3)
            if peso_problema > 10:  # Threshold de problema
                top_dias_problematicos.append((
                    item['data'], 
                    {
                        'peso_problema': peso_problema,
                        'total_erros': item['total_erros'],
                        'taxa_erro': item['taxa_erro'],
                        'xml_pendentes': item['xml_pendentes'],
                        'total_registros': item['total_registros']
                    }
                ))
    
    top_dias_problematicos.sort(key=lambda x: x[1]['peso_problema'], reverse=True)
    
    # Padrões sazonais (dia da semana)
    padroes_sazonais = {
        'por_dia_semana': {'Segunda': 0, 'Terça': 0, 'Quarta': 0, 'Quinta': 0, 'Sexta': 0, 'Sábado': 0, 'Domingo': 0},
        'periodo_pico': '',
        'periodo_baixo': '',
        'tendencia': ''
    }
    
    dias_semana_registros = {}
    for item in dados_por_dia:
        try:
            dt = datetime.strptime(item['data'], '%d/%m/%Y')
            dia_semana = dt.strftime('%A')
            # Tradução simples
            traducao = {
                'Monday': 'Segunda', 'Tuesday': 'Terça', 'Wednesday': 'Quarta',
                'Thursday': 'Quinta', 'Friday': 'Sexta', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
            }
            dia_semana_pt = traducao.get(dia_semana, dia_semana)
            
            if dia_semana_pt not in dias_semana_registros:
                dias_semana_registros[dia_semana_pt] = []
            dias_semana_registros[dia_semana_pt].append(item['total_registros'])
        except ValueError:
            continue
    
    # Calcular médias por dia da semana
    for dia, valores in dias_semana_registros.items():
        padroes_sazonais['por_dia_semana'][dia] = sum(valores) / len(valores) if valores else 0
    
    # Identificar padrões
    if padroes_sazonais['por_dia_semana']:
        dia_pico = max(padroes_sazonais['por_dia_semana'], key=padroes_sazonais['por_dia_semana'].get)
        dia_baixo = min(padroes_sazonais['por_dia_semana'], key=padroes_sazonais['por_dia_semana'].get)
        padroes_sazonais['periodo_pico'] = f"{dia_pico} ({padroes_sazonais['por_dia_semana'][dia_pico]:.0f} reg/dia)"
        padroes_sazonais['periodo_baixo'] = f"{dia_baixo} ({padroes_sazonais['por_dia_semana'][dia_baixo]:.0f} reg/dia)"
    
def obter_estatisticas_temporais(conn: sqlite3.Connection) -> EstatisticasTemporais:
    """Obtém estatísticas temporais e distribuições otimizadas"""
    cursor = conn.cursor()
    
    # OTIMIZAÇÃO: Usa campo anomesdia quando disponível, fallback para dEmi
    # Primeiro tenta usar o campo anomesdia (mais rápido) ou view otimizada
    try:
        # Verifica se existe view otimizada
        cursor.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='vw_resumo_diario'")
        tem_view_resumo = cursor.fetchone() is not None
        
        if tem_view_resumo:
            # Usa view pré-calculada (mais rápido)
            cursor.execute("SELECT data_formatada, total_registros FROM vw_resumo_diario ORDER BY data_iso")
            distribuicao_por_dia = dict(cursor.fetchall())
        else:
            # Usa anomesdia se disponível, mais rápido que conversão de string
            cursor.execute(f"""
                SELECT COUNT(*) FROM {TABLE_NAME} 
                WHERE anomesdia IS NOT NULL AND anomesdia > 0 
                LIMIT 1
            """)
            tem_anomesdia = cursor.fetchone()[0] > 0
            
            if tem_anomesdia:
                # Query otimizada usando anomesdia (índice numérico)
                cursor.execute(f"""
                    SELECT 
                        printf('%02d/%02d/%04d', 
                            anomesdia % 100, 
                            (anomesdia / 100) % 100, 
                            anomesdia / 10000) as data_formatada,
                        COUNT(*) as total
                    FROM {TABLE_NAME} 
                    WHERE anomesdia IS NOT NULL AND anomesdia > 0
                    GROUP BY anomesdia 
                    ORDER BY anomesdia
                """)
            else:
                # Fallback para dEmi (mais lento)
                cursor.execute(f"""
                    SELECT dEmi, COUNT(*) as total
                    FROM {TABLE_NAME} 
                    WHERE dEmi IS NOT NULL AND dEmi != '' AND dEmi LIKE '__/__/____'
                    GROUP BY dEmi 
                    ORDER BY date(substr(dEmi, 7, 4) || '-' || substr(dEmi, 4, 2) || '-' || substr(dEmi, 1, 2))
                """)
            
            distribuicao_por_dia = dict(cursor.fetchall())
    
    except Exception as e:
        # Em caso de erro, usa método tradicional
        cursor.execute(f"""
            SELECT dEmi, COUNT(*) as total
            FROM {TABLE_NAME} 
            WHERE dEmi IS NOT NULL AND dEmi != '' AND dEmi LIKE '__/__/____'
            GROUP BY dEmi 
            ORDER BY date(substr(dEmi, 7, 4) || '-' || substr(dEmi, 4, 2) || '-' || substr(dEmi, 1, 2))
        """)
        distribuicao_por_dia = dict(cursor.fetchall())
    
    # Distribuição por mês e ano (otimizada)
    distribuicao_por_mes = defaultdict(int)
    distribuicao_por_ano = defaultdict(int)
    
    for data, count in distribuicao_por_dia.items():
        try:
            dt = datetime.strptime(data, '%d/%m/%Y')
            mes_ano = dt.strftime('%m/%Y')
            ano = dt.strftime('%Y')
            distribuicao_por_mes[mes_ano] += count
            distribuicao_por_ano[ano] += count
        except ValueError:
            continue
    
    # Top dias com mais registros
    dias_com_mais_registros = sorted(
        distribuicao_por_dia.items(), 
        key=lambda x: x[1], 
        reverse=True
    )[:10]
    
    # OTIMIZAÇÃO: Dias com mais erros usando índices específicos
    try:
        # Verifica se tem view de erros
        cursor.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='vw_notas_com_erro'")
        tem_view_erros = cursor.fetchone() is not None
        
        if tem_view_erros:
            cursor.execute("""
                SELECT data_formatada, COUNT(*) as erros
                FROM vw_notas_com_erro 
                GROUP BY data_formatada 
                ORDER BY erros DESC 
                LIMIT 10
            """)
        else:
            # Query otimizada com índices
            cursor.execute(f"""
                SELECT dEmi, COUNT(*) as erros
                FROM {TABLE_NAME} 
                WHERE (erro = 1 OR (erro_xml IS NOT NULL AND erro_xml != ''))
                AND dEmi IS NOT NULL AND dEmi != '' AND dEmi LIKE '__/__/____'
                GROUP BY dEmi 
                ORDER BY erros DESC 
                LIMIT 10
            """)
        
        dias_com_mais_erros = cursor.fetchall()
    except Exception:
        dias_com_mais_erros = []
    
    # Período mais ativo (otimizado)
    periodo_mais_ativo = ("N/A", "N/A", 0)
    if distribuicao_por_dia:
        dia_max = max(distribuicao_por_dia.items(), key=lambda x: x[1])
        periodo_mais_ativo = (dia_max[0], dia_max[0], dia_max[1])
    
    # Análise detalhada (com limite para performance)
    analise_detalhada = obter_analise_detalhada_por_dia(conn)
    
    return EstatisticasTemporais(
        distribuicao_por_dia=distribuicao_por_dia,
        distribuicao_por_mes=dict(distribuicao_por_mes),
        distribuicao_por_ano=dict(distribuicao_por_ano),
        dias_com_mais_registros=dias_com_mais_registros,
        dias_com_mais_erros=dias_com_mais_erros,
        periodo_mais_ativo=periodo_mais_ativo,
        analise_detalhada=analise_detalhada
    )
    """Obtém estatísticas temporais e distribuições"""
    cursor = conn.cursor()
    
    # Distribuição por dia - ordenada cronologicamente
    cursor.execute(f"""
        SELECT dEmi, COUNT(*) as total
        FROM {TABLE_NAME} 
        WHERE dEmi IS NOT NULL AND dEmi != '' AND dEmi LIKE '__/__/____'
        GROUP BY dEmi 
        ORDER BY date(substr(dEmi, 7, 4) || '-' || substr(dEmi, 4, 2) || '-' || substr(dEmi, 1, 2))
    """)
    distribuicao_por_dia = dict(cursor.fetchall())
    
    # Distribuição por mês (extraindo mês/ano da data)
    distribuicao_por_mes = defaultdict(int)
    distribuicao_por_ano = defaultdict(int)
    
    for data, count in distribuicao_por_dia.items():
        try:
            dt = datetime.strptime(data, '%d/%m/%Y')
            mes_ano = dt.strftime('%m/%Y')
            ano = dt.strftime('%Y')
            distribuicao_por_mes[mes_ano] += count
            distribuicao_por_ano[ano] += count
        except ValueError:
            continue
    
    # Top dias com mais registros
    dias_com_mais_registros = sorted(
        distribuicao_por_dia.items(), 
        key=lambda x: x[1], 
        reverse=True
    )[:10]
    
    # Dias com mais erros - ordenados por quantidade de erros
    cursor.execute(f"""
        SELECT dEmi, COUNT(*) as erros
        FROM {TABLE_NAME} 
        WHERE (erro = 1 OR erro_xml IS NOT NULL) 
        AND dEmi IS NOT NULL AND dEmi != '' AND dEmi LIKE '__/__/____'
        GROUP BY dEmi 
        ORDER BY erros DESC 
        LIMIT 10
    """)
    dias_com_mais_erros = cursor.fetchall()
    
    # Período mais ativo (semana com mais registros)
    periodo_mais_ativo = ("N/A", "N/A", 0)
    if distribuicao_por_dia:
        # Simplificado: pega o dia com mais registros
        dia_max = max(distribuicao_por_dia.items(), key=lambda x: x[1])
        periodo_mais_ativo = (dia_max[0], dia_max[0], dia_max[1])
    
    return EstatisticasTemporais(
        distribuicao_por_dia=distribuicao_por_dia,
        distribuicao_por_mes=dict(distribuicao_por_mes),
        distribuicao_por_ano=dict(distribuicao_por_ano),
        dias_com_mais_registros=dias_com_mais_registros,
        dias_com_mais_erros=dias_com_mais_erros,
        periodo_mais_ativo=periodo_mais_ativo
    )

def obter_qualidade_dados(conn: sqlite3.Connection) -> QualidadeDados:
    """Análise de qualidade de dados otimizada usando índices e views"""
    cursor = conn.cursor()
    
    # OTIMIZAÇÃO 1: Total geral usando COUNT(*) simples
    cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
    total_registros = cursor.fetchone()[0]
    
    # OTIMIZAÇÃO 2: Campos obrigatórios - query única com CASE
    cursor.execute(f"""
        SELECT 
            SUM(CASE WHEN cChaveNFe IS NULL OR cChaveNFe = '' THEN 1 ELSE 0 END) as chaves_nulas,
            SUM(CASE WHEN nIdNF IS NULL OR nIdNF = '' THEN 1 ELSE 0 END) as id_nulas,
            SUM(CASE WHEN dEmi IS NULL OR dEmi = '' OR dEmi NOT LIKE '__/__/____' THEN 1 ELSE 0 END) as datas_nulas,
            SUM(CASE WHEN nNF IS NULL OR nNF = '' THEN 1 ELSE 0 END) as numeros_nulos,
            SUM(CASE WHEN cRazao IS NULL OR cRazao = '' THEN 1 ELSE 0 END) as razoes_nulas,
            SUM(CASE WHEN cnpj_cpf IS NULL OR cnpj_cpf = '' THEN 1 ELSE 0 END) as cnpj_nulos
        FROM {TABLE_NAME}
    """)
    chaves_nulas, id_nulas, datas_nulas, numeros_nulos, razoes_nulas, cnpj_nulos = cursor.fetchone()
    
    campos_obrigatorios_vazios = {
        'Chave NFe': chaves_nulas,
        'ID NFe': id_nulas,
        'Data Emissão': datas_nulas,
        'Número NFe': numeros_nulos,
        'Razão Social': razoes_nulas,
        'CNPJ/CPF': cnpj_nulos
    }
    
    # OTIMIZAÇÃO 3: Registros duplicados - query otimizada
    cursor.execute(f"""
        SELECT COUNT(*) - COUNT(DISTINCT cChaveNFe) 
        FROM {TABLE_NAME} 
        WHERE cChaveNFe IS NOT NULL AND cChaveNFe != ''
    """)
    registros_duplicados = cursor.fetchone()[0]
    
    # OTIMIZAÇÃO 4: Registros inconsistentes - query otimizada
    cursor.execute(f"""
        SELECT COUNT(*) FROM {TABLE_NAME} 
        WHERE xml_baixado = 1 AND (caminho_arquivo IS NULL OR caminho_arquivo = '')
    """)
    registros_inconsistentes = cursor.fetchone()[0]
    
    # OTIMIZAÇÃO 5: CNPJs inválidos com verificação de tamanho otimizada
    cursor.execute(f"""
        SELECT COUNT(*) FROM {TABLE_NAME} 
        WHERE cnpj_cpf IS NOT NULL 
        AND cnpj_cpf != '' 
        AND LENGTH(REPLACE(REPLACE(REPLACE(cnpj_cpf, '.', ''), '/', ''), '-', '')) NOT IN (11, 14)
    """)
    cnpjs_invalidos = cursor.fetchone()[0]
    
    # OTIMIZAÇÃO 6: Datas inválidas - verifica formato DD/MM/YYYY
    datas_invalidas = datas_nulas  # Já calculado acima
    
    # OTIMIZAÇÃO 7: Valores fora do padrão - queries consolidadas
    cursor.execute(f"""
        SELECT 
            SUM(CASE WHEN nNF IS NOT NULL AND nNF != '' 
                AND (CAST(nNF AS INTEGER) <= 0 OR LENGTH(nNF) > 20) THEN 1 ELSE 0 END) as numeros_invalidos,
            SUM(CASE WHEN vNF IS NOT NULL AND CAST(vNF AS FLOAT) <= 0 THEN 1 ELSE 0 END) as valores_invalidos,
            SUM(CASE WHEN xml_baixado = 1 THEN 1 ELSE 0 END) as baixados,
            SUM(CASE WHEN anomesdia IS NOT NULL AND anomesdia > 0 THEN 1 ELSE 0 END) as com_anomesdia
        FROM {TABLE_NAME}
    """)
    numeros_invalidos, valores_invalidos, arquivos_baixados, com_anomesdia = cursor.fetchone()
    
    valores_fora_padrao = {
        'Números NFe inválidos': numeros_invalidos,
        'Valores NFe inválidos': valores_invalidos
    }
    
    # OTIMIZAÇÃO 8: Verificação de erros usando índices
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='vw_notas_com_erro'")
        tem_view_erros = cursor.fetchone() is not None
        
        if tem_view_erros:
            cursor.execute("SELECT COUNT(*) FROM vw_notas_com_erro")
            registros_com_erro = cursor.fetchone()[0]
        else:
            cursor.execute(f"""
                SELECT COUNT(*) FROM {TABLE_NAME} 
                WHERE erro = 1 OR (erro_xml IS NOT NULL AND erro_xml != '')
            """)
            registros_com_erro = cursor.fetchone()[0]
    except Exception:
        registros_com_erro = 0
    
    # Calcular percentuais de qualidade
    nao_baixados = total_registros - arquivos_baixados
    sem_anomesdia = total_registros - com_anomesdia
    registros_sem_erro = total_registros - registros_com_erro
    
    # Campos nulos consolidados
    campos_nulos = {
        'cChaveNFe': chaves_nulas,
        'cnpj_cpf': cnpj_nulos,
        'dEmi': datas_nulas,
        'nNF': numeros_nulos,
        'cRazao': razoes_nulas,
        'anomesdia': sem_anomesdia
    }
    
    # Top inconsistências ordenadas
    inconsistencias = []
    if chaves_nulas > 0:
        inconsistencias.append(("Chaves NFe nulas/vazias", chaves_nulas))
    if cnpj_nulos > 0:
        inconsistencias.append(("CNPJ/CPF nulos/vazios", cnpj_nulos))
    if nao_baixados > 0:
        inconsistencias.append(("XMLs não baixados", nao_baixados))
    if registros_duplicados > 0:
        inconsistencias.append(("Registros duplicados", registros_duplicados))
    if registros_inconsistentes > 0:
        inconsistencias.append(("Registros inconsistentes", registros_inconsistentes))
    if cnpjs_invalidos > 0:
        inconsistencias.append(("CNPJs inválidos", cnpjs_invalidos))
    
    inconsistencias.sort(key=lambda x: x[1], reverse=True)
    top_inconsistencias = inconsistencias[:10]
    
    # Percentuais de qualidade
    percentual_baixados = (arquivos_baixados / total_registros * 100) if total_registros > 0 else 0
    percentual_com_anomesdia = (com_anomesdia / total_registros * 100) if total_registros > 0 else 0
    percentual_sem_erro = (registros_sem_erro / total_registros * 100) if total_registros > 0 else 0
    percentual_chaves_validas = ((total_registros - chaves_nulas) / total_registros * 100) if total_registros > 0 else 0
    
    return QualidadeDados(
        total_registros=total_registros,
        registros_validos=total_registros - chaves_nulas,
        registros_com_erro=registros_com_erro,
        registros_sem_erro=registros_sem_erro,
        arquivos_baixados=arquivos_baixados,
        arquivos_nao_baixados=nao_baixados,
        com_anomesdia=com_anomesdia,
        sem_anomesdia=sem_anomesdia,
        campos_nulos=campos_nulos,
        campos_obrigatorios_vazios=campos_obrigatorios_vazios,
        registros_duplicados=registros_duplicados,
        registros_inconsistentes=registros_inconsistentes,
        cnpjs_invalidos=cnpjs_invalidos,
        datas_invalidas=datas_invalidas,
        valores_fora_padrao=valores_fora_padrao,
        top_inconsistencias=top_inconsistencias,
        percentual_completos=round(percentual_chaves_validas, 2),
        percentual_baixados=round(percentual_baixados, 2),
        percentual_com_anomesdia=round(percentual_com_anomesdia, 2),
        percentual_sem_erro=round(percentual_sem_erro, 2)
    )

def obter_metricas_performance(conn: sqlite3.Connection) -> MetricasPerformance:
    """Calcula métricas de performance otimizadas usando índices e views"""
    cursor = conn.cursor()
    
    # OTIMIZAÇÃO 1: Verifica se existem views otimizadas
    cursor.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='vw_resumo_diario'")
    tem_view_resumo = cursor.fetchone() is not None
    
    # OTIMIZAÇÃO 2: Usa anomesdia quando disponível (mais rápido)
    cursor.execute(f"""
        SELECT COUNT(*) FROM {TABLE_NAME} 
        WHERE anomesdia IS NOT NULL AND anomesdia > 0 
        LIMIT 1
    """)
    tem_anomesdia = cursor.fetchone()[0] > 0
    
    # OTIMIZAÇÃO 3: Velocidade por dia usando campo mais eficiente
    if tem_view_resumo:
        # Usa view pré-calculada (mais rápido)
        cursor.execute("""
            SELECT data_formatada, total_registros
            FROM vw_resumo_diario 
            WHERE total_registros > 0
            ORDER BY data_iso
        """)
        dados_por_dia = cursor.fetchall()
    elif tem_anomesdia:
        # Query otimizada usando anomesdia (índice numérico)
        cursor.execute(f"""
            SELECT 
                printf('%02d/%02d/%04d', 
                    anomesdia % 100, 
                    (anomesdia / 100) % 100, 
                    anomesdia / 10000) as data_formatada,
                COUNT(*) as total_dia
            FROM {TABLE_NAME} 
            WHERE xml_baixado = 1 AND anomesdia IS NOT NULL AND anomesdia > 0
            GROUP BY anomesdia 
            HAVING total_dia > 0
            ORDER BY anomesdia
        """)
        dados_por_dia = cursor.fetchall()
    else:
        # Fallback para dEmi (mais lento)
        cursor.execute(f"""
            SELECT dEmi, COUNT(*) as total_dia
            FROM {TABLE_NAME} 
            WHERE xml_baixado = 1 AND dEmi IS NOT NULL AND dEmi != '' AND dEmi LIKE '__/__/____'
            GROUP BY dEmi 
            HAVING total_dia > 0
            ORDER BY date(substr(dEmi, 7, 4) || '-' || substr(dEmi, 4, 2) || '-' || substr(dEmi, 1, 2))
        """)
        dados_por_dia = cursor.fetchall()
    
    # OTIMIZAÇÃO 4: Cálculos de performance consolidados
    velocidade_media_por_dia = 0
    dias_rapidos = []
    dias_lentos = []
    
    if dados_por_dia:
        velocidades = [count for _, count in dados_por_dia]
        velocidade_media_por_dia = sum(velocidades) / len(velocidades)
        
        # Ordenar por velocidade (top 5 mais rápidos e 5 mais lentos)
        dados_ordenados = sorted(dados_por_dia, key=lambda x: x[1], reverse=True)
        dias_rapidos = dados_ordenados[:5]
        dias_lentos = dados_ordenados[-5:]
    
    # OTIMIZAÇÃO 5: Contadores únicos para eficiência
    cursor.execute(f"""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN xml_baixado = 1 THEN 1 ELSE 0 END) as baixados,
            SUM(CASE WHEN xml_baixado = 0 OR xml_baixado IS NULL THEN 1 ELSE 0 END) as pendentes
        FROM {TABLE_NAME}
    """)
    total, baixados, pendentes = cursor.fetchone()
    
    # OTIMIZAÇÃO 6: Projeção de conclusão otimizada
    if velocidade_media_por_dia > 0 and pendentes > 0:
        dias_restantes = pendentes / velocidade_media_por_dia
        data_conclusao = datetime.now() + timedelta(days=dias_restantes)
        projecao_conclusao = data_conclusao.strftime('%d/%m/%Y')
        tempo_restante_estimado = f"{dias_restantes:.1f} dias"
    else:
        projecao_conclusao = "N/A"
        tempo_restante_estimado = "N/A"
    
    # OTIMIZAÇÃO 7: Eficiência geral calculada com dados já obtidos
    eficiencia_geral = (baixados / max(1, total)) * 100
    
    # OTIMIZAÇÃO 8: Métricas adicionais de performance
    if dados_por_dia:
        # Análise de tendência (últimos 7 dias vs média geral)
        ultimos_dados = dados_por_dia[-7:] if len(dados_por_dia) >= 7 else dados_por_dia
        media_ultimos_dias = sum(count for _, count in ultimos_dados) / len(ultimos_dados)
        tendencia = "Crescente" if media_ultimos_dias > velocidade_media_por_dia else "Estável/Decrescente"
        
        # Variabilidade de performance
        max_dia = max(dados_por_dia, key=lambda x: x[1])[1]
        min_dia = min(dados_por_dia, key=lambda x: x[1])[1]
        variabilidade = ((max_dia - min_dia) / max(1, velocidade_media_por_dia)) * 100
    else:
        tendencia = "N/A"
        variabilidade = 0
    
    return MetricasPerformance(
        velocidade_media_por_dia=round(velocidade_media_por_dia, 2),
        dias_mais_rapidos=dias_rapidos,
        dias_mais_lentos=dias_lentos,
        projecao_conclusao=projecao_conclusao,
        tempo_restante_estimado=tempo_restante_estimado,
        eficiencia_geral=round(eficiencia_geral, 2),
        tendencia_performance=tendencia,
        variabilidade_performance=round(variabilidade, 2),
        total_registros=total,
        registros_baixados=baixados,
        registros_pendentes=pendentes
    )

def obter_analise_erros_detalhada(conn: sqlite3.Connection) -> AnaliseErros:
    """Análise otimizada de padrões de erros usando views e índices"""
    cursor = conn.cursor()
    
    # OTIMIZAÇÃO 1: Verifica se existe view específica para erros
    cursor.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='vw_notas_com_erro'")
    tem_view_erros = cursor.fetchone() is not None
    
    tipos_erro = defaultdict(int)
    distribuicao_erro_temporal = defaultdict(int)
    erros_por_cnpj = defaultdict(int)
    erros_por_faixa_nf = defaultdict(int)
    detalhes_erros = []
    
    # OTIMIZAÇÃO 2: Verifica colunas de erro disponíveis uma única vez
    cursor.execute("PRAGMA table_info(notas)")
    colunas = [col[1] for col in cursor.fetchall()]
    tem_erro_xml = 'erro_xml' in colunas
    tem_erro_flag = 'erro' in colunas
    
    # OTIMIZAÇÃO 3: Query consolidada para análise de erros
    if tem_view_erros:
        # Usa view otimizada se disponível
        cursor.execute("""
            SELECT 
                erro_xml, 
                data_formatada as dEmi, 
                cnpj_cpf,
                nNF,
                chave_nfe,
                1 as count_erros
            FROM vw_notas_com_erro 
            WHERE erro_xml IS NOT NULL AND erro_xml != ''
            ORDER BY data_iso DESC
            LIMIT 1000
        """)
    elif tem_erro_xml:
        # Query otimizada usando índices
        cursor.execute(f"""
            SELECT 
                erro_xml, 
                dEmi, 
                cnpj_cpf,
                nNF,
                cChaveNFe,
                1 as count_erros
            FROM {TABLE_NAME} 
            WHERE erro_xml IS NOT NULL AND erro_xml != ''
            ORDER BY ROWID DESC
            LIMIT 1000
        """)
    else:
        # Fallback se não houver coluna erro_xml
        cursor.execute(f"""
            SELECT 
                'Erro genérico' as erro_xml,
                dEmi, 
                cnpj_cpf,
                nNF,
                cChaveNFe,
                1 as count_erros
            FROM {TABLE_NAME} 
            WHERE erro = 1
            ORDER BY ROWID DESC
            LIMIT 1000
        """)
    
    # OTIMIZAÇÃO 4: Processamento eficiente dos resultados
    erros_processados = cursor.fetchall()
    
    for erro, data, cnpj, nf, chave, count in erros_processados:
        # Limita dados para performance
        detalhes_erros.append({
            'tipo': 'Erro XML',
            'descricao': erro[:100] if erro else 'Erro não especificado',
            'data': data or 'N/A',
            'cnpj': cnpj[:20] if cnpj else 'N/A',
            'nf': str(nf) if nf else 'N/A',
            'chave': chave[:44] if chave else 'N/A',
            'ocorrencias': count
        })
        
        # OTIMIZAÇÃO 5: Categorização otimizada de erros
        if erro:
            erro_lower = erro.lower()
            if 'timeout' in erro_lower or 'time' in erro_lower:
                tipos_erro['Timeout/Tempo Limite'] += count
            elif '500' in erro or 'internal server' in erro_lower:
                tipos_erro['Erro 500 (Servidor)'] += count
            elif '425' in erro or 'too early' in erro_lower:
                tipos_erro['Erro 425 (Too Early)'] += count
            elif '404' in erro or 'not found' in erro_lower:
                tipos_erro['Erro 404 (Não Encontrado)'] += count
            elif '403' in erro or 'forbidden' in erro_lower:
                tipos_erro['Erro 403 (Proibido)'] += count
            elif 'connection' in erro_lower or 'conexao' in erro_lower:
                tipos_erro['Erro de Conexão'] += count
            elif 'ssl' in erro_lower or 'certificate' in erro_lower:
                tipos_erro['Erro SSL/Certificado'] += count
            elif 'xml' in erro_lower or 'parse' in erro_lower:
                tipos_erro['Erro de XML/Parse'] += count
            elif 'memory' in erro_lower or 'memoria' in erro_lower:
                tipos_erro['Erro de Memória'] += count
            else:
                tipos_erro['Outros Erros'] += count
        
        # OTIMIZAÇÃO 6: Distribuição temporal usando anomesdia quando possível
        if data and data != 'N/A':
            try:
                # Tenta converter data para agrupamento mensal
                if '/' in data:
                    dt = datetime.strptime(data, '%d/%m/%Y')
                    mes_ano = dt.strftime('%m/%Y')
                    distribuicao_erro_temporal[mes_ano] += count
            except ValueError:
                distribuicao_erro_temporal['Data Inválida'] += count
        
        # Erros por CNPJ (limitado para performance)
        if cnpj and cnpj != 'N/A':
            erros_por_cnpj[cnpj[:20]] += count
        
        # Erros por faixa de NF
        if nf and str(nf).isdigit():
            try:
                num_nf = int(nf)
                if num_nf < 1000:
                    faixa = '001-999'
                elif num_nf < 10000:
                    faixa = '1.000-9.999'
                elif num_nf < 100000:
                    faixa = '10.000-99.999'
                else:
                    faixa = '100.000+'
                erros_por_faixa_nf[faixa] += count
            except ValueError:
                erros_por_faixa_nf['NF Inválida'] += count
    
    # OTIMIZAÇÃO 7: Estatísticas consolidadas usando queries únicas
    cursor.execute(f"""
        SELECT 
            COUNT(*) as total_registros,
            SUM(CASE WHEN erro = 1 OR (erro_xml IS NOT NULL AND erro_xml != '') THEN 1 ELSE 0 END) as total_erros,
            SUM(CASE WHEN xml_baixado = 1 THEN 1 ELSE 0 END) as total_baixados
        FROM {TABLE_NAME}
    """)
    total_registros, total_erros, total_baixados = cursor.fetchone()
    
    # OTIMIZAÇÃO 8: Top erros mais frequentes (limitado para performance)
    top_tipos_erro = sorted(tipos_erro.items(), key=lambda x: x[1], reverse=True)[:10]
    top_cnpj_erro = sorted(erros_por_cnpj.items(), key=lambda x: x[1], reverse=True)[:10]
    top_faixa_nf_erro = sorted(erros_por_faixa_nf.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Calcular taxa de erro
    taxa_erro_geral = (total_erros / max(1, total_registros)) * 100
    taxa_sucesso = ((total_registros - total_erros) / max(1, total_registros)) * 100
    
    # OTIMIZAÇÃO 9: Análise de padrões temporais otimizada
    if tem_view_erros:
        cursor.execute("""
            SELECT data_formatada, COUNT(*) as erros_dia
            FROM vw_notas_com_erro
            GROUP BY data_formatada
            ORDER BY data_iso DESC
            LIMIT 30
        """)
        ultimos_30_dias_erros = dict(cursor.fetchall())
    else:
        cursor.execute(f"""
            SELECT dEmi, COUNT(*) as erros_dia
            FROM {TABLE_NAME}
            WHERE (erro = 1 OR (erro_xml IS NOT NULL AND erro_xml != ''))
            AND dEmi IS NOT NULL AND dEmi != '' AND dEmi LIKE '__/__/____'
            GROUP BY dEmi
            ORDER BY date(substr(dEmi, 7, 4) || '-' || substr(dEmi, 4, 2) || '-' || substr(dEmi, 1, 2)) DESC
            LIMIT 30
        """)
        ultimos_30_dias_erros = dict(cursor.fetchall())
    
    return AnaliseErros(
        tipos_erro=dict(tipos_erro),
        distribuicao_erro_temporal=dict(distribuicao_erro_temporal),
        erros_por_cnpj=dict(erros_por_cnpj),
        erros_por_faixa_nf=dict(erros_por_faixa_nf),
        detalhes_erros=detalhes_erros[:100],  # Limita para performance
        top_tipos_erro=top_tipos_erro,
        top_cnpj_erro=top_cnpj_erro,
        top_faixa_nf_erro=top_faixa_nf_erro,
        total_erros=total_erros,
        taxa_erro_geral=round(taxa_erro_geral, 2),
        taxa_sucesso=round(taxa_sucesso, 2),
        ultimos_30_dias_erros=ultimos_30_dias_erros
    )

# =============================================================================
# FUNÇÕES DE RELATÓRIO E FORMATAÇÃO  
# =============================================================================

    
    # 2. Análise de XMLs não baixados por dia
    cursor.execute(f"""
        SELECT 
            dEmi,
            COUNT(*) as total_dia,
            SUM(CASE WHEN xml_baixado = 0 OR xml_baixado IS NULL THEN 1 ELSE 0 END) as nao_baixados,
            COUNT(DISTINCT cnpj_cpf) as cnpjs_afetados
        FROM {TABLE_NAME} 
        WHERE dEmi IS NOT NULL AND dEmi != '' AND dEmi LIKE '__/__/____'
        GROUP BY dEmi
        HAVING nao_baixados > 0
        ORDER BY nao_baixados DESC
        LIMIT 20
    """)
    
    for data, total, nao_baixados, cnpjs in cursor.fetchall():
        tipos_erro['XMLs Não Baixados'] += nao_baixados
        distribuicao_erro_temporal[data] += nao_baixados
        
        if nao_baixados > total * 0.1:  # Mais de 10% de falha no dia
            detalhes_erros.append({
                'tipo': 'Falha em Massa',
                'descricao': f'{nao_baixados} XMLs não baixados de {total} total',
                'data': data,
                'cnpj': f'{cnpjs} CNPJs afetados',
                'nf': '',
                'chave': '',
                'ocorrencias': nao_baixados
            })
    
    # 3. Análise de registros inconsistentes
    cursor.execute(f"""
        SELECT 
            'Inconsistência' as tipo,
            'XML marcado como baixado mas sem caminho' as descricao,
            dEmi,
            cnpj_cpf,
            nNF,
            cChaveNFe
        FROM {TABLE_NAME} 
        WHERE xml_baixado = 1 AND (caminho_arquivo IS NULL OR caminho_arquivo = '')
        LIMIT 50
    """)
    
    inconsistencias = cursor.fetchall()
    if inconsistencias:
        tipos_erro['Inconsistências de Estado'] += len(inconsistencias)
        for _, desc, data, cnpj, nf, chave in inconsistencias:
            detalhes_erros.append({
                'tipo': 'Inconsistência',
                'descricao': desc,
                'data': data or 'N/A',
                'cnpj': cnpj[:20] if cnpj else '',
                'nf': nf or '',
                'chave': chave[:44] if chave else '',
                'ocorrencias': 1
            })
    
    # Padrões identificados (mais sofisticados)
    padroes_erro = []
    total_erros = sum(tipos_erro.values())
    
    if tipos_erro.get('Erro 500 (Servidor)', 0) > total_erros * 0.3:
        padroes_erro.append(f"Alta incidência de erros 500 ({tipos_erro['Erro 500 (Servidor)']} - {tipos_erro['Erro 500 (Servidor)']/total_erros*100:.1f}%) - instabilidade do servidor")
    
    if tipos_erro.get('Timeout/Tempo Limite', 0) > 100:
        padroes_erro.append(f"Muitos timeouts ({tipos_erro['Timeout/Tempo Limite']}) - possível lentidão na rede")
    
    if tipos_erro.get('XMLs Não Baixados', 0) > 50000:
        padroes_erro.append(f"Grande volume de XMLs pendentes ({tipos_erro['XMLs Não Baixados']:,}) - processamento em andamento")
    
    # Identificar CNPJs problemáticos
    cnpjs_problema = sorted(erros_por_cnpj.items(), key=lambda x: x[1], reverse=True)[:5]
    if cnpjs_problema:
        padroes_erro.append(f"CNPJs com mais erros: {', '.join([f'{cnpj}({count})' for cnpj, count in cnpjs_problema])}")
    
    # Identificar dias problemáticos
    dias_problema = sorted(distribuicao_erro_temporal.items(), key=lambda x: x[1], reverse=True)[:3]
    if dias_problema:
        padroes_erro.append(f"Dias com mais erros: {', '.join([f'{dia}({count})' for dia, count in dias_problema])}")
    
    # Sugestões de correção (mais específicas)
    sugestoes_correcao = []
    
    if tipos_erro.get('Erro 500 (Servidor)', 0) > 100:
        sugestoes_correcao.append("Implementar retry exponencial para erros 500 com delay de 5-30 segundos")
    
    if tipos_erro.get('Timeout/Tempo Limite', 0) > 50:
        sugestoes_correcao.append("Aumentar timeout para 60+ segundos e reduzir concorrência")
    
    if tipos_erro.get('Erro 425 (Too Early)', 0) > 0:
        sugestoes_correcao.append("Implementar delay de 1+ segundo entre requisições")
    
    if tipos_erro.get('Erro de Autenticação', 0) > 0:
        sugestoes_correcao.append("Verificar validade e configuração dos certificados/tokens")
    
    if tipos_erro.get('XMLs Não Baixados', 0) > 10000:
        sugestoes_correcao.append("Continuar execução do extrator funcional para completar downloads")
    
    if cnpjs_problema and cnpjs_problema[0][1] > 100:
        sugestoes_correcao.append(f"Investigar especificamente CNPJ {cnpjs_problema[0][0]} ({cnpjs_problema[0][1]} erros)")
    
    # Ordenar detalhes de erro por relevância
    detalhes_erros.sort(key=lambda x: x['ocorrencias'], reverse=True)
    
    return AnaliseErros(
        tipos_erro=dict(tipos_erro),
        distribuicao_erro_temporal=dict(distribuicao_erro_temporal),
        padroes_erro=padroes_erro,
        sugestoes_correcao=sugestoes_correcao,
        detalhes_erros=detalhes_erros[:50],  # Top 50 erros mais frequentes
        erros_por_cnpj=dict(sorted(erros_por_cnpj.items(), key=lambda x: x[1], reverse=True)[:20]),
        erros_por_faixa_nf=dict(erros_por_faixa_nf)
    )
    """Analisa padrões de erros"""
    cursor = conn.cursor()
    
    tipos_erro = defaultdict(int)
    distribuicao_erro_temporal = defaultdict(int)
    
    # Verificar colunas de erro disponíveis
    cursor.execute("PRAGMA table_info(notas)")
    colunas = [col[1] for col in cursor.fetchall()]
    
    # Tentar diferentes colunas de erro
    consultas_erro = []
    
    if 'erro_xml' in colunas:
        consultas_erro.append("""
            SELECT erro_xml as erro_desc, dEmi, COUNT(*) as count_erros
            FROM {TABLE_NAME} 
            WHERE erro_xml IS NOT NULL AND erro_xml != ''
            GROUP BY erro_xml, dEmi
        """)
    
    if 'erro' in colunas:
        consultas_erro.append("""
            SELECT 'Erro genérico' as erro_desc, dEmi, COUNT(*) as count_erros
            FROM {TABLE_NAME} 
            WHERE erro = 1
            GROUP BY dEmi
        """)
    
    # XML não baixado pode ser considerado erro
    consultas_erro.append("""
        SELECT 'XML não baixado' as erro_desc, dEmi, COUNT(*) as count_erros
        FROM {TABLE_NAME} 
        WHERE xml_baixado = 0 OR xml_baixado IS NULL
        GROUP BY dEmi
        HAVING count_erros > 0
        LIMIT 10
    """)
    
    # Executar consultas de erro
    for consulta in consultas_erro:
        try:
            cursor.execute(consulta.format(TABLE_NAME=TABLE_NAME))
            for erro_desc, data, count in cursor.fetchall():
                # Categorizar tipos de erro
                if erro_desc and isinstance(erro_desc, str):
                    if 'timeout' in erro_desc.lower():
                        tipos_erro['Timeout'] += count
                    elif '500' in erro_desc:
                        tipos_erro['Erro 500 (API)'] += count
                    elif '425' in erro_desc:
                        tipos_erro['Erro 425 (Too Early)'] += count
                    elif 'xml' in erro_desc.lower() and ('vazio' in erro_desc.lower() or 'não baixado' in erro_desc.lower()):
                        tipos_erro['XML não baixado/vazio'] += count
                    elif 'connection' in erro_desc.lower():
                        tipos_erro['Erro de Conexão'] += count
                    else:
                        tipos_erro['Outros'] += count
                
                # Distribuição temporal
                if data:
                    distribuicao_erro_temporal[data] += count
        except Exception as e:
            print(f"Aviso: Erro ao executar consulta de erro: {e}")
            continue
    
    # Se não encontrou erros específicos, contar XMLs pendentes
    if not tipos_erro:
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE xml_baixado = 0 OR xml_baixado IS NULL")
        pendentes = cursor.fetchone()[0]
        if pendentes > 0:
            tipos_erro['XMLs Pendentes'] = pendentes
    
    # Padrões identificados
    padroes_erro = []
    if tipos_erro.get('Erro 500 (API)', 0) > tipos_erro.get('Outros', 0):
        padroes_erro.append("Alta incidência de erros 500 - possível instabilidade da API")
    
    if tipos_erro.get('Timeout', 0) > 100:
        padroes_erro.append("Muitos timeouts - possível lentidão na rede ou API")
    
    if tipos_erro.get('XML não baixado/vazio', 0) > 50:
        padroes_erro.append("XMLs não baixados/vazios frequentes - verificar conectividade")
    
    if tipos_erro.get('XMLs Pendentes', 0) > 50000:
        padroes_erro.append("Grande volume de XMLs pendentes - processamento em andamento")
    
    # Sugestões de correção
    sugestoes_correcao = []
    if tipos_erro.get('Erro 500 (API)', 0) > 100:
        sugestoes_correcao.append("Implementar backoff mais agressivo para erros 500")
    
    if tipos_erro.get('Timeout', 0) > 50:
        sugestoes_correcao.append("Aumentar timeout das requisições ou reduzir concorrência")
    
    if tipos_erro.get('Erro 425 (Too Early)', 0) > 0:
        sugestoes_correcao.append("Implementar delay maior entre requisições")
    
    if tipos_erro.get('XMLs Pendentes', 0) > 10000:
        sugestoes_correcao.append("Continuar execução do extrator para completar downloads pendentes")
    
    return AnaliseErros(
        tipos_erro=dict(tipos_erro),
        distribuicao_erro_temporal=dict(distribuicao_erro_temporal),
        padroes_erro=padroes_erro,
        sugestoes_correcao=sugestoes_correcao
    )

# =============================================================================
# RELATÓRIOS E VISUALIZAÇÕES
# =============================================================================

def exibir_estatisticas_gerais(stats: EstatisticasGerais):
    """Exibe estatísticas gerais formatadas"""
    print(f"\n=== ESTATÍSTICAS GERAIS ===")
    print("=" * 50)
    
    print(f"📋 Total de registros: {formatar_numero(stats.total_registros)}")
    print(f"✅ XMLs baixados: {formatar_numero(stats.xml_baixados)}")
    print(f"⏳ XMLs pendentes: {formatar_numero(stats.xml_pendentes)}")
    print(f"❌ Com erro: {formatar_numero(stats.com_erro)}")
    print(f"✨ Sem erro: {formatar_numero(stats.sem_erro)}")
    print()
    print(f"📈 Progresso: {stats.percentual_concluido:.1f}%")
    print(f"⚠️  Taxa de erro: {stats.percentual_erro:.1f}%")
    print()
    print(f"📅 Período: {stats.data_inicio} até {stats.data_fim}")
    print(f"📆 Total de dias: {stats.total_dias} dias")
    
    # Status adicional
    if stats.percentual_concluido >= 95:
        print(f" STATUS: QUASE CONCLUÍDO ({stats.percentual_concluido:.1f}%)")
    elif stats.percentual_concluido >= 80:
        print(f"⚡ STATUS: FASE FINAL ({stats.percentual_concluido:.1f}%)")
    elif stats.percentual_concluido >= 50:
        print(f"STATUS: EM PROGRESSO ({stats.percentual_concluido:.1f}%)")
    else:
        print(f"� STATUS: INICIANDO ({stats.percentual_concluido:.1f}%)")
    
    print(f"💾 Registros restantes: {formatar_numero(stats.xml_pendentes)}")
    
    if stats.xml_pendentes > 0:
        if stats.xml_pendentes < 10000:
            print("🎯 PRÓXIMA AÇÃO: Finalização rápida possível")
        elif stats.xml_pendentes < 100000:
            print("⚡ PRÓXIMA AÇÃO: Continuar com extrator focado")
        else:
            print("PRÓXIMA AÇÃO: Execução prolongada necessária")

def exibir_analise_detalhada_por_dia(analise: AnaliseDetalhada):
    """Exibe análise detalhada dia a dia"""
    print(f"\n=== ANÁLISE DETALHADA POR DIA ===")
    print("=" * 80)
    
    # Verificar se analise não é None
    if not analise or not hasattr(analise, 'dados_por_dia'):
        print("⚠️ Dados detalhados não disponíveis")
        return
    
    # Resumo geral dos dias
    if analise.dados_por_dia:
        total_dias = len(analise.dados_por_dia)
        print(f"📅 Total de dias com dados: {total_dias}")
        
        # Estatísticas dos dias
        registros_por_dia = [d['total_registros'] for d in analise.dados_por_dia]
        print(f"📊 Média de registros/dia: {sum(registros_por_dia) / len(registros_por_dia):.0f}")
        print(f"📈 Máximo registros/dia: {max(registros_por_dia):,}")
        print(f"📉 Mínimo registros/dia: {min(registros_por_dia):,}")
        
        # Top 10 dias mais ativos
        dias_mais_ativos = sorted(analise.dados_por_dia, key=lambda x: x['total_registros'], reverse=True)[:10]
        dados_ativos = [[d['data'], formatar_numero(d['total_registros']), 
                        formatar_numero(d['xml_baixados']), formatar_numero(d['xml_pendentes']),
                        f"{d['taxa_sucesso']:.1f}%"] for d in dias_mais_ativos]
        
        print(criar_tabela(
            "📈 TOP 10 DIAS MAIS ATIVOS",
            ["Data", "Total", "Baixados", "Pendentes", "Taxa Sucesso"],
            dados_ativos
        ))
    else:
        print("⚠️ Nenhum dado diário encontrado")
    
    # Resumo mensal detalhado
    if hasattr(analise, 'resumo_mensal') and analise.resumo_mensal:
        print(f"\n=== RESUMO MENSAL DETALHADO ===")
        print("=" * 80)
        
        dados_mensais = []
        for mes_ano, resumo in sorted(analise.resumo_mensal.items()):
            dados_mensais.append([
                mes_ano,
                str(resumo['total_dias']),
                formatar_numero(resumo['total_registros']),
                formatar_numero(resumo['total_baixados']),
                formatar_numero(resumo['total_pendentes']),
                f"{resumo['eficiencia_media']:.1f}%",
                resumo['melhor_dia']['data']
            ])
        
        print(criar_tabela(
            "📊 RESUMO POR MÊS",
            ["Mês/Ano", "Dias", "Total", "Baixados", "Pendentes", "Efic%", "Melhor Dia"],
            dados_mensais
        ))
    
    # Dias problemáticos
    if hasattr(analise, 'top_dias_problematicos') and analise.top_dias_problematicos:
        print(f"\n=== DIAS PROBLEMÁTICOS ===")
        print("=" * 60)
        
        dados_problemas = []
        for data, info in analise.top_dias_problematicos:
            dados_problemas.append([
                data,
                str(info['total_erros']),
                f"{info['taxa_erro']:.1f}%",
                str(info['xml_pendentes']),
                f"{info['peso_problema']:.1f}"
            ])
        
        print(criar_tabela(
            "⚠️ DIAS COM MAIS PROBLEMAS",
            ["Data", "Erros", "Taxa Erro", "Pendentes", "Peso"],
            dados_problemas
        ))
    
    # Padrões sazonais
    if hasattr(analise, 'padroes_sazonais') and analise.padroes_sazonais.get('por_dia_semana'):
        print(f"\n=== PADRÕES SAZONAIS ===")
        print("=" * 50)
        
        dados_semana = []
        for dia, media in analise.padroes_sazonais['por_dia_semana'].items():
            if media > 0:  # Só mostrar dias com dados
                dados_semana.append([dia, f"{media:.0f}"])
        
        if dados_semana:
            print(criar_tabela(
                "📅 MÉDIA POR DIA DA SEMANA",
                ["Dia da Semana", "Média Registros"],
                dados_semana
            ))
            
            if analise.padroes_sazonais.get('periodo_pico'):
                print(f"🔥 Período de pico: {analise.padroes_sazonais['periodo_pico']}")
            if analise.padroes_sazonais.get('periodo_baixo'):
                print(f"📉 Período mais baixo: {analise.padroes_sazonais['periodo_baixo']}")

def exibir_estatisticas_temporais(stats: EstatisticasTemporais):
    """Exibe estatísticas temporais"""
    print(f"\n=== ANÁLISE TEMPORAL ===")
    print("=" * 50)
    
    # Top dias com mais registros
    if stats.dias_com_mais_registros:
        dados_dias = [[data, formatar_numero(count)] for data, count in stats.dias_com_mais_registros[:10]]
        print(criar_tabela(
            "🔥 DIAS COM MAIS REGISTROS",
            ["Data", "Quantidade"],
            dados_dias
        ))
    
    # Distribuição por mês
    if stats.distribuicao_por_mes:
        dados_meses = [[mes, formatar_numero(count)] for mes, count in 
                      sorted(stats.distribuicao_por_mes.items(), key=lambda x: x[1], reverse=True)[:10]]
        print(criar_tabela(
            "📊 DISTRIBUIÇÃO POR MÊS",
            ["Mês/Ano", "Quantidade"],
            dados_meses
        ))
    
    # Dias com mais erros
    if stats.dias_com_mais_erros:
        dados_erros = [[data, formatar_numero(count)] for data, count in stats.dias_com_mais_erros]
        print(criar_tabela(
            "❌ DIAS COM MAIS ERROS",
            ["Data", "Erros"],
            dados_erros
        ))
    
    # Análise detalhada
    exibir_analise_detalhada_por_dia(stats.analise_detalhada)

def exibir_qualidade_dados(qualidade: QualidadeDados):
    """Exibe métricas de qualidade dos dados"""
    print(f"\n=== QUALIDADE DOS DADOS ===")
    print("=" * 50)
    
    # Campos obrigatórios vazios
    dados_campos = [[campo, formatar_numero(count)] for campo, count in qualidade.campos_obrigatorios_vazios.items()]
    print(criar_tabela(
        "📝 CAMPOS OBRIGATÓRIOS VAZIOS",
        ["Campo", "Quantidade"],
        dados_campos
    ))
    
    print(f"\nRegistros duplicados: {formatar_numero(qualidade.registros_duplicados)}")
    print(f"⚠️  Registros inconsistentes: {formatar_numero(qualidade.registros_inconsistentes)}")
    print(f"🆔 CNPJs inválidos: {formatar_numero(qualidade.cnpjs_invalidos)}")
    print(f"📅 Datas inválidas: {formatar_numero(qualidade.datas_invalidas)}")
    
    if qualidade.valores_fora_padrao:
        dados_valores = [[tipo, formatar_numero(count)] for tipo, count in qualidade.valores_fora_padrao.items()]
        print(criar_tabela(
            "⚡ VALORES FORA DO PADRÃO",
            ["Tipo", "Quantidade"],
            dados_valores
        ))

def exibir_metricas_performance(metricas: MetricasPerformance):
    """Exibe métricas de performance"""
    print(f"\n=== MÉTRICAS DE PERFORMANCE ===")
    print("=" * 50)
    
    print(f"⚡ Velocidade média: {metricas.velocidade_media_por_dia:.0f} registros/dia")
    
    # Converter para outras unidades mais compreensíveis
    if metricas.velocidade_media_por_dia > 0:
        registros_por_hora = metricas.velocidade_media_por_dia / 24
        registros_por_minuto = registros_por_hora / 60
        registros_por_segundo = registros_por_minuto / 60
        
        print(f"   └── {registros_por_hora:.0f} registros/hora")
        print(f"   └── {registros_por_minuto:.1f} registros/minuto") 
        print(f"   └── {registros_por_segundo:.2f} registros/segundo")
    
    print(f"🎯 Eficiência geral: {metricas.eficiencia_geral:.1f}%")
    print(f"🏁 Projeção de conclusão: {metricas.projecao_conclusao}")
    print(f"⏰ Tempo restante estimado: {metricas.tempo_restante_estimado}")
    
    # Dias mais rápidos
    if metricas.dias_mais_rapidos:
        dados_rapidos = [[data, formatar_numero(count)] for data, count in metricas.dias_mais_rapidos]
        print(criar_tabela(
            "🏆 DIAS MAIS PRODUTIVOS",
            ["Data", "Registros"],
            dados_rapidos
        ))

def exibir_analise_erros(analise: AnaliseErros):
    """Exibe análise de erros detalhada"""
    print(f"\n=== ANÁLISE DE ERROS DETALHADA ===")
    print("=" * 60)
    
    # Tipos de erro
    if analise.tipos_erro:
        dados_tipos = [[tipo, formatar_numero(count)] for tipo, count in 
                      sorted(analise.tipos_erro.items(), key=lambda x: x[1], reverse=True)]
        print(criar_tabela(
            "📊 TIPOS DE ERRO",
            ["Tipo", "Quantidade"],
            dados_tipos
        ))
    
    # Erros por CNPJ (top problemáticos)
    if analise.erros_por_cnpj:
        print(f"\n=== CNPJs COM MAIS ERROS ===")
        dados_cnpj = [[cnpj, formatar_numero(count)] for cnpj, count in 
                     list(analise.erros_por_cnpj.items())[:10]]
        print(criar_tabela(
            "🏢 TOP CNPJs PROBLEMÁTICOS",
            ["CNPJ", "Erros"],
            dados_cnpj
        ))
    
    # Erros por faixa de número de NF
    if analise.erros_por_faixa_nf:
        dados_faixa = [[faixa, formatar_numero(count)] for faixa, count in 
                      sorted(analise.erros_por_faixa_nf.items(), key=lambda x: x[1], reverse=True)]
        print(criar_tabela(
            "📊 ERROS POR FAIXA DE NÚMERO NF",
            ["Faixa", "Erros"],
            dados_faixa
        ))
    
    # Distribuição temporal de erros (top 10 dias)
    if analise.distribuicao_erro_temporal:
        dados_temporal = [[data, formatar_numero(count)] for data, count in 
                         sorted(analise.distribuicao_erro_temporal.items(), key=lambda x: x[1], reverse=True)[:10]]
        print(criar_tabela(
            "📅 DISTRIBUIÇÃO TEMPORAL DE ERROS",
            ["Data", "Erros"],
            dados_temporal
        ))
    
    # Detalhes específicos dos erros mais frequentes
    if analise.detalhes_erros:
        print(f"\n=== DETALHES DOS PRINCIPAIS ERROS ===")
        print("=" * 80)
        
        dados_detalhes = []
        for erro in analise.detalhes_erros[:15]:  # Top 15 erros
            dados_detalhes.append([
                erro['tipo'],
                erro['descricao'][:40] + "..." if len(erro['descricao']) > 40 else erro['descricao'],
                erro['data'],
                erro['cnpj'][:14] if erro['cnpj'] else '',
                str(erro['ocorrencias'])
            ])
        
        print(criar_tabela(
            " DETALHAMENTO DOS ERROS MAIS FREQUENTES",
            ["Tipo", "Descrição", "Data", "CNPJ", "Qtd"],
            dados_detalhes
        ))
    
    # Padrões identificados
    if analise.padroes_erro:
        print(f"\n PADRÕES IDENTIFICADOS:")
        for i, padrao in enumerate(analise.padroes_erro, 1):
            print(f"{i}. {padrao}")
    
    # Sugestões de correção
    if analise.sugestoes_correcao:
        print(f"\n💡 SUGESTÕES DE CORREÇÃO:")
        for i, sugestao in enumerate(analise.sugestoes_correcao, 1):
            print(f"{i}. {sugestao}")
    
    # Resumo executivo de erros
    total_erros = sum(analise.tipos_erro.values())
    if total_erros > 0:
        print(f"\n=== RESUMO EXECUTIVO DE ERROS ===")
        print("=" * 50)
        print(f"📊 Total de erros catalogados: {formatar_numero(total_erros)}")
        
        # Top 3 tipos de erro
        top_3_erros = sorted(analise.tipos_erro.items(), key=lambda x: x[1], reverse=True)[:3]
        print(f"🔥 Top 3 tipos de erro:")
        for i, (tipo, count) in enumerate(top_3_erros, 1):
            percentual = (count / total_erros) * 100
            print(f"   {i}. {tipo}: {formatar_numero(count)} ({percentual:.1f}%)")
        
        # Impacto por período
        if analise.distribuicao_erro_temporal:
            dias_com_erro = len(analise.distribuicao_erro_temporal)
            media_erros_dia = total_erros / dias_com_erro
            print(f"📅 Dias com registro de erros: {dias_com_erro}")
            print(f"📈 Média de erros por dia: {media_erros_dia:.1f}")
        
        # Concentração de erros
        if analise.erros_por_cnpj:
            cnpjs_com_erro = len(analise.erros_por_cnpj)
            print(f"🏢 CNPJs afetados por erros: {cnpjs_com_erro}")
            
            # Analisar concentração
            top_cnpj_erros = list(analise.erros_por_cnpj.values())[:5]
            concentracao_top5 = sum(top_cnpj_erros) / total_erros * 100
            print(f"🎯 Concentração: Top 5 CNPJs representam {concentracao_top5:.1f}% dos erros")

def exibir_insights_avancados(stats_gerais, stats_temporais, qualidade, performance, erros):
    """Exibe insights avançados e correlações"""
    print(f"\n=== INSIGHTS E CORRELAÇÕES AVANÇADAS ===")
    print("=" * 70)
    
    # 1. Análise de tendências
    print(f" ANÁLISE DE TENDÊNCIAS:")
    
    # Verificar se dados temporais estão disponíveis
    if not stats_temporais or not hasattr(stats_temporais, 'analise_detalhada') or not stats_temporais.analise_detalhada:
        print("   ⚠️ Dados temporais não disponíveis para análise de tendências")
        dados_temporais = []
    else:
        dados_temporais = stats_temporais.analise_detalhada.dados_por_dia or []
    
    # Tendência de crescimento/redução
    if len(dados_temporais) >= 7:
        primeiro_periodo = dados_temporais[:7]
        ultimo_periodo = dados_temporais[-7:]
        
        media_inicio = sum(d['total_registros'] for d in primeiro_periodo) / 7
        media_fim = sum(d['total_registros'] for d in ultimo_periodo) / 7
        
        if media_fim > media_inicio * 1.1:
            print(f"   📈 Tendência de CRESCIMENTO: +{((media_fim/media_inicio)-1)*100:.1f}% (últimos 7 dias vs primeiros 7)")
        elif media_fim < media_inicio * 0.9:
            print(f"   📉 Tendência de REDUÇÃO: {((media_fim/media_inicio)-1)*100:.1f}% (últimos 7 dias vs primeiros 7)")
        else:
            print(f"   ➡️ Tendência ESTÁVEL: {((media_fim/media_inicio)-1)*100:.1f}% de variação")
    
    # 2. Correlação entre volume e erros
    if dados_temporais:
        dias_alto_volume = [d for d in dados_temporais if d['total_registros'] > 10000]
        if dias_alto_volume:
            taxa_erro_alto_volume = sum(d['taxa_erro'] for d in dias_alto_volume) / len(dias_alto_volume)
            
            dias_baixo_volume = [d for d in dados_temporais if d['total_registros'] < 5000]
            if dias_baixo_volume:
                taxa_erro_baixo_volume = sum(d['taxa_erro'] for d in dias_baixo_volume) / len(dias_baixo_volume)
                
                print(f"📊 CORRELAÇÃO VOLUME vs ERROS:")
                print(f"   Alto volume (>10k): {taxa_erro_alto_volume:.1f}% taxa de erro")
                print(f"   Baixo volume (<5k): {taxa_erro_baixo_volume:.1f}% taxa de erro")
                
                if taxa_erro_alto_volume > taxa_erro_baixo_volume * 1.5:
                    print(f"   ⚠️ ALERTA: Dias de alto volume têm {taxa_erro_alto_volume/taxa_erro_baixo_volume:.1f}x mais erros!")
                elif taxa_erro_baixo_volume > taxa_erro_alto_volume * 1.5:
                    print(f"   💡 INSIGHT: Sistema performa melhor com alto volume")
    
    # 3. Análise de eficiência por período
    print(f"\n🎯 ANÁLISE DE EFICIÊNCIA:")
    
    eficiencia_geral = stats_gerais.percentual_concluido
    if eficiencia_geral >= 95:
        status_eficiencia = "EXCELENTE 🏆"
    elif eficiencia_geral >= 85:
        status_eficiencia = "BOA 👍"
    elif eficiencia_geral >= 70:
        status_eficiencia = "REGULAR ⚠️"
    else:
        status_eficiencia = "BAIXA 🚨"
    
    print(f"   Status geral: {status_eficiencia} ({eficiencia_geral:.1f}%)")
    
    # Eficiência por mês
    if (stats_temporais and hasattr(stats_temporais, 'analise_detalhada') and 
        stats_temporais.analise_detalhada and 
        hasattr(stats_temporais.analise_detalhada, 'resumo_mensal') and
        stats_temporais.analise_detalhada.resumo_mensal):
        print(f"   Eficiência por mês:")
        for mes, dados in sorted(stats_temporais.analise_detalhada.resumo_mensal.items()):
            print(f"   - {mes}: {dados['eficiencia_media']:.1f}%")
    else:
        print(f"   ⚠️ Dados mensais não disponíveis para análise de eficiência")
    
    # 4. Previsões e projeções
    print(f"\n🔮 PREVISÕES E PROJEÇÕES:")
    
    registros_restantes = stats_gerais.xml_pendentes
    velocidade_atual = performance.velocidade_media_por_dia
    
    if velocidade_atual > 0 and registros_restantes > 0:
        dias_para_conclusao = registros_restantes / velocidade_atual
        
        if dias_para_conclusao <= 7:
            urgencia = "🎯 FINALIZAÇÃO IMINENTE"
        elif dias_para_conclusao <= 30:
            urgencia = "⚡ FINALIZAÇÃO BREVE"
        else:
            urgencia = "⏳ FINALIZAÇÃO LONGA"
        
        print(f"   {urgencia}: {dias_para_conclusao:.1f} dias restantes")
        print(f"   Data estimada: {(datetime.now() + timedelta(days=dias_para_conclusao)).strftime('%d/%m/%Y')}")
        
        # Projeção de recursos necessários
        if velocidade_atual < 5000:
            print(f"   💡 RECOMENDAÇÃO: Aumentar paralelização para acelerar processamento")
        elif velocidade_atual > 20000:
            print(f"   ⚠️ CUIDADO: Velocidade alta pode sobrecarregar API")
    
    # 5. Análise de qualidade crítica
    print(f"\n🔬 ANÁLISE DE QUALIDADE CRÍTICA:")
    
    problemas_criticos = []
    
    if qualidade.registros_duplicados > 0:
        problemas_criticos.append(f"{qualidade.registros_duplicados:,} registros duplicados")
    
    if qualidade.registros_inconsistentes > 1000:
        problemas_criticos.append(f"⚠️ {qualidade.registros_inconsistentes:,} registros inconsistentes")
    
    if qualidade.datas_invalidas > 10000:
        problemas_criticos.append(f"📅 {qualidade.datas_invalidas:,} datas inválidas ({qualidade.datas_invalidas/stats_gerais.total_registros*100:.1f}%)")
    
    total_erros = sum(erros.tipos_erro.values())
    if total_erros > stats_gerais.total_registros * 0.1:
        problemas_criticos.append(f"🚨 {total_erros:,} erros ({total_erros/stats_gerais.total_registros*100:.1f}% do total)")
    
    if problemas_criticos:
        print(f"   PROBLEMAS CRÍTICOS IDENTIFICADOS:")
        for problema in problemas_criticos:
            print(f"   - {problema}")
    else:
        print(f"   ✅ Nenhum problema crítico de qualidade identificado")
    
    # 6. Recomendações estratégicas
    print(f"\n💡 RECOMENDAÇÕES ESTRATÉGICAS:")
    
    recomendacoes = []
    
    # Baseado na fase do projeto
    if eficiencia_geral >= 90:
        recomendacoes.append("Manter estratégia atual e focar na finalização dos registros restantes")
        recomendacoes.append("Preparar pipeline de processamento dos XMLs baixados")
    elif eficiencia_geral >= 70:
        recomendacoes.append("Intensificar esforços de download para acelerar conclusão")
        recomendacoes.append("Investigar e corrigir principais fontes de erro")
    else:
        recomendacoes.append("Revisar estratégia de processamento - baixa eficiência detectada")
        recomendacoes.append("Priorizar correção de problemas de infraestrutura")
    
    # Baseado nos tipos de erro
    if erros.tipos_erro:
        maior_erro = max(erros.tipos_erro.items(), key=lambda x: x[1])
        recomendacoes.append(f"Priorizar correção de '{maior_erro[0]}' ({maior_erro[1]:,} ocorrências)")
    
    # Baseado na qualidade dos dados
    if qualidade.datas_invalidas > stats_gerais.total_registros * 0.05:
        recomendacoes.append("Implementar validação e normalização de datas na entrada")
    
    for i, rec in enumerate(recomendacoes, 1):
        print(f"   {i}. {rec}")

# =============================================================================
# EXPORTAÇÃO E RELATÓRIOS
# =============================================================================

def exportar_relatorio_json(dados: Dict[str, Any], caminho: str = "relatorio_db.json"):
    """Exporta relatório completo em JSON"""
    try:
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n📄 Relatório JSON exportado: {caminho}")
    except Exception as e:
        print(f"\n❌ Erro ao exportar JSON: {e}")

def exportar_relatorio_csv(dados: Dict[str, Any], caminho: str = "relatorio_db.csv"):
    """Exporta estatísticas principais em CSV"""
    try:
        with open(caminho, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Cabeçalho
            writer.writerow(['Métrica', 'Valor', 'Tipo'])
            
            # Estatísticas gerais
            if 'estatisticas_gerais' in dados:
                stats = dados['estatisticas_gerais']
                writer.writerow(['Total Registros', stats['total_registros'], 'Geral'])
                writer.writerow(['XMLs Baixados', stats['xml_baixados'], 'Geral'])
                writer.writerow(['XMLs Pendentes', stats['xml_pendentes'], 'Geral'])
                writer.writerow(['Com Erro', stats['com_erro'], 'Geral'])
                writer.writerow(['Percentual Concluído', f"{stats['percentual_concluido']:.1f}%", 'Geral'])
        
        print(f"\n📊 Relatório CSV exportado: {caminho}")
    except Exception as e:
        print(f"\n❌ Erro ao exportar CSV: {e}")

# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def main():
    """Função principal de análise"""
    inicio = time.time()
    
    exibir_header()
    
    # Verificar banco de dados
    if not Path(DB_PATH).exists():
        print(f"❌ Banco de dados não encontrado: {DB_PATH}")
        return
    
    print(f"🔌 Conectando ao banco: {DB_PATH}")
    
    try:
        # Conectar com otimizações
        conn = conectar_banco_otimizado(DB_PATH)
        
        print(f"✅ Conexão estabelecida com sucesso")
        print(f"🔧 Aplicando otimizações de performance...")
        
        # Executar análises
        print(f"\n Coletando estatísticas gerais...")
        estatisticas_gerais = obter_estatisticas_gerais(conn)
        
        print(f"📈 Analisando dados temporais...")
        estatisticas_temporais = obter_estatisticas_temporais(conn)
        
        print(f" Verificando qualidade dos dados...")
        qualidade_dados = obter_qualidade_dados(conn)
        
        print(f"🚀 Calculando métricas de performance...")
        metricas_performance = obter_metricas_performance(conn)
        
        print(f"🚨 Analisando erros...")
        analise_erros = obter_analise_erros_detalhada(conn)
        
        # Exibir resultados
        exibir_estatisticas_gerais(estatisticas_gerais)
        exibir_estatisticas_temporais(estatisticas_temporais)
        exibir_qualidade_dados(qualidade_dados)
        exibir_metricas_performance(metricas_performance)
        exibir_analise_erros(analise_erros)
        
        # Nova seção de insights avançados
        exibir_insights_avancados(estatisticas_gerais, estatisticas_temporais, 
                                qualidade_dados, metricas_performance, analise_erros)
        
        # Preparar dados para exportação
        dados_completos = {
            'timestamp': datetime.now().isoformat(),
            'banco_dados': DB_PATH,
            'estatisticas_gerais': {
                'total_registros': estatisticas_gerais.total_registros,
                'xml_baixados': estatisticas_gerais.xml_baixados,
                'xml_pendentes': estatisticas_gerais.xml_pendentes,
                'com_erro': estatisticas_gerais.com_erro,
                'sem_erro': estatisticas_gerais.sem_erro,
                'percentual_concluido': estatisticas_gerais.percentual_concluido,
                'percentual_erro': estatisticas_gerais.percentual_erro,
                'data_inicio': estatisticas_gerais.data_inicio,
                'data_fim': estatisticas_gerais.data_fim,
                'total_dias': estatisticas_gerais.total_dias
            },
            'estatisticas_temporais': {
                'distribuicao_por_dia': estatisticas_temporais.distribuicao_por_dia,
                'distribuicao_por_mes': estatisticas_temporais.distribuicao_por_mes,
                'distribuicao_por_ano': estatisticas_temporais.distribuicao_por_ano,
                'dias_com_mais_registros': estatisticas_temporais.dias_com_mais_registros,
                'dias_com_mais_erros': estatisticas_temporais.dias_com_mais_erros,
                'analise_detalhada': {
                    'dados_por_dia': estatisticas_temporais.analise_detalhada.dados_por_dia if estatisticas_temporais.analise_detalhada else [],
                    'resumo_mensal': estatisticas_temporais.analise_detalhada.resumo_mensal if estatisticas_temporais.analise_detalhada else {},
                    'top_dias_problematicos': estatisticas_temporais.analise_detalhada.top_dias_problematicos if estatisticas_temporais.analise_detalhada else [],
                    'padroes_sazonais': estatisticas_temporais.analise_detalhada.padroes_sazonais if estatisticas_temporais.analise_detalhada else {}
                }
            },
            'qualidade_dados': {
                'campos_obrigatorios_vazios': qualidade_dados.campos_obrigatorios_vazios,
                'registros_duplicados': qualidade_dados.registros_duplicados,
                'registros_inconsistentes': qualidade_dados.registros_inconsistentes,
                'cnpjs_invalidos': qualidade_dados.cnpjs_invalidos,
                'datas_invalidas': qualidade_dados.datas_invalidas,
                'valores_fora_padrao': qualidade_dados.valores_fora_padrao
            },
            'metricas_performance': {
                'velocidade_media_por_dia': metricas_performance.velocidade_media_por_dia,
                'dias_mais_rapidos': metricas_performance.dias_mais_rapidos,
                'dias_mais_lentos': metricas_performance.dias_mais_lentos,
                'projecao_conclusao': metricas_performance.projecao_conclusao,
                'tempo_restante_estimado': metricas_performance.tempo_restante_estimado,
                'eficiencia_geral': metricas_performance.eficiencia_geral
            },
            'analise_erros': {
                'tipos_erro': analise_erros.tipos_erro,
                'distribuicao_erro_temporal': analise_erros.distribuicao_erro_temporal,
                'padroes_erro': analise_erros.padroes_erro,
                'sugestoes_correcao': analise_erros.sugestoes_correcao,
                'detalhes_erros': analise_erros.detalhes_erros,
                'erros_por_cnpj': analise_erros.erros_por_cnpj,
                'erros_por_faixa_nf': analise_erros.erros_por_faixa_nf
            }
        }
        
        # Exportar relatórios
        print(f"\n=== EXPORTAÇÃO DE RELATÓRIOS ===")
        print("=" * 50)
        
        exportar_relatorio_json(dados_completos)
        #exportar_relatorio_csv(dados_completos)
        
        # Estatísticas de execução
        fim = time.time()
        duracao = fim - inicio
        
        print(f"\n✅ ANÁLISE CONCLUÍDA")
        print("=" * 50)
        print(f" Tempo de execução do script: {formatar_duracao(duracao)}")
        print(f"🎯 Registros consultados: {formatar_numero(estatisticas_gerais.total_registros)}")
        
        # Calcular taxa realística baseada na velocidade de processamento real
        if metricas_performance.velocidade_media_por_dia > 0:
            # Converter para registros por segundo (assumindo 8 horas de trabalho por dia)
            registros_por_segundo_real = metricas_performance.velocidade_media_por_dia / (8 * 3600)
            print(f"📊 Velocidade real de processamento: {registros_por_segundo_real:.1f} registros/segundo")
        else:
            print(f"📊 Performance do script: {estatisticas_gerais.total_registros/duracao:.0f} consultas/segundo")
        
        # Estimativa realística para conclusão
        if estatisticas_gerais.xml_pendentes > 0 and metricas_performance.velocidade_media_por_dia > 0:
            dias_para_conclusao = estatisticas_gerais.xml_pendentes / metricas_performance.velocidade_media_por_dia
            print(f"🎯 Estimativa realística: {dias_para_conclusao:.1f} dias para conclusão")
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Erro durante análise: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
