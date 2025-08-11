# =============================================================================
# MÓDULO DE UTILITÁRIOS PARA PIPELINE OMIE V3
# =============================================================================
"""
Módulo de utilitários centralizados para o pipeline de extração de dados do Omie.

Este módulo fornece funções essenciais organizadas por categoria:

## CONSULTA E MANIPULAÇÃO DE REGISTROS
- obter_registros_pendentes()
- obter_registros_filtrados()
- buscar_registros_invalidos_para_reprocessar()


## VALIDAÇÃO E NORMALIZAÇÃO DE DADOS
- normalizar_data()
- normalizar_valor_nf()

## MANIPULAÇÃO DE ARQUIVOS E CAMINHOS
- gerar_nome_arquivo_xml()
- gerar_xml_path()
- gerar_xml_path_otimizado() - NOVA: Versão otimizada usando descobrir_todos_xmls()
- mapear_xml_data_chave_caminho() - NOVA: Mapeamento por data de emissão
- gerar_xml_info_dict() - NOVA: Informações XML como dicionário
- criar_mapeamento_completo_com_descobrir_xmls() - NOVA: Mapeamento completo otimizado
- extrair_mes_do_path()
- criar_lockfile()
- listar_arquivos_xml_em()
- listar_arquivos_xml_multithreading()
- descobrir_todos_xmls() - Busca recursiva eficiente

## CONTROLE DE RATE LIMITING
- respeitar_limite_requisicoes()
- respeitar_limite_requisicoes_async()

## OPERAÇÕES DE BANCO DE DADOS
- iniciar_db()
- salvar_nota()
- salvar_varias_notas()
- atualizar_status_xml()
- marcar_como_erro()
- marcar_como_baixado()

## TRANSFORMAÇÃO DE DADOS
- transformar_em_tuple()

Características técnicas:
- Operações batch para máxima performance
- Validação rigorosa de dados com recuperação de erros
- Logging estruturado com contexto específico
- Tratamento de exceções não-propagante
- Suporte a múltiplos formatos de data
- Indexação automática de banco de dados

Padrões implementados (PEP 8):
- Type hints completos
- Docstrings detalhadas no formato Google/NumPy
- Tratamento de erros robusto
- Logging estruturado por contexto
- Validação de pré-condições
- Fallbacks seguros para operações críticas
"""

# =============================================================================
# IMPORTAÇÕES DA BIBLIOTECA PADRÃO
# =============================================================================
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import logging
import os
import re
import sqlite3
import time
import warnings
import configparser
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from time import monotonic, sleep
from typing import Any, Dict, List, Optional, Tuple, Union, Set
from xml.etree import ElementTree as ET
import aiofiles

# =============================================================================
# CONFIGURAÇÃO DO LOGGER
# =============================================================================
logger = logging.getLogger(__name__)

# =============================================================================
# CACHE GLOBAL PARA OTIMIZAÇÃO DE INDEXAÇÃO
# =============================================================================
# Cache global para evitar múltiplas indexações do mesmo diretório
_cache_indexacao_xmls: Dict[str, Dict[str, Tuple[Path, Dict[str, str]]]] = {}
_cache_lock = Lock()
_cache_stats = {
    'hits': 0,
    'misses': 0,
    'directories_indexed': 0
}

# =============================================================================
# CONSTANTES E CONFIGURAÇÕES GLOBAIS
# =============================================================================
# Campos obrigatórios para validação de integridade de registros
CAMPOS_ESSENCIAIS: List[str] = [
    'cChaveNFe', 'nIdNF', 'nIdPedido', 'dEmi', 'dReg', 'nNF', 'caminho_arquivo']

# XPaths para extração de dados de arquivos XML
XPATHS: Dict[str, str] = {
    "dEmi": ".//{*}ide/{*}dEmi",
    "nNF": ".//{*}ide/{*}nNF",
    "cRazao": ".//{*}dest/{*}xNome",
    "cnpj_cpf": ".//{*}dest/{*}CNPJ|.//{*}dest/{*}CPF"
}

# Configurações de otimização SQLite
SQLITE_PRAGMAS: Dict[str, str] = {
    "journal_mode": "WAL",
    "synchronous": "NORMAL",
    "temp_store": "MEMORY",
    "cache_size": "-64000",  # 64MB cache
    "mmap_size": "268435456"  # 256MB mmap
}

# Schema SQL para criação de tabelas
SCHEMA_NOTAS_CREATE = """
    CREATE TABLE IF NOT EXISTS notas (
        -- Campos principais da NFe
        cChaveNFe TEXT PRIMARY KEY,
        nIdNF INTEGER,
        nIdPedido INTEGER,
        
        -- Campos de data/hora
        dCan TEXT,
        dEmi TEXT,
        dInut TEXT,
        dReg TEXT,
        dSaiEnt TEXT,
        hEmi TEXT,
        hSaiEnt TEXT,
        
        -- Campos de identificação
        mod TEXT,
        nNF TEXT,
        serie TEXT,
        tpAmb TEXT,
        tpNF TEXT,
        
        -- Campos do destinatário
        cnpj_cpf TEXT,
        cRazao TEXT,
        
        -- Valores
        vNF REAL,
        
        -- Campos de controle
        anomesdia INTEGER DEFAULT NULL,
        xml_vazio INTEGER DEFAULT 0,
        xml_baixado BOOLEAN DEFAULT 0,
        baixado_novamente BOOLEAN DEFAULT 0,
        status TEXT DEFAULT NULL,
        erro BOOLEAN DEFAULT 0,
        erro_xml TEXT DEFAULT NULL,
        mensagem_erro TEXT DEFAULT NULL,
        caminho_arquivo TEXT DEFAULT NULL,
        
    )
"""

# Schema SQL para inserção de registros (mantido para compatibilidade)
SCHEMA_NOTAS_INSERT = """
    INSERT INTO notas (
        cChaveNFe, nIdNF, nIdPedido, dCan, dEmi, dInut, dReg, dSaiEnt, hEmi, hSaiEnt,
        mod, nNF, serie, tpAmb, tpNF, cnpj_cpf, cRazao, vNF,
        caminho_arquivo, xml_baixado
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

# Para compatibilidade retroativa
SCHEMA_NOTAS = SCHEMA_NOTAS_INSERT  # Mantém referência antiga

# Estado global para rate limiting assíncrono
_ultima_chamada_async = 0.0

def carregar_configuracoes(config_path: str = "configuracao.ini") -> dict:
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {config_path}")

    config = configparser.ConfigParser()
    config.read(config_file)

    # Leitura de todas as seções e conversão de tipos
    return {
        "paths": {
            "resultado_dir": config.get("paths", "resultado_dir", fallback="resultado"),
            "db_name": config.get("paths", "db_name", fallback="omie.db"),
            "log_dir": config.get("paths", "log_dir", fallback="log"),
            "temp_dir": config.get("paths", "temp_dir", fallback="temp"),
        },
        "compactador": {
            "arquivos_por_pasta": config.getint("compactador", "arquivos_por_pasta", fallback=10000),
            "max_workers": config.getint("compactador", "max_workers", fallback=4),
            "batch_size": config.getint("compactador", "batch_size", fallback=1000),
        },
        "ONEDRIVE": {
            "upload_onedrive": config.getboolean("ONEDRIVE", "upload_onedrive", fallback=False),
            "pasta_destino": config.get("ONEDRIVE", "pasta_destino", fallback="Documentos Compartilhados"),
            "upload_max_retries": config.getint("ONEDRIVE", "upload_max_retries", fallback=3),
            "upload_backoff_factor": config.getfloat("ONEDRIVE", "upload_backoff_factor", fallback=1.5),
            "upload_retry_status": config.get("ONEDRIVE", "upload_retry_status", fallback="429,500,502,503,504"),
        },
        "omie_api": {
            "app_key": config.get("omie_api", "app_key"),
            "app_secret": config.get("omie_api", "app_secret"),
            "base_url_nf": config.get("omie_api", "base_url_nf"),
            "base_url_xml": config.get("omie_api", "base_url_xml"),
            "calls_per_second": config.getint("omie_api", "calls_per_second", fallback=4),
        },
        "query_params": {
            "start_date": config.get("query_params", "start_date"),
            "end_date": config.get("query_params", "end_date"),
            "records_per_page": config.getint("query_params", "records_per_page", fallback=200),
        },
        "pipeline": {
            "modo_hibrido_ativo": config.getboolean("pipeline", "modo_hibrido_ativo", fallback=True),
            "min_erros_para_reprocessamento": config.getint("pipeline", "min_erros_para_reprocessamento", fallback=30000),
            "reprocessar_automaticamente": config.getboolean("pipeline", "reprocessar_automaticamente", fallback=True),
            "apenas_normal": config.getboolean("pipeline", "apenas_normal", fallback=False),
        },
        "logging": {
            "log_level": config.get("logging", "log_level", fallback="INFO"),
            "log_file": config.get("logging", "log_file", fallback="extrator.log"),
        }
    }

def log_configuracoes(config: dict, logger) -> None:
    for secao, valores in config.items():
        logger.info(f"[CONFIG] Seção: {secao}")
        for chave, valor in valores.items():
            logger.info(f"    {chave}: {valor}")
# =============================================================================
# CLASSES E DATACLASSES
# =============================================================================
@dataclass
class DatabaseConfig:
    """Configuração personalizada para banco de dados SQLite."""
    
    cache_size: str = "-64000"  # 64MB cache
    mmap_size: str = "268435456"  # 256MB memory-mapped
    journal_mode: str = "WAL"
    synchronous: str = "NORMAL"
    temp_store: str = "MEMORY"
    timeout: int = 30  # Timeout em segundos
    
    def get_pragmas(self) -> Dict[str, str]:
        """
        Retorna dicionário com os PRAGMAs de configuração do banco.
        
        Returns:
            Dict[str, str]: PRAGMAs de configuração
        """
        return {
            "cache_size": self.cache_size,
            "mmap_size": self.mmap_size,
            "journal_mode": self.journal_mode,
            "synchronous": self.synchronous,
            "temp_store": self.temp_store
        }

@dataclass
class ResultadoSalvamento:
    """Resultado estruturado de operações de salvamento."""
    
    sucesso: bool
    chave: Optional[str] = None
    duplicata: bool = False
    motivo: Optional[str] = None
    tempo_execucao: Optional[float] = None

class DatabaseError(Exception):
    """Exceção específica para erros de banco de dados."""
    pass

class SchemaError(DatabaseError):
    """Exceção para erros de schema."""
    pass

class RegistroInvalidoError(ValueError):
    """Exceção para registros com dados inválidos."""
    pass

# =============================================================================
# VALIDAÇÃO E NORMALIZAÇÃO DE DADOS
# =============================================================================

def normalizar_data(data: Optional[str]) -> Optional[str]:
    """
    Normaliza datas para formato brasileiro dd/mm/YYYY.
    Aceita múltiplos formatos de entrada e converte para dd/mm/YYYY.
    
    Formatos aceitos:
    - dd/mm/yyyy, d/m/yyyy, dd-mm-yyyy, d-m-yyyy
    - yyyy-mm-dd, yyyy/mm/dd, yyyymmdd
    - 17jul2025, 2025jul17, 20250717, etc.
    - Aceita separadores /, -, . ou nenhum
    - Retorna None se não conseguir converter
    
    Args:
        data: String contendo data em qualquer formato comum
    Returns:
        String em formato dd/mm/YYYY ou None se inválida
    """
    if not data or not isinstance(data, str):
        return None
    data_limpa = data.strip().replace('.', '/').replace('-', '/').replace(' ', '/').replace('_', '/')
    if not data_limpa:
        return None
    formatos = [
        "%d/%m/%Y", "%d/%m/%y", "%d/%m/%Y", "%d/%m/%y",
        "%Y/%m/%d", "%Y/%d/%m", "%Y/%m/%d", "%Y/%d/%m",
        "%Y%m%d", "%d%m%Y", "%d%b%Y", "%Y%b%d",
        "%d/%b/%Y", "%d/%b/%y", "%Y/%b/%d", "%Y/%b/%d",
    ]
    # Tenta todos os formatos conhecidos
    for fmt in formatos:
        try:
            data_obj = datetime.strptime(data_limpa, fmt)
            return data_obj.strftime("%d/%m/%Y")
        except Exception:
            continue
    # Tenta ISO puro
    try:
        data_obj = datetime.strptime(data.strip(), "%Y-%m-%d")
        return data_obj.strftime("%d/%m/%Y")
    except Exception:
        pass
    # Tenta só números (yyyymmdd)
    if data_limpa.isdigit() and len(data_limpa) == 8:
        try:
            data_obj = datetime.strptime(data_limpa, "%Y%m%d")
            return data_obj.strftime("%d/%m/%Y")
        except Exception:
            pass
    logger.warning(f"[DATA] Formato de data não reconhecido: '{data}'")
    return None

def normalizar_valor_nf(valor: Union[str, float, int, None]) -> float:
    """
    Converte valor para float com tratamento robusto de erros.
    
    Args:
        valor: Valor como string, float, int ou None
        
    Returns:
        Valor convertido para float (0.0 se invalido)
        
    Examples:
        >>> normalizar_valor_nf("1234.56")
        1234.56
        >>> normalizar_valor_nf("invalid")
        0.0
    """
    if valor is None:
        return 0.0
    
    try:
        # Remove espacos e converte virgula para ponto
        if isinstance(valor, str):
            valor_limpo = valor.strip().replace(',', '.')
            return float(valor_limpo)
        
        return float(valor)
    
    except (ValueError, TypeError) as e:
        logger.warning(f"[VALOR] Valor invalido '{valor}': {e}")
        return 0.0
    except Exception as e:
        logger.warning(f"[VALOR] Erro inesperado ao normalizar valor '{valor}': {e}")
        return 0.0

# =============================================================================
# TRANSFORMAÇÃO DE DADOS
# =============================================================================
def transformar_em_tuple(registro: Dict) -> Tuple:
    """
    Transforma dicionario de nota fiscal em tupla para insercoo otimizada no banco.
    
    Realiza validacoo rigorosa, normalizacoo de dados e transformacoo de tipos
    para garantir consistência e integridade dos dados no banco SQLite.
    
    Validacões realizadas:
    - Campos essenciais obrigatorios
    - Tipos de dados corretos
    - Valores numericos validos
    - Formatos de data consistentes
    - Campos de texto sanitizados
    
    Args:
        registro: Dicionario contendo dados da nota fiscal
        
    Returns:
        Tupla com dados normalizados prontos para insercoo
        
    Raises:
        ValueError: Se campos essenciais estiverem ausentes
        
    Examples:
        >>> registro = {'cChaveNFe': '123...', 'dEmi': '17/07/2025', 'nNF': '123'}
        >>> tupla = transformar_em_tuple(registro)
    """
    # Validacoo de campos essenciais
    campos_obrigatorios = ['cChaveNFe', 'dEmi', 'nNF']
    campos_ausentes = [campo for campo in campos_obrigatorios if not registro.get(campo)]
    
    if campos_ausentes:
        erro_msg = f"Campos obrigatorios ausentes: {campos_ausentes}"
        logger.error(f"[TUPLE] {erro_msg} no registro: {registro}")
        raise ValueError(erro_msg)
    
    # Funcões auxiliares para conversoo segura de tipos
    def safe_str(valor) -> Optional[str]:
        """Converte valor para string, tratando None e espacos."""
        if valor is None:
            return None
        valor_str = str(valor).strip()
        return valor_str if valor_str not in ('', '-', 'None') else None
    
    def safe_int(valor) -> Optional[int]:
        """Converte valor para int, tratando erros."""
        if valor is None:
            return None
        try:
            return int(float(valor))  # Converte via float para tratar decimais
        except (ValueError, TypeError):
            logger.warning(f"[TUPLE] Valor inteiro invalido: {valor}")
            return None
    
    def safe_float(valor) -> float:
        """Converte valor para float, retornando 0.0 se invalido."""
        return normalizar_valor_nf(valor)
    
    try:
        # Construcoo da tupla com validacoo e conversoo de tipos
        tupla = (
            safe_str(registro['cChaveNFe']),                    # chave_nfe
            safe_int(registro.get('nIdNF')),                    # id_nf
            safe_int(registro.get('nIdPedido')),                # id_pedido
            safe_str(registro.get('dCan')),                     # data_cancelamento
            normalizar_data(safe_str(registro.get('dEmi'))),    # data_emissao
            safe_str(registro.get('dInut')),                    # data_inutilizacao
            safe_str(registro.get('dReg')),                     # data_registro
            safe_str(registro.get('dSaiEnt')),                  # data_saida_entrada
            safe_str(registro.get('hEmi')),                     # hora_emissao
            safe_str(registro.get('hSaiEnt')),                  # hora_saida_entrada
            safe_str(registro.get('mod')),                      # modelo
            safe_str(registro.get('nNF')),                      # numero_nf
            safe_str(registro.get('serie')),                    # serie
            safe_str(registro.get('tpAmb')),                    # tipo_ambiente
            safe_str(registro.get('tpNF')),                     # tipo_nf
            safe_str(registro.get('cnpj_cpf')),                 # cnpj_cpf
            safe_str(registro.get('cRazao')),                   # razao_social
            safe_float(registro.get('vNF')),                    # valor_nf
            None,                                               # caminho_arquivo
            0                                                   # xml_baixado
        )
        
        # Log de debug para registros processados
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"[TUPLE] Registro transformado: {registro['cChaveNFe']}")
        
        return tupla
        
    except Exception as e:
        logger.error(f"[TUPLE] Erro critico ao transformar registro: {e}")
        logger.error(f"[TUPLE] Registro problematico: {registro}")
        raise

# =============================================================================
# MANIPULAÇÃO DE ARQUIVOS E CAMINHOS
# =============================================================================
def criar_lockfile(pasta: Path) -> Path:
    """
    Cria arquivo de lock para controle de acesso exclusivo à pasta.
    
    Args:
        pasta: Diretorio onde criar o lockfile
        
    Returns:
        Path do lockfile criado
        
    Raises:
        RuntimeError: Se a pasta ja estiver em uso (lockfile existe)
        
    Examples:
        >>> lockfile = criar_lockfile(Path("resultado/2025/07/17"))
    """
    lockfile = pasta / ".processando.lock"
    
    if lockfile.exists():
        raise RuntimeError(f"Pasta em uso por outro processo: {pasta}")
    
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        lockfile.touch()
        logger.debug(f"[LOCK] Lockfile criado: {lockfile}")
        return lockfile
    except Exception as e:
        raise RuntimeError(f"Erro ao criar lockfile em {pasta}: {e}")

async def criar_lockfile_async(pasta: Path) -> Path:
    lockfile = pasta / ".processando.lock"
    if lockfile.exists():
        raise RuntimeError("Lockfile já existe")
    async with aiofiles.open(lockfile, "w") as f:
        await f.write("locked")
    return lockfile

def normalizar_chave_nfe(chave: str) -> str:
    """
    Normaliza chave NFe para exatamente 44 caracteres, removendo caracteres extras.
    
    A chave NFe deve ter exatamente 44 dígitos. Esta função remove qualquer
    caractere extra no final que possa ter sido adicionado incorretamente.
    
    Args:
        chave: Chave NFe potencialmente com caracteres extras
        
    Returns:
        Chave NFe normalizada com exatamente 44 caracteres
        
    Examples:
        >>> normalizar_chave_nfe("35250714200166000196550010000123451234567890")
        '35250714200166000196550010000123451234567890'[:44]
        >>> normalizar_chave_nfe("35250714200166000196550010000123451234567890")
        '35250714200166000196550010000123451234567890'
    """
    if not chave:
        return ''
    
    # Remove espaços e mantém apenas dígitos
    chave_limpa = re.sub(r'\D', '', str(chave).strip())
    
    # Normaliza para exatamente 44 caracteres
    if len(chave_limpa) >= 44:
        return chave_limpa[:44]  # Trunca se for maior
    else:
        # Se for menor, mantém como está (pode ser chave inválida, mas preserva original)
        logger.warning(f"[CHAVE_NFE] Chave com menos de 44 caracteres: {chave_limpa} (len={len(chave_limpa)})")
        return chave_limpa

def gerar_nome_arquivo_xml(chave: str, dEmi: Union[str, datetime], num_nfe: str) -> str:
    """
    Gera nome padronizado para arquivo XML baseado nos dados da NFe.
    
    Padroo: {numero_nf}_{data_emissao_YYYYMMDD}_{chave_nfe_44_chars}.xml
    
    Args:
        chave: Chave unica da NFe (será normalizada para 44 caracteres)
        dEmi: Data de emissoo (string ou datetime)
        num_nfe: Numero da nota fiscal
        
    Returns:
        Nome do arquivo XML no formato padronizado
        
    Raises:
        ValueError: Se dados obrigatorios estiverem ausentes ou invalidos
        
    Examples:
        >>> gerar_nome_arquivo_xml("35250714200166000196550010000123451234567890", "17/07/2025", "123")
        '123_20250717_35250714200166000196550010000123451234567890.xml'
    """
    if not all([chave, dEmi, num_nfe]):
        raise ValueError(f"Dados obrigatorios ausentes: chave={chave}, dEmi={dEmi}, num_nfe={num_nfe}")
    
    try:
        # Conversoo de data para datetime se necessario
        if isinstance(dEmi, str):
            dEmi_normalizada = normalizar_data(dEmi.strip())
            if not dEmi_normalizada:
                raise ValueError(f"Data de emissoo invalida: '{dEmi}'")
            dEmi_dt = datetime.strptime(dEmi_normalizada, "%Y-%m-%d")
        elif isinstance(dEmi, datetime):
            dEmi_dt = dEmi
        else:
            raise ValueError(f"Tipo de dEmi invalido: {type(dEmi)}")
        
        # Sanitizacoo dos componentes do nome
        num_nfe_limpo = str(num_nfe).strip()
        chave_normalizada = normalizar_chave_nfe(chave)  # NOVA: Normaliza chave para 44 chars
        data_formatada = dEmi_dt.strftime('%Y%m%d')
        
        nome_arquivo = f"{num_nfe_limpo}_{data_formatada}_{chave_normalizada}.xml"
        
        # Validacoo do nome gerado
        if len(nome_arquivo) > 255:  # Limite do sistema de arquivos
            logger.warning(f"[ARQUIVO] Nome muito longo: {nome_arquivo[:50]}...")
        
        return nome_arquivo
        
    except Exception as e:
        raise ValueError(f"Erro ao gerar nome do arquivo XML: {e}")

def gerar_pasta_xml_path(cChave: str, dEmi: str, num_nfe: str, base_dir: str = "resultado") -> Tuple[Path, Path]:
    """
    Gera o caminho da pasta onde os XMLs devem ser armazenados e o caminho do arquivo XML.
    
    A pasta é estruturada por ano, mês e dia, seguindo o padrão:
    resultado/YYYY/MM/DD/

    Retorna: Tuple[Path, Path]"""
    
    try:
        # Normaliza a data de emissão
        data_normalizada = normalizar_data(dEmi.strip())
        if not data_normalizada:
            raise ValueError(f"Data de emissão inválida: '{dEmi}'")
        
        data_dt = datetime.strptime(data_normalizada, "%d/%m/%Y")  # Formato brasileiro dd/mm/YYYY
        
        # Gera o nome do arquivo XML
        nome_arquivo = gerar_nome_arquivo_xml(cChave, data_dt, num_nfe)
        
        # Cria a estrutura de pastas
        pasta_dia = Path(base_dir) / data_dt.strftime('%Y') / data_dt.strftime('%m') / data_dt.strftime('%d')
        
        # Retorna a pasta e o caminho completo do arquivo
        return pasta_dia, pasta_dia / nome_arquivo
    except Exception as e:
        raise ValueError(f"Erro ao gerar caminho XML: {e}")

def gerar_xml_path_otimizado(
    chave: str,
    dEmi: str,
    num_nfe: str,
    base_dir: str = "resultado"
) -> Tuple[Path, Path]:
    """ 
    Versão otimizada com cache global para evitar múltiplas indexações.
    
    MELHORIAS V2:
    - Cache global para evitar múltiplas indexações do mesmo diretório
    - Busca otimizada com índice por chave NFe
    - Logging otimizado para reduzir spam
    - Performance melhorada para chamadas paralelas
    
    Args:
        chave: Chave única da NFe (44 caracteres)
        dEmi: Data de emissão (dd/mm/yyyy ou yyyy-mm-dd)
        num_nfe: Número da nota fiscal
        base_dir: Diretório base para armazenamento
        
    Returns:
        Tupla contendo (Path da pasta, Path do arquivo completo)
        
    Raises:
        ValueError: Se dados obrigatórios estiverem ausentes ou inválidos
    """
    global _cache_indexacao_xmls, _cache_lock
    
    # Validação de pré-condições
    if not all([chave, dEmi, num_nfe]):
        raise ValueError(f"Dados obrigatórios ausentes: chave={chave}, dEmi={dEmi}, num_nfe={num_nfe}")
    
    try:
        # Normalização da data
        data_normalizada = normalizar_data(str(dEmi).strip())
        if not data_normalizada:
            raise ValueError(f"Data de emissão inválida: '{dEmi}'")

        data_dt = datetime.strptime(data_normalizada, "%d/%m/%Y")
        
        # Construção da pasta do dia
        pasta_dia = Path(base_dir) / data_dt.strftime('%Y') / data_dt.strftime('%m') / data_dt.strftime('%d')
        
        # Se pasta não existe, retorna caminho para criação
        if not pasta_dia.exists():
            nome_arquivo = gerar_nome_arquivo_xml(chave, data_dt, num_nfe)
            return pasta_dia, pasta_dia / nome_arquivo
        
        # CACHE: Verifica se já indexamos este diretório
        pasta_key = str(pasta_dia.resolve())
        chave_limpa = str(chave).strip()
        
        with _cache_lock:
            if pasta_key not in _cache_indexacao_xmls:
                # Indexa APENAS este diretório (não recursivo) para evitar travamento
                logger.debug(f"[XML_PATH_CACHE] Indexando diretório (não-recursivo): {pasta_dia}")
                
                # Busca direta apenas no diretório especificado (sem recursão)
                todos_xmls = []
                try:
                    # Verifica se há XMLs direto na pasta
                    for entry in os.scandir(pasta_dia):
                        if entry.is_file() and entry.name.lower().endswith('.xml'):
                            todos_xmls.append(Path(entry.path))
                    
                    # Verifica subpastas imediatas (apenas 1 nível) - estrutura típica: dia/pasta_N/
                    for entry in os.scandir(pasta_dia):
                        if entry.is_dir():
                            subdir = Path(entry.path)
                            try:
                                for xml_entry in os.scandir(subdir):
                                    if xml_entry.is_file() and xml_entry.name.lower().endswith('.xml'):
                                        todos_xmls.append(Path(xml_entry.path))
                            except (OSError, PermissionError) as e:
                                logger.debug(f"[XML_PATH_CACHE] Erro ao acessar subpasta {subdir}: {e}")
                                
                except (OSError, PermissionError) as e:
                    logger.warning(f"[XML_PATH_CACHE] Erro ao indexar {pasta_dia}: {e}")
                    todos_xmls = []
                
                # Cria índice local para este diretório
                xml_index_local = {}
                for xml_path in todos_xmls:
                    nome = xml_path.name
                    # Padrão: numero_dataYYYYMMDD_chave44digitos.xml
                    match = re.match(r'^(\d+)_([0-9]{8})_([0-9]{44})\.xml$', nome, re.IGNORECASE)
                    if match:
                        chave_arquivo = match.group(3)
                        xml_index_local[chave_arquivo] = (xml_path, {})
                    else:
                        # Busca por chave no nome (fallback para nomes não padronizados)
                        if len(chave_limpa) == 44 and chave_limpa in nome:
                            xml_index_local[chave_limpa] = (xml_path, {})
                
                _cache_indexacao_xmls[pasta_key] = xml_index_local
                logger.debug(f"[XML_PATH_CACHE] Diretório indexado: {len(xml_index_local)} arquivos")
        
        # Busca no cache
        xml_index_local = _cache_indexacao_xmls[pasta_key]
        
        if chave_limpa in xml_index_local:
            xml_path, _ = xml_index_local[chave_limpa]
            logger.debug(f"[XML_PATH_CACHE] Cache hit: {xml_path.name}")
            return pasta_dia, xml_path
        
        # Se não encontrou no cache, busca alternativa (nome pode ter variado)
        nome_arquivo_esperado = gerar_nome_arquivo_xml(chave, data_dt, num_nfe)
        for chave_cache, (xml_path, _) in xml_index_local.items():
            if xml_path.name == nome_arquivo_esperado:
                logger.debug(f"[XML_PATH_CACHE] Encontrado por nome: {xml_path.name}")
                return pasta_dia, xml_path
        
        # Se não encontrou, retorna caminho para criação
        # Escolhe a melhor localização baseada na estrutura existente
        try:
            subpastas = [item for item in pasta_dia.iterdir() if item.is_dir()]
            if subpastas:
                # Usa a primeira subpasta se existir
                primeira_subpasta = sorted(subpastas, key=lambda x: x.name)[0]
                return primeira_subpasta, primeira_subpasta / nome_arquivo_esperado
        except Exception:
            pass  # Ignora erros de listagem
        
        # Fallback: pasta direta
        return pasta_dia, pasta_dia / nome_arquivo_esperado
        
    except Exception as e:
        raise ValueError(f"Erro ao gerar caminho XML otimizado: {e}")

def mapear_xml_data_chave_caminho(
    registros: List[Tuple[str, str, str]], 
    base_dir: str = "resultado"
) -> Dict[str, Dict[str, str]]:
    """
    Mapeia registros de NFe para dicionário estruturado por data de emissão.
    
    Cria um mapeamento organizado por data de emissão contendo chave NFe e 
    caminho do arquivo XML correspondente, seguindo a estrutura hierárquica 
    do sistema de arquivos.
    
    Estrutura de retorno:
    {
        "2025-07-17": {
            "cChaveNFe": "chave_da_nfe_principal_do_dia",
            "caminho_arquivo": "/caminho/para/arquivo.xml"
        },
        "2025-07-18": {
            "cChaveNFe": "outra_chave_nfe",
            "caminho_arquivo": "/caminho/para/outro_arquivo.xml"
        }
    }
    
    Args:
        registros: Lista de tuplas contendo (chave, dEmi, num_nfe)
        base_dir: Diretório base para busca de arquivos (padrão: "resultado")
        
    Returns:
        Dicionário mapeado por data de emissão normalizada (YYYY-MM-DD)
        
    Raises:
        ValueError: Se dados obrigatórios estiverem ausentes ou inválidos
        
    Examples:
        >>> registros = [("123...", "17/07/2025", "001"), ("456...", "18/07/2025", "002")]
        >>> resultado = mapear_xml_data_chave_caminho(registros)
        >>> # {"2025-07-17": {"cChaveNFe": "123...", "caminho_arquivo": "/.../001_20250717_123....xml"}}
    """
    mapeamento = {}
    registros_processados = 0
    registros_com_erro = 0
    
    logger.info(f"[MAPEAR] Iniciando mapeamento de {len(registros)} registros")
    
    for chave, dEmi, num_nfe in registros:
        try:
            # Validação de dados obrigatórios
            if not all([chave, dEmi, num_nfe]):
                logger.warning(f"[MAPEAR] Registro com dados incompletos ignorado: chave={chave}, dEmi={dEmi}, num_nfe={num_nfe}")
                registros_com_erro += 1
                continue
            
            # Normalização da data de emissão
            data_normalizada = normalizar_data(str(dEmi).strip())
            if not data_normalizada:
                logger.warning(f"[MAPEAR] Data de emissão inválida ignorada: '{dEmi}' para chave {chave}")
                registros_com_erro += 1
                continue
            
            # Geração do caminho do arquivo XML usando versão otimizada
            try:
                pasta_xml, caminho_xml = gerar_xml_path_otimizado(chave, dEmi, num_nfe, base_dir)
                
                # Mapeamento da estrutura de retorno
                mapeamento[data_normalizada] = {
                    "cChaveNFe": str(chave).strip(),
                    "caminho_arquivo": str(caminho_xml)
                }
                
                registros_processados += 1
                
                # Log de debug para registros processados
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"[MAPEAR] Mapeado: {data_normalizada} -> {chave[:20]}... -> {caminho_xml}")
                    
            except ValueError as e:
                logger.warning(f"[MAPEAR] Erro ao gerar caminho XML para chave {chave}: {e}")
                registros_com_erro += 1
                continue
                
        except Exception as e:
            logger.error(f"[MAPEAR] Erro inesperado ao processar registro (chave={chave}): {e}")
            registros_com_erro += 1
            continue
    
    # Log de resumo da operação
    logger.info(f"[MAPEAR] Mapeamento concluído: {registros_processados} sucessos, {registros_com_erro} erros")
    
    if registros_com_erro > 0:
        taxa_erro = (registros_com_erro / len(registros)) * 100
        logger.warning(f"[MAPEAR] Taxa de erro: {taxa_erro:.1f}% ({registros_com_erro}/{len(registros)})")
    
    return mapeamento

def gerar_xml_info_dict(
    chave: str,
    dEmi: str,
    num_nfe: str,
    base_dir: str = "resultado"
) -> Dict[str, str]:
    """
    Versão simplificada que retorna informações de um único XML como dicionário.
    
    Gera dicionário com data de emissão normalizada, chave NFe e caminho do arquivo
    para um único registro de nota fiscal.
    
    Args:
        chave: Chave única da NFe
        dEmi: Data de emissão (dd/mm/yyyy ou yyyy-mm-dd)
        num_nfe: Número da nota fiscal
        base_dir: Diretório base para armazenamento
        
    Returns:
        Dicionário com as chaves: dEmi, cChaveNFe, caminho_arquivo
        
    Raises:
        ValueError: Se dados obrigatórios estiverem ausentes ou inválidos
        
    Examples:
        >>> info = gerar_xml_info_dict("123...", "17/07/2025", "001")
        >>> # {"dEmi": "2025-07-17", "cChaveNFe": "123...", "caminho_arquivo": "/.../arquivo.xml"}
    """
    # Validação de pré-condições
    if not all([chave, dEmi, num_nfe]):
        raise ValueError(f"Dados obrigatórios ausentes: chave={chave}, dEmi={dEmi}, num_nfe={num_nfe}")
    
    try:
        # Normalização da data
        data_normalizada = normalizar_data(str(dEmi).strip())
        if not data_normalizada:
            raise ValueError(f"Data de emissão inválida: '{dEmi}'")
        
        # Geração do caminho do arquivo XML usando versão otimizada
        pasta_xml, caminho_xml = gerar_xml_path_otimizado(chave, dEmi, num_nfe, base_dir)
        
        return {
            "dEmi": data_normalizada,
            "cChaveNFe": str(chave).strip(),
            "caminho_arquivo": str(caminho_xml)
        }
        
    except Exception as e:
        raise ValueError(f"Erro ao gerar informações do XML: {e}")

def extrair_mes_do_path(caminho: Path) -> str:
    """
    Extrai identificador de mês (YYYY-MM) da estrutura hierarquica de pastas.
    
    Esperado: .../ano/mes/dia/arquivo
    
    Args:
        caminho: Path do arquivo na estrutura hierarquica
        
    Returns:
        String no formato 'YYYY-MM' ou 'outros' se noo conseguir extrair
        
    Examples:
        >>> extrair_mes_do_path(Path("resultado/2025/07/17/arquivo.xml"))
        '2025-07'
    """
    try:
        partes = caminho.parts
        
        # Busca padroo ano/mes na estrutura
        for i in range(len(partes) - 2):
            possivel_ano = partes[i]
            possivel_mes = partes[i + 1]
            
            # Validacoo de ano (4 digitos, entre 2000-2099)
            if (possivel_ano.isdigit() and 
                len(possivel_ano) == 4 and 
                2000 <= int(possivel_ano) <= 2099):
                
                # Validacoo de mês (2 digitos, entre 01-12)
                if (possivel_mes.isdigit() and 
                    len(possivel_mes) == 2 and 
                    1 <= int(possivel_mes) <= 12):
                    
                    return f"{possivel_ano}-{possivel_mes}"
        
        logger.warning(f"[PATH] Estrutura ano/mês noo encontrada em: {caminho}")
        return "outros"
        
    except Exception as e:
        logger.warning(f"[PATH] Erro ao extrair mês do caminho {caminho}: {e}")
        return "outros"

def listar_arquivos_xml_em(pasta: Path, incluir_subpastas: bool = True) -> List[Path]:
    """
    Lista todos os arquivos XML em uma pasta e suas subpastas de forma otimizada.
    
    Args:
        pasta: Diretorio para listar arquivos
        incluir_subpastas: Se True, percorre subpastas recursivamente (padrão: True)
        
    Returns:
        Lista ordenada de Paths para arquivos .xml encontrados
        
    Examples:
        >>> xmls = listar_arquivos_xml_em(Path("resultado/2025/07/17"))
        >>> xmls_apenas_pasta = listar_arquivos_xml_em(Path("resultado"), incluir_subpastas=False)
    """
    try:
        if not pasta.exists():
            logger.warning(f"[LISTAR] Pasta nao existe: {pasta}")
            return []
        
        arquivos_xml = []
        
        if incluir_subpastas:
            # Busca recursiva usando rglob para melhor performance
            arquivos_xml = [
                arquivo for arquivo in pasta.rglob("*.xml")
                if arquivo.is_file()
            ]
        else:
            # Busca apenas na pasta atual (comportamento original)
            arquivos_xml = [
                arquivo for arquivo in pasta.iterdir()
                if arquivo.is_file() and arquivo.suffix.lower() == ".xml"
            ]
        
        # Ordenacoo por nome para consistência
        arquivos_xml.sort()
        
        if arquivos_xml:
            tipo_busca = "recursivamente" if incluir_subpastas else "na pasta atual"
            logger.debug(f"[LISTAR] Encontrados {len(arquivos_xml)} arquivos XML {tipo_busca} em {pasta}")
        
        return arquivos_xml
        
    except Exception as e:
        logger.warning(f"[LISTAR] Erro ao listar arquivos XML em {pasta}: {e}")
        return []

def listar_arquivos_xml_multithreading(root: Path, max_workers: int = 2) -> list[Path]:
    """
    Busca recursiva eficiente de arquivos XML usando os.scandir e multithreading.
    Percorre toda a árvore a partir de root, retornando todos os arquivos .xml encontrados.
    """
    arquivos_xml = []
    stack = [root]

    def _scan_dir(pasta: Path):
        encontrados = []
        try:
            for entry in pasta.iterdir():
                if entry.is_dir():
                    encontrados.append(entry)
                elif entry.is_file() and entry.name.lower().endswith('.xml'):
                    arquivos_xml.append(entry)
        except Exception as e:
            logger.warning(f"[LISTAR_XMLS] Erro ao acessar {pasta}: {e}")
        return encontrados

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        while stack:
            # Processa até 10 subpastas por vez para evitar sobrecarga
            batch = stack[:10]
            stack = stack[10:]
            futures = [executor.submit(_scan_dir, p) for p in batch]
            for f in as_completed(futures):
                novas = f.result()
                stack.extend(novas)
    return arquivos_xml

def listar_xmls_os_scandir(root: Path) -> list[Path]:
        # Percorre recursivamente usando os.scandir para máxima performance.
        arquivos = []
        try:
            for entry in os.scandir(root):
                if entry.is_file() and entry.name.lower().endswith('.xml'):
                    arquivos.append(Path(entry.path))
                elif entry.is_dir():
                    arquivos.extend(listar_xmls_os_scandir(Path(entry.path)))
        except Exception as e:
            logger.warning(f"[INDEXAÇÃO] Erro ao acessar {root}: {e}")
        return arquivos

def listar_xmls_hibrido(root: Path, max_workers: int = 8, enable_cache: bool = True) -> list[Path]:
    """
    Lista arquivos XML usando processamento paralelo otimizado com cache global.
    
    MELHORIAS IMPLEMENTADAS V2:
    - Cache global para evitar múltiplas indexações do mesmo diretório
    - Deduplicação inteligente de diretórios 
    - Logging otimizado para reduzir spam
    - Validação robusta de entrada
    - Estatísticas de cache para debugging
    - Controle de nível de log configurável
    
    Args:
        root: Diretório raiz para busca
        max_workers: Número máximo de workers paralelos
        enable_cache: Se habilitado, usa cache global (padrão: True)
        
    Returns:
        list[Path]: Lista de arquivos XML encontrados
        
    Raises:
        ValueError: Se root não for um diretório válido
    """
    global _cache_indexacao_xmls, _cache_lock, _cache_stats
    
    # Validação de entrada
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Diretório inválido: {root}")
    
    # Cache key baseado no path resolvido
    root_resolved = root.resolve()
    cache_key = str(root_resolved)
    
    # Verifica cache primeiro se habilitado
    if enable_cache:
        with _cache_lock:
            if cache_key in _cache_indexacao_xmls:
                _cache_stats['hits'] += 1
                cached_data = _cache_indexacao_xmls[cache_key]
                arquivos_xml = [xml_path for xml_path, _ in cached_data.values()]
                logger.debug(f"[UTILS.LISTAGEM_HIBRIDA.CACHE] Cache hit: {root} - {len(arquivos_xml)} XMLs")
                return arquivos_xml
            else:
                _cache_stats['misses'] += 1
    
    logger.debug(f"[UTILS.LISTAGEM_HIBRIDA] Iniciando indexação: {root}")
    
    def scan_dir(p: Path) -> tuple[list[Path], int, int]:
        """
        Escaneia diretório recursivamente otimizado.
        
        Returns:
            tuple: (arquivos_xml, contador_arquivos, contador_subdirs)
        """
        arquivos = []
        contador_arquivos = 0
        contador_subdirs = 0
        
        try:
            for entry in os.scandir(p):
                if entry.is_file() and entry.name.lower().endswith('.xml'):
                    arquivos.append(Path(entry.path))
                    contador_arquivos += 1
                elif entry.is_dir():
                    # Recursão para subdiretórios
                    arquivos_rec, arquivos_count, subdirs_count = scan_dir(Path(entry.path))
                    arquivos.extend(arquivos_rec)
                    contador_arquivos += arquivos_count
                    contador_subdirs += subdirs_count
            
            contador_subdirs += 1  # Conta o diretório atual
            
            # Log otimizado apenas para diretórios com conteúdo significativo
            if contador_arquivos >= 1000:  # Log apenas para > 1k arquivos
                logger.info(f"[UTILS.LISTAGEM_HIBRIDA.SCAN_DIR] Arquivos encontrados em {p}: {contador_arquivos}")
            elif contador_arquivos >= 100:  # Debug para 100-999 arquivos
                logger.debug(f"[UTILS.LISTAGEM_HIBRIDA.SCAN_DIR] Arquivos encontrados em {p}: {contador_arquivos}")
                
        except (OSError, PermissionError) as e:
            logger.warning(f"[UTILS.LISTAGEM_HIBRIDA.SCAN_DIR] Erro ao acessar {p}: {e}")
        
        return arquivos, contador_arquivos, contador_subdirs

    # Processamento principal
    arquivos_xml = []
    total_arquivos = 0
    total_subdirs = 0
    
    # Processa arquivos XML no root primeiro
    try:
        arquivos_root = [
            Path(entry.path) 
            for entry in os.scandir(root) 
            if entry.is_file() and entry.name.lower().endswith('.xml')
        ]
        arquivos_xml.extend(arquivos_root)
        total_arquivos += len(arquivos_root)
        
        if len(arquivos_root) >= 100:  # Log apenas se significativo
            logger.debug(f"[UTILS.LISTAGEM_HIBRIDA] {len(arquivos_root)} XMLs no diretório root")
            
    except (OSError, PermissionError) as e:
        logger.error(f"[UTILS.LISTAGEM_HIBRIDA] Erro ao acessar root {root}: {e}")
        return []

    # Lista subdiretórios únicos
    subdirs = []
    try:
        subdirs_set = set()  # Evita duplicatas
        for entry in os.scandir(root):
            if entry.is_dir():
                subdir_path = Path(entry.path).resolve()
                if subdir_path not in subdirs_set:
                    subdirs_set.add(subdir_path)
                    subdirs.append(Path(entry.path))
        
        if len(subdirs) > 10:  # Log apenas se muitos subdiretórios
            logger.debug(f"[UTILS.LISTAGEM_HIBRIDA] {len(subdirs)} subdiretórios únicos para processar")
        
    except (OSError, PermissionError) as e:
        logger.error(f"[UTILS.LISTAGEM_HIBRIDA] Erro ao listar subdiretórios: {e}")

    # Processamento paralelo otimizado
    if subdirs:
        effective_workers = min(max_workers, len(subdirs))
        if len(subdirs) > 5:  # Log apenas se processamento paralelo significativo
            logger.debug(f"[UTILS.LISTAGEM_HIBRIDA] Usando {effective_workers} workers para {len(subdirs)} subdiretórios")
        
        with ThreadPoolExecutor(max_workers=effective_workers) as executor:
            # Submit tasks
            future_to_subdir = {
                executor.submit(scan_dir, subdir): subdir 
                for subdir in subdirs
            }
            
            # Collect results
            processed_count = 0
            for future in as_completed(future_to_subdir):
                try:
                    arquivos_rec, contador_arquivos, contador_subdirs = future.result()
                    arquivos_xml.extend(arquivos_rec)
                    total_arquivos += contador_arquivos
                    total_subdirs += contador_subdirs
                    
                    processed_count += 1
                    
                    # Log de progresso reduzido - apenas para processamentos grandes
                    if len(subdirs) >= 20 and (processed_count % max(1, len(subdirs) // 5) == 0 or processed_count == len(subdirs)):
                        progress = (processed_count / len(subdirs)) * 100
                        logger.debug(f"[UTILS.LISTAGEM_HIBRIDA.PROGRESSO] {progress:.1f}% - {processed_count}/{len(subdirs)} processados")
                        
                except Exception as e:
                    subdir = future_to_subdir[future]
                    logger.error(f"[UTILS.LISTAGEM_HIBRIDA] Erro ao processar {subdir}: {e}")

    # Armazena resultado no cache se habilitado
    if enable_cache and arquivos_xml:
        with _cache_lock:
            # Cria índice por chave NFe para o cache
            cache_entry = {}
            for xml_path in arquivos_xml:
                nome = xml_path.name
                # Tenta extrair chave NFe do nome do arquivo (padrão: numero_dataYYYYMMDD_chave44.xml)
                match = re.match(r'^(\d+)_([0-9]{8})_([0-9]{44})\.xml$', nome, re.IGNORECASE)
                if match:
                    chave_nfe = match.group(3)
                    cache_entry[chave_nfe] = (xml_path, {})
            
            _cache_indexacao_xmls[cache_key] = cache_entry
            _cache_stats['directories_indexed'] += 1
            logger.debug(f"[UTILS.LISTAGEM_HIBRIDA.CACHE] Diretório indexado no cache: {len(cache_entry)} arquivos")

    # Log final apenas para resultados significativos
    if total_arquivos >= 100 or total_subdirs >= 10:
        logger.debug(f"[UTILS.LISTAGEM_HIBRIDA] ✓ Concluído: {total_arquivos:,} XMLs em {total_subdirs:,} diretórios")
    elif total_arquivos > 0:
        logger.debug(f"[UTILS.LISTAGEM_HIBRIDA] ✓ {total_arquivos} XMLs encontrados")
    
    return arquivos_xml

def limpar_cache_indexacao_xmls() -> int:
    """
    Limpa o cache global de indexação de XMLs.
    
    Útil quando:
    - Arquivos foram movidos/removidos/adicionados
    - Memória precisa ser liberada
    - Debuging de problemas de cache
    
    Returns:
        int: Número de entradas removidas do cache
    """
    global _cache_indexacao_xmls, _cache_lock, _cache_stats
    
    with _cache_lock:
        entries_removed = len(_cache_indexacao_xmls)
        _cache_indexacao_xmls.clear()
        _cache_stats = {
            'hits': 0,
            'misses': 0,
            'directories_indexed': 0
        }
        logger.info(f"[CACHE] Cache limpo: {entries_removed} entradas removidas")
        return entries_removed

def obter_estatisticas_cache() -> Dict[str, Any]:
    """
    Retorna estatísticas do cache de indexação.
    
    Returns:
        Dict contendo estatísticas de uso do cache
    """
    global _cache_indexacao_xmls, _cache_lock, _cache_stats
    
    with _cache_lock:
        total_files_cached = sum(len(entries) for entries in _cache_indexacao_xmls.values())
        hit_rate = (_cache_stats['hits'] / (_cache_stats['hits'] + _cache_stats['misses'])) * 100 if (_cache_stats['hits'] + _cache_stats['misses']) > 0 else 0
        
        return {
            'directories_cached': len(_cache_indexacao_xmls),
            'total_files_cached': total_files_cached,
            'cache_hits': _cache_stats['hits'],
            'cache_misses': _cache_stats['misses'],
            'hit_rate_percent': hit_rate,
            'directories_indexed': _cache_stats['directories_indexed']
        }
# =============================================================================
# CONTROLE DE RATE LIMITING
# =============================================================================

# Estado global para rate limiting assíncrono
_ultima_chamada_async = 0.0

async def respeitar_limite_requisicoes_async(min_intervalo: float = 0.25) -> None:
    """
    Implementa rate limiting assíncrono para controle de frequência de requisições.
    
    Versão assíncrona que não bloqueia o event loop e mantém estado global
    adequado para múltiplas chamadas.
    
    Args:
        min_intervalo: Intervalo mínimo em segundos entre chamadas (padrão: 0.25s = 4 req/s)
    """
    global _ultima_chamada_async
    
    tempo_atual = monotonic()
    tempo_decorrido = tempo_atual - _ultima_chamada_async
    
    if tempo_decorrido < min_intervalo:
        tempo_espera = min_intervalo - tempo_decorrido
        await asyncio.sleep(tempo_espera)
    
    _ultima_chamada_async = monotonic()

# Variável global para controle de rate limiting
_ultima_chamada_sync: float = 0.0

def respeitar_limite_requisicoes(min_intervalo: float = 0.25, ultima_chamada: Optional[List[float]] = None) -> None:
    """
    Implementa rate limiting para controle de frequência de requisicões.
    
    Garante intervalo minimo entre chamadas para evitar sobrecarga de APIs
    e respeitar limites de requisicões por segundo.
    
    Args:
        min_intervalo: Intervalo minimo em segundos entre chamadas
        ultima_chamada: Lista mutavel para armazenar timestamp da ultima chamada (deprecated)
        
    Examples:
        >>> respeitar_limite_requisicoes(0.25)  # 4 req/s maximo
        >>> respeitar_limite_requisicoes(1.0)   # 1 req/s maximo
    """
    global _ultima_chamada_sync
    
    tempo_atual = monotonic()
    tempo_decorrido = tempo_atual - _ultima_chamada_sync
    
    if tempo_decorrido < min_intervalo:
        tempo_espera = min_intervalo - tempo_decorrido
        sleep(tempo_espera)
    
    _ultima_chamada_sync = monotonic()

# =============================================================================
# 🗃️ OPERAÇÕES DE BANCO DE DADOS
# =============================================================================

@contextmanager
def conexao_otimizada(db_path: str, config: Optional[DatabaseConfig] = None):
    """
    Context manager para conexão SQLite otimizada.
    
    Args:
        db_path: Caminho para o banco de dados
        config: Configuração personalizada (opcional)
        
    Yields:
        sqlite3.Connection: Conexão configurada
        
    Raises:
        DatabaseError: Se não conseguir conectar
    """
    if config is None:
        config = DatabaseConfig()
    
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=config.timeout)
        conn.row_factory = sqlite3.Row
        
        # Aplica configurações de performance
        for pragma, valor in config.get_pragmas().items():
            conn.execute(f"PRAGMA {pragma} = {valor}")
        
        yield conn
        
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise DatabaseError(f"Erro de conexão SQLite: {e}")
    finally:
        if conn:
            conn.close()

def validar_parametros_banco(db_path: str, table_name: str) -> None:
    """
    Valida parâmetros de entrada para operações de banco.
    
    Args:
        db_path: Caminho do banco de dados
        table_name: Nome da tabela
        
    Raises:
        ValueError: Se parâmetros são inválidos
        DatabaseError: Se caminho não é acessível
    """
    if not db_path or not isinstance(db_path, str):
        raise ValueError("db_path deve ser uma string não vazia")
    
    if not table_name or not isinstance(table_name, str):
        raise ValueError("table_name deve ser uma string não vazia")
    
    # Validação de segurança SQL injection
    if not table_name.replace('_', '').isalnum():
        raise ValueError(f"table_name contém caracteres inválidos: {table_name}")
    
    # Verifica se diretório é acessível
    db_dir = Path(db_path).parent
    if not db_dir.exists():
        try:
            db_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            raise DatabaseError(f"Não foi possível criar diretório {db_dir}: {e}")

def criar_schema_base(conn: sqlite3.Connection, table_name: str) -> None:
    """
    Cria schema base da tabela de notas fiscais.
    
    Schema atualizado conforme estrutura real do banco de dados,
    incluindo todos os campos e tipos corretos baseados na análise.
    
    Args:
        conn: Conexão SQLite ativa
        table_name: Nome da tabela a criar
        
    Raises:
        SchemaError: Se não conseguir criar tabela
    """
    schema_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            -- Campos principais da NFe
            cChaveNFe TEXT PRIMARY KEY,
            nIdNF INTEGER,
            nIdPedido INTEGER,

            -- Campos de data/hora
            dCan TEXT,
            dEmi TEXT,
            dInut TEXT,
            dReg TEXT,
            dSaiEnt TEXT,
            hEmi TEXT,
            hSaiEnt TEXT,

            -- Campos de identificação
            mod TEXT,
            nNF TEXT,
            serie TEXT,
            tpAmb TEXT,
            tpNF TEXT,

            -- Campos do destinatário
            cnpj_cpf TEXT,
            cRazao TEXT,

            -- Valores
            vNF REAL,

            -- Campos de controle
            anomesdia INTEGER DEFAULT NULL,
            xml_vazio INTEGER DEFAULT 0,
            xml_baixado BOOLEAN DEFAULT 0,
            baixado_novamente INTEGER DEFAULT 0,
            status TEXT DEFAULT NULL,
            erro BOOLEAN DEFAULT 0,
            erro_xml TEXT DEFAULT NULL,
            mensagem_erro TEXT DEFAULT NULL,
            caminho_arquivo TEXT DEFAULT NULL
        )
    """
    
    try:
        conn.execute(schema_sql)
        logger.info(f"[SCHEMA] Tabela '{table_name}' criada/verificada com sucesso")
    except sqlite3.Error as e:
        raise SchemaError(f"Falha ao criar tabela {table_name}: {e}")

def criar_indices_otimizados(conn: sqlite3.Connection, table_name: str) -> None:
    """
    Cria índices otimizados conforme estrutura real do banco de dados.
    
    Índices baseados na análise da estrutura atual do banco,
    incluindo todos os índices necessários para performance.
    
    Args:
        conn: Conexão SQLite ativa
        table_name: Nome da tabela
        
    Raises:
        SchemaError: Se não conseguir criar índices
    """
    indices = [
    # Índice único para garantir integridade e acelerar busca por chave da nota fiscal
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_chave_nfe ON notas(cChaveNFe)",

    # Índice para filtrar rapidamente notas por data "anomesdia"
    "CREATE INDEX IF NOT EXISTS idx_anomesdia ON notas(anomesdia)",

    # Índice combinado: filtro por data de emissão e status de download
    "CREATE INDEX IF NOT EXISTS idx_anomesdia_baixado ON notas(anomesdia, xml_baixado)",

    # Índice para facilitar buscas por NFe baixada
    "CREATE INDEX IF NOT EXISTS idx_xml_baixado ON notas(xml_baixado)",

    # Índice para busca rápida de erros em processos
    "CREATE INDEX IF NOT EXISTS idx_erro ON notas(erro)",

    # Índice composto para consulta por data de emissão e número da nota
    "CREATE INDEX IF NOT EXISTS idx_dEmi_nNF ON notas(dEmi, nNF)",

    # Índice parcial: pendências não baixadas
    "CREATE INDEX IF NOT EXISTS idx_pendentes ON notas(xml_baixado) WHERE xml_baixado = 0",

    # Índice parcial para arquivos XML vazios
    "CREATE INDEX IF NOT EXISTS idx_xml_vazio ON notas(xml_vazio) WHERE xml_vazio = 1",
]

    
    indices_criados = 0
    for sql_indice in indices:
        try:
            conn.execute(sql_indice)
            indices_criados += 1
        except sqlite3.Error as e:
            # Log warning mas não falha - alguns índices podem já existir
            logger.debug(f"[ÍNDICE] Aviso ao criar índice: {e}")
    
    logger.info(f"[ÍNDICE] {indices_criados}/{len(indices)} comandos de índice executados")

def iniciar_db(
    db_path: str, 
    table_name: str = "notas",
    config: Optional[DatabaseConfig] = None,
    criar_auditoria: bool = True
) -> None:
    """
    Inicializa banco de dados SQLite com schema otimizado para notas fiscais.
    
    Esta função configura um banco SQLite de alta performance para armazenar
    dados de notas fiscais da API Omie, incluindo:
    
    Características implementadas:
    - Configurações SQLite otimizadas (WAL, cache, mmap)
    - Schema robusto com campos de controle e auditoria
    - Índices otimizados para consultas principais
    - Validação rigorosa de parâmetros de entrada
    - Tratamento específico de erros
    - Triggers de auditoria automática (opcional)
    - Context managers para gestão de recursos
    
    Args:
        db_path: Caminho para o arquivo do banco SQLite.
                Diretório será criado se não existir.
        table_name: Nome da tabela principal (padrão: "notas").
                   Deve conter apenas caracteres alfanuméricos e underscore.
        config: Configuração personalizada do SQLite (opcional).
               Se None, usa configuração otimizada padrão.
        criar_auditoria: Se True, cria triggers para auditoria automática.
        
    Returns:
        None - Operação executada por efeito colateral
        
    Raises:
        ValueError: Se parâmetros de entrada são inválidos
        DatabaseError: Se não conseguir conectar ou configurar banco
        SchemaError: Se falhar na criação de tabelas ou índices
        OSError: Se não conseguir criar diretório do banco
        
    Examples:
        >>> # Inicialização básica
        >>> iniciar_db("omie.db")
        
        >>> # Com configuração personalizada
        >>> config = DatabaseConfig(cache_size="-128000")  # 128MB cache
        >>> iniciar_db("dados/omie.db", "notas_2024", config)
        
        >>> # Sem auditoria para melhor performance
        >>> iniciar_db("omie.db", criar_auditoria=False)
        
    Performance:
        - WAL mode: Permite leituras concorrentes durante escritas
        - Cache 64MB: Reduz I/O em consultas frequentes
        - Índices parciais: Otimizam queries específicas
        - Memory temp store: Operações temporárias em RAM
        
    Segurança:
        - Validação contra SQL injection no table_name
        - Timeout de conexão para evitar travamentos
        - Rollback automático em caso de erro
        - Verificação de permissões de diretório
    """
    logger.info(f"[DB] Inicializando banco de dados: {db_path}")
    
    # 1. Validação rigorosa de parâmetros
    validar_parametros_banco(db_path, table_name)
    
    # 2. Configuração padrão se não fornecida
    if config is None:
        config = DatabaseConfig()
    
    inicio = time.time()
    
    try:
        # 3. Conexão otimizada com context manager
        with conexao_otimizada(db_path, config) as conn:
            
            # 4. Criação do schema base
            logger.info(f"[DB] Criando schema para tabela '{table_name}'...")
            criar_schema_base(conn, table_name)
            
            # 5. Criação de índices otimizados
            logger.info(f"[DB] Criando índices otimizados...")
            # criar_indices_otimizados(conn, table_name)

            # 7. Commit final
            conn.commit()
            
        tempo_total = time.time() - inicio
        
        # 8. Verificação final
        with conexao_otimizada(db_path, config) as conn:
            cursor = conn.execute(f"SELECT COUNT(*) FROM sqlite_master WHERE name = ?", (table_name,))
            if cursor.fetchone()[0] == 0:
                raise SchemaError(f"Tabela {table_name} não foi criada corretamente")
        
        # 9. Log de sucesso com métricas
        logger.info(
            f"[DB] Banco inicializado com sucesso. "
            f"Tabela: {table_name}, "
            f"Arquivo: {db_path}, "
            f"Tempo: {tempo_total:.3f}s"
        )
        
    except (ValueError, DatabaseError, SchemaError):
        # Re-propaga exceções conhecidas
        raise
    except Exception as e:
        # Captura e converte exceções inesperadas
        logger.exception(f"[DB] Erro inesperado durante inicialização: {e}")
        raise DatabaseError(f"Falha crítica na inicialização do banco: {e}")

def atualizar_status_xml(
    db_path: str,
    chave: str,
    caminho: Path,
    xml_str: str,
    baixado_novamente: bool = False,
    xml_vazio: int = 0
) -> None:
    if not chave:
        logger.warning("[ERRO] Chave nao fornecida para atualizacao do XML.")
        return

    caminho_arquivo = str(caminho.resolve())

    if not caminho.exists():
        logger.warning(f"[ERRO] Caminho {caminho_arquivo} nao existe no disco.")
        return

    if not caminho_arquivo:
        logger.warning(f"[ERRO] Caminho do XML esta vazio para chave {chave}.")
        return

    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA temp_store=MEMORY")

            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE notas 
                SET xml_baixado = 1, caminho_arquivo = ?, xml_vazio = ? 
                WHERE cChaveNFe = ? AND (? IS NOT NULL)
                """,
                (caminho_arquivo, xml_vazio, chave, caminho_arquivo)
            )

            if cursor.rowcount == 0:
                logger.warning(f"[ALERT] Nenhum registro atualizado para chave: {chave}")
            conn.commit()
    except Exception as e:
        logger.exception(f"[ERRO] Falha ao atualizar status do XML para {chave}: {e}")

def atualizar_campos_registros_pendentes(db_path: str, resultado_dir: str = "resultado") -> None:
    """
    Verifica se os arquivos marcados como xml_baixado = 0 realmente não foram baixados,
    atualizando o status quando encontrados nos diretórios locais.
    
    Funcionalidades implementadas:
    - Processamento paralelo otimizado com concurrent.futures
    - Verificação inteligente baseada na estrutura de nomes dos arquivos
    - Extração de campos essenciais (dEmi, nNF, cChaveNFe) dos nomes dos arquivos
    - Updates em batch para máxima performance
    - Logging estruturado para monitoramento
    
    Estrutura esperada do nome: {nNF}_{dEmi_YYYYMMDD}_{cChaveNFe}.xml
    
    Args:
        db_path: Caminho do banco SQLite.
        resultado_dir: Diretório base onde os XMLs estão salvos.
    """
    import xml.etree.ElementTree as ET
    import concurrent.futures
    from typing import List, Dict, Optional, Tuple
    import re
    from datetime import datetime
    
    logger.info("[ATUALIZACAO_PENDENTES] Iniciando verificação otimizada de arquivos baixados...")
    etapa_inicio = time.time()
    
    # 0. Verificação de otimizações disponíveis
    logger.info("[ATUALIZACAO_PENDENTES.VERIFICACAO_VIEWS_INDICES] Iniciando verificação de otimizações disponíveis no banco...")
    db_otimizacoes = _verificar_views_e_indices_disponiveis(db_path)
    views_disponiveis = sum(1 for k, v in db_otimizacoes.items() if k.startswith('vw_') and v)
    indices_disponiveis = sum(1 for k, v in db_otimizacoes.items() if k.startswith('idx_') and v)
    logger.info(f"[ATUALIZACAO_PENDENTES.VERIFICACAO_VIEWS_INDICES] Otimizações DB: {views_disponiveis} views, {indices_disponiveis} índices específicos")

    # 1. Indexação dos XMLs com extração de dados dos nomes
    logger.info(f"[ATUALIZACAO_PENDENTES.INDEXACAO_XML] Iniciando indexação com extração de dados em: {resultado_dir}")
    t0 = time.time()
    xml_index = _indexar_xmls_por_chave_com_dados(resultado_dir)
    t1 = time.time()
    logger.info(f"[ATUALIZACAO_PENDENTES.INDEXACAO_XML] XMLs indexados em {t1-t0:.2f}s ({len(xml_index)} arquivos)")

    # 2. Busca otimizada dos registros marcados como não baixados usando views e índices
    t2 = time.time()
    try:
        with sqlite3.connect(db_path) as conn:
            # Configurações de performance para SQLite
            for pragma, value in SQLITE_PRAGMAS.items():
                conn.execute(f"PRAGMA {pragma} = {value}")
            
            # Usa view otimizada se disponível, senão usa query com índices
            if db_otimizacoes.get('vw_notas_pendentes', False):
                # Usa view otimizada que já tem filtros e índices aplicados
                logger.debug("[VERIFICAÇÃO] Usando view otimizada 'vw_notas_pendentes'")
                cursor = conn.execute("""
                    SELECT cChaveNFe, nNF, dEmi, anomesdia
                    FROM vw_notas_pendentes
                    ORDER BY anomesdia DESC, cChaveNFe
                """)
            elif db_otimizacoes.get('idx_anomesdia_baixado', False):
                # Usa índice específico disponível
                logger.debug("[VERIFICAÇÃO] Usando índice específico 'idx_anomesdia_baixado'")
                cursor = conn.execute("""
                    SELECT cChaveNFe, nNF, dEmi, anomesdia
                    FROM notas INDEXED BY idx_anomesdia_baixado
                    WHERE xml_baixado = 0
                    ORDER BY anomesdia DESC, cChaveNFe
                """)
            elif db_otimizacoes.get('idx_baixado', False):
                # Usa índice genérico para xml_baixado
                logger.debug("[VERIFICAÇÃO] Usando índice 'idx_baixado'")
                cursor = conn.execute("""
                    SELECT cChaveNFe, nNF, dEmi, 
                           COALESCE(anomesdia, 
                                   CASE WHEN dEmi IS NOT NULL 
                                        THEN CAST(REPLACE(dEmi, '-', '') AS INTEGER)
                                        ELSE NULL END) as anomesdia
                    FROM notas INDEXED BY idx_baixado
                    WHERE xml_baixado = 0
                    ORDER BY anomesdia DESC NULLS LAST, cChaveNFe
                """)
            else:
                # Query padrão sem hints específicos
                logger.debug("[VERIFICAÇÃO] Usando consulta padrão sem índices específicos")
                cursor = conn.execute("""
                    SELECT cChaveNFe, nNF, dEmi, 
                           COALESCE(anomesdia, 
                                   CASE WHEN dEmi IS NOT NULL 
                                        THEN CAST(REPLACE(dEmi, '-', '') AS INTEGER)
                                        ELSE NULL END) as anomesdia
                    FROM notas 
                    WHERE xml_baixado = 0
                    ORDER BY anomesdia DESC NULLS LAST, cChaveNFe
                """)
            
            pendentes = cursor.fetchall()
    except sqlite3.OperationalError as e:
        # Se índice específico não existir, usa consulta padrão otimizada
        logger.warning(f"[ATUALIZACAO_PENDENTES] Índice específico não encontrado, usando consulta padrão: {e}")
        try:
            with sqlite3.connect(db_path) as conn:
                for pragma, value in SQLITE_PRAGMAS.items():
                    conn.execute(f"PRAGMA {pragma} = {value}")
                
                # Query otimizada usando qualquer índice disponível para xml_baixado
                cursor = conn.execute("""
                    SELECT cChaveNFe, nNF, dEmi, 
                           COALESCE(anomesdia, 
                                   CASE WHEN dEmi IS NOT NULL 
                                        THEN CAST(REPLACE(dEmi, '-', '') AS INTEGER)
                                        ELSE NULL END) as anomesdia
                    FROM notas 
                    WHERE 
                    ORDER BY anomesdia DESC NULLS LAST, cChaveNFe
                """)
                pendentes = cursor.fetchall()
        except Exception as inner_e:
            logger.error(f"[ATUALIZACAO_PENDENTES] Erro na consulta fallback: {inner_e}")
            return
    except Exception as e:
        logger.error(f"[ATUALIZACAO_PENDENTES] Erro ao buscar registros: {e}")
        return
        
    t3 = time.time()
    logger.info(f"[ATUALIZACAO_PENDENTES] {len(pendentes)} registros marcados como não baixados carregados em {t3-t2:.2f}s")

    if not pendentes:
        logger.info("[ATUALIZACAO_PENDENTES] Nenhum registro marcado como não baixado encontrado")
        return

    # 3. Processamento paralelo otimizado
    def processar_lote_verificacao(lote_registros: List[Tuple]) -> List[Dict]:
        """Processa um lote de registros verificando se foram realmente baixados"""
        resultados_lote = []
        
        for registro in lote_registros:
            # Adaptação para suportar tanto 3 quanto 4 campos (com anomesdia)
            if len(registro) == 4:
                chave_nfe, nnf_db, demi_db, anomesdia_db = registro
            else:
                chave_nfe, nnf_db, demi_db = registro
                anomesdia_db = None
            
            # Busca arquivo XML correspondente no índice
            dados_xml = xml_index.get(chave_nfe)
            if not dados_xml:
                resultados_lote.append({"chave": chave_nfe, "status": "nao_encontrado"})
                continue
                
            xml_path, dados_extraidos = dados_xml
            
            if not xml_path.exists():
                resultados_lote.append({"chave": chave_nfe, "status": "arquivo_removido"})
                continue
                
            try:
                # Verifica se o arquivo tem tamanho válido
                tamanho_arquivo = xml_path.stat().st_size
                xml_vazio = 1 if tamanho_arquivo < 100 else 0  # Arquivos muito pequenos são considerados vazios
                
                # Prepara dados para atualização
                novos_dados = {
                    'xml_baixado': 1,
                    'caminho_arquivo': str(xml_path.resolve()),
                    'xml_vazio': xml_vazio
                }
                
                # Atualiza campos essenciais se estiverem vazios no banco
                if dados_extraidos:
                    if not demi_db and dados_extraidos.get('dEmi'):
                        novos_dados['dEmi'] = dados_extraidos['dEmi']
                    if not nnf_db and dados_extraidos.get('nNF'):
                        novos_dados['nNF'] = dados_extraidos['nNF']
                
                resultados_lote.append({
                    "chave": chave_nfe, 
                    "status": "encontrado",
                    "novos_dados": novos_dados,
                    "tamanho": tamanho_arquivo
                })
                
            except OSError as e:
                logger.warning(f"[ATUALIZACAO_PENDENTES.PROCESSAR_LOTE] Erro ao acessar arquivo {xml_path}: {e}")
                resultados_lote.append({"chave": chave_nfe, "status": "erro_acesso"})
            except Exception as e:
                logger.warning(f"[ATUALIZACAO_PENDENTES.PROCESSAR_LOTE] Erro inesperado para {chave_nfe}: {e}")
                resultados_lote.append({"chave": chave_nfe, "status": "erro_geral"})
                
        return resultados_lote

    # Divisão em lotes para processamento paralelo
    t4 = time.time()
    TAMANHO_LOTE = max(100000, len(pendentes) // (os.cpu_count() or 4))
    lotes = [pendentes[i:i + TAMANHO_LOTE] for i in range(0, len(pendentes), TAMANHO_LOTE)]

    logger.info(f"[ATUALIZACAO_PENDENTES.PROCESSAR_LOTE] Processando {len(lotes)} lotes de ~{TAMANHO_LOTE} registros...")

    # Processamento paralelo por lotes
    todos_resultados = []
    max_workers = min(os.cpu_count() or 4, len(lotes))
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submete todos os lotes para processamento paralelo
        future_to_lote = {executor.submit(processar_lote_verificacao, lote): i 
                         for i, lote in enumerate(lotes)}
        
        # Coleta resultados conforme completam
        for future in concurrent.futures.as_completed(future_to_lote):
            lote_idx = future_to_lote[future]
            try:
                resultados_lote = future.result()
                todos_resultados.extend(resultados_lote)
                
                # Log de progresso apenas para lotes grandes
                if len(lotes) > 5 and (lote_idx + 1) % max(1, len(lotes) // 10) == 0:
                    progresso = (lote_idx + 1) / len(lotes) * 100
                    logger.info(f"[ATUALIZACAO_PENDENTES.PROCESSAR_LOTE] Progresso: {progresso:.0f}% ({lote_idx + 1}/{len(lotes)} lotes)")
                else:
                    logger.debug(f"[ATUALIZACAO_PENDENTES.PROCESSAR_LOTE] Lote {lote_idx + 1}/{len(lotes)} processado com sucesso")

            except Exception as e:
                logger.warning(f"[ATUALIZACAO_PENDENTES.PROCESSAR_LOTE] Erro ao processar lote {lote_idx}: {e}")
    
    t5 = time.time()
    logger.info(f"[ATUALIZACAO_PENDENTES.PROCESSAR_LOTE] Processamento paralelo concluído em {t5-t4:.2f}s")

    # 4. Atualização em batch otimizada
    t6 = time.time()
    encontrados = 0
    nao_encontrados = 0
    erros = 0
    arquivos_vazios = 0
    
    # Separa resultados por status
    para_atualizar = []
    
    for resultado in todos_resultados:
        status = resultado.get("status")
        if status == "encontrado":
            para_atualizar.append(resultado)
            encontrados += 1
            if resultado.get("novos_dados", {}).get("xml_vazio") == 1:
                arquivos_vazios += 1
        elif status == "nao_encontrado":
            nao_encontrados += 1
        else:
            erros += 1
    
    # Executa updates em batch
    if para_atualizar:
        try:
            with sqlite3.connect(db_path) as conn:
                # Configurações de performance máxima
                for pragma, value in SQLITE_PRAGMAS.items():
                    conn.execute(f"PRAGMA {pragma} = {value}")
                
                # Prepara dados para batch update
                dados_update = []
                for resultado in para_atualizar:
                    novos_dados = resultado["novos_dados"]
                    valores = [
                        novos_dados.get('xml_baixado', 1),
                        novos_dados.get('caminho_arquivo', ''),
                        novos_dados.get('xml_vazio', 0),
                        novos_dados.get('dEmi'),
                        novos_dados.get('nNF'),
                        resultado["chave"]
                    ]
                    dados_update.append(valores)
                
                # Executa batch update otimizado com hint de índice para WHERE clause
                # Usa o índice único da chave primária para máxima eficiência
                query_update = """
                    UPDATE notas 
                    SET xml_baixado = ?, 
                        caminho_arquivo = ?, 
                        xml_vazio = ?,
                        dEmi = COALESCE(?, dEmi),
                        nNF = COALESCE(?, nNF),
                        anomesdia = COALESCE(
                            anomesdia,
                            CASE WHEN COALESCE(?, dEmi) IS NOT NULL 
                                 THEN CAST(REPLACE(COALESCE(?, dEmi), '-', '') AS INTEGER)
                                 ELSE NULL END
                        )
                    WHERE cChaveNFe = ?
                """
                
                # Prepara dados incluindo dEmi para cálculo de anomesdia
                dados_update_otimizados = []
                for resultado in para_atualizar:
                    novos_dados = resultado["novos_dados"]
                    demi_para_anomesdia = novos_dados.get('dEmi')
                    valores = [
                        novos_dados.get('xml_baixado', 1),
                        novos_dados.get('caminho_arquivo', ''),
                        novos_dados.get('xml_vazio', 0),
                        novos_dados.get('dEmi'),
                        novos_dados.get('nNF'),
                        demi_para_anomesdia,  # Para cálculo de anomesdia
                        demi_para_anomesdia,  # Duplicado para o CASE WHEN
                        resultado["chave"]
                    ]
                    dados_update_otimizados.append(valores)
                
                conn.executemany(query_update, dados_update_otimizados)
                conn.commit()
                
                # Verificação pós-atualização usando view se disponível
                try:
                    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='vw_notas_mes_atual'")
                    if cursor.fetchone():
                        # Usa view para verificar se atualizações foram aplicadas corretamente
                        cursor = conn.execute("""
                            SELECT COUNT(*) as atualizados_hoje 
                            FROM vw_notas_mes_atual 
                            WHERE xml_baixado = 1 
                            AND caminho_arquivo IS NOT NULL
                        """)
                        verificacao = cursor.fetchone()
                        if verificacao:
                            logger.debug(f"[ATUALIZACAO_PENDENTES] Verificação pós-update: {verificacao[0]} registros com XML baixado no período atual")
                except Exception as ve:
                    logger.debug(f"[ATUALIZACAO_PENDENTES] Verificação pós-update opcional falhou: {ve}")

                logger.info(f"[ATUALIZACAO_PENDENTES] Batch update executado para {len(dados_update_otimizados)} registros")

        except Exception as e:
            logger.error(f"[ATUALIZACAO_PENDENTES] Erro durante batch update: {e}")
            return
    
    t7 = time.time()
    logger.info(f"[ATUALIZACAO_PENDENTES] Updates em batch concluídos em {t7-t6:.2f}s")

    # 5. Relatório final detalhado com estatísticas usando views se disponíveis
    tempo_total = t7 - etapa_inicio
    taxa_processamento = len(pendentes) / tempo_total if tempo_total > 0 else 0
    
    # Estatísticas adicionais usando views otimizadas
    try:
        with sqlite3.connect(db_path) as conn:
            estatisticas_extras = {}
            
            # Usa view de estatísticas se disponível
            if db_otimizacoes.get('vw_notas_mes_atual', False):
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_mes_atual,
                        SUM(CASE WHEN xml_baixado = 1 THEN 1 ELSE 0 END) as baixados_mes_atual,
                        SUM(CASE WHEN xml_vazio = 1 THEN 1 ELSE 0 END) as vazios_mes_atual
                    FROM vw_notas_mes_atual
                """)
                stats_mes = cursor.fetchone()
                if stats_mes:
                    estatisticas_extras.update({
                        'total_mes_atual': stats_mes[0],
                        'baixados_mes_atual': stats_mes[1],
                        'vazios_mes_atual': stats_mes[2]
                    })
            
            # Estatísticas gerais
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_geral,
                    SUM(CASE WHEN xml_baixado = 1 THEN 1 ELSE 0 END) as baixados_geral,
                    SUM(CASE WHEN xml_vazio = 1 THEN 1 ELSE 0 END) as vazios_geral
                FROM notas
            """)
            stats_geral = cursor.fetchone()
            if stats_geral:
                estatisticas_extras.update({
                    'total_geral': stats_geral[0],
                    'baixados_geral': stats_geral[1],
                    'vazios_geral': stats_geral[2]
                })
                
    except Exception as e:
        logger.debug(f"[ATUALIZACAO_PENDENTES] Erro ao obter estatísticas extras: {e}")
        estatisticas_extras = {}

    logger.info(f"[ATUALIZACAO_PENDENTES] === RESULTADO DA VERIFICAÇÃO ===")
    logger.info(f"[ATUALIZACAO_PENDENTES] Registros verificados: {len(pendentes)}")
    logger.info(f"[ATUALIZACAO_PENDENTES] Arquivos encontrados: {encontrados}")
    logger.info(f"[ATUALIZACAO_PENDENTES] Arquivos não encontrados: {nao_encontrados}")
    logger.info(f"[ATUALIZACAO_PENDENTES] Arquivos vazios detectados: {arquivos_vazios}")
    logger.info(f"[ATUALIZACAO_PENDENTES] Erros: {erros}")
    logger.info(f"[ATUALIZACAO_PENDENTES] Tempo total: {tempo_total:.2f}s")
    logger.info(f"[ATUALIZACAO_PENDENTES] Taxa: {taxa_processamento:.2f} registros/s")
    
    # Relatório de estatísticas extras se disponíveis
    if estatisticas_extras:
        logger.info(f"[ATUALIZACAO_PENDENTES] === ESTATÍSTICAS ADICIONAIS ===")
        if 'total_geral' in estatisticas_extras:
            percentual_baixado = (estatisticas_extras['baixados_geral'] / estatisticas_extras['total_geral'] * 100) if estatisticas_extras['total_geral'] > 0 else 0
            logger.info(f"[ATUALIZACAO_PENDENTES] Total geral: {estatisticas_extras['total_geral']} | Baixados: {estatisticas_extras['baixados_geral']} ({percentual_baixado:.1f}%)")
        if 'total_mes_atual' in estatisticas_extras:
            logger.info(f"[ATUALIZACAO_PENDENTES] Mês atual: {estatisticas_extras['total_mes_atual']} | Baixados: {estatisticas_extras['baixados_mes_atual']}")
    
    logger.info(f"[ATUALIZACAO_PENDENTES] ==========================================")

def _verificar_views_e_indices_disponiveis(db_path: str) -> Dict[str, bool]:
    """
    Verifica quais views e índices estão disponíveis no banco para otimização.
    
    Args:
        db_path: Caminho do banco SQLite
        
    Returns:
        Dict com disponibilidade de views e índices importantes
    """
    views = [
        'vw_notas_mes_atual',
        'vw_notas_pendentes',
        'vw_notas_recentes',
        'vw_notas_vazias',
        'vw_resumo_diario',
    ]
    indices = [
        'idx_anomesdia',
        'idx_anomesdia_baixado',
        'idx_anomesdia_pendentes',
        'idx_baixado',
        'idx_chave',
        'idx_chave_nfe',
        'idx_dEmi_baixado',
        'idx_dEmi_nNF',
        'idx_data_emissao',
        'idx_erro',
        'idx_notas_baixado',
        'idx_notas_chave',
        'idx_notas_data',
        'idx_notas_pendentes',
        'idx_pendentes',
        'idx_xml_baixado',
        'idx_xml_vazio',
    ]
    disponibilidade = {v: False for v in views + indices}

    try:
        with sqlite3.connect(db_path) as conn:
            # Verifica views
            cursor = conn.execute(
                f"SELECT name FROM sqlite_master WHERE type='view' AND name IN ({','.join(['?']*len(views))})",
                views
            )
            views_existentes = {row[0] for row in cursor.fetchall()}

            # Verifica índices
            cursor = conn.execute(
                f"SELECT name FROM sqlite_master WHERE type='index' AND name IN ({','.join(['?']*len(indices))})",
                indices
            )
            indices_existentes = {row[0] for row in cursor.fetchall()}

            # Atualiza disponibilidade
            for v in views:
                disponibilidade[v] = v in views_existentes
            for idx in indices:
                disponibilidade[idx] = idx in indices_existentes

    except Exception as e:
        logger.warning(f"[UTILS.VERIFICACAO_VIEWS_INDICES] Erro ao verificar views/índices: {e}")

    logger.debug(f"[UTILS.VERIFICACAO_VIEWS_INDICES] Disponibilidade: {disponibilidade}")
    return disponibilidade

def _indexar_xmls_por_chave_com_dados(resultado_dir: str) -> Dict[str, Tuple[Path, Dict[str, str]]]:
    """
    Indexa XMLs por chave fiscal extraindo dados essenciais dos nomes dos arquivos.
    
    Padrão esperado: {nNF}_{dEmi_YYYYMMDD}_{cChaveNFe}.xml
    
    Args:
        resultado_dir: Diretório base para busca
        
    Returns:
        Dict[chave_nfe, (Path, dados_extraidos)]
    """
    import re
    import time
    from datetime import datetime
    from pathlib import Path
    from typing import Optional, Tuple, Dict

    # Regex para nome padrão: numero_dataYYYYMMDD_chave44digitos.xml
    PADRAO_NOME = re.compile(r'^(\d+)_([0-9]{8})_([0-9]{44})\.xml$', re.IGNORECASE)

    def processar_arquivo_xml_com_dados(xml_file: Path) -> Optional[Tuple[str, Path, Dict[str, str]]]:
        try:
            nome = xml_file.name
            match = PADRAO_NOME.match(nome)
            if match:
                nnf, data_str, chave_nfe = match.groups()
                try:
                    data_obj = datetime.strptime(data_str, '%Y%m%d')
                    demi_iso = data_obj.strftime('%Y-%m-%d')
                except ValueError:
                    demi_iso = None
                dados_extraidos = {
                    'nNF': nnf,
                    'dEmi': demi_iso,
                    'cChaveNFe': chave_nfe
                }
                return (chave_nfe, xml_file, dados_extraidos)
            else:
                chaves_encontradas = re.findall(r'[0-9]{44}', nome)
                if chaves_encontradas:
                    chave_nfe = chaves_encontradas[0]
                    return (chave_nfe, xml_file, {})
                logger.debug(f"[UTILS.INDEXACAO_XML.PROCESSAR_XML] Padrão não reconhecido: {nome}")
                return None
        except Exception as e:
            logger.warning(f"[UTILS.INDEXACAO_XML.PROCESSAR_XML] Falha ao processar {xml_file}: {e}")
            return None

    logger.info(f"[UTILS.INDEXACAO_XML] Iniciando indexação com extração de dados em: {resultado_dir}")
    inicio = time.time()
    resultado_path = Path(resultado_dir)
    if not resultado_path.exists():
        logger.error(f"[UTILS.INDEXACAO_XML] Diretório não existe: {resultado_dir}")
        return {}

    # Listagem eficiente
    try:
        logger.debug(f"[UTILS.INDEXACAO_XML.LISTAGEM_HIBRIDA] Listando arquivos XML em: {resultado_dir}")
        todos_xmls = listar_xmls_hibrido(resultado_path)
    except Exception as e:
        logger.error(f"[UTILS.INDEXACAO_XML.LISTAGEM_HIBRIDA] Erro ao acessar diretório {resultado_dir}: {e}")
        return {}

    total_arquivos = len(todos_xmls)
    if total_arquivos == 0:
        logger.warning(f"[UTILS.INDEXACAO_XML.LISTAGEM_HIBRIDA] Nenhum arquivo XML encontrado em: {resultado_dir}")
        return {}

    logger.info(f"[UTILS.INDEXACAO_XML.LISTAGEM_HIBRIDA] Encontrados {total_arquivos} arquivos XML para indexar")

    xml_index: Dict[str, Tuple[Path, Dict[str, str]]] = {}
    processados = 0
    duplicatas = 0
    max_workers = min(6, (os.cpu_count() or 1) + 4)

    # Processamento em lotes para reduzir overhead
    BATCH_SIZE = 100000
    batches = [todos_xmls[i:i+BATCH_SIZE] for i in range(0, total_arquivos, BATCH_SIZE)]
    last_log = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for batch in batches:
            futures = {executor.submit(processar_arquivo_xml_com_dados, xml_file): xml_file for xml_file in batch}
            for future in as_completed(futures):
                xml_file = futures[future]
                try:
                    resultado = future.result()
                    if resultado:
                        chave, caminho, dados = resultado
                        if chave in xml_index:
                            duplicatas += 1
                            logger.debug(f"[UTILS.INDEXACAO_XML.PROCESSAR_XML] Chave duplicada encontrada: {caminho} já existe como {xml_index[chave][0]}")
                        else:
                            xml_index[chave] = (caminho, dados)
                    processados += 1
                    # Log adaptativo: a cada 50000 arquivos ou 10s
                    now = time.time()
                    if processados % 50000 == 0 or (now - last_log) > 10:
                        tempo_decorrido = now - inicio
                        taxa = processados / tempo_decorrido if tempo_decorrido > 0 else 0
                        progresso = processados / total_arquivos * 100
                        logger.info(f"[UTILS.INDEXACAO_XML.PROCESSAR_XML] Progresso: {progresso:.1f}% - Taxa: {taxa:.0f} arq/s")
                        last_log = now
                except Exception as e:
                    logger.warning(f"[UTILS.INDEXACAO_XML.PROCESSAR_XML] Erro ao processar {xml_file}: {e}")

    tempo_total = time.time() - inicio
    total_indexado = len(xml_index)
    taxa_media = processados / tempo_total if tempo_total > 0 else 0

    logger.info(f"[UTILS.INDEXACAO_XML] Indexação concluída em {tempo_total:.2f}s:")
    logger.info(f"[UTILS.INDEXACAO_XML] - {total_indexado} chaves únicas indexadas")
    logger.info(f"[UTILS.INDEXACAO_XML] - {processados} arquivos processados")
    logger.info(f"[UTILS.INDEXACAO_XML] - {duplicatas} duplicatas encontradas")
    logger.info(f"[UTILS.INDEXACAO_XML] - Taxa média: {taxa_media:.0f} arquivos/segundo")

    return xml_index

def verificar_schema_banco(db_path: str) -> Dict[str, bool]:
    """
    Verifica se o schema do banco contém todas as colunas necessárias.
    
    Returns:
        Dict[str, bool]: Mapeamento coluna -> existe
    """
    colunas_requeridas = [
        'cChaveNFe', 'nIdNF', 'xml_baixado', 'anomesdia', 
        'caminho_arquivo', 'xml_vazio'
    ]
    
    # Colunas opcionais para compatibilidade
    colunas_opcionais = ['tentativas']
    
    try:
        with conexao_otimizada(db_path) as conn:
            cursor = conn.execute("PRAGMA table_info(notas)")
            colunas_existentes = {row['name'] for row in cursor.fetchall()}
            
            resultado = {}
            
            # Verifica colunas obrigatórias
            for coluna in colunas_requeridas:
                resultado[coluna] = coluna in colunas_existentes
            
            # Verifica colunas opcionais
            for coluna in colunas_opcionais:
                resultado[coluna] = coluna in colunas_existentes
            
            return resultado
            
    except Exception as e:
        logger.error(f"[SCHEMA] Erro ao verificar schema: {e}")
        return {col: False for col in colunas_requeridas + colunas_opcionais}

def marcar_como_erro(
    db_path: str, 
    chave: str, 
    mensagem_erro: str,
    validar_schema: bool = True
) -> bool:
    """
    FUNÇÃO REMOVIDA - Colunas de erro foram removidas do schema.
    
    Esta função foi mantida apenas para compatibilidade retroativa,
    mas não executa nenhuma ação já que as colunas erro, mensagem_erro
    e erro_xml foram removidas do banco de dados.
    
    Args:
        db_path: Caminho do banco SQLite (ignorado)
        chave: Chave NFe (ignorado)
        mensagem_erro: Mensagem de erro (ignorado)
        validar_schema: Validação de schema (ignorado)
        
    Returns:
        bool: Sempre retorna True para manter compatibilidade
    """
    logger.debug(f"[ERRO] Função marcar_como_erro chamada para {chave[:8] if chave else 'N/A'}... - IGNORADA (colunas removidas)")
    return True  # Retorna True para não quebrar código existente

def marcar_como_baixado(
    db_path: str, 
    chave: str, 
    caminho: Path, 
    rebaixado: bool = False,
    xml_vazio: int = 0
) -> None:
    """
    Marca um registro como baixado no banco de dados.
    
    Args:
        db_path: Caminho do banco SQLite
        chave: Chave da NFe
        caminho: Caminho do arquivo XML
        rebaixado: Se foi rebaixado (parâmetro mantido para compatibilidade, mas ignorado)
        xml_vazio: Se o XML esta vazio (0=noo, 1=sim)
    """
    if not chave:
        logger.warning("[ERRO] Chave noo fornecida para marcar como baixado.")
        return
    
    try:
        caminho_arquivo = str(caminho.resolve())
        
        with sqlite3.connect(db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE notas 
                SET xml_baixado = 1, caminho_arquivo = ?, xml_vazio = ? 
                WHERE cChaveNFe = ?
                """,
                (caminho_arquivo, xml_vazio, chave)
            )
            
            if cursor.rowcount == 0:
                logger.warning(f"[ALERT] Nenhum registro encontrado para marcar como baixado: {chave}")
            else:
                logger.info(f"[BAIXADO] Registro marcado como baixado: {chave}")
            
            conn.commit()
            
    except Exception as e:
        logger.exception(f"[ERRO] Falha ao marcar registro como baixado para {chave}: {e}")

def _validar_registro_nota(registro: Dict[str, Union[str, int, float, None]]) -> None:
    """
    Valida campos obrigatórios de um registro de nota fiscal.
    
    Args:
        registro: Dicionário com dados da nota fiscal
        
    Raises:
        RegistroInvalidoError: Se campos obrigatórios estão ausentes ou inválidos
        
    Examples:
        >>> _validar_registro_nota({"cChaveNFe": "123...", "dEmi": "2025-07-20"})
        # OK - Não levanta exceção
        
        >>> _validar_registro_nota({"cChaveNFe": ""})
        # RegistroInvalidoError: Chave fiscal ausente ou vazia
    """
    if not isinstance(registro, dict):
        raise RegistroInvalidoError(f"Registro deve ser um dicionário, recebido: {type(registro)}")
    
    # Validação da chave fiscal
    chave = registro.get('cChaveNFe')
    if not chave or not isinstance(chave, str) or len(chave.strip()) != 44:
        raise RegistroInvalidoError(f"Chave fiscal inválida: '{chave}' (deve ter 44 caracteres)")
    
    # Validação da data de emissão
    dEmi = registro.get('dEmi')
    if not dEmi or (isinstance(dEmi, str) and not dEmi.strip()):
        raise RegistroInvalidoError(f"Data de emissão ausente para chave: {chave}")
    
    # Validação do número da NFe
    nNF = registro.get('nNF')
    if not nNF or (isinstance(nNF, str) and not nNF.strip()):
        raise RegistroInvalidoError(f"Número da NFe ausente para chave: {chave}")

def salvar_varias_notas(
    registros: List[Dict[str, Union[str, int, float, None]]], 
    db_path: str,
    validar_entrada: bool = True,
    log_detalhado: bool = False,
    tamanho_lote: int = 200
) -> Dict[str, Union[int, List[str]]]:
    """
    Versão otimizada para salvamento em lote de múltiplas notas fiscais.
    
    RECOMENDADO: Use esta função para operações com > 10 registros.
    Performance até 100x superior ao salvar_nota() individual.
    
    Otimizações implementadas:
    - Transação única para todo o lote
    - Configuração SQLite aplicada uma vez
    - executemany() para inserção em massa
    - Processamento em lotes configuráveis
    - Validação em paralelo (opcional)
    
    Args:
        registros: Lista de dicionários com dados das notas fiscais
        db_path: Caminho do banco SQLite
        validar_entrada: Se True, valida todos os registros antes de inserir
        log_detalhado: Se True, log detalhado por lote
        tamanho_lote: Número de registros por transação (padrão: 1000)
        
    Returns:
        Dict com estatísticas: {
            'total_processados': int,
            'inseridos': int,
            'duplicatas': int,
            'erros': int,
            'chaves_com_erro': List[str]
        }
        
    Examples:
        >>> registros = [
        ...     {'cChaveNFe': '123...', 'dEmi': '2025-07-20', 'nNF': '1'},
        ...     {'cChaveNFe': '456...', 'dEmi': '2025-07-20', 'nNF': '2'},
        ... ]
        >>> resultado = salvar_varias_notas(registros, "omie.db")
        >>> print(f"Inseridos: {resultado['inseridos']}, Erros: {resultado['erros']}")
    """
    if not registros:
        logger.info("[LOTE] Nenhum registro fornecido para salvamento")
        return {
            'total_processados': 0,
            'inseridos': 0,
            'duplicatas': 0,
            'erros': 0,
            'chaves_com_erro': []
        }
    
    logger.info(f"[LOTE] Iniciando salvamento de {len(registros)} registros em lotes de {tamanho_lote}")
    inicio = time.time()
    
    total_inseridos = 0
    total_duplicatas = 0
    total_erros = 0
    chaves_com_erro = []
    
    # Validação opcional de todos os registros primeiro
    if validar_entrada:
        logger.info("[LOTE] Validando registros de entrada...")
        registros_validos = []
        
        for i, registro in enumerate(registros):
            try:
                _validar_registro_nota(registro)
                registros_validos.append(registro)
            except RegistroInvalidoError as e:
                chave = registro.get('cChaveNFe', f'REGISTRO_{i}')
                chave_str = str(chave) if chave else f'REGISTRO_{i}'
                logger.warning(f"[LOTE] Registro inválido ignorado ({chave_str[:8]}...): {e}")
                chaves_com_erro.append(chave)
                total_erros += 1
        
        registros = registros_validos
        logger.info(f"[LOTE] {len(registros)} registros válidos após validação")
    
    # Processamento em lotes
    try:
        with conexao_otimizada(db_path) as conn:
            # Processa em lotes para otimizar memória
            for i in range(0, len(registros), tamanho_lote):
                lote_atual = registros[i:i + tamanho_lote]
                dados_lote = []
                
                # Transforma registros em tuplas
                for registro in lote_atual:
                    try:
                        dados_lote.append(transformar_em_tuple(registro))
                    except Exception as e:
                        chave = registro.get('cChaveNFe', 'NULL')
                        chave_str = str(chave) if chave else 'NULL'
                        logger.warning(f"[LOTE] Erro na transformação ({chave_str[:8]}...): {e}")
                        chaves_com_erro.append(chave)
                        total_erros += 1
                
                if dados_lote:
                    try:
                        # Insert em lote com INSERT OR IGNORE para tratar duplicatas
                        conn.executemany(
                            SCHEMA_NOTAS_INSERT.replace("INSERT INTO", "INSERT OR IGNORE INTO"),
                            dados_lote
                        )
                        
                        inseridos_lote = conn.total_changes - total_inseridos - total_duplicatas
                        duplicatas_lote = len(dados_lote) - inseridos_lote
                        
                        total_inseridos += inseridos_lote
                        total_duplicatas += duplicatas_lote
                        
                        if log_detalhado:
                            logger.info(f"[LOTE] Lote {i//tamanho_lote + 1}: {inseridos_lote} inseridos, {duplicatas_lote} duplicatas")
                            
                    except sqlite3.Error as e:
                        logger.error(f"[LOTE] Erro no lote {i//tamanho_lote + 1}: {e}")
                        total_erros += len(dados_lote)
            
            conn.commit()
            
    except Exception as e:
        logger.exception(f"[LOTE] Erro crítico durante salvamento em lote: {e}")
        raise DatabaseError(f"Falha no salvamento em lote: {e}")
    
    # Relatório final
    tempo_total = time.time() - inicio
    tempo_total_ms = tempo_total * 1000  # Converter para milissegundos
    taxa_processamento_ms = len(registros) / tempo_total_ms if tempo_total_ms > 0 else 0
    taxa_insercao_ms = total_inseridos / tempo_total_ms if tempo_total_ms > 0 and total_inseridos > 0 else 0
    
    resultado = {
        'total_processados': len(registros),
        'inseridos': total_inseridos,
        'duplicatas': total_duplicatas,
        'erros': total_erros,
        'chaves_com_erro': chaves_com_erro
    }
    
    logger.info(f"[LOTE] Concluído em {tempo_total:.2f}s:")
    logger.info(f"[LOTE] - {total_inseridos} inseridos")
    logger.info(f"[LOTE] - {total_duplicatas} duplicatas")
    logger.info(f"[LOTE] - {total_erros} erros")
    
    # Métricas mais precisas com taxa em registros/ms
    if total_inseridos > 0:
        logger.info(f"[LOTE] - Taxa inserção: {taxa_insercao_ms:.2f} novos registros/ms")
        logger.info(f"[LOTE] - Taxa processamento: {taxa_processamento_ms:.2f} registros verificados/ms")
    else:
        logger.info(f"[LOTE] - Taxa processamento: {taxa_processamento_ms:.2f} registros verificados/ms (todos duplicatas)")
        logger.info(f"[LOTE] - Nota: Taxa alta indica verificação rápida de duplicatas, não inserções")
    
    return resultado

# =============================================================================
# 📅 FUNÇÕES DE INDEXAÇÃO TEMPORAL
# =============================================================================

def garantir_coluna_anomesdia(db_path: str = "omie.db", table_name: str = "notas") -> bool:
    """
    Garante que a coluna anomesdia existe na tabela de notas.
    
    Esta função verifica se a coluna anomesdia (INTEGER) existe e a cria se necessário.
    É executada na inicialização do pipeline para garantir compatibilidade.
    
    Args:
        db_path: Caminho para o banco SQLite
        table_name: Nome da tabela (padrão: "notas")
        
    Returns:
        True se coluna existe ou foi criada com sucesso, False caso contrário
        
    Examples:
        >>> garantir_coluna_anomesdia("omie.db")
        True  # coluna já existia ou foi criada
    """
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Verifica se a coluna anomesdia já existe
            cursor.execute(f"PRAGMA table_info({table_name})")
            colunas = [coluna[1] for coluna in cursor.fetchall()]
            
            if 'anomesdia' in colunas:
                logger.debug("[ANOMESDIA] Coluna anomesdia já existe")
                return True
            
            # Adiciona a coluna anomesdia
            logger.info("[ANOMESDIA] Adicionando coluna anomesdia à tabela...")
            cursor.execute(f"""
                ALTER TABLE {table_name} 
                ADD COLUMN anomesdia INTEGER DEFAULT NULL
            """)
            
            conn.commit()
            logger.info("[ANOMESDIA] ✓ Coluna anomesdia criada com sucesso")
            return True
            
    except sqlite3.Error as e:
        logger.error(f"[ANOMESDIA] Erro de banco ao criar coluna: {e}")
        return False
    except Exception as e:
        logger.error(f"[ANOMESDIA] Erro inesperado ao criar coluna: {e}")
        return False

def atualizar_anomesdia(db_path: str = "omie.db", table_name: str = "notas") -> int:
    """
    Atualiza o campo anomesdia (YYYYMMDD) baseado no campo dEmi.
    
    Esta função converte datas no formato brasileiro (dd/mm/yyyy) ou ISO (yyyy-mm-dd)
    para o formato inteiro YYYYMMDD, facilitando filtros e consultas temporais.
    
    Args:
        db_path: Caminho para o banco SQLite
        table_name: Nome da tabela (padrão: "notas")
        
    Returns:
        Número de registros atualizados
        
    Examples:
        >>> atualizar_anomesdia("omie.db")
        150  # registros atualizados
        
        # Consultas facilitadas:
        # SELECT * FROM notas WHERE anomesdia >= 20250101 AND anomesdia <= 20250131
        # SELECT * FROM notas WHERE anomesdia = 20250721
    """
    try:
        with sqlite3.connect(db_path) as conn:
            # Otimizações de performance
            for pragma, valor in SQLITE_PRAGMAS.items():
                conn.execute(f"PRAGMA {pragma}={valor}")
            
            cursor = conn.cursor()
            
            # Busca registros com dEmi válido mas sem anomesdia
            cursor.execute(f"""
                SELECT cChaveNFe, dEmi 
                FROM {table_name} 
                WHERE dEmi IS NOT NULL 
                AND dEmi != '' 
                AND dEmi != '-'
            """)
            
            registros = cursor.fetchall()
            if not registros:
                logger.info("[ANOMESDIA] Nenhum registro para atualizar")
                return 0
            
            logger.info(f"[ANOMESDIA] Processando {len(registros)} registros...")
            
            atualizacoes = []
            erros = 0
            
            for chave, dEmi in registros:
                try:
                    # Normaliza a data para formato ISO
                    data_normalizada = normalizar_data(dEmi)
                    if data_normalizada:
                        # Converte para YYYYMMDD
                        dia, mes, ano = data_normalizada.split('/')
                        anomesdia = int(f"{ano}{mes}{dia}")
                        atualizacoes.append((anomesdia, chave))
                    else:
                        logger.warning(f"[ANOMESDIA] Data inválida para chave {chave}: {dEmi}")
                        erros += 1
                        
                except Exception as e:
                    logger.warning(f"[ANOMESDIA] Erro ao processar {chave}: {e}")
                    erros += 1
            
            # Executa atualizações em lote
            if atualizacoes:
                cursor.executemany(f"""
                    UPDATE {table_name} 
                    SET anomesdia = ? 
                    WHERE cChaveNFe = ?
                """, atualizacoes)
                
                conn.commit()
                atualizados = len(atualizacoes)
                
                logger.info(f"[ANOMESDIA] ✓ {atualizados} registros atualizados")
                if erros > 0:
                    logger.warning(f"[ANOMESDIA] ⚠ {erros} registros com erro")
                
                return atualizados
            else:
                logger.info("[ANOMESDIA] Nenhuma atualização válida encontrada")
                return 0
                
    except sqlite3.Error as e:
        logger.error(f"[ANOMESDIA] Erro de banco: {e}")
        return 0
    except Exception as e:
        logger.error(f"[ANOMESDIA] Erro inesperado: {e}")
        return 0

def criar_views_otimizadas(db_path: str = "omie.db", table_name: str = "notas") -> None:
    """
    Cria views otimizadas para facilitar consultas comuns na tabela de notas fiscais.
    """
    import sqlite3
    import logging

    logger = logging.getLogger("criar_views_otimizadas")

    views = {
        "vw_notas_pendentes": f"""
            CREATE VIEW IF NOT EXISTS vw_notas_pendentes AS
            SELECT 
                cChaveNFe, nNF, dEmi, nIdNF, cRazao, vNF, anomesdia, caminho_arquivo,
                CASE 
                    WHEN anomesdia IS NOT NULL THEN
                        SUBSTR(CAST(anomesdia AS TEXT), 1, 4) || '-' ||
                        SUBSTR(CAST(anomesdia AS TEXT), 5, 2) || '-' ||
                        SUBSTR(CAST(anomesdia AS TEXT), 7, 2)
                    ELSE dEmi
                END as data_formatada
            FROM {table_name}
            WHERE xml_baixado = 0
            ORDER BY anomesdia DESC, nNF
        """,
        "vw_notas_vazias": f"""
            CREATE VIEW IF NOT EXISTS vw_notas_vazias AS
            SELECT 
                cChaveNFe, nNF, dEmi, nIdNF, cRazao, anomesdia, caminho_arquivo,
                CASE 
                    WHEN xml_vazio = 1 THEN 'XML Vazio'
                    WHEN xml_baixado = 0 THEN 'nao Baixado'
                    ELSE 'Processando'
                END as tipo_problema
            FROM {table_name}
            WHERE xml_vazio = 1
            ORDER BY anomesdia DESC
        """,
        "vw_notas_mes_atual": f"""
            CREATE VIEW IF NOT EXISTS vw_notas_mes_atual AS
            SELECT 
                COUNT(*) as total_notas,
                SUM(CASE WHEN xml_baixado = 1 THEN 1 ELSE 0 END) as baixadas,
                SUM(CASE WHEN xml_vazio = 1 THEN 1 ELSE 0 END) as vazias,
                SUM(CASE WHEN xml_baixado = 0 THEN 1 ELSE 0 END) as pendentes,
                SUM(vNF) as valor_total,
                MIN(anomesdia) as primeira_nota,
                MAX(anomesdia) as ultima_nota
            FROM {table_name}
            WHERE anomesdia >= CAST(strftime('%Y%m', 'now') || '01' AS INTEGER)
        """,
        "vw_resumo_diario": f"""
            CREATE VIEW IF NOT EXISTS vw_resumo_diario AS
            SELECT 
                anomesdia,
                CASE 
                    WHEN anomesdia IS NOT NULL THEN
                        SUBSTR(CAST(anomesdia AS TEXT), 7, 2) || '/' ||
                        SUBSTR(CAST(anomesdia AS TEXT), 5, 2) || '/' ||
                        SUBSTR(CAST(anomesdia AS TEXT), 1, 4)
                    ELSE 'Data Inválida'
                END as data_br,
                COUNT(*) as total_notas,
                SUM(CASE WHEN xml_baixado = 1 THEN 1 ELSE 0 END) as baixadas,
                SUM(CASE WHEN xml_vazio = 1 THEN 1 ELSE 0 END) as vazias,
                SUM(vNF) as valor_total,
                ROUND(AVG(vNF), 2) as valor_medio,
                MIN(nNF) as menor_numero,
                MAX(nNF) as maior_numero
            FROM {table_name}
            WHERE anomesdia IS NOT NULL
            GROUP BY anomesdia
            ORDER BY anomesdia DESC
        """,
        "vw_notas_recentes": f"""
            CREATE VIEW IF NOT EXISTS vw_notas_recentes AS
            SELECT 
                cChaveNFe, nIdNF, nNF, dEmi, cRazao, vNF, xml_baixado, xml_vazio, anomesdia,
                CASE 
                    WHEN xml_baixado = 1 AND xml_vazio = 0 THEN 'Baixado'
                    WHEN xml_baixado = 1 AND xml_vazio = 1 THEN 'Vazio'
                    ELSE 'Pendente'
                END as status_visual
            FROM {table_name}
            WHERE anomesdia >= CAST(strftime('%Y%m%d', 'now', '-7 days') AS INTEGER)
            ORDER BY anomesdia DESC, nNF DESC
        """
    }

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            views_criadas = 0
            for nome, sql in views.items():
                try:
                    cursor.execute(f'DROP VIEW IF EXISTS {nome}')
                    cursor.execute(sql)
                    views_criadas += 1
                except sqlite3.Error as e:
                    logger.warning(f"[VIEW] Erro ao criar {nome}: {e}")
            conn.commit()
            logger.info(f"[VIEWS] ✓ {views_criadas}/{len(views)} views criadas com sucesso")
    except sqlite3.Error as e:
        logger.error(f"[VIEWS] Erro de banco: {e}")
    except Exception as e:
        logger.error(f"[VIEWS] Erro inesperado: {e}")

# =============================================================================
# 📊 FUNÇÕES DE MÉTRICAS E RELATÓRIOS
# =============================================================================

def formatar_numero(n: int) -> str:
    """
    Formata número com separadores para melhor legibilidade.
    
    Args:
        n: Número inteiro para formatação
        
    Returns:
        String formatada com separadores (ex: "1.234.567")
        
    Examples:
        >>> formatar_numero(1234567)
        '1.234.567'
    """
    return f"{n:,}".replace(",", ".")

def obter_metricas_completas_banco(db_path: str = "omie.db") -> Dict[str, Any]:
    """
    Obtém métricas completas e detalhadas do banco de dados.
    
    Baseado no dashboard_db.py, esta função coleta todas as métricas
    relevantes do banco de dados em uma única operação otimizada.
    
    Args:
        db_path: Caminho para o banco de dados SQLite
        
    Returns:
        Dicionário contendo todas as métricas do banco
        
    Raises:
        sqlite3.Error: Em caso de erro de acesso ao banco
        
    Examples:
        >>> metricas = obter_metricas_completas_banco()
        >>> print(f"Total: {metricas['total']}")
    """
    if not Path(db_path).exists():
        logger.error(f"[MÉTRICAS] Banco não encontrado: {db_path}")
        return {}
    
    try:
        with sqlite3.connect(db_path) as conn:
            # Otimizações básicas
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.execute("PRAGMA cache_size = -64000")
            
            cursor = conn.cursor()
            
            # ========================================
            # Estatísticas básicas
            # ========================================
            cursor.execute("SELECT COUNT(*) FROM notas")
            total = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 1")
            baixados = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 0 OR xml_baixado IS NULL")
            pendentes = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_vazio = 1")
            vazios = cursor.fetchone()[0]
            
            # ========================================
            # Indexação temporal
            # ========================================
            cursor.execute("SELECT COUNT(*) FROM notas WHERE anomesdia IS NOT NULL")
            com_anomesdia = cursor.fetchone()[0]
            
            # ========================================
            # Datas extremas (conversão inteligente)
            # ========================================
            cursor.execute("""
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
                FROM notas 
                WHERE dEmi IS NOT NULL AND dEmi != ''
            """)
            resultado = cursor.fetchone()
            
            # Converter para formato brasileiro
            data_inicio_iso = resultado[0] or "N/A"
            data_fim_iso = resultado[1] or "N/A"
            
            data_inicio = normalizar_data(data_inicio_iso)
            data_fim = normalizar_data(data_fim_iso)
            
            # ========================================
            # Top 10 dias com mais registros
            # ========================================
            cursor.execute("""
                SELECT dEmi, COUNT(*) as total
                FROM notas 
                WHERE dEmi IS NOT NULL AND dEmi != ''
                GROUP BY dEmi 
                ORDER BY total DESC 
                LIMIT 10
            """)
            top_dias = cursor.fetchall()
            
            # ========================================
            # Campos vazios importantes
            # ========================================
            campos_vazios = {}
            for campo in ['dEmi', 'nNF', 'cRazao', 'cnpj_cpf', 'cChaveNFe']:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM notas WHERE {campo} IS NULL OR {campo} = ''")
                    campos_vazios[campo] = cursor.fetchone()[0]
                except sqlite3.Error:
                    campos_vazios[campo] = 0
            
            # ========================================
            # Progresso por período
            # ========================================
            cursor.execute("""
                SELECT 
                    substr(dEmi, 4, 7) as mes_ano,
                    COUNT(*) as total,
                    SUM(CASE WHEN xml_baixado = 1 THEN 1 ELSE 0 END) as baixados
                FROM notas
                WHERE dEmi IS NOT NULL AND dEmi != '' AND dEmi LIKE '__/__/____'
                GROUP BY mes_ano
                ORDER BY substr(dEmi, 7, 4), substr(dEmi, 4, 2)
                LIMIT 12
            """)
            progresso_mensal = cursor.fetchall()
            
            # ========================================
            # Infraestrutura do banco
            # ========================================
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='view'")
            total_views = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index'")
            total_indices = cursor.fetchone()[0]
            
            # ========================================
            # Cálculos de percentuais
            # ========================================
            percentual_baixados = (baixados / max(1, total)) * 100
            percentual_pendentes = (pendentes / max(1, total)) * 100
            percentual_vazios = (vazios / max(1, total)) * 100
            percentual_anomesdia = (com_anomesdia / max(1, total)) * 100
            
            # ========================================
            # Estimativas de tempo
            # ========================================
            tempo_estimado = _calcular_tempo_estimado(total, baixados, pendentes, percentual_baixados)
            
            return {
                # Contadores básicos
                'total': total,
                'baixados': baixados,
                'pendentes': pendentes,
                'vazios': vazios,
                'com_anomesdia': com_anomesdia,
                
                # Percentuais
                'percentual_baixados': percentual_baixados,
                'percentual_pendentes': percentual_pendentes,
                'percentual_vazios': percentual_vazios,
                'percentual_anomesdia': percentual_anomesdia,
                
                # Datas
                'data_inicio': data_inicio,
                'data_fim': data_fim,
                
                # Rankings e distribuições
                'top_dias': top_dias,
                'progresso_mensal': progresso_mensal,
                'campos_vazios': campos_vazios,
                
                # Infraestrutura
                'total_views': total_views,
                'total_indices': total_indices,
                
                # Estimativas
                'tempo_estimado': tempo_estimado,
                
                # Status do processamento
                'status_processamento': _determinar_status_processamento(percentual_baixados, pendentes)
            }
            
    except sqlite3.Error as e:
        logger.error(f"[MÉTRICAS] Erro de banco de dados: {e}")
        return {}
    except Exception as e:
        logger.error(f"[MÉTRICAS] Erro inesperado: {e}")
        return {}

def _calcular_tempo_estimado(total: int, baixados: int, pendentes: int, percentual: float) -> str:
    """
    Calcula tempo estimado para conclusão baseado no progresso atual.
    
    Args:
        total: Total de registros
        baixados: Registros já baixados
        pendentes: Registros pendentes
        percentual: Percentual de conclusão
        
    Returns:
        String com estimativa de tempo
    """
    if pendentes == 0:
        return "Processamento concluído"
    
    if percentual > 95:
        return "< 1 hora (fase final)"
    elif percentual > 90:
        return "< 1 dia (fase final)"
    elif percentual > 50:
        # Estimativa baseada na velocidade atual
        dias_estimados = (pendentes / max(baixados / 30, 1000))  # Assume 30 dias de processamento
        return f"~{dias_estimados:.1f} dias"
    elif percentual > 10:
        return "Algumas semanas"
    else:
        return "Calculando..."

def _determinar_status_processamento(percentual: float, pendentes: int) -> str:
    """
    Determina o status atual do processamento.
    
    Args:
        percentual: Percentual de conclusão
        pendentes: Número de registros pendentes
        
    Returns:
        String descrevendo o status
    """
    if pendentes == 0:
        return "✅ Concluído"
    elif percentual > 95:
        return "🏁 Fase final"
    elif percentual > 75:
        return "🚀 Avançado"
    elif percentual > 50:
        return "📈 Em progresso"
    elif percentual > 25:
        return "Inicial"
    else:
        return "🟡 Iniciando"

def exibir_metricas_completas(db_path: str = "omie.db") -> None:
    """
    Exibe métricas completas do banco de dados de forma organizada.
    
    Args:
        db_path: Caminho para o banco de dados SQLite
    """
    logger.info("=" * 80)
    logger.info("📊 MÉTRICAS COMPLETAS DO BANCO DE DADOS")
    logger.info("=" * 80)
    
    metricas = obter_metricas_completas_banco(db_path)
    
    if not metricas:
        logger.error("[MÉTRICAS] Não foi possível obter métricas do banco")
        return
    
    # ========================================
    # Estatísticas principais
    # ========================================
    logger.info("📈 ESTATÍSTICAS PRINCIPAIS:")
    logger.info(f"   • Total de registros: {formatar_numero(metricas['total'])}")
    logger.info(f"   • XMLs baixados: {formatar_numero(metricas['baixados'])} ({metricas['percentual_baixados']:.1f}%)")
    logger.info(f"   • Pendentes: {formatar_numero(metricas['pendentes'])} ({metricas['percentual_pendentes']:.1f}%)")
    logger.info(f"   • XMLs vazios: {formatar_numero(metricas['vazios'])} ({metricas['percentual_vazios']:.1f}%)")
    logger.info(f"   • Status: {metricas['status_processamento']}")
    
    # ========================================
    # Período e indexação
    # ========================================
    logger.info("")
    logger.info("📅 PERÍODO E INDEXAÇÃO:")
    logger.info(f"   • Data início: {metricas['data_inicio']}")
    logger.info(f"   • Data fim: {metricas['data_fim']}")
    logger.info(f"   • Indexação temporal: {formatar_numero(metricas['com_anomesdia'])} ({metricas['percentual_anomesdia']:.1f}%)")
    
    # ========================================
    # Infraestrutura do banco
    # ========================================
    logger.info("")
    logger.info("🏗️ INFRAESTRUTURA DO BANCO:")
    logger.info(f"   • Views otimizadas: {metricas['total_views']}")
    logger.info(f"   • Índices criados: {metricas['total_indices']}")
    
    # ========================================
    # Top dias com mais registros
    # ========================================
    if metricas['top_dias']:
        logger.info("")
        logger.info("🔥 TOP 5 DIAS COM MAIS REGISTROS:")
        for i, (data, total) in enumerate(metricas['top_dias'][:5], 1):
            logger.info(f"   {i}. {data}: {formatar_numero(total)} registros")
    
    # ========================================
    # Campos vazios (apenas se houver problemas)
    # ========================================
    campos_problematicos = {k: v for k, v in metricas['campos_vazios'].items() if v > 0}
    if campos_problematicos:
        logger.info("")
        logger.info("⚠️  CAMPOS OBRIGATÓRIOS VAZIOS:")
        for campo, total in campos_problematicos.items():
            percentual = (total / max(1, metricas['total'])) * 100
            logger.info(f"   • {campo}: {formatar_numero(total)} ({percentual:.1f}%)")
    
    # ========================================
    # Progresso por período
    # ========================================
    if metricas['progresso_mensal']:
        logger.info("")
        logger.info("📊 PROGRESSO POR PERÍODO (ÚLTIMOS 6 MESES):")
        for mes_ano, total, baixados in metricas['progresso_mensal'][:6]:
            percentual = (baixados / max(1, total)) * 100
            logger.info(f"   • {mes_ano}: {formatar_numero(baixados)}/{formatar_numero(total)} ({percentual:.1f}%)")
    
    # ========================================
    # Estimativas e performance
    # ========================================
    logger.info("")
    logger.info("🎯 ESTIMATIVAS:")
    logger.info(f"   • Tempo estimado restante: {metricas['tempo_estimado']}")
    
    # Performance baseada no volume processado
    if metricas['baixados'] > 100000:
        performance = "Excelente (>100k XMLs processados)"
    elif metricas['baixados'] > 10000:
        performance = "Boa (>10k XMLs processados)"
    elif metricas['baixados'] > 1000:
        performance = "Regular"
    else:
        performance = "Inicial"
    
    logger.info(f"   • Performance: {performance}")
    
    logger.info("=" * 80)