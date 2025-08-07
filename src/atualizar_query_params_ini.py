# atualizar_query_params_ini_v2.py

import configparser
from datetime import datetime, timedelta
import calendar
import logging
from pathlib import Path
from typing import Optional

# Logger centralizado
logger = logging.getLogger(__name__)

def eh_fim_de_semana_ou_feriado(data: datetime, feriados: Optional[list[datetime]] = None) -> bool:
    """
    Verifica se a data informada e um sabado, domingo ou feriado.

    Args:
        data: Data a ser avaliada.
        feriados: Lista opcional de feriados (datetime).

    Returns:
        True se for fim de semana ou feriado, False caso contrario.
    """
    if data.weekday() >= 5:  # sabado (5) ou domingo (6)
        return True
    if feriados and data.date() in [f.date() for f in feriados]:
        return True
    return False


def carregar_feriados(arquivo: str = 'feriados.txt') -> list[datetime]:
    """
    Carrega uma lista de feriados a partir de um arquivo texto.

    Args:
        arquivo: Nome do arquivo contendo as datas dos feriados no formato dd/mm/aaaa.

    Returns:
        Lista de objetos datetime representando os feriados.
    """
    caminho = Path(arquivo)
    if not caminho.exists():
        return []  # Retorna lista vazia se o arquivo noo existir

    with caminho.open('r', encoding='utf-8') as f:
        return [
            datetime.strptime(linha.strip(), "%d/%m/%Y")
            for linha in f
            if linha.strip()
        ]


def atualizar_datas_configuracao_ini():
    """
    Atualiza os parâmetros `start_date` e `end_date` no arquivo de configuracoo INI,
    garantindo que `start_date` corresponda ao ultimo dia util anterior
    (ignorando finais de semana e feriados) e `end_date` ao ultimo dia do mês atual.

    - Lê caminho do arquivo INI a partir da secoo `[paths]`.
    - Lê e atualiza a secoo `[query_params]`.
    - Considera o arquivo 'feriados.txt' para validacoo de dias uteis.
    """
    config = configparser.ConfigParser()
    config.read('configuracao.ini', encoding='utf-8')

    # Verificar se a seção query_params existe
    if 'query_params' not in config:
        logger.error("Seção [query_params] não encontrada no arquivo de configuração!")
        # Criar a seção se não existir
        config['query_params'] = {}
        config['query_params']['start_date'] = '01/06/2025'
        config['query_params']['end_date'] = '31/12/2025'
        config['query_params']['records_per_page'] = '200'
        logger.info("Seção [query_params] criada com valores padrão")

    # Obtem o caminho real do arquivo de configuracoo a ser atualizado
    caminho_arquivo = 'configuracao.ini'  # Usa o próprio arquivo de configuração
    formato_data = "%d/%m/%Y"

    # Carrega lista de feriados, se houver
    feriados = carregar_feriados()

    hoje = datetime.today()
    ontem = hoje - timedelta(days=1)

    # Retrocede ate encontrar o ultimo dia util (desconsiderando finais de semana e feriados)
    while eh_fim_de_semana_ou_feriado(ontem, feriados):
        ontem -= timedelta(days=1)

    # Define o ultimo dia do mês atual para o campo end_date
    ultimo_dia_mes = calendar.monthrange(hoje.year, hoje.month)[1]
    end_date = datetime(hoje.year, hoje.month, ultimo_dia_mes)

    # Atualiza os valores no dicionario de configuracoo
    config['query_params']['start_date'] = ontem.strftime(formato_data)
    config['query_params']['end_date'] = end_date.strftime(formato_data)

    # Escreve as alteracões no arquivo INI
    with open(caminho_arquivo, 'w', encoding='utf-8') as configfile:
        config.write(configfile)

    # Loga as alteracões realizadas
    logging.info(f"start_date atualizado: {config['query_params']['start_date']}")
    logging.info(f"end_date atualizado: {config['query_params']['end_date']}")


# Ponto de entrada do script
if __name__ == "__main__":
    atualizar_datas_configuracao_ini()
