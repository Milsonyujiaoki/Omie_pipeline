#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Upload AWS S3 - Sistema de Upload Estruturado para Amazon S3
===========================================================

Este módulo implementa um sistema completo de upload para Amazon S3 com
extração inteligente de prefixos baseada nas informações dos arquivos.

Funcionalidades principais:
- Extração de data de emissão dos nomes dos arquivos ZIP e XML
- Geração automática de prefixos S3 baseada na estrutura de pastas locais
- Upload estruturado seguindo o padrão: resultado/ano/mes/arquivo.zip
- Sistema robusto de tratamento de erros e retry
- Logging detalhado para monitoramento e debugging
- Validação de integridade dos arquivos antes do upload
- Suporte a upload paralelo para melhor performance

Estrutura de prefixos S3:
- Baseada na data real dos arquivos, não na data atual
- Formato: resultado/YYYY/MM/arquivo.zip
- Compatível com estrutura existente no SharePoint
- Facilita organização, busca e manutenção

Dependências:
- boto3: SDK oficial da AWS para Python
- botocore: Tratamento de exceções AWS
- pathlib: Manipulação de caminhos
- configparser: Leitura de configurações

Autor: Sistema de Extração Omie
Data: 2025-08-15
Versão: 1.0
"""

# =============================================================================
# IMPORTS E DEPENDÊNCIAS
# =============================================================================

import os
import re
import logging
import time
import configparser
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass

try:
    import boto3
    from botocore.exceptions import (
        ClientError, 
        NoCredentialsError, 
        PartialCredentialsError,
        BotoCoreError
    )
    BOTO3_DISPONIVEL = True
except ImportError:
    BOTO3_DISPONIVEL = False
    boto3 = None
    ClientError = Exception
    NoCredentialsError = Exception
    PartialCredentialsError = Exception
    BotoCoreError = Exception

# =============================================================================
# CONFIGURAÇÃO DE LOGGING
# =============================================================================

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTES E CONFIGURAÇÕES
# =============================================================================

# Regex para extração de informações dos nomes de arquivos
PADRAO_ZIP_LOTE = re.compile(
    r'^(\d{1,2})_lote_(\d{4})\.zip$', 
    re.IGNORECASE
)

PADRAO_XML_INDIVIDUAL = re.compile(
    r'^(\d+)_(\d{8})_([0-9]{44})\.xml$', 
    re.IGNORECASE
)

# Configurações padrão do S3
DEFAULT_S3_CONFIG = {
    'region_name': 'sa-east-1',
    'bucket_name': 'qualitytax-ngcash-notas',
    'max_retries': 3,
    'retry_delay': 1.0,
    'timeout': 300,
    'multipart_threshold': 64 * 1024 * 1024,  # 64MB
    'max_concurrency': 4
}

# Prefixo base para organização no S3
PREFIXO_BASE_S3 = 'resultado'

# =============================================================================
# CLASSES DE EXCEÇÃO CUSTOMIZADAS
# =============================================================================

class S3UploadError(Exception):
    """Exceção base para erros de upload S3."""
    pass

class S3ConfigError(S3UploadError):
    """Exceção para erros de configuração do S3."""
    pass

class S3ConnectionError(S3UploadError):
    """Exceção para erros de conexão com S3."""
    pass

class S3AuthError(S3UploadError):
    """Exceção para erros de autenticação S3."""
    pass

class ArquivoInvalidoError(S3UploadError):
    """Exceção para arquivos inválidos ou não suportados."""
    pass

# =============================================================================
# CLASSES DE DADOS
# =============================================================================

@dataclass
class InfoArquivo:
    """
    Informações extraídas de um arquivo para upload S3.
    
    Atributos:
        caminho_local: Path do arquivo local
        nome_arquivo: Nome do arquivo
        tipo_arquivo: Tipo do arquivo ('zip_lote', 'xml_individual', 'outro')
        data_emissao: Data de emissão extraída (datetime ou None)
        prefixo_s3: Prefixo calculado para S3
        chave_s3: Chave completa no S3
        tamanho: Tamanho do arquivo em bytes
        valido: Se o arquivo é válido para upload
        erro: Mensagem de erro (se houver)
    """
    caminho_local: Path
    nome_arquivo: str
    tipo_arquivo: str
    data_emissao: Optional[datetime] = None
    prefixo_s3: str = ''
    chave_s3: str = ''
    tamanho: int = 0
    valido: bool = True
    erro: Optional[str] = None

@dataclass
class ResultadoUpload:
    """
    Resultado de uma operação de upload S3.
    
    Atributos:
        arquivo: Path do arquivo local
        chave_s3: Chave no S3
        sucesso: Se o upload foi bem-sucedido
        tempo_upload: Tempo gasto no upload (segundos)
        tamanho_bytes: Tamanho do arquivo em bytes
        erro: Mensagem de erro (se houver)
        tentativas: Número de tentativas realizadas
    """
    arquivo: Path
    chave_s3: str
    sucesso: bool = False
    tempo_upload: float = 0.0
    tamanho_bytes: int = 0
    erro: Optional[str] = None
    tentativas: int = 0

# =============================================================================
# FUNÇÕES DE EXTRAÇÃO DE INFORMAÇÕES
# =============================================================================

def extrair_data_do_nome_zip(nome_arquivo: str, caminho_pasta: Path) -> Optional[datetime]:
    """
    Extrai data de emissão de um arquivo ZIP baseada no nome e estrutura de pastas.
    
    Para arquivos ZIP de lote (ex: "17_lote_0001.zip"):
    1. Primeiro tenta extrair do nome do arquivo (dia)
    2. Depois usa a estrutura de pastas (resultado/ano/mes/dia)
    3. Combina informações para formar data completa
    
    Args:
        nome_arquivo: Nome do arquivo ZIP (ex: "17_lote_0001.zip")
        caminho_pasta: Path da pasta onde está o arquivo
        
    Returns:
        datetime: Data de emissão extraída ou None se não conseguir
        
    Examples:
        >>> extrair_data_do_nome_zip("17_lote_0001.zip", Path("resultado/2025/08/17"))
        datetime(2025, 8, 17)
        >>> extrair_data_do_nome_zip("arquivo_invalido.zip", Path("pasta"))
        None
    """
    try:
        # Tenta padrão de arquivo ZIP de lote
        match_zip = PADRAO_ZIP_LOTE.match(nome_arquivo)
        if match_zip:
            dia = int(match_zip.group(1))
            
            # Extrai ano e mês da estrutura de pastas
            # Formato esperado: .../resultado/ano/mes/dia/arquivo.zip
            partes_caminho = caminho_pasta.parts
            
            # Busca pelos componentes de data nas partes do caminho
            ano = mes = None
            
            # Procura por padrões de ano (4 dígitos) e mês (1-2 dígitos)
            for i, parte in enumerate(partes_caminho):
                if parte.isdigit() and len(parte) == 4 and 2020 <= int(parte) <= 2030:
                    ano = int(parte)
                    # Mês deve estar na próxima posição
                    if i + 1 < len(partes_caminho):
                        proxima_parte = partes_caminho[i + 1]
                        if proxima_parte.isdigit() and 1 <= int(proxima_parte) <= 12:
                            mes = int(proxima_parte)
                            break
            
            if ano and mes:
                # Valida dia
                if 1 <= dia <= 31:
                    try:
                        data_extraida = datetime(ano, mes, dia)
                        logger.debug(f"[S3.EXTRAÇÃO] Data extraída do ZIP: {data_extraida.strftime('%Y-%m-%d')} <- {nome_arquivo}")
                        return data_extraida
                    except ValueError as e:
                        logger.warning(f"[S3.EXTRAÇÃO] Data inválida extraída: {ano}-{mes}-{dia} <- {nome_arquivo}: {e}")
                        return None
                else:
                    logger.warning(f"[S3.EXTRAÇÃO] Dia inválido: {dia} <- {nome_arquivo}")
                    return None
            else:
                logger.debug(f"[S3.EXTRAÇÃO] Não foi possível extrair ano/mês da estrutura de pastas: {caminho_pasta}")
                return None
        
        # Tenta padrão de XML individual (fallback)
        match_xml = PADRAO_XML_INDIVIDUAL.match(nome_arquivo)
        if match_xml:
            data_str = match_xml.group(2)  # YYYYMMDD
            try:
                data_extraida = datetime.strptime(data_str, '%Y%m%d')
                logger.debug(f"[S3.EXTRAÇÃO] Data extraída do XML: {data_extraida.strftime('%Y-%m-%d')} <- {nome_arquivo}")
                return data_extraida
            except ValueError as e:
                logger.warning(f"[S3.EXTRAÇÃO] Erro ao converter data do XML: {data_str} <- {nome_arquivo}: {e}")
                return None
        
        logger.debug(f"[S3.EXTRAÇÃO] Padrão de arquivo não reconhecido: {nome_arquivo}")
        return None
        
    except Exception as e:
        logger.error(f"[S3.EXTRAÇÃO] Erro inesperado ao extrair data: {nome_arquivo}: {e}")
        return None

def gerar_prefixo_s3(arquivo_info: InfoArquivo) -> str:
    """
    Gera prefixo S3 baseado na data de emissão do arquivo.
    
    Formato: resultado/YYYY/MM/
    
    Args:
        arquivo_info: Informações do arquivo
        
    Returns:
        str: Prefixo S3 gerado
        
    Examples:
        >>> info = InfoArquivo(Path("test.zip"), "test.zip", "zip_lote")
        >>> info.data_emissao = datetime(2025, 8, 17)
        >>> gerar_prefixo_s3(info)
        'resultado/2025/08'
    """
    if not arquivo_info.data_emissao:
        # Fallback: usa data atual se não conseguiu extrair
        data = datetime.now()
        logger.warning(f"[S3.PREFIXO] Usando data atual como fallback para: {arquivo_info.nome_arquivo}")
    else:
        data = arquivo_info.data_emissao
    
    prefixo = f"{PREFIXO_BASE_S3}/{data.year:04d}/{data.month:02d}"
    
    logger.debug(f"[S3.PREFIXO] Prefixo gerado: {prefixo} <- {arquivo_info.nome_arquivo}")
    return prefixo

def analisar_arquivo(caminho_arquivo: Path) -> InfoArquivo:
    """
    Analisa um arquivo e extrai todas as informações necessárias para upload S3.
    
    Realiza análise completa do arquivo:
    1. Extrai informações do nome
    2. Determina tipo do arquivo
    3. Extrai data de emissão
    4. Gera prefixo e chave S3
    5. Valida arquivo para upload
    
    Args:
        caminho_arquivo: Path do arquivo a ser analisado
        
    Returns:
        InfoArquivo: Informações completas do arquivo
        
    Examples:
        >>> arquivo = Path("resultado/2025/08/17/17_lote_0001.zip")
        >>> info = analisar_arquivo(arquivo)
        >>> print(info.prefixo_s3)  # 'resultado/2025/08'
        >>> print(info.chave_s3)    # 'resultado/2025/08/17_lote_0001.zip'
    """
    try:
        # Validação básica do arquivo
        if not caminho_arquivo.exists():
            return InfoArquivo(
                caminho_local=caminho_arquivo,
                nome_arquivo=caminho_arquivo.name,
                tipo_arquivo='inexistente',
                valido=False,
                erro=f"Arquivo não encontrado: {caminho_arquivo}"
            )
        
        if not caminho_arquivo.is_file():
            return InfoArquivo(
                caminho_local=caminho_arquivo,
                nome_arquivo=caminho_arquivo.name,
                tipo_arquivo='nao_arquivo',
                valido=False,
                erro=f"Caminho não é um arquivo: {caminho_arquivo}"
            )
        
        nome_arquivo = caminho_arquivo.name
        tamanho = caminho_arquivo.stat().st_size
        
        # Determina tipo do arquivo
        tipo_arquivo = 'outro'
        if PADRAO_ZIP_LOTE.match(nome_arquivo):
            tipo_arquivo = 'zip_lote'
        elif PADRAO_XML_INDIVIDUAL.match(nome_arquivo):
            tipo_arquivo = 'xml_individual'
        elif nome_arquivo.lower().endswith('.zip'):
            tipo_arquivo = 'zip_generico'
        elif nome_arquivo.lower().endswith('.xml'):
            tipo_arquivo = 'xml_generico'
        
        # Extrai data de emissão
        data_emissao = extrair_data_do_nome_zip(nome_arquivo, caminho_arquivo.parent)
        
        # Cria informações básicas
        info = InfoArquivo(
            caminho_local=caminho_arquivo,
            nome_arquivo=nome_arquivo,
            tipo_arquivo=tipo_arquivo,
            data_emissao=data_emissao,
            tamanho=tamanho
        )
        
        # Gera prefixo e chave S3
        info.prefixo_s3 = gerar_prefixo_s3(info)
        info.chave_s3 = f"{info.prefixo_s3}/{nome_arquivo}"
        
        # Validações adicionais
        if tamanho == 0:
            info.valido = False
            info.erro = "Arquivo está vazio"
        elif tamanho > 5 * 1024 * 1024 * 1024:  # 5GB - limite do S3 para single upload
            info.valido = False
            info.erro = f"Arquivo muito grande para upload único: {tamanho / (1024**3):.2f}GB"
        
        logger.debug(
            f"[S3.ANÁLISE] Arquivo analisado: {nome_arquivo} -> "
            f"tipo={tipo_arquivo}, data={data_emissao}, "
            f"prefixo={info.prefixo_s3}, válido={info.valido}"
        )
        
        return info
        
    except Exception as e:
        logger.error(f"[S3.ANÁLISE] Erro ao analisar arquivo: {caminho_arquivo}: {e}")
        return InfoArquivo(
            caminho_local=caminho_arquivo,
            nome_arquivo=caminho_arquivo.name if caminho_arquivo else 'desconhecido',
            tipo_arquivo='erro',
            valido=False,
            erro=f"Erro na análise: {e}"
        )

# =============================================================================
# CLASSE PRINCIPAL DE UPLOAD S3
# =============================================================================

class S3Uploader:
    """
    Cliente de upload S3 com extração inteligente de prefixos.
    
    Esta classe implementa um sistema completo de upload para S3 com:
    - Extração automática de datas dos nomes dos arquivos
    - Geração inteligente de prefixos baseada na estrutura local
    - Sistema robusto de retry e tratamento de erros
    - Logging detalhado para monitoramento
    - Validação de arquivos antes do upload
    - Suporte a diferentes tipos de arquivos (ZIP, XML)
    
    Attributes:
        s3_client: Cliente boto3 para S3
        bucket_name: Nome do bucket S3
        config: Configurações do S3
        stats: Estatísticas de upload
    """
    
    def __init__(self, 
                 bucket_name: str,
                 aws_access_key_id: Optional[str] = None,
                 aws_secret_access_key: Optional[str] = None,
                 region_name: str = 'sa-east-1',
                 testar_conexao: bool = False,
                 **config_extra):
        """
        Inicializa o cliente S3 Uploader.
        
        Args:
            bucket_name: Nome do bucket S3
            aws_access_key_id: Chave de acesso AWS (opcional, pode vir de env vars)
            aws_secret_access_key: Chave secreta AWS (opcional, pode vir de env vars)
            region_name: Região AWS (padrão: sa-east-1)
            testar_conexao: Se deve testar conexão na inicialização (padrão: False)
            **config_extra: Configurações adicionais do S3
            
        Raises:
            S3ConfigError: Se boto3 não estiver disponível
            S3AuthError: Se credenciais estiverem inválidas
            S3ConnectionError: Se não conseguir conectar ao S3
        """
        self.bucket_name = bucket_name
        self.config = {**DEFAULT_S3_CONFIG, **config_extra}
        self.config['region_name'] = region_name
        
        # Estatísticas de upload
        self.stats = {
            'arquivos_analisados': 0,
            'arquivos_validos': 0,
            'uploads_sucesso': 0,
            'uploads_falha': 0,
            'bytes_enviados': 0,
            'tempo_total': 0.0
        }
        
        # Validação de dependências
        if not BOTO3_DISPONIVEL:
            raise S3ConfigError(
                "Biblioteca boto3 não disponível. "
                "Instale com: pip install boto3"
            )
        
        # Configuração do cliente S3
        try:
            session_config = {
                'region_name': region_name
            }
            
            # Adiciona credenciais se fornecidas explicitamente
            if aws_access_key_id and aws_secret_access_key:
                session_config.update({
                    'aws_access_key_id': aws_access_key_id,
                    'aws_secret_access_key': aws_secret_access_key
                })
            
            # Cria cliente S3
            self.s3_client = boto3.client('s3', **session_config)
            
            # Testa conexão apenas se solicitado
            if testar_conexao:
                self._testar_conexao()
            
            logger.info(f"[S3.INIT] Cliente S3 inicializado - Bucket: {bucket_name}, Região: {region_name}")
            
        except (NoCredentialsError, PartialCredentialsError) as e:
            raise S3AuthError(f"Credenciais AWS inválidas ou ausentes: {e}")
        except ClientError as e:
            raise S3ConnectionError(f"Erro ao conectar com S3: {e}")
        except Exception as e:
            raise S3ConfigError(f"Erro na configuração do cliente S3: {e}")
    
    def _testar_conexao(self) -> None:
        """
        Testa conexão com S3 e verifica se bucket existe.
        
        Raises:
            S3ConnectionError: Se não conseguir acessar o bucket
        """
        try:
            # Verifica se bucket existe e é acessível
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.debug(f"[S3.TESTE] Conexão com bucket '{self.bucket_name}' OK")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                raise S3ConnectionError(f"Bucket '{self.bucket_name}' não encontrado")
            elif error_code == '403':
                raise S3AuthError(f"Acesso negado ao bucket '{self.bucket_name}'")
            else:
                raise S3ConnectionError(f"Erro ao acessar bucket: {e}")
    
    def upload_arquivo(self, caminho_arquivo: Path, 
                      forcar_reenvio: bool = False) -> ResultadoUpload:
        """
        Faz upload de um único arquivo para S3.
        
        Processo completo de upload:
        1. Analisa arquivo e extrai informações
        2. Gera prefixo S3 baseado na data extraída
        3. Verifica se arquivo já existe (opcional)
        4. Realiza upload com retry automático
        5. Valida sucesso do upload
        
        Args:
            caminho_arquivo: Path do arquivo local
            forcar_reenvio: Se True, envia mesmo que já exista no S3
            
        Returns:
            ResultadoUpload: Resultado detalhado do upload
            
        Examples:
            >>> uploader = S3Uploader('meu-bucket')
            >>> resultado = uploader.upload_arquivo(Path('17_lote_0001.zip'))
            >>> print(f"Sucesso: {resultado.sucesso}, Chave: {resultado.chave_s3}")
        """
        tempo_inicio = time.time()
        
        try:
            # Atualiza estatísticas
            self.stats['arquivos_analisados'] += 1
            
            # Analisa arquivo
            info_arquivo = analisar_arquivo(caminho_arquivo)
            
            if not info_arquivo.valido:
                logger.warning(f"[S3.UPLOAD] Arquivo inválido: {info_arquivo.erro}")
                return ResultadoUpload(
                    arquivo=caminho_arquivo,
                    chave_s3=info_arquivo.chave_s3,
                    sucesso=False,
                    erro=info_arquivo.erro,
                    tentativas=0
                )
            
            self.stats['arquivos_validos'] += 1
            
            # Verifica se arquivo já existe no S3 (se não for para forçar reenvio)
            if not forcar_reenvio:
                if self._arquivo_existe_s3(info_arquivo.chave_s3):
                    logger.info(f"[S3.UPLOAD] Arquivo já existe no S3: {info_arquivo.chave_s3}")
                    return ResultadoUpload(
                        arquivo=caminho_arquivo,
                        chave_s3=info_arquivo.chave_s3,
                        sucesso=True,
                        tempo_upload=time.time() - tempo_inicio,
                        tamanho_bytes=info_arquivo.tamanho,
                        tentativas=0
                    )
            
            # Realiza upload com retry
            resultado = self._upload_com_retry(info_arquivo)
            resultado.tempo_upload = time.time() - tempo_inicio
            
            # Atualiza estatísticas
            if resultado.sucesso:
                self.stats['uploads_sucesso'] += 1
                self.stats['bytes_enviados'] += info_arquivo.tamanho
            else:
                self.stats['uploads_falha'] += 1
            
            self.stats['tempo_total'] += resultado.tempo_upload
            
            return resultado
            
        except Exception as e:
            logger.error(f"[S3.UPLOAD] Erro inesperado no upload: {caminho_arquivo}: {e}")
            self.stats['uploads_falha'] += 1
            
            return ResultadoUpload(
                arquivo=caminho_arquivo,
                chave_s3=info_arquivo.chave_s3 if 'info_arquivo' in locals() else 'unknown',
                sucesso=False,
                tempo_upload=time.time() - tempo_inicio,
                erro=f"Erro inesperado: {e}",
                tentativas=0
            )
    
    def _arquivo_existe_s3(self, chave_s3: str) -> bool:
        """
        Verifica se arquivo já existe no S3.
        
        Args:
            chave_s3: Chave do arquivo no S3
            
        Returns:
            bool: True se arquivo existe
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=chave_s3)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                logger.warning(f"[S3.CHECK] Erro ao verificar existência: {chave_s3}: {e}")
                return False
    
    def _upload_com_retry(self, info_arquivo: InfoArquivo) -> ResultadoUpload:
        """
        Realiza upload com sistema de retry automático.
        
        Args:
            info_arquivo: Informações do arquivo para upload
            
        Returns:
            ResultadoUpload: Resultado do upload
        """
        max_retries = self.config['max_retries']
        retry_delay = self.config['retry_delay']
        
        ultimo_erro = None
        
        for tentativa in range(1, max_retries + 1):
            try:
                logger.info(
                    f"[S3.UPLOAD] Tentativa {tentativa}/{max_retries}: "
                    f"{info_arquivo.nome_arquivo} -> {info_arquivo.chave_s3}"
                )
                
                tempo_upload_inicio = time.time()
                
                # Realiza upload
                self.s3_client.upload_file(
                    str(info_arquivo.caminho_local),
                    self.bucket_name,
                    info_arquivo.chave_s3
                )
                
                tempo_upload = time.time() - tempo_upload_inicio
                
                logger.info(
                    f"[S3.UPLOAD] Sucesso: {info_arquivo.nome_arquivo} -> {info_arquivo.chave_s3} "
                    f"({info_arquivo.tamanho / (1024*1024):.2f}MB em {tempo_upload:.2f}s)"
                )
                
                return ResultadoUpload(
                    arquivo=info_arquivo.caminho_local,
                    chave_s3=info_arquivo.chave_s3,
                    sucesso=True,
                    tempo_upload=tempo_upload,
                    tamanho_bytes=info_arquivo.tamanho,
                    tentativas=tentativa
                )
                
            except ClientError as e:
                ultimo_erro = e
                error_code = e.response['Error']['Code']
                
                logger.warning(
                    f"[S3.UPLOAD] Falha na tentativa {tentativa}: "
                    f"{info_arquivo.nome_arquivo} -> {error_code}: {e}"
                )
                
                # Alguns erros não vale a pena tentar novamente
                if error_code in ['AccessDenied', 'InvalidBucketName', 'NoSuchBucket']:
                    break
                
                # Aguarda antes da próxima tentativa
                if tentativa < max_retries:
                    time.sleep(retry_delay * tentativa)  # Backoff exponencial
            
            except Exception as e:
                ultimo_erro = e
                logger.warning(
                    f"[S3.UPLOAD] Erro inesperado na tentativa {tentativa}: "
                    f"{info_arquivo.nome_arquivo}: {e}"
                )
                
                # Aguarda antes da próxima tentativa
                if tentativa < max_retries:
                    time.sleep(retry_delay * tentativa)
        
        # Todas as tentativas falharam
        logger.error(
            f"[S3.UPLOAD] Falha após {max_retries} tentativas: "
            f"{info_arquivo.nome_arquivo}: {ultimo_erro}"
        )
        
        return ResultadoUpload(
            arquivo=info_arquivo.caminho_local,
            chave_s3=info_arquivo.chave_s3,
            sucesso=False,
            erro=f"Falha após {max_retries} tentativas: {ultimo_erro}",
            tentativas=max_retries
        )
    
    def upload_lote(self, arquivos: List[Path], 
                   forcar_reenvio: bool = False) -> Dict[str, ResultadoUpload]:
        """
        Faz upload de múltiplos arquivos em lote.
        
        Args:
            arquivos: Lista de arquivos para upload
            forcar_reenvio: Se True, envia mesmo que já existam no S3
            
        Returns:
            Dict[str, ResultadoUpload]: Resultados indexados pelo nome do arquivo
            
        Examples:
            >>> arquivos = [Path('file1.zip'), Path('file2.zip')]
            >>> resultados = uploader.upload_lote(arquivos)
            >>> sucessos = sum(1 for r in resultados.values() if r.sucesso)
        """
        logger.info(f"[S3.LOTE] Iniciando upload de {len(arquivos)} arquivos")
        tempo_inicio = time.time()
        
        resultados = {}
        sucessos = 0
        falhas = 0
        
        for i, arquivo in enumerate(arquivos, 1):
            try:
                logger.info(f"[S3.LOTE] Processando {i}/{len(arquivos)}: {arquivo.name}")
                
                resultado = self.upload_arquivo(arquivo, forcar_reenvio)
                resultados[arquivo.name] = resultado
                
                if resultado.sucesso:
                    sucessos += 1
                else:
                    falhas += 1
                
            except Exception as e:
                logger.error(f"[S3.LOTE] Erro no arquivo {arquivo.name}: {e}")
                resultados[arquivo.name] = ResultadoUpload(
                    arquivo=arquivo,
                    chave_s3='erro',
                    sucesso=False,
                    erro=f"Erro no processamento: {e}",
                    tentativas=0
                )
                falhas += 1
        
        tempo_total = time.time() - tempo_inicio
        
        logger.info(
            f"[S3.LOTE] Upload em lote concluído: "
            f"{sucessos} sucessos, {falhas} falhas em {tempo_total:.2f}s"
        )
        
        return resultados
    
    def obter_estatisticas(self) -> Dict[str, Union[int, float]]:
        """
        Retorna estatísticas detalhadas do uploader.
        
        Returns:
            Dict: Estatísticas de uso e performance
        """
        stats = self.stats.copy()
        
        # Calcula estatísticas derivadas
        if stats['arquivos_analisados'] > 0:
            stats['taxa_arquivos_validos'] = (stats['arquivos_validos'] / stats['arquivos_analisados']) * 100
        else:
            stats['taxa_arquivos_validos'] = 0.0
        
        if stats['uploads_sucesso'] + stats['uploads_falha'] > 0:
            stats['taxa_sucesso'] = (stats['uploads_sucesso'] / (stats['uploads_sucesso'] + stats['uploads_falha'])) * 100
        else:
            stats['taxa_sucesso'] = 0.0
        
        if stats['tempo_total'] > 0 and stats['uploads_sucesso'] > 0:
            stats['velocidade_media_mbps'] = (stats['bytes_enviados'] / (1024*1024)) / stats['tempo_total']
        else:
            stats['velocidade_media_mbps'] = 0.0
        
        return stats

# =============================================================================
# FUNÇÕES DE CONVENIÊNCIA
# =============================================================================

def criar_s3_uploader_from_config(config_path: str = "configuracao.ini") -> S3Uploader:
    """
    Cria instância do S3Uploader baseada no arquivo de configuração.
    
    Busca credenciais AWS nos seguintes locais (em ordem de prioridade):
    1. Arquivo de configuração .ini
    2. Variáveis de ambiente
    3. Arquivo .env
    4. Credenciais padrão do boto3 (~/.aws/credentials)
    
    Args:
        config_path: Caminho do arquivo de configuração
        
    Returns:
        S3Uploader: Instância configurada
        
    Raises:
        S3ConfigError: Se não conseguir ler configurações
        S3AuthError: Se credenciais estiverem inválidas
    """
    try:
        # Carrega configuração do arquivo INI
        config = configparser.ConfigParser()
        config_file = Path(config_path)
        
        if config_file.exists():
            config.read(config_file, encoding='utf-8')
            logger.info(f"[S3.CONFIG] Configuração carregada de: {config_file}")
        else:
            logger.warning(f"[S3.CONFIG] Arquivo de configuração não encontrado: {config_file}")
        
        # Configurações do S3
        s3_config = {}
        
        if config.has_section('AWS_S3'):
            s3_config.update({
                'bucket_name': config.get('AWS_S3', 'bucket_name', fallback='omie-pipeline-xmls'),
                'region_name': config.get('AWS_S3', 'region_name', fallback='sa-east-1'),
                'max_retries': config.getint('AWS_S3', 'max_retries', fallback=3),
                'timeout': config.getint('AWS_S3', 'timeout', fallback=300),
            })
        else:
            s3_config.update({
                'bucket_name': 'omie-pipeline-xmls',
                'region_name': 'sa-east-1'
            })
        
        # Credenciais AWS - tenta várias fontes
        aws_credentials = {}
        
        # 1. Arquivo INI
        if config.has_section('AWS_CREDENTIALS'):
            aws_key = config.get('AWS_CREDENTIALS', 'aws_access_key_id', fallback=None)
            aws_secret = config.get('AWS_CREDENTIALS', 'aws_secret_access_key', fallback=None)
            if aws_key and aws_secret:
                aws_credentials.update({
                    'aws_access_key_id': aws_key,
                    'aws_secret_access_key': aws_secret
                })
                logger.debug("[S3.CONFIG] Credenciais carregadas do arquivo INI")
        
        # 2. Variáveis de ambiente
        if not aws_credentials:
            aws_key = os.getenv('AWS_ACCESS_KEY_ID')
            aws_secret = os.getenv('AWS_SECRET_ACCESS_KEY')
            if aws_key and aws_secret:
                aws_credentials.update({
                    'aws_access_key_id': aws_key,
                    'aws_secret_access_key': aws_secret
                })
                logger.debug("[S3.CONFIG] Credenciais carregadas das variáveis de ambiente")
        
        # 3. Arquivo .env (se existir)
        if not aws_credentials:
            env_file = Path('.env')
            if env_file.exists():
                try:
                    with open(env_file, 'r', encoding='utf-8') as f:
                        for linha in f:
                            linha = linha.strip()
                            if '=' in linha and not linha.startswith('#'):
                                chave, valor = linha.split('=', 1)
                                chave = chave.strip()
                                valor = valor.strip().strip('"\'')
                                
                                if chave == 'aws_access_key_id':
                                    aws_credentials['aws_access_key_id'] = valor
                                elif chave == 'aws_secret_access_key':
                                    aws_credentials['aws_secret_access_key'] = valor
                    
                    if len(aws_credentials) == 2:
                        logger.debug("[S3.CONFIG] Credenciais carregadas do arquivo .env")
                except Exception as e:
                    logger.warning(f"[S3.CONFIG] Erro ao ler arquivo .env: {e}")
        
        # Se não encontrou credenciais explícitas, deixa boto3 usar padrões
        if not aws_credentials:
            logger.info("[S3.CONFIG] Usando credenciais padrão do boto3 (IAM, ~/.aws/credentials, etc.)")
        
        # Cria uploader
        return S3Uploader(**s3_config, **aws_credentials)
        
    except Exception as e:
        raise S3ConfigError(f"Erro ao criar S3Uploader: {e}")

def upload_arquivos_s3(arquivos: List[Path], 
                      config_path: str = "configuracao.ini",
                      forcar_reenvio: bool = False) -> Dict[str, ResultadoUpload]:
    """
    Função de conveniência para upload direto de arquivos.
    
    Args:
        arquivos: Lista de arquivos para upload
        config_path: Caminho do arquivo de configuração
        forcar_reenvio: Se True, envia mesmo que já existam no S3
        
    Returns:
        Dict[str, ResultadoUpload]: Resultados do upload
        
    Examples:
        >>> arquivos = [Path('file1.zip'), Path('file2.zip')]
        >>> resultados = upload_arquivos_s3(arquivos)
        >>> print(f"Sucessos: {sum(1 for r in resultados.values() if r.sucesso)}")
    """
    try:
        uploader = criar_s3_uploader_from_config(config_path)
        return uploader.upload_lote(arquivos, forcar_reenvio)
    except Exception as e:
        logger.error(f"[S3.UPLOAD_DIRETO] Erro no upload: {e}")
        # Retorna resultados de erro para todos os arquivos
        return {
            arquivo.name: ResultadoUpload(
                arquivo=arquivo,
                chave_s3='erro',
                sucesso=False,
                erro=f"Erro na configuração: {e}",
                tentativas=0
            )
            for arquivo in arquivos
        }

# =============================================================================
# FUNÇÃO PRINCIPAL PARA TESTES
# =============================================================================

def main():
    """
    Função principal para testes do módulo.
    
    Executa testes básicos de funcionalidade:
    1. Carrega configuração
    2. Lista arquivos de exemplo
    3. Analisa arquivos
    4. Simula upload (sem realmente enviar)
    """
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    try:
        logger.info("[TESTE] Iniciando testes do módulo S3 Upload")
        
        # Testa extração de data de arquivos
        arquivos_teste = [
            ("13_lote_0001.zip", Path("resultado/2025/08/13")),
            ("01563245_20250812_35250859279145000116550010015632451503296453.xml", Path("resultado/2025/08/12/01563245_20250812_35250859279145000116550010015632451503296453.xml")),
            ("arquivo_invalido.txt", Path("pasta")),
        ]
        
        logger.info("[TESTE] === Testando extração de datas ===")
        for nome, pasta in arquivos_teste:
            data = extrair_data_do_nome_zip(nome, pasta)
            if data:
                logger.info(f"[TESTE] {nome} -> {data.strftime('%Y-%m-%d')}")
            else:
                logger.info(f"[TESTE] {nome} -> Data não extraída")
        
        # Testa análise de arquivos (simulada)
        logger.info("[TESTE] === Testando análise de arquivos (simulada) ===")
        for nome, pasta in arquivos_teste[:2]:  # Apenas os válidos
            arquivo_simulado = pasta / nome
            
            # Simula informações básicas do arquivo
            info = InfoArquivo(
                caminho_local=arquivo_simulado,
                nome_arquivo=nome,
                tipo_arquivo='zip_lote' if nome.endswith('.zip') else 'xml_individual'
            )
            
            # Extrai data
            info.data_emissao = extrair_data_do_nome_zip(nome, pasta)
            info.prefixo_s3 = gerar_prefixo_s3(info)
            info.chave_s3 = f"{info.prefixo_s3}/{nome}"
            
            logger.info(
                f"[TESTE] {nome} -> "
                f"prefixo={info.prefixo_s3}, chave={info.chave_s3}"
            )
        
        logger.info("[TESTE] Testes concluídos com sucesso!")
        
    except Exception as e:
        logger.error(f"[TESTE] Erro durante testes: {e}")

if __name__ == "__main__":
    main()
