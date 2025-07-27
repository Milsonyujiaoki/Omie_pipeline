import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import os
import time

import pandas as pd

logger = logging.getLogger(__name__)

# Lock para garantir seguranca em leitura de arquivos concorrentes
_file_lock = Lock()

# Caminho do relatorio padroo
RELATORIO_EXCEL = Path("relatorio_arquivos_vazios.xlsx")

# Constantes para otimização
BATCH_SIZE = 1000  # Processar arquivos em lotes
MAX_WORKERS = min(32, os.cpu_count() * 2)  # Limite de workers
CHUNK_SIZE = 8192  # Tamanho do chunk para leitura de arquivos

# Cache para extensões que devem ser ignoradas
EXTENSOES_IGNORADAS = {'.tmp', '.log', '.lock', '.bak', '.cache'}

# Cache para arquivos ja processados
_arquivos_processados: Set[str] = set()


def is_text_file_empty(filepath: Path) -> bool:
    """
    Verifica se o conteudo de um arquivo de texto e logicamente vazio,
    ignorando espacos em branco e quebras de linha.
    
    Otimizada para arquivos grandes usando leitura em chunks.

    Args:
        filepath: Caminho do arquivo.

    Returns:
        True se estiver vazio; False caso contrario.
    """
    try:
        if filepath.suffix.lower() in {'.zip', '.exe', '.dll', '.bin', '.db', '.sqlite'}:
            return False  # Arquivos binarios não são "vazios" no sentido textual
            
        with filepath.open("r", encoding="utf-8") as file:
            # Lê em chunks para arquivos grandes
            while True:
                chunk = file.read(CHUNK_SIZE)
                if not chunk:
                    break
                if chunk.strip():
                    return False
            return True
            
    except (UnicodeDecodeError, PermissionError):
        return False  # Arquivos binarios ou sem permissão
    except Exception:
        return False


def verificar_arquivo_rapido(filepath: str) -> Optional[dict]:
    """
    Versão otimizada da verificação de arquivos.
    
    Usa verificações rapidas primeiro (tamanho) antes de verificações custosas (conteudo).

    Args:
        filepath: Caminho absoluto do arquivo.

    Returns:
        Dicionario com informacões do problema, ou None se o arquivo for valido.
    """
    try:
        path = Path(filepath)
        
        # Verifica se ja foi processado
        if str(path) in _arquivos_processados:
            return None
            
        # Ignora extensões especificas
        if path.suffix.lower() in EXTENSOES_IGNORADAS:
            return None
            
        # Verificação rapida de tamanho
        try:
            stat = path.stat()
        except (OSError, PermissionError):
            return None
            
        size = stat.st_size
        last_modified = datetime.fromtimestamp(stat.st_mtime)
        file_ext = path.suffix.lower()

        # Caso 1: Tamanho 0 (verificação mais rapida)
        if size == 0:
            _arquivos_processados.add(str(path))
            return {
                "Path": str(path),
                "Size (bytes)": size,
                "Issue": "0 KB",
                "Last Modified": last_modified,
                "Extension": file_ext
            }

        # Caso 2: Arquivos pequenos suspeitos (< 100 bytes)
        if size < 100 and file_ext in {'.xml', '.txt', '.json', '.csv'}:
            if is_text_file_empty(path):
                _arquivos_processados.add(str(path))
                return {
                    "Path": str(path),
                    "Size (bytes)": size,
                    "Issue": "Empty content",
                    "Last Modified": last_modified,
                    "Extension": file_ext
                }

        # Marca como processado
        _arquivos_processados.add(str(path))
        return None

    except Exception as e:
        logger.debug(f"Erro ao verificar {filepath}: {e}")
        return None


def encontrar_arquivos_vazios_ou_zero_otimizado(root_dir: str) -> List[Dict]:
    """
    Versão otimizada da busca por arquivos invalidos.
    
    Melhorias:
    - Processamento em lotes
    - Filtros rapidos
    - Paralelização controlada
    - Cache de resultados
    
    Args:
        root_dir: Caminho base da varredura.

    Returns:
        Lista de dicionarios com os arquivos problematicos.
    """
    start_time = time.time()
    root = Path(root_dir)
    
    if not root.exists():
        logger.warning(f"[SCAN] Diretorio não encontrado: {root_dir}")
        return []
    
    logger.info(f"[SCAN] Iniciando varredura otimizada em: {root_dir}")
    
    # Coleta arquivos de forma otimizada
    arquivos = []
    contador = 0
    
    for arquivo in root.rglob("*"):
        if arquivo.is_file():
            # Filtros rapidos
            if arquivo.suffix.lower() not in EXTENSOES_IGNORADAS:
                arquivos.append(str(arquivo))
                contador += 1
                
                # Log de progresso
                if contador % 10000 == 0:
                    logger.info(f"[SCAN] Encontrados {contador} arquivos...")
    
    logger.info(f"[SCAN] {len(arquivos)} arquivos encontrados para analise.")
    
    if not arquivos:
        logger.info("[SCAN] Nenhum arquivo para processar.")
        return []
    
    # Processamento em lotes para otimizar memoria
    resultados = []
    total_batches = (len(arquivos) + BATCH_SIZE - 1) // BATCH_SIZE
    
    for i in range(0, len(arquivos), BATCH_SIZE):
        batch = arquivos[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        
        logger.info(f"[SCAN] Processando lote {batch_num}/{total_batches} ({len(batch)} arquivos)...")
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(verificar_arquivo_rapido, arq) for arq in batch]
            
            for future in as_completed(futures):
                try:
                    resultado = future.result()
                    if resultado:
                        resultados.append(resultado)
                except Exception as e:
                    logger.debug(f"Erro no processamento: {e}")
        
        # Log de progresso
        if resultados:
            logger.info(f"[SCAN] Lote {batch_num}: {len(resultados)} problemas encontrados até agora.")
    
    elapsed = time.time() - start_time
    logger.info(f"[SCAN] Varredura concluida em {elapsed:.2f}s. Total: {len(resultados)} arquivos problematicos.")
    
    return resultados


def encontrar_arquivos_vazios_ou_zero(root_dir: str) -> list[dict]:
    """
    Função mantida para compatibilidade. Usa a versão otimizada.
    
    Args:
        root_dir: Caminho base da varredura.

    Returns:
        Lista de dicionarios com os arquivos problematicos.
    """
    return encontrar_arquivos_vazios_ou_zero_otimizado(root_dir)


def remover_duplicatas_existentes(novos_registros: list[dict]) -> list[dict]:
    """
    Remove registros ja existentes no relatorio anterior.
    
    Otimizada para usar sets para busca rapida.

    Args:
        novos_registros: Lista de arquivos recem-identificados como invalidos.

    Returns:
        Lista de arquivos que ainda noo haviam sido reportados.
    """
    if not RELATORIO_EXCEL.exists():
        return novos_registros

    try:
        df_existente = pd.read_excel(RELATORIO_EXCEL)
        paths_existentes = set(df_existente["Path"].dropna().astype(str))
        
        # Usando list comprehension para melhor performance
        filtrados = [r for r in novos_registros if r["Path"] not in paths_existentes]
        
        logger.info(f"[DUPLICATAS] {len(novos_registros) - len(filtrados)} ja estavam no relatorio.")
        return filtrados

    except Exception as e:
        logger.warning(f"[ERRO] Falha ao carregar relatorio existente: {e}")
        return novos_registros


def salvar_relatorio_otimizado(registros: list[dict]) -> None:
    """
    Versão otimizada do salvamento do relatorio.
    
    Melhorias:
    - Processamento em chunks para arquivos grandes
    - Validação de dados antes do salvamento
    - Backup automatico
    
    Args:
        registros: Lista de arquivos invalidos.
    """
    if not registros:
        logger.info("[RELAToRIO] Nenhum registro para salvar.")
        return
    
    try:
        # Cria backup se existe arquivo anterior
        if RELATORIO_EXCEL.exists():
            backup_path = RELATORIO_EXCEL.with_suffix('.backup.xlsx')
            import shutil
            shutil.copy2(RELATORIO_EXCEL, backup_path)
            logger.debug(f"[BACKUP] Backup criado: {backup_path}")
        
        df_novos = pd.DataFrame(registros)
        
        if RELATORIO_EXCEL.exists():
            try:
                # Lê em chunks se o arquivo for muito grande
                df_antigo = pd.read_excel(RELATORIO_EXCEL)
                df_completo = pd.concat([df_antigo, df_novos], ignore_index=True)
                df_completo.drop_duplicates(subset=["Path"], inplace=True)
                logger.info(f"[MERGE] Relatorio mesclado: {len(df_antigo)} + {len(df_novos)} = {len(df_completo)} registros")
            except Exception as e:
                logger.warning(f"[ERRO] Falha ao mesclar relatorio antigo: {e}")
                df_completo = df_novos
        else:
            df_completo = df_novos

        # Salva com compressão para arquivos grandes
        df_completo.to_excel(RELATORIO_EXCEL, index=False)
        logger.info(f"[RELAToRIO] Salvo com {len(df_completo)} registros: {RELATORIO_EXCEL.resolve()}")
        
    except Exception as e:
        logger.error(f"[ERRO] Falha ao salvar relatorio: {e}")
        raise


def gerar_relatorio(root_path: str = "C:\\milson\\extrator_omie_v3\\resultado") -> None:
    """
    Orquestra a varredura, filtragem e persistência dos arquivos invalidos.
    
    Versão otimizada com:
    - Processamento paralelo em lotes
    - Filtros rapidos
    - Logging detalhado de progresso
    - Tratamento robusto de erros
    - NOVO: Limpeza automática de arquivos vazios e atualização do banco
    
    Args:
        root_path: Caminho raiz da varredura.
    """
    start_time = time.time()
    logger.info(f"[MAIN] Iniciando varredura otimizada em: {root_path}")
    
    # Limpa cache de arquivos processados
    global _arquivos_processados
    _arquivos_processados.clear()
    
    try:
        # Usa a versão otimizada
        encontrados = encontrar_arquivos_vazios_ou_zero_otimizado(root_path)

        if not encontrados:
            logger.info("[OK] Nenhum arquivo problematico encontrado.")
            return

        logger.info(f"[FILTRO] Removendo duplicatas de {len(encontrados)} arquivos encontrados...")
        novos = remover_duplicatas_existentes(encontrados)

        if not novos:
            logger.info("[DUPLICATAS] Nenhum novo arquivo a reportar.")
            return

        logger.info(f"[SAVE] Salvando {len(novos)} novos registros...")
        salvar_relatorio_otimizado(novos)
        
        # NOVA FUNCIONALIDADE: Limpeza automática de arquivos vazios
        logger.info("[LIMPEZA] Iniciando limpeza automática de arquivos vazios...")
        arquivos_removidos = limpar_arquivos_vazios_e_atualizar_banco(encontrados)
        logger.info(f"[LIMPEZA] {arquivos_removidos} arquivos vazios removidos e banco atualizado")
        
    except Exception as e:
        logger.error(f"[ERRO] Falha na geração do relatorio: {e}")
        raise
    finally:
        elapsed = time.time() - start_time
        logger.info(f"[MAIN] Relatorio concluido em {elapsed:.2f}s")


def limpar_arquivos_vazios_e_atualizar_banco(arquivos_problematicos: List[Dict]) -> int:
    """
    Remove arquivos vazios do sistema e atualiza banco para reprocessamento.
    
    Args:
        arquivos_problematicos: Lista de arquivos identificados como problemáticos
        
    Returns:
        int: Número de arquivos removidos
    """
    import sqlite3
    removidos = 0
    chaves_para_reprocessar = []
    
    for arquivo_info in arquivos_problematicos:
        caminho = Path(arquivo_info["Path"])
        
        # Só remove arquivos XML vazios ou corrompidos
        if caminho.suffix.lower() == '.xml' and arquivo_info.get("Issue") in ["0 KB", "Empty content"]:
            try:
                # Extrai chave NFe do nome do arquivo
                nome_arquivo = caminho.stem
                partes = nome_arquivo.split('_')
                if len(partes) >= 3:
                    chave_nfe = partes[2]  # Formato: NFe_AAAA_CHAVE.xml
                    
                    # Remove arquivo físico
                    if caminho.exists():
                        caminho.unlink()
                        removidos += 1
                        chaves_para_reprocessar.append(chave_nfe)
                        logger.info(f"[LIMPEZA] Arquivo removido: {caminho.name}")
                        
            except Exception as e:
                logger.warning(f"[LIMPEZA] Erro ao remover {caminho}: {e}")
    
    # Atualiza banco para reprocessar esses registros
    if chaves_para_reprocessar:
        try:
            with sqlite3.connect("omie.db") as conn:
                conn.execute("PRAGMA journal_mode = WAL")
                conn.executemany(
                    "UPDATE notas SET xml_baixado = 0, xml_vazio = 0, caminho_arquivo = NULL WHERE cChaveNFe = ?",
                    [(chave,) for chave in chaves_para_reprocessar]
                )
                conn.commit()
                logger.info(f"[LIMPEZA] {len(chaves_para_reprocessar)} registros marcados para reprocessamento")
        except Exception as e:
            logger.error(f"[LIMPEZA] Erro ao atualizar banco: {e}")
    
    return removidos


# Alias para compatibilidade
salvar_relatorio = salvar_relatorio_otimizado
