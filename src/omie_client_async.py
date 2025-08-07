# omie_client_async_v4.py

import asyncio
import aiohttp
import configparser
from typing import Any, Callable, Coroutine
from functools import wraps

# ==============================================================================
# Decorador de Retry para chamadas assincronas
# ==============================================================================

def with_retries(max_retries: int = 3, delay: float = 1.0):
    """
    Decorador para aplicar tentativas automaticas com atraso exponencial em chamadas assincronas.

    Args:
        max_retries: Numero maximo de tentativas antes de lancar excecoo.
        delay: Tempo base de espera (em segundos) entre tentativas.

    Returns:
        funcao decorada com comportamento de retry.
    """
    def decorator(func: Callable[..., Coroutine[Any, Any, Any]]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        raise  # ultima tentativa: propaga erro
                    await asyncio.sleep(delay * attempt)  # Atraso exponencial progressivo
        return wrapper
    return decorator

# ==============================================================================
# Cliente assincrono para a API Omie
# ==============================================================================

class OmieClient:
    """
    Cliente assincrono para chamadas à API do Omie, com controle de concorrência (via Semaphore)
    e suporte a multiplas chamadas por segundo (limitadas por configuracoo).
    """

    def __init__(
        self,
        app_key: str,
        app_secret: str,
        calls_per_second: int = 4,
        base_url_nf: str = "https://app.omie.com.br/api/v1/produtos/nfconsultar/",
        base_url_xml: str = "https://app.omie.com.br/api/v1/produtos/dfedocs/"
    ):
        """
        Inicializa o cliente com as credenciais da API e parâmetros de controle.

        Args:
            app_key: Chave do aplicativo Omie.
            app_secret: Segredo do aplicativo Omie.
            calls_per_second: Numero maximo de chamadas simultâneas permitidas.
            base_url_nf: URL da API para listagem de NFs.
            base_url_xml: URL da API para download de XMLs.
        """
        self.app_key = app_key
        self.app_secret = app_secret
        self.base_url_nf = base_url_nf
        self.base_url_xml = base_url_xml
        self.semaphore = asyncio.Semaphore(calls_per_second)  # Limita concorrência simultânea

    @with_retries(max_retries=3, delay=2)
    async def call_api(
        self,
        session: aiohttp.ClientSession,
        metodo: str,
        params: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Realiza uma chamada assincrona POST para a API Omie usando a sessoo informada.

        Args:
            session: Sessoo HTTP reutilizavel (recomendada com `aiohttp.ClientSession()`).
            metodo: Nome do metodo da API Omie a ser chamado (ex: "ListarNF", "ObterNfe").
            params: Parâmetros do metodo (dicionario).

        Returns:
            Dicionario com a resposta JSON da API.

        Raises:
            ValueError: Se a resposta noo for um JSON valido do tipo esperado.
            HTTPError: Em caso de falha de status HTTP.
        """
        payload = {
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "call": metodo,
            "param": [params],
        }

        # Define a URL correta com base no tipo de chamada
        url = self.base_url_nf if metodo == "ListarNF" else self.base_url_xml

        async with self.semaphore:  # Limita chamadas simultâneas
            async with session.post(url, json=payload, timeout=60) as response:
                response.raise_for_status()
                resultado = await response.json()
                if not isinstance(resultado, dict):
                    raise ValueError("Resposta inesperada da API Omie")
                return resultado


# ==============================================================================
# Carregamento de configuracões do arquivo INI
# ==============================================================================

def carregar_configuracoes_client(path_arquivo: str = 'configuracao.ini') -> dict[str, Any]:
    """
    Carrega e interpreta o arquivo INI com as credenciais e parâmetros da API.

    Args:
        path_arquivo: Caminho do arquivo de configuracoo INI.

    Returns:
        Dicionario contendo chaves de configuracoo da API.
    """
    config = configparser.ConfigParser()
    config.read(path_arquivo, encoding='utf-8')

    return {
        "app_key": config['omie_api']['app_key'],
        "app_secret": config['omie_api']['app_secret'],
        "start_date": config['query_params']['start_date'],
        "end_date": config['query_params']['end_date'],
        "records_per_page": int(config['query_params']['records_per_page']),
        "calls_per_second": int(config['omie_api']['calls_per_second']),
        "base_url_nf": config.get(
            'omie_api',
            'base_url_nf',
            fallback='https://app.omie.com.br/api/v1/produtos/nfconsultar/'
        ),
        "base_url_xml": config.get(
            'omie_api',
            'base_url_xml',
            fallback='https://app.omie.com.br/api/v1/produtos/dfedocs/'
        )
    }
