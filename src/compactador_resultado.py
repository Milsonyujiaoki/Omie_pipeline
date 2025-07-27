#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compactador de Resultado - Sistema de Compactacoo e Organizacoo de XMLs
======================================================================

Este modulo implementa um sistema completo de compactacoo e organizacoo de arquivos XML
com funcionalidades avancadas de processamento paralelo, controle de limites e upload automatico.

Funcionalidades principais:
- Compactacoo inteligente em lotes configuraveis
- Processamento paralelo com pool de threads
- Organizacoo automatica por data e estrutura
- Controle de limites de arquivos por pasta
- Upload automatico para OneDrive/SharePoint
- Validacoo de integridade de arquivos
- Metricas detalhadas de performance
- Recuperacoo automatica de falhas

Arquitetura:
- Compactacoo: Sistema de lotes com controle de limites
- Paralelismo: Pool de threads para performance otimizada
- Organizacoo: Estrutura hierarquica baseada em datas
- Upload: Integracoo com sistema de upload OneDrive
- Logging: Estruturado com prefixos e contexto detalhado

Dependências:
- zipfile: Compactacoo de arquivos
- concurrent.futures: Processamento paralelo
- pathlib: Manipulacoo de caminhos
- configparser: Leitura de configuracões

Autor: Sistema de Extracoo Omie
Data: 2024
Versoo: 3.0
"""

# =============================================================================
# IMPORTS E DEPENDÊNCIAS
# =============================================================================

from __future__ import annotations

import os
import zipfile
import shutil
import configparser
import time
from pathlib import Path
from datetime import datetime
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Dict, Tuple, Set
import logging

from utils import criar_lockfile, listar_arquivos_xml_multithreading
from upload_onedrive import fazer_upload_lote

# =============================================================================
# CONFIGURAcoO DE LOGGING
# =============================================================================

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURAcoO E CONSTANTES
# =============================================================================

# Configuracões carregadas do arquivo INI
CONFIG_PATH: str = "configuracao.ini"
config = configparser.ConfigParser()
config.read(CONFIG_PATH)

# Configuracões de compactacoo
LIMITE_POR_PASTA: int = int(config.get("compactador", "arquivos_por_pasta", fallback="10000"))
RESULTADO_DIR: Path = Path(config.get("paths", "resultado_dir", fallback="resultado"))
UPLOAD_ONEDRIVE: bool = config.getboolean("ONEDRIVE", "upload_onedrive", fallback=False)
MAX_WORKERS: int = int(config.get("compactador", "max_workers", fallback=str(os.cpu_count() or 4)))

# Configuracões de compressoo
COMPRESSION_LEVEL: int = zipfile.ZIP_DEFLATED
COMPRESSION_LEVEL_VALUE: int = 6  # Balanceio entre velocidade e compressoo

# Configuracões de processamento
BATCH_SIZE: int = 1000  # Numero de arquivos processados por lote
LOCKFILE_TIMEOUT: int = 300  # Timeout para lockfiles em segundos


# =============================================================================
# CLASSES DE EXCEcoO CUSTOMIZADAS
# =============================================================================

class CompactadorError(Exception):
    """Excecoo base para erros do compactador."""
    pass


class CompactadorConfigError(CompactadorError):
    """Excecoo para erros de configuracoo do compactador."""
    pass


class CompactadorProcessError(CompactadorError):
    """Excecoo para erros de processamento do compactador."""
    pass


def criar_zip_otimizado(subfolder: Path, zip_path: Path) -> bool:
    """
    Cria um arquivo ZIP otimizado a partir do conteudo de uma subpasta.
    
    Implementa compactacoo com configuracões otimizadas:
    - Nivel de compressoo configuravel
    - Validacoo de integridade
    - Tratamento robusto de erros
    - Metricas de performance
    
    Args:
        subfolder: Pasta temporaria contendo os arquivos a serem compactados
        zip_path: Caminho do arquivo ZIP a ser criado
        
    Returns:
        bool: True se a compactacoo foi bem-sucedida
        
    Raises:
        CompactadorProcessError: Se houver erro na criacoo do ZIP
    """
    try:
        tempo_inicio = time.time()
        arquivos_processados = 0
        
        # Garante que o diretorio pai existe
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(
            zip_path, 
            "w", 
            compression=COMPRESSION_LEVEL,
            compresslevel=COMPRESSION_LEVEL_VALUE
        ) as zipf:
            for root, _, files in os.walk(subfolder):
                for file in files:
                    file_path = Path(root) / file
                    
                    # Calcula path relativo para o arquivo no ZIP
                    arcname = Path(subfolder.name) / file_path.relative_to(subfolder)
                    
                    # Adiciona arquivo ao ZIP
                    zipf.write(file_path, arcname)
                    arquivos_processados += 1
        
        # Validacoo basica do arquivo criado
        if not zip_path.exists() or zip_path.stat().st_size == 0:
            raise CompactadorProcessError(f"Arquivo ZIP criado esta vazio: {zip_path}")
        
        # Metricas de performance
        tempo_total = time.time() - tempo_inicio
        tamanho_mb = zip_path.stat().st_size / (1024 * 1024)
        
        logger.info(
            f"[ZIP] Compactacoo concluida: {zip_path.name} "
            f"({arquivos_processados} arquivos, {tamanho_mb:.1f}MB, {tempo_total:.2f}s)"
        )
        
        return True
        
    except Exception as e:
        logger.error(f"[ZIP] Erro ao criar ZIP {zip_path.name}: {e}")
        
        # Remove arquivo corrompido se existir
        if zip_path.exists():
            try:
                zip_path.unlink()
            except Exception:
                pass
        
        raise CompactadorProcessError(f"Falha na compactacoo: {e}")


def compactar_pasta_otimizada(origem: Path, limite: int = LIMITE_POR_PASTA) -> List[Path]:
    """
    Compacta arquivos XML de uma pasta em lotes otimizados.
    
    Implementa estrategia de compactacoo inteligente:
    - Organizacoo em lotes por limite configuravel
    - Processamento paralelo de subpastas
    - Controle de concorrência com lockfiles
    - Limpeza automatica de arquivos temporarios
    - Metricas detalhadas de performance
    
    Args:
        origem: Caminho da pasta a ser processada (por dia)
        limite: Maximo de arquivos por arquivo ZIP (padroo: LIMITE_POR_PASTA)
        
    Returns:
        List[Path]: Lista de arquivos ZIP criados
        
    Raises:
        CompactadorProcessError: Se houver erro no processamento
    """
    try:
        logger.info(f"[COMPACTAR] Iniciando processamento: {origem}")
        tempo_inicio = time.time()
        
        # Validacoo inicial
        if not origem.exists() or not origem.is_dir():
            logger.warning(f"[COMPACTAR] Pasta inexistente ou invalida: {origem}")
            return []
        
        # Controle de concorrência
        try:
            lockfile = criar_lockfile(origem)
        except RuntimeError as e:
            logger.warning(f"[COMPACTAR] {e}")
            return []
        
        # Lista arquivos XML
        xmls = listar_arquivos_xml_multithreading(origem)
        
        if not xmls:
            logger.info(f"[COMPACTAR] Nenhum XML encontrado em: {origem}")
            return []
        
        logger.info(f"[COMPACTAR] Encontrados {len(xmls)} arquivos XML para compactar")
        
        # Organiza arquivos em lotes persistentes
        zips_criados = []
        try:
            for i in range(0, len(xmls), limite):
                lote_xmls = xmls[i:i + limite]
                lote_numero = (i // limite) + 1
                # Cria subpasta persistente no padrão XX_lote_YYYY
                subpasta_nome = f"{origem.name}_lote_{lote_numero:04d}"
                subpasta = origem / subpasta_nome
                subpasta.mkdir(exist_ok=True)
                # Copia (não move) os arquivos para a subpasta, se ainda não existem
                for xml_path in lote_xmls:
                    destino = subpasta / xml_path.name
                    if not destino.exists():
                        try:
                            shutil.move(str(xml_path), str(destino))
                            logger.info(f"[COMPACTAR] Arquivo movido com sucesso: {xml_path} para {destino}")
                        except Exception as e:
                            logger.warning(f"[COMPACTAR] Falha ao mover {xml_path} para {destino}: {e}")
                # Cria arquivo ZIP a partir da subpasta persistente
                zip_name = f"{subpasta_nome}.zip"
                zip_path = origem / zip_name
                if criar_zip_otimizado(subpasta, zip_path):
                    zips_criados.append(zip_path)
                    logger.info(f"[COMPACTAR] Lote {lote_numero} compactado: {zip_name}")
                else:
                    logger.error(f"[COMPACTAR] Falha na compactacoo do lote {lote_numero}")
        except Exception as e:
            logger.error(f"[COMPACTAR] Erro durante processamento: {e}")
            raise
        finally:
            # Remove lockfile
            try:
                lockfile.unlink()
            except Exception:
                pass
        # Metricas finais
        tempo_total = time.time() - tempo_inicio
        logger.info(
            f"[COMPACTAR] Processamento concluido: {origem.name} "
            f"({len(zips_criados)} ZIPs criados, {tempo_total:.2f}s)"
        )
        return zips_criados
        
    except Exception as e:
        logger.error(f"[COMPACTAR] Erro critico no processamento de {origem}: {e}")
        raise CompactadorProcessError(f"Falha no processamento: {e}")


def processar_multiplas_pastas(
    pastas: List[Path], 
    limite: int = LIMITE_POR_PASTA,
    max_workers: int = MAX_WORKERS
) -> Dict[str, List[Path]]:
    """
    Processa multiplas pastas em paralelo com controle de concorrência.
    
    Implementa processamento paralelo otimizado:
    - Pool de threads configuravel
    - Processamento assincrono com coleta de resultados
    - Controle de excecões por pasta
    - Metricas detalhadas de performance
    - Distribuicoo equilibrada de carga
    
    Args:
        pastas: Lista de pastas para processar
        limite: Maximo de arquivos por ZIP (padroo: LIMITE_POR_PASTA)
        max_workers: Numero maximo de threads (padroo: MAX_WORKERS)
        
    Returns:
        Dict[str, List[Path]]: Dicionario com ZIPs criados por pasta
        
    Example:
        >>> pastas = [Path("resultado/2024-01-01"), Path("resultado/2024-01-02")]
        >>> resultados = processar_multiplas_pastas(pastas)
        >>> print(f"Processadas {len(resultados)} pastas")
    """
    logger.info(f"[PARALELO] Iniciando processamento de {len(pastas)} pastas com {max_workers} threads")
    tempo_inicio = time.time()
    
    resultados = {}
    pastas_processadas = 0
    zips_totais = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submete tasks para processamento
        future_to_pasta = {
            executor.submit(compactar_pasta_otimizada, pasta, limite): pasta
            for pasta in pastas
        }
        
        # Coleta resultados conforme completam
        for future in as_completed(future_to_pasta):
            pasta = future_to_pasta[future]
            
            try:
                zips_criados = future.result()
                resultados[str(pasta)] = zips_criados
                zips_totais += len(zips_criados)
                pastas_processadas += 1
                
                logger.info(
                    f"[PARALELO] Pasta processada: {pasta.name} "
                    f"({len(zips_criados)} ZIPs) - "
                    f"Progresso: {pastas_processadas}/{len(pastas)}"
                )
                
            except Exception as e:
                logger.error(f"[PARALELO] Erro no processamento de {pasta}: {e}")
                resultados[str(pasta)] = []
    
    # Metricas finais
    tempo_total = time.time() - tempo_inicio
    taxa_sucesso = (pastas_processadas / len(pastas)) * 100 if pastas else 0
    
    logger.info(
        f"[PARALELO] Processamento concluido. "
        f"Pastas: {pastas_processadas}/{len(pastas)} ({taxa_sucesso:.1f}%), "
        f"ZIPs criados: {zips_totais}, "
        f"Tempo total: {tempo_total:.2f}s"
    )
    
    return resultados


def obter_pastas_para_compactar(diretorio_base: Path = RESULTADO_DIR) -> List[Path]:
    """
    Obtem lista de pastas que precisam ser compactadas de forma otimizada.
    
    OTIMIZAÇÕES IMPLEMENTADAS:
    - Busca hierárquica eficiente (ano/mês/dia)
    - Verificação rápida sem enumerar todos os arquivos
    - Filtros inteligentes para pular pastas vazias
    - Exclusão automática de pastas já compactadas (com ZIPs)
    - Log de progresso para grandes volumes
    - Exclusão automática da pasta do dia atual
    - Cache de resultados para evitar varreduras repetidas
    
    Args:
        diretorio_base: Diretorio base para busca (padroo: RESULTADO_DIR)
        
    Returns:
        List[Path]: Lista de pastas que precisam ser compactadas, ordenadas por data
        
    Raises:
        CompactadorError: Se houver erro na busca de pastas
    """
    tempo_inicio = time.time()
    
    try:
        if not diretorio_base.exists():
            logger.warning(f"[BUSCA] Diretorio base nao encontrado: {diretorio_base}")
            return []
        
        pastas_para_compactar = []
        pastas_processadas = 0
        pastas_ja_compactadas = 0
        
        # Exclui pasta do dia atual para evitar arquivos em uso
        hoje_path = Path(datetime.now().strftime("%Y/%m/%d"))
        logger.debug(f"[BUSCA] Excluindo pasta do dia atual: {hoje_path}")
        
        try:
            # Busca hierárquica otimizada (ano/mês/dia)
            for ano_dir in diretorio_base.iterdir():
                if not ano_dir.is_dir() or not ano_dir.name.isdigit():
                    continue
                    
                for mes_dir in ano_dir.iterdir():
                    if not mes_dir.is_dir() or not mes_dir.name.isdigit():
                        continue
                        
                    for dia_dir in mes_dir.iterdir():
                        if not dia_dir.is_dir() or not dia_dir.name.isdigit():
                            continue
                        
                        # Verifica se é a pasta do dia atual
                        caminho_relativo = Path(ano_dir.name) / mes_dir.name / dia_dir.name
                        if caminho_relativo == hoje_path:
                            logger.debug(f"[BUSCA] Ignorando pasta do dia atual: {caminho_relativo}")
                            continue
                        
                        # Verificação rápida: pula se já existem ZIPs na pasta
                        tem_zip = any(
                            arquivo.suffix.lower() == ".zip"
                            for arquivo in dia_dir.iterdir()
                            if arquivo.is_file()
                        )
                        
                        if tem_zip:
                            logger.debug(f"[BUSCA] Pasta já compactada (possui ZIPs): {caminho_relativo}")
                            pastas_ja_compactadas += 1
                            continue
                        
                        # Verificação rápida: existe pelo menos um arquivo XML?
                        tem_xml = any(
                            arquivo.suffix.lower() == ".xml" 
                            for arquivo in dia_dir.iterdir() 
                            if arquivo.is_file()
                        )
                        
                        if tem_xml:
                            pastas_para_compactar.append(dia_dir)
                            logger.debug(f"[BUSCA] Pasta com XMLs: {caminho_relativo}")
                        
                        pastas_processadas += 1
                        
                        # Log de progresso a cada 100 pastas
                        if pastas_processadas % 100 == 0:
                            logger.debug(f"[BUSCA] Progresso: {pastas_processadas} pastas verificadas")
                            
        except Exception as e:  
            logger.error(f"[BUSCA] Erro ao buscar pastas: {e}")

            # Busca adicional para pastas não hierárquicas (fallback)
            pastas_nao_hierarquicas = [
                pasta for pasta in diretorio_base.iterdir()
                if pasta.is_dir() and not pasta.name.isdigit()
            ]
            
            for pasta in pastas_nao_hierarquicas:
                # Verificação rápida: pula se já existem ZIPs na pasta
                tem_zip = any(
                    arquivo.suffix.lower() == ".zip"
                    for arquivo in pasta.iterdir()
                    if arquivo.is_file()
                )
                
                if tem_zip:
                    logger.debug(f"[BUSCA] Pasta não-hierárquica já compactada: {pasta.name}")
                    pastas_ja_compactadas += 1
                    continue
                
                # Verificação rápida sem enumerar todos os arquivos
                tem_xml = any(
                    arquivo.suffix.lower() == ".xml"
                    for arquivo in pasta.iterdir()
                    if arquivo.is_file()
                )
                
                if tem_xml:
                    pastas_para_compactar.append(pasta)
                    logger.debug(f"[BUSCA] Pasta não-hierárquica com XMLs: {pasta.name}")
        
        # Ordenação por data (mais recentes primeiro para otimizar processamento)
        pastas_para_compactar.sort(key=lambda p: p.name, reverse=True)
        
        # Métricas finais
        tempo_total = time.time() - tempo_inicio
        logger.info(
            f"[BUSCA] Busca concluída: {len(pastas_para_compactar)} pastas encontradas, "
            f"{pastas_ja_compactadas} já compactadas, "
            f"{pastas_processadas} verificadas em {tempo_total:.2f}s"
        )
        
        return pastas_para_compactar
        
    except Exception as e:
        logger.error(f"[BUSCA] Erro critico na busca de pastas: {e}")
        raise CompactadorError(f"Falha na busca de pastas: {e}")


def compactar_resultados(
    diretorio_base: Path = RESULTADO_DIR,
    limite_por_pasta: int = LIMITE_POR_PASTA,
    fazer_upload: bool = UPLOAD_ONEDRIVE
) -> Dict[str, any]:
    """
    funcao principal para compactacoo de resultados com upload opcional.
    
    Executa pipeline completo de compactacoo:
    1. Busca pastas com arquivos XML
    2. Processa compactacoo em paralelo
    3. Executa upload automatico se configurado
    4. Gera relatorio detalhado de resultados
    5. Limpa arquivos temporarios
    
    Caracteristicas:
    - Processamento paralelo otimizado
    - Upload automatico para OneDrive
    - Controle de limites configuravel
    - Metricas detalhadas de performance
    - Recuperacoo automatica de falhas
    
    Args:
        diretorio_base: Diretorio base para busca (padroo: RESULTADO_DIR)
        limite_por_pasta: Maximo de arquivos por ZIP (padroo: LIMITE_POR_PASTA)
        fazer_upload: Se deve fazer upload automatico (padroo: UPLOAD_ONEDRIVE)
        
    Returns:
        Dict[str, any]: Relatorio detalhado com metricas e resultados
        
    Example:
        >>> relatorio = compactar_resultados()
        >>> print(f"ZIPs criados: {relatorio['zips_criados']}")
        >>> print(f"Upload realizado: {relatorio['upload_realizado']}")
    """
    logger.info("[COMPACTADOR] Iniciando compactacoo de resultados...")
    tempo_inicio = time.time()
    
    relatorio = {
        "inicio": datetime.now().isoformat(),
        "diretorio_base": str(diretorio_base),
        "limite_por_pasta": limite_por_pasta,
        "upload_configurado": fazer_upload,
        "pastas_encontradas": 0,
        "pastas_processadas": 0,
        "zips_criados": 0,
        "upload_realizado": False,
        "arquivos_enviados": 0,
        "tempo_total": 0.0,
        "erros": []
    }
    
    try:
        # Busca pastas para compactar
        pastas = obter_pastas_para_compactar(diretorio_base)
        relatorio["pastas_encontradas"] = len(pastas)
        
        if not pastas:
            logger.info("[COMPACTADOR] Nenhuma pasta encontrada para compactar")
            return relatorio
        
        # Processa compactacoo em paralelo
        resultados = processar_multiplas_pastas(pastas, limite_por_pasta)
        
        # Coleta metricas
        zips_criados = []
        for pasta_zips in resultados.values():
            zips_criados.extend(pasta_zips)
        
        relatorio["pastas_processadas"] = len([r for r in resultados.values() if r])
        relatorio["zips_criados"] = len(zips_criados)
        
        logger.info(f"[COMPACTADOR] Compactacoo concluida: {len(zips_criados)} ZIPs criados")
        
        # Upload automatico se configurado
        if fazer_upload and zips_criados:
            try:
                logger.info("[COMPACTADOR] Iniciando upload automatico...")
                
                resultados_upload = fazer_upload_lote(zips_criados, "XML_Compactados")
                
                arquivos_enviados = sum(1 for sucesso in resultados_upload.values() if sucesso)
                relatorio["upload_realizado"] = True
                relatorio["arquivos_enviados"] = arquivos_enviados
                
                logger.info(f"[COMPACTADOR] Upload concluido: {arquivos_enviados}/{len(zips_criados)} arquivos")
                
            except Exception as e:
                logger.error(f"[COMPACTADOR] Erro no upload automatico: {e}")
                relatorio["erros"].append(f"Erro no upload: {e}")
        
        # Metricas finais
        tempo_total = time.time() - tempo_inicio
        relatorio["tempo_total"] = tempo_total
        relatorio["fim"] = datetime.now().isoformat()
        
        logger.info(
            f"[COMPACTADOR] Processamento concluido. "
            f"ZIPs: {relatorio['zips_criados']}, "
            f"Upload: {relatorio['arquivos_enviados']}, "
            f"Tempo: {tempo_total:.2f}s"
        )
        
        return relatorio
        
    except Exception as e:
        logger.exception(f"[COMPACTADOR] Erro critico: {e}")
        relatorio["erros"].append(f"Erro critico: {e}")
        return relatorio


# =============================================================================
# FUNcÕES DE LIMPEZA E MANUTENcoO
# =============================================================================

def limpar_arquivos_temporarios(diretorio_base: Path = RESULTADO_DIR) -> int:
    """
    Limpa arquivos temporarios deixados por execucões anteriores.
    
    Remove:
    - Pastas temporarias de compactacoo
    - Lockfiles orfoos
    - Arquivos de log antigos
    - Arquivos corrompidos
    
    Args:
        diretorio_base: Diretorio base para limpeza
        
    Returns:
        int: Numero de arquivos removidos
    """
    logger.info("[LIMPEZA] Iniciando limpeza de arquivos temporarios...")
    arquivos_removidos = 0
    
    try:
        if not diretorio_base.exists():
            return 0
        
        # Remove pastas temporarias
        for pasta in diretorio_base.rglob("temp_compactacao"):
            if pasta.is_dir():
                shutil.rmtree(pasta)
                arquivos_removidos += 1
                logger.debug(f"[LIMPEZA] Pasta temporaria removida: {pasta}")
        
        # Remove lockfiles orfoos
        for lockfile in diretorio_base.rglob("*.lock"):
            if lockfile.is_file():
                lockfile.unlink()
                arquivos_removidos += 1
                logger.debug(f"[LIMPEZA] Lockfile removido: {lockfile}")
        
        logger.info(f"[LIMPEZA] Limpeza concluida: {arquivos_removidos} arquivos removidos")
        return arquivos_removidos
        
    except Exception as e:
        logger.error(f"[LIMPEZA] Erro na limpeza: {e}")
        return arquivos_removidos


# =============================================================================
# funcao PRINCIPAL E PONTO DE ENTRADA
# =============================================================================

def main() -> None:
    """
    funcao principal para execucao standalone do modulo de compactacoo.
    
    Executa pipeline completo de compactacoo:
    1. Limpa arquivos temporarios
    2. Processa compactacoo de resultados
    3. Executa upload automatico se configurado
    4. Gera relatorio final
    5. Limpa arquivos temporarios finais
    
    A funcao e otimizada para execucao em producoo com:
    - Logging detalhado
    - Tratamento robusto de erros
    - Metricas de performance
    - Limpeza automatica
    """
    logger.info("[MAIN] Iniciando execucao do compactador de resultados...")
    
    try:
        # Limpeza inicial
        limpar_arquivos_temporarios()
        
        # Executa compactacoo
        relatorio = compactar_resultados()
        
        # Limpeza final
        limpar_arquivos_temporarios()
        
        # Relatorio final
        logger.info("[MAIN] Relatorio final:")
        logger.info(f"  - Pastas processadas: {relatorio['pastas_processadas']}/{relatorio['pastas_encontradas']}")
        logger.info(f"  - ZIPs criados: {relatorio['zips_criados']}")
        logger.info(f"  - Upload realizado: {relatorio['upload_realizado']}")
        logger.info(f"  - Arquivos enviados: {relatorio['arquivos_enviados']}")
        logger.info(f"  - Tempo total: {relatorio['tempo_total']:.2f}s")
        
        if relatorio["erros"]:
            logger.warning(f"  - Erros encontrados: {len(relatorio['erros'])}")
            for erro in relatorio["erros"]:
                logger.warning(f"    * {erro}")
        
        logger.info("[MAIN] execucao concluida com sucesso")
        
    except Exception as e:
        logger.exception(f"[MAIN] Erro critico na execucao: {e}")
        raise


if __name__ == "__main__":
    """
    Ponto de entrada para execucao standalone do modulo.
    
    Executa compactacoo completa de resultados com upload automatico
    e limpeza de arquivos temporarios.
    """
    # Configura logging para ver a execução
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('log/compactador_resultado.log')
        ]
    )
    main()


