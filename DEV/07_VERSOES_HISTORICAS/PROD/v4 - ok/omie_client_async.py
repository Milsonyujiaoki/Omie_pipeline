# omie_client_async.py

import asyncio
import aiohttp
import configparser
from typing import Any

class OmieClient:
    """
    Cliente assincrono para chamadas à API do Omie com controle de concorrência.
    """

    def __init__(self, app_key: str, app_secret: str, calls_per_second: int = 4):
        self.app_key = app_key
        self.app_secret = app_secret
        self.base_url_nf = "https://app.omie.com.br/api/v1/produtos/nfconsultar/"
        self.base_url_xml = "https://app.omie.com.br/api/v1/produtos/dfedocs/"
        self.semaphore = asyncio.Semaphore(calls_per_second)

    async def call_api(self, session: aiohttp.ClientSession, metodo: str, params: dict) -> dict[str, Any]:
        """
        Executa chamada POST assincrona para a API do Omie.
        """
        payload = {
            "app_key": self.app_key,
            "app_secret": self.app_secret,
            "call": metodo,
            "param": [params],
        }

        url = self.base_url_nf if metodo == "ListarNF" else self.base_url_xml

        async with self.semaphore:
            try:
                async with session.post(url, json=payload, timeout=60) as response:
                    response.raise_for_status()
                    return await response.json()
            except aiohttp.ClientResponseError as e:
                print(f"[ERRO] {metodo} falhou - status {e.status}: {e.message}")
                raise
            except Exception as e:
                print(f"[ERRO] {metodo} falhou: {e}")
                raise


def carregar_configuracoes(path_arquivo: str = 'configuracao.ini') -> dict:
    """
    Lê configuracões do arquivo INI e retorna como dicionario.
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
