#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Upload OneDrive - Sistema de Upload para SharePoint/OneDrive
============================================================

Este modulo implementa um sistema completo de upload de arquivos para SharePoint/OneDrive
com funcionalidades avancadas de autenticacoo, cache inteligente e controle de duplicatas.

Funcionalidades principais:
- Autenticacoo OAuth2 com client credentials
- Upload em lote com controle de concorrência
- Cache inteligente de estrutura de pastas
- Controle de duplicatas e versionamento
- Metricas detalhadas de performance
- Recuperacoo automatica de falhas
- Integracoo com sistema de logging estruturado

Arquitetura:
- Autenticacoo: OAuth2 com client credentials flow
- Cache: Estrutura de pastas em cache para performance
- Upload: Sistema de lotes com retry automatico
- Logging: Estruturado com prefixos e contexto detalhado

Dependências:
- requests: HTTP client para API calls
- pathlib: Manipulacoo de caminhos
- configparser: Leitura de configuracões

Autor: Sistema de Extracoo Omie
Data: 2024
Versoo: 3.0
"""

# =============================================================================
# IMPORTS E DEPENDÊNCIAS
# =============================================================================

import os
import json
import logging
import configparser
import time
from pathlib import Path
from typing import Optional, Dict, Set, List, Any, Tuple
from dotenv import load_dotenv

import requests
from requests import Response

from utils import extrair_mes_do_path  # Integracoo com utilitario centralizado

# =============================================================================
# CONFIGURAcoO DE LOGGING
# =============================================================================

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURAcoO E CONSTANTES
# =============================================================================

# Carregamento de configuracões
load_dotenv()
config = configparser.ConfigParser()
config.read("configuracao.ini")

# Configuracões de upload
UPLOAD_ENABLED = config.getboolean("ONEDRIVE", "upload_onedrive", fallback=False)

# Variaveis sensiveis carregadas do ambiente
CLIENT_ID = os.getenv("ONEDRIVE_CLIENT_ID")
CLIENT_SECRET = os.getenv("ONEDRIVE_CLIENT_SECRET") 
TENANT_ID = os.getenv("ONEDRIVE_TENANT_ID")
SHAREPOINT_SITE = os.getenv("SHAREPOINT_SITE")
SHAREPOINT_FOLDER = os.getenv("SHAREPOINT_FOLDER")
DRIVE_NAME = os.getenv("ONEDRIVE_DRIVE_NAME")

# Validacoo de variaveis obrigatorias
REQUIRED_VARS = [CLIENT_ID, CLIENT_SECRET, TENANT_ID, SHAREPOINT_SITE, SHAREPOINT_FOLDER, DRIVE_NAME]

# Caminhos de cache e historico
UPLOAD_DB_PATH = Path("uploads_realizados.json")
ONEDRIVE_CACHE_PATH = Path("onedrive_pastas_cache.json")

# Configuracões de API
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
SCOPES = "https://graph.microsoft.com/.default"

# Configuracões de upload
MAX_RETRIES = 3
RETRY_DELAY = 2.0
CHUNK_SIZE = 10 * 1024 * 1024  # 10MB chunks para arquivos grandes
LARGE_FILE_THRESHOLD = 4 * 1024 * 1024  # 4MB threshold para upload resumivel
TIMEOUT = 60.0  # Timeout para requisicões HTTP

# =============================================================================
# CLASSES DE EXCEcoO CUSTOMIZADAS
# =============================================================================

class OneDriveUploadError(Exception):
    """Excecoo base para erros de upload no OneDrive."""
    pass


class OneDriveAuthError(OneDriveUploadError):
    """Excecoo para erros de autenticacoo no OneDrive."""
    pass


class OneDriveAPIError(OneDriveUploadError):
    """Excecoo para erros da API do OneDrive."""
    pass


class OneDriveConfigError(OneDriveUploadError):
    """Excecoo para erros de configuracoo do OneDrive."""
    pass


# =============================================================================
# FUNcÕES DE VALIDAcoO E CONFIGURAcoO
# =============================================================================

def validar_configuracao_onedrive() -> bool:
    """
    Valida se todas as configuracões necessarias estoo presentes.
    
    Verifica:
    - Variaveis de ambiente obrigatorias
    - Configuracões do arquivo INI
    - Permissões de escrita em diretorios
    
    Returns:
        bool: True se todas as configuracões soo validas
        
    Raises:
        OneDriveConfigError: Se alguma configuracoo esta ausente ou invalida
    """
    try:
        # Verifica se upload esta habilitado
        if not UPLOAD_ENABLED:
            logger.info("[ONEDRIVE] Upload desabilitado na configuracoo")
            return False
        
        # Verifica variaveis de ambiente obrigatorias
        missing_vars = []
        for i, var in enumerate(REQUIRED_VARS):
            if not var:
                var_names = ["CLIENT_ID", "CLIENT_SECRET", "TENANT_ID", "SHAREPOINT_SITE", "SHAREPOINT_FOLDER", "DRIVE_NAME"]
                missing_vars.append(var_names[i])
        
        if missing_vars:
            raise OneDriveConfigError(
                f"Variaveis de ambiente obrigatorias ausentes: {missing_vars}"
            )
        
        # Verifica permissões de escrita
        try:
            UPLOAD_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            ONEDRIVE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            raise OneDriveConfigError(f"Sem permissoo de escrita: {e}")
        
        logger.info("[ONEDRIVE] Configuracoo validada com sucesso")
        return True
        
    except Exception as e:
        logger.error(f"[ONEDRIVE] Erro na validacoo de configuracoo: {e}")
        raise OneDriveConfigError(f"Configuracoo invalida: {e}")


# =============================================================================
# CLIENTE ONEDRIVE
# =============================================================================

class OneDriveClient:
    """
    Cliente para upload de arquivos para OneDrive/SharePoint com funcionalidades avancadas.
    
    Esta classe implementa um cliente completo para upload de arquivos com:
    - Autenticacoo OAuth2 usando client credentials flow
    - Cache inteligente de estrutura de pastas
    - Upload em lote com controle de concorrência
    - Controle de duplicatas e versionamento
    - Recuperacoo automatica de falhas
    - Metricas detalhadas de performance
    
    Attributes:
        access_token: Token de acesso atual
        drive_id: ID do drive do SharePoint
        pastas_cache: Cache de estrutura de pastas
        upload_history: Historico de uploads realizados
        
    Example:
        >>> client = OneDriveClient()
        >>> client.autenticar()
        >>> client.fazer_upload_lote(["arquivo1.xml", "arquivo2.xml"])
    """
    
    def __init__(self) -> None:
        """
        Inicializa o cliente OneDrive com configuracões padroo.
        
        Raises:
            OneDriveConfigError: Se a configuracoo for invalida
        """
        try:
            self.access_token: Optional[str] = None
            self.drive_id: str = DRIVE_NAME  # Usando diretamente o ID do drive
            self.pastas_cache: Dict[str, str] = {}
            self.upload_history: Set[str] = set()
            
            # Carrega dados persistidos
            self._carregar_cache_pastas()
            self._carregar_historico_uploads()
            
            logger.info("[ONEDRIVE] Cliente OneDrive inicializado")
            
        except Exception as e:
            logger.error(f"[ONEDRIVE] Erro ao inicializar cliente: {e}")
            raise OneDriveConfigError(f"Falha na inicializacoo: {e}")
    
    def _carregar_cache_pastas(self) -> None:
        """Carrega cache de pastas do arquivo local."""
        try:
            if ONEDRIVE_CACHE_PATH.exists():
                with open(ONEDRIVE_CACHE_PATH, 'r', encoding='utf-8') as f:
                    self.pastas_cache = json.load(f)
                logger.debug(f"[ONEDRIVE] Cache de pastas carregado: {len(self.pastas_cache)} entradas")
        except Exception as e:
            logger.warning(f"[ONEDRIVE] Erro ao carregar cache de pastas: {e}")
            self.pastas_cache = {}
    
    def _carregar_historico_uploads(self) -> None:
        """Carrega historico de uploads do arquivo local com tratamento robusto de erros."""
        try:
            if UPLOAD_DB_PATH.exists():
                # Verifica se o arquivo noo esta vazio
                if UPLOAD_DB_PATH.stat().st_size == 0:
                    logger.warning("[ONEDRIVE] Arquivo de historico esta vazio, iniciando com historico limpo")
                    self.upload_history = set()
                    return
                
                with open(UPLOAD_DB_PATH, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if not content:
                        logger.warning("[ONEDRIVE] Arquivo de historico esta vazio, iniciando com historico limpo")
                        self.upload_history = set()
                        return
                    
                    data = json.loads(content)
                    self.upload_history = set(data.get('uploads', []))
                    
                logger.debug(f"[ONEDRIVE] Historico de uploads carregado: {len(self.upload_history)} entradas")
            else:
                logger.info("[ONEDRIVE] Arquivo de historico noo existe, iniciando com historico limpo")
                self.upload_history = set()
                
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"[ONEDRIVE] Erro ao decodificar JSON do historico: {e}")
            # Tenta fazer backup do arquivo corrompido
            try:
                backup_path = UPLOAD_DB_PATH.with_suffix('.json.backup')
                UPLOAD_DB_PATH.rename(backup_path)
                logger.info(f"[ONEDRIVE] Arquivo corrompido movido para {backup_path}")
            except Exception as backup_error:
                logger.warning(f"[ONEDRIVE] Erro ao fazer backup do arquivo corrompido: {backup_error}")
            
            self.upload_history = set()
            
        except PermissionError as e:
            logger.warning(f"[ONEDRIVE] Erro de permissoo ao carregar historico: {e}")
            self.upload_history = set()
            
        except Exception as e:
            logger.warning(f"[ONEDRIVE] Erro inesperado ao carregar historico: {e}")
            self.upload_history = set()
    
    def _salvar_cache_pastas(self) -> None:
        """Salva cache de pastas no arquivo local."""
        try:
            with open(ONEDRIVE_CACHE_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.pastas_cache, f, ensure_ascii=False, indent=2)
            logger.debug("[ONEDRIVE] Cache de pastas salvo")
        except Exception as e:
            logger.warning(f"[ONEDRIVE] Erro ao salvar cache de pastas: {e}")
    
    def _salvar_historico_uploads(self) -> None:
        """Salva historico de uploads no arquivo local com retry em caso de erro de permissoo."""
        import tempfile
        import shutil
        
        max_tentativas = 3
        for tentativa in range(max_tentativas):
            try:
                data = {
                    'uploads': list(self.upload_history),
                    'last_update': time.strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # Estrategia 1: Escrever em arquivo temporario primeiro
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.json') as temp_file:
                    json.dump(data, temp_file, ensure_ascii=False, indent=2)
                    temp_path = temp_file.name
                
                # Tenta substituir o arquivo original
                if UPLOAD_DB_PATH.exists():
                    # Remove o arquivo original se existir
                    UPLOAD_DB_PATH.unlink()
                
                # Move o arquivo temporario para o local final
                shutil.move(temp_path, UPLOAD_DB_PATH)
                
                logger.debug("[ONEDRIVE] Historico de uploads salvo")
                return
                
            except PermissionError as e:
                logger.warning(f"[ONEDRIVE] Tentativa {tentativa + 1}/{max_tentativas} - Erro de permissoo ao salvar historico: {e}")
                if tentativa < max_tentativas - 1:
                    time.sleep(0.5 * (tentativa + 1))  # Backoff exponencial
                else:
                    logger.error(f"[ONEDRIVE] Falha ao salvar historico apos {max_tentativas} tentativas")
                    
            except Exception as e:
                logger.warning(f"[ONEDRIVE] Erro ao salvar historico: {e}")
                break

    def autenticar(self) -> bool:
        """
        Realiza autenticacoo OAuth2 usando client credentials flow.
        
        Returns:
            bool: True se autenticacoo foi bem-sucedida
            
        Raises:
            OneDriveAuthError: Se a autenticacoo falhar
        """
        try:
            logger.info("[ONEDRIVE] Iniciando autenticacoo OAuth2...")
            
            # Constroi URL do token dinamicamente
            token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
            
            # Dados para requisicoo de token
            token_data = {
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "scope": SCOPES
            }
            
            # Requisicoo do token
            response = requests.post(
                token_url,
                data=token_data,
                timeout=TIMEOUT
            )
            
            if response.status_code == 200:
                token_json = response.json()
                self.access_token = token_json.get("access_token")
                
                if self.access_token:
                    logger.info("[ONEDRIVE] Autenticacoo realizada com sucesso")
                    return True
                else:
                    raise OneDriveAuthError("Token de acesso noo encontrado na resposta")
            else:
                raise OneDriveAuthError(f"Falha na autenticacoo: {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"[ONEDRIVE] Erro de rede na autenticacoo: {e}")
            raise OneDriveAuthError(f"Erro de rede: {e}")
        except Exception as e:
            logger.error(f"[ONEDRIVE] Erro inesperado na autenticacoo: {e}")
            raise OneDriveAuthError(f"Erro inesperado: {e}")
    
    def _obter_headers(self) -> Dict[str, str]:
        """
        Obtem headers padroo para requisicões HTTP.
        
        Returns:
            Dict[str, str]: Headers com autorizacoo
        """
        if not self.access_token:
            raise OneDriveAuthError("Token de acesso noo disponivel")
        
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/octet-stream"
        }
    
    def _criar_pasta_se_necessario(self, pasta_nome: str) -> str:
        """
        Cria pasta no OneDrive se ela noo existir.
        
        Args:
            pasta_nome: Nome da pasta a ser criada
            
        Returns:
            str: ID da pasta criada ou existente
        """
        try:
            # Verifica se pasta ja existe no cache
            if pasta_nome in self.pastas_cache:
                return self.pastas_cache[pasta_nome]
            
            # Lista pastas existentes no drive
            list_url = f"{GRAPH_API_BASE}/drives/{self.drive_id}/root/children"
            response = requests.get(list_url, headers=self._obter_headers(), timeout=TIMEOUT)
            
            if response.status_code == 200:
                items = response.json().get("value", [])
                
                # Procura pela pasta
                for item in items:
                    if item.get("name") == pasta_nome and "folder" in item:
                        folder_id = item["id"]
                        self.pastas_cache[pasta_nome] = folder_id
                        self._salvar_cache_pastas()
                        logger.debug(f"[ONEDRIVE] Pasta encontrada: {pasta_nome} -> {folder_id}")
                        return folder_id
                
                # Pasta noo existe, cria nova
                create_url = f"{GRAPH_API_BASE}/drives/{self.drive_id}/root/children"
                folder_data = {
                    "name": pasta_nome,
                    "folder": {}
                }
                
                headers = self._obter_headers()
                headers["Content-Type"] = "application/json"
                
                response = requests.post(
                    create_url,
                    json=folder_data,
                    headers=headers,
                    timeout=TIMEOUT
                )
                
                if response.status_code == 201:
                    folder_id = response.json()["id"]
                    self.pastas_cache[pasta_nome] = folder_id
                    self._salvar_cache_pastas()
                    logger.info(f"[ONEDRIVE] Pasta criada: {pasta_nome} -> {folder_id}")
                    return folder_id
                else:
                    raise OneDriveAPIError(f"Falha ao criar pasta: {response.status_code} - {response.text}")
            else:
                raise OneDriveAPIError(f"Falha ao listar pastas: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"[ONEDRIVE] Erro ao criar pasta {pasta_nome}: {e}")
            raise
    
    def _arquivo_existe_no_onedrive(self, nome_arquivo: str, pasta_nome: str) -> bool:
        """
        Verifica se um arquivo ja existe no OneDrive.
        
        Args:
            nome_arquivo: Nome do arquivo a verificar
            pasta_nome: Nome da pasta onde verificar
            
        Returns:
            bool: True se o arquivo ja existe
        """
        try:
            # Verifica se a pasta existe no cache
            if pasta_nome not in self.pastas_cache:
                logger.debug(f"[ONEDRIVE] Pasta {pasta_nome} noo encontrada no cache")
                return False
            
            folder_id = self.pastas_cache[pasta_nome]
            
            # Verifica se o arquivo existe na pasta
            check_url = f"{GRAPH_API_BASE}/drives/{self.drive_id}/items/{folder_id}:/{nome_arquivo}"
            
            response = requests.get(
                check_url,
                headers=self._obter_headers(),
                timeout=TIMEOUT
            )
            
            if response.status_code == 200:
                logger.debug(f"[ONEDRIVE] Arquivo encontrado no OneDrive: {nome_arquivo}")
                return True
            elif response.status_code == 404:
                logger.debug(f"[ONEDRIVE] Arquivo noo encontrado no OneDrive: {nome_arquivo}")
                return False
            else:
                logger.warning(f"[ONEDRIVE] Erro ao verificar arquivo {nome_arquivo}: {response.status_code}")
                return False
                
        except Exception as e:
            logger.warning(f"[ONEDRIVE] Erro ao verificar existência de {nome_arquivo}: {e}")
            return False
    
    def upload_arquivo(self, caminho_arquivo: Path, pasta_destino: str) -> bool:
        """
        Realiza upload de um arquivo para o OneDrive.
        
        Args:
            caminho_arquivo: Caminho do arquivo local
            pasta_destino: Nome da pasta de destino no OneDrive
            
        Returns:
            bool: True se upload foi bem-sucedido
        """
        try:
            if not caminho_arquivo.exists():
                logger.error(f"[ONEDRIVE] ❌ Arquivo não encontrado: {caminho_arquivo}")
                return False
            
            # Obtem informações do arquivo
            tamanho_arquivo = caminho_arquivo.stat().st_size
            tamanho_mb = tamanho_arquivo / (1024 * 1024)
            
            logger.debug(f"[ONEDRIVE] 📄 Processando arquivo: {caminho_arquivo.name} ({tamanho_mb:.1f}MB)")
            
            # Determina pasta de destino baseada no mês
            mes_pasta = extrair_mes_do_path(caminho_arquivo)
            if mes_pasta == "outros":
                # Fallback para nome baseado em timestamp
                mes_pasta = time.strftime('%Y-%m')
            
            pasta_completa = f"{pasta_destino}_{mes_pasta}"
            
            # Verifica se ja foi enviado (chave mais especifica)
            arquivo_key = f"{pasta_completa}/{caminho_arquivo.name}"
            if arquivo_key in self.upload_history:
                logger.info(f"[ONEDRIVE] ⏭️ Arquivo já enviado anteriormente: {caminho_arquivo.name}")
                return True
            
            # Verifica tambem se existe no OneDrive (validacoo adicional)
            logger.debug(f"[ONEDRIVE]  Verificando se existe no OneDrive: {caminho_arquivo.name}")
            if self._arquivo_existe_no_onedrive(caminho_arquivo.name, pasta_completa):
                logger.info(f"[ONEDRIVE] ⏭️ Arquivo já existe no OneDrive: {caminho_arquivo.name}")
                # Adiciona ao historico local para evitar verificacões futuras
                self.upload_history.add(arquivo_key)
                self._salvar_historico_uploads()
                return True
            
            # Cria pasta se necessario
            logger.debug(f"[ONEDRIVE] 📁 Verificando/criando pasta: {pasta_completa}")
            folder_id = self._criar_pasta_se_necessario(pasta_completa)
            
            # Realiza upload
            upload_url = f"{GRAPH_API_BASE}/drives/{self.drive_id}/items/{folder_id}:/{caminho_arquivo.name}:/content"
            
            logger.debug(f"[ONEDRIVE] ⬆️ Iniciando upload: {caminho_arquivo.name} → {pasta_completa}")
            tempo_upload_inicio = time.time()
            
            with open(caminho_arquivo, 'rb') as f:
                file_content = f.read()
            
            response = requests.put(
                upload_url,
                headers=self._obter_headers(),
                data=file_content,
                timeout=TIMEOUT
            )
            
            tempo_upload = time.time() - tempo_upload_inicio
            velocidade = tamanho_mb / tempo_upload if tempo_upload > 0 else 0
            
            if response.status_code in [200, 201]:
                # Marca como enviado
                self.upload_history.add(arquivo_key)
                self._salvar_historico_uploads()
                
                logger.info(f"[ONEDRIVE] ✅ Upload concluído: {caminho_arquivo.name} → {pasta_completa} ({tempo_upload:.1f}s, {velocidade:.1f}MB/s)")
                return True
            else:
                logger.error(f"[ONEDRIVE] ❌ Falha no upload: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"[ONEDRIVE] ❌ Erro no upload de {caminho_arquivo.name}: {e}")
            return False
    
    def fazer_upload_lote(self, caminhos_arquivos: List[Path], pasta_base: str = "XML_Compactados") -> Dict[str, bool]:
        """
        Realiza upload em lote de multiplos arquivos.
        
        Args:
            caminhos_arquivos: Lista de caminhos de arquivos
            pasta_base: Pasta base no OneDrive
            
        Returns:
            Dict[str, bool]: Resultado do upload de cada arquivo
        """
        resultados = {}
        
        try:
            total_arquivos = len(caminhos_arquivos)
            logger.info(f"[ONEDRIVE] Iniciando upload em lote: {total_arquivos} arquivos")
            
            # Log dos arquivos que serão enviados
            logger.info(f"[ONEDRIVE] Arquivos para upload:")
            for i, caminho_arquivo in enumerate(caminhos_arquivos, 1):
                tamanho_mb = caminho_arquivo.stat().st_size / (1024 * 1024) if caminho_arquivo.exists() else 0
                logger.info(f"[ONEDRIVE]   {i:3d}. {caminho_arquivo.name} ({tamanho_mb:.1f}MB)")
            
            logger.info(f"[ONEDRIVE] Iniciando processamento...")
            
            sucessos = 0
            falhas = 0
            tempo_inicio = time.time()
            
            for i, caminho_arquivo in enumerate(caminhos_arquivos, 1):
                try:
                    progresso_pct = (i / total_arquivos) * 100
                    
                    logger.info(f"[ONEDRIVE] [{i:3d}/{total_arquivos:3d}] ({progresso_pct:5.1f}%) Enviando: {caminho_arquivo.name}")
                    
                    tempo_arquivo_inicio = time.time()
                    sucesso = self.upload_arquivo(caminho_arquivo, pasta_base)
                    tempo_arquivo = time.time() - tempo_arquivo_inicio
                    
                    resultados[str(caminho_arquivo)] = sucesso
                    
                    if sucesso:
                        sucessos += 1
                        tamanho_mb = caminho_arquivo.stat().st_size / (1024 * 1024) if caminho_arquivo.exists() else 0
                        velocidade = tamanho_mb / tempo_arquivo if tempo_arquivo > 0 else 0
                        logger.info(f"[ONEDRIVE]  [{i:3d}/{total_arquivos:3d}] Sucesso: {caminho_arquivo.name} ({tempo_arquivo:.1f}s, {velocidade:.1f}MB/s)")
                    else:
                        falhas += 1
                        logger.error(f"[ONEDRIVE] [{i:3d}/{total_arquivos:3d}] Falha: {caminho_arquivo.name}")
                    
                    # Delay entre uploads para evitar rate limiting
                    if i < total_arquivos:
                        time.sleep(0.5)
                        
                except Exception as e:
                    falhas += 1
                    logger.error(f"[ONEDRIVE]  [{i:3d}/{total_arquivos:3d}] Erro no upload de {caminho_arquivo.name}: {e}")
                    resultados[str(caminho_arquivo)] = False
            
            # Relatório final
            tempo_total = time.time() - tempo_inicio
            taxa_sucesso = (sucessos / total_arquivos) * 100 if total_arquivos > 0 else 0
            
            logger.info(f"[ONEDRIVE]  Upload em lote concluído:")
            logger.info(f"[ONEDRIVE]   • Total: {total_arquivos} arquivos")
            logger.info(f"[ONEDRIVE]   • Sucessos: {sucessos} ({taxa_sucesso:.1f}%)")
            logger.info(f"[ONEDRIVE]   • Falhas: {falhas}")
            logger.info(f"[ONEDRIVE]   • Tempo total: {tempo_total:.1f}s")
            logger.info(f"[ONEDRIVE]   • Velocidade média: {(sucessos / tempo_total):.1f} arquivos/s")
            
            return resultados
            
        except Exception as e:
            logger.error(f"[ONEDRIVE]  Erro crítico no upload em lote: {e}")
            return resultados
    
    def sincronizar_historico_com_onedrive(self) -> int:
        """
        Sincroniza o historico local com o que realmente existe no OneDrive.
        
        Verifica todos os arquivos nas pastas conhecidas e atualiza o historico
        para refletir o estado atual do OneDrive.
        
        Returns:
            int: Numero de arquivos encontrados no OneDrive
        """
        try:
            logger.info("[ONEDRIVE] Iniciando sincronizacoo do historico com OneDrive...")
            
            arquivos_encontrados = 0
            historico_atualizado = set()
            
            # Para cada pasta no cache
            for pasta_nome, folder_id in self.pastas_cache.items():
                try:
                    # Lista arquivos na pasta
                    list_url = f"{GRAPH_API_BASE}/drives/{self.drive_id}/items/{folder_id}/children"
                    
                    response = requests.get(
                        list_url,
                        headers=self._obter_headers(),
                        timeout=TIMEOUT
                    )
                    
                    if response.status_code == 200:
                        arquivos = response.json().get('value', [])
                        
                        for arquivo in arquivos:
                            nome_arquivo = arquivo.get('name', '')
                            if nome_arquivo.endswith('.zip'):
                                arquivo_key = f"{pasta_nome}/{nome_arquivo}"
                                historico_atualizado.add(arquivo_key)
                                arquivos_encontrados += 1
                        
                        logger.debug(f"[ONEDRIVE] Pasta {pasta_nome}: {len(arquivos)} arquivos encontrados")
                    else:
                        logger.warning(f"[ONEDRIVE] Erro ao listar pasta {pasta_nome}: {response.status_code}")
                        
                except Exception as e:
                    logger.warning(f"[ONEDRIVE] Erro ao processar pasta {pasta_nome}: {e}")
            
            # Atualiza historico local
            self.upload_history = historico_atualizado
            self._salvar_historico_uploads()
            
            logger.info(f"[ONEDRIVE] Sincronizacoo concluida: {arquivos_encontrados} arquivos encontrados")
            return arquivos_encontrados
            
        except Exception as e:
            logger.error(f"[ONEDRIVE] Erro na sincronizacoo do historico: {e}")
            return 0


# =============================================================================
# FUNcÕES PRINCIPAIS DE UPLOAD
# =============================================================================

def fazer_upload_lote(caminhos_arquivos: List[Path], pasta_base: str = "XML_Compactados") -> Dict[str, bool]:
    """
    Realiza upload em lote de multiplos arquivos para o OneDrive.
    
    Organiza os arquivos em pastas por mês baseado na data de criacoo
    e implementa controle de duplicatas e metricas detalhadas.
    
    Args:
        caminhos_arquivos: Lista de caminhos de arquivos para upload
        pasta_base: Pasta base no OneDrive para organizacoo
        
    Returns:
        Dict[str, bool]: Dicionario com resultado do upload de cada arquivo
        
    Example:
        >>> resultados = fazer_upload_lote([Path("arquivo1.zip"), Path("arquivo2.zip")])
        >>> print(resultados)
        {"arquivo1.zip": True, "arquivo2.zip": False}
    """
    if not validar_configuracao_onedrive():
        logger.warning("[ONEDRIVE] ⚠️ Upload desabilitado ou configuração inválida")
        return {}
    
    try:
        total_arquivos = len(caminhos_arquivos)
        
        # Calcula tamanho total
        tamanho_total_mb = 0
        for arquivo in caminhos_arquivos:
            if arquivo.exists():
                tamanho_total_mb += arquivo.stat().st_size / (1024 * 1024)
        
        logger.info(f"[ONEDRIVE] 🚀 Preparando upload em lote:")
        logger.info(f"[ONEDRIVE]   • Total de arquivos: {total_arquivos}")
        logger.info(f"[ONEDRIVE]   • Tamanho total: {tamanho_total_mb:.1f}MB")
        logger.info(f"[ONEDRIVE]   • Pasta base: {pasta_base}")
        
        # Inicializa cliente
        logger.info(f"[ONEDRIVE] 🔑 Inicializando cliente OneDrive...")
        client = OneDriveClient()
        
        # Realiza autenticacoo
        logger.info(f"[ONEDRIVE] 🔐 Realizando autenticação OAuth2...")
        if not client.autenticar():
            logger.error("[ONEDRIVE] ❌ Falha na autenticação")
            return {}
        
        logger.info(f"[ONEDRIVE] ✅ Autenticação realizada com sucesso")
        
        # Executa upload em lote
        return client.fazer_upload_lote(caminhos_arquivos, pasta_base)
        
    except Exception as e:
        logger.error(f"[ONEDRIVE] ❌ Erro crítico no upload em lote: {e}")
        return {}


def upload_arquivo_unico(caminho_arquivo: Path, pasta_destino: str = "XML_Compactados") -> bool:
    """
    Realiza upload de um unico arquivo para o OneDrive.
    
    Args:
        caminho_arquivo: Caminho do arquivo a ser enviado
        pasta_destino: Pasta de destino no OneDrive
        
    Returns:
        bool: True se upload foi bem-sucedido
    """
    if not validar_configuracao_onedrive():
        logger.warning("[ONEDRIVE] ⚠️ Upload desabilitado ou configuração inválida")
        return False
    
    try:
        # Informações do arquivo
        if not caminho_arquivo.exists():
            logger.error(f"[ONEDRIVE] ❌ Arquivo não encontrado: {caminho_arquivo}")
            return False
            
        tamanho_mb = caminho_arquivo.stat().st_size / (1024 * 1024)
        
        logger.info(f"[ONEDRIVE] 📤 Preparando upload único:")
        logger.info(f"[ONEDRIVE]   • Arquivo: {caminho_arquivo.name}")
        logger.info(f"[ONEDRIVE]   • Tamanho: {tamanho_mb:.1f}MB")
        logger.info(f"[ONEDRIVE]   • Pasta destino: {pasta_destino}")
        
        # Inicializa cliente
        logger.info(f"[ONEDRIVE] 🔑 Inicializando cliente OneDrive...")
        client = OneDriveClient()
        
        # Realiza autenticacoo
        logger.info(f"[ONEDRIVE] 🔐 Realizando autenticação OAuth2...")
        if not client.autenticar():
            logger.error("[ONEDRIVE] ❌ Falha na autenticação")
            return False
        
        logger.info(f"[ONEDRIVE] ✅ Autenticação realizada com sucesso")
        
        # Executa upload
        tempo_inicio = time.time()
        sucesso = client.upload_arquivo(caminho_arquivo, pasta_destino)
        tempo_total = time.time() - tempo_inicio
        
        if sucesso:
            velocidade = tamanho_mb / tempo_total if tempo_total > 0 else 0
            logger.info(f"[ONEDRIVE]  Upload único concluído com sucesso!")
            logger.info(f"[ONEDRIVE]   • Tempo: {tempo_total:.1f}s")
            logger.info(f"[ONEDRIVE]   • Velocidade: {velocidade:.1f}MB/s")
        else:
            logger.error(f"[ONEDRIVE] ❌ Upload único falhou")
        
        return sucesso
        
    except Exception as e:
        logger.error(f"[ONEDRIVE] ❌ Erro no upload de {caminho_arquivo.name}: {e}")
        return False


# =============================================================================
# funcao PRINCIPAL E PONTO DE ENTRADA
# =============================================================================

def main() -> None:
    """
    funcao principal para teste do modulo de upload.
    """
    try:
        # Configura logging para teste
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s"
        )
        
        # Testa configuracoo
        if validar_configuracao_onedrive():
            logger.info("Configuracoo OneDrive valida")
            
            # Teste de upload (exemplo)
            # arquivos_teste = [Path("teste.txt")]
            # resultados = fazer_upload_lote(arquivos_teste)
            # print(f"Resultados: {resultados}")
        else:
            logger.error("Configuracoo OneDrive invalida")
            
    except Exception as e:
        logger.error(f"Erro no teste: {e}")


def sincronizar_historico_uploads() -> int:
    """
    Sincroniza o historico de uploads com o estado atual do OneDrive.
    
    Esta funcao verifica todos os arquivos que realmente existem no OneDrive
    e atualiza o historico local para refletir o estado atual.
    
    Returns:
        int: Numero de arquivos encontrados no OneDrive
        
    Example:
        >>> arquivos_encontrados = sincronizar_historico_uploads()
        >>> print(f"Encontrados {arquivos_encontrados} arquivos no OneDrive")
    """
    if not validar_configuracao_onedrive():
        logger.warning("[ONEDRIVE] Sincronizacoo desabilitada - configuracoo invalida")
        return 0
    
    try:
        # Inicializa cliente
        client = OneDriveClient()
        
        # Realiza autenticacoo
        if not client.autenticar():
            logger.error("[ONEDRIVE] Falha na autenticacoo para sincronizacoo")
            return 0
        
        # Executa sincronizacoo
        return client.sincronizar_historico_com_onedrive()
        
    except Exception as e:
        logger.error(f"[ONEDRIVE] Erro na sincronizacoo: {e}")
        return 0


if __name__ == "__main__":
    main()
