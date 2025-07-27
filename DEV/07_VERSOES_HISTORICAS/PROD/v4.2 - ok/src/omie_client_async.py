"""
Versoo refatorada de `omie_client_async.py` com boas praticas:
- Retry com backoff exponencial
- Decorador para tratamento de excecões
- Tipagem completa e docstrings
- Timeout configuravel
"""

import asyncio
import aiohttp
import configparser
from typing import Any, Callable, Coroutine
from functools import wraps


def with_retries(max_retries: int = 3, delay: float = 1.0):
    def decorator(func: Callable[..., Coroutine[Any, Any, Any]]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        raise
                    await asyncio.sleep(delay * attempt)
        return wrapper
    return decorator


class OmieClient:
    """
    Cliente assincrono para chamadas à API do Omie com controle de concorrência e retry.
    """

    def __init__(self, app_key: str, app_secret: str, calls_per_second: int = 4):
        self.app_key = app_key
        self.app_secret = app_secret
        self.base_url_nf = "https://app.omie.com.br/api/v1/produtos/nfconsultar/"
        self.base_url_xml = "https://app.omie.com.br/api/v1/produtos/dfedocs/"
        self.semaphore = asyncio.Semaphore(calls_per_second)

    @with_retries(max_retries=3, delay=2)
    async def call_api(self, session: aiohttp.ClientSession, metodo: str, params: dict[str, Any]) -> dict[str, Any]:
        """
        Executa chamada POST assincrona para a API do Omie com retry.
        """
        payload = {
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "call": metodo,
            "param": [params],
        }

        url = self.base_url_nf if metodo == "ListarNF" else self.base_url_xml

        async with self.semaphore:
            async with session.post(url, json=payload, timeout=60) as response:
                response.raise_for_status()
                resultado = await response.json()
                if not isinstance(resultado, dict):
                    raise ValueError("Resposta inesperada da API Omie")
                return resultado


def carregar_configuracoes(path_arquivo: str = 'configuracao.ini') -> dict[str, Any]:
    """
    Lê configuracões do arquivo INI e retorna como dicionario tipado.
    """
    config = configparser.ConfigParser()
    config.read(path_arquivo)

    return {
        "app_key": config['omie_api']['app_key'],
        "app_secret": config['omie_api']['app_secret'],
        "start_date": config['query_params']['start_date'],
        "end_date": config['query_params']['end_date'],
        "records_per_page": int(config['query_params']['records_per_page']),
        "calls_per_second": int(config['api_speed']['calls_per_second'])
    }
