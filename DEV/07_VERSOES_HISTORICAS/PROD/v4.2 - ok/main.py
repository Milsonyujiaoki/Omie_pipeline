import logging
import configparser
import asyncio
from datetime import datetime
from pathlib import Path
import importlib

# Modulos locais
from src.Old import limitador_por_pasta
from src import report_arquivos_vazios
from src import verificador_xmls
from src import atualizar_query_params_ini
from src import extrator_async


def configurar_logging() -> None:
    log_dir = Path("log")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"main_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )


def carregar_configuracoes(config_path: str = "configuracao.ini") -> dict:
    config = configparser.ConfigParser()
    config.read(config_path)

    resultado_dir = config.get("paths", "resultado_dir", fallback="resultado")
    data_zip_str = config.get("paths", "data_zip", fallback=datetime.today().strftime('%Y-%m-%d'))
    data_zip = datetime.strptime(data_zip_str, "%Y-%m-%d")
    pasta_zip = Path(resultado_dir) / data_zip.strftime('%Y') / data_zip.strftime('%m') / data_zip.strftime('%d')
    modo_download = config.get("api_speed", "modo_download", fallback="async").lower()

    return {
        "resultado_dir": resultado_dir,
        "pasta_zip": str(pasta_zip),
        "modo_download": modo_download
    }


def executar_limitador_por_pasta(pasta: str) -> None:
    try:
        logging.info(f"📦 Compactando arquivos em: {pasta}")
        limitador_por_pasta.separar_em_pastas_e_zipar(pasta)
        logging.info("📦 Compactacoo finalizada.")
    except Exception as e:
        logging.exception(f"Erro ao executar compactacoo: {e}")


def executar_relatorio_arquivos_vazios(pasta: str) -> None:
    try:
        logging.info(f"📋 Gerando relatorio de arquivos vazios em: {pasta}")
        report_arquivos_vazios.gerar_relatorio(pasta)
        logging.info("✅ Relatorio gerado.")
    except Exception as e:
        logging.exception(f"Erro no relatorio de arquivos vazios: {e}")


def executar_verificador_xmls() -> None:
    try:
        logging.info(" Verificando arquivos XML ja baixados...")
        verificador_xmls.verificar()
        logging.info(" verificacao concluida.")
    except Exception as e:
        logging.exception(f"Erro na verificacao de XMLs: {e}")


def executar_pipeline(config: dict) -> None:
    if config['modo_download'] == 'async':
        asyncio.run(extrator_async.main())
    else:
        # Executa o modo paralelo completo via import dinâmico
        logging.info("⚙️ Executando modo paralelo completo via baixar_parallel.main()")
        baixar_parallel = importlib.import_module("src.baixar_parallel")
        baixar_parallel.main()


def main():
    configurar_logging()
    logging.info("🔧 Iniciando pipeline do Extrator Omie V3...")

    config = carregar_configuracoes()
    resultado_dir = config['resultado_dir']
    pasta_zip = config['pasta_zip']

    executar_pipeline(config)
    executar_verificador_xmls()
    executar_limitador_por_pasta(pasta_zip)
    executar_relatorio_arquivos_vazios(resultado_dir)

    logging.info("✅ Pipeline completa com sucesso.")


if __name__ == "__main__":
    main()
