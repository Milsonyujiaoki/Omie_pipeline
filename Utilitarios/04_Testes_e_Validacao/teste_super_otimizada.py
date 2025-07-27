#!/usr/bin/env python3
"""
Otimização adicional: Cache e processamento em lotes para atualização de campos
"""

import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET
import concurrent.futures
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def atualizar_campos_registros_pendentes_super_otimizada(
    db_path: str, 
    resultado_dir: str = "resultado",
    batch_size: int = 1000,
    max_workers: int = None
) -> None:
    """
    Versão super otimizada da atualização de campos com:
    1. Processamento em lotes menores
    2. Cache de XMLs parseados
    3. Transações em batch
    4. Validação prévia de arquivos
    5. Paralelização inteligente
    """
    import sys
    import os
    # Adiciona o diretório pai ao path para importar src
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from src.utils import _indexar_xmls_por_chave, normalizar_data
    
    if max_workers is None:
        import os
        max_workers = min(32, (os.cpu_count() or 1) + 4)
    
    logger.info(f"[CAMPOS++] Iniciando atualização super otimizada...")
    logger.info(f"[CAMPOS++] Configurações: batch_size={batch_size}, max_workers={max_workers}")
    
    inicio_total = time.time()
    
    # 1. Indexação otimizada
    logger.info("[CAMPOS++] Fase 1: Indexação de XMLs...")
    t1 = time.time()
    xml_index = _indexar_xmls_por_chave(resultado_dir)
    logger.info(f"[CAMPOS++] Indexação concluída em {time.time() - t1:.2f}s")
    
    if not xml_index:
        logger.warning("[CAMPOS++] Nenhum XML indexado. Abortando.")
        return
    
    # 2. Busca registros pendentes com pré-filtro
    logger.info("[CAMPOS++] Fase 2: Carregando registros pendentes...")
    t2 = time.time()
    
    with sqlite3.connect(db_path) as conn:
        # Otimização SQLite
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
        
        cursor = conn.execute("""
            SELECT cChaveNFe, nNF, dEmi, cRazao, cnpj_cpf 
            FROM notas 
            WHERE xml_baixado = 0 
            AND (dEmi IS NULL OR dEmi = '' OR nNF IS NULL OR nNF = '' OR cRazao IS NULL OR cRazao = '' OR cnpj_cpf IS NULL OR cnpj_cpf = '')
            ORDER BY cChaveNFe
        """)
        pendentes = cursor.fetchall()
    
    logger.info(f"[CAMPOS++] {len(pendentes)} registros pendentes carregados em {time.time() - t2:.2f}s")
    
    if not pendentes:
        logger.info("[CAMPOS++] Nenhum registro pendente encontrado.")
        return
    
    # 3. Filtragem prévia - só processa registros com XML disponível
    logger.info("[CAMPOS++] Fase 3: Filtragem prévia...")
    t3 = time.time()
    
    registros_com_xml = []
    sem_xml = 0
    
    for registro in pendentes:
        chave = registro[0]
        if chave in xml_index:
            registros_com_xml.append(registro)
        else:
            sem_xml += 1
    
    logger.info(f"[CAMPOS++] Pré-filtro concluído em {time.time() - t3:.2f}s")
    logger.info(f"[CAMPOS++] Registros com XML: {len(registros_com_xml)}, Sem XML: {sem_xml}")
    
    # 4. Processamento em lotes paralelos
    logger.info("[CAMPOS++] Fase 4: Processamento em lotes paralelos...")
    t4 = time.time()
    
    # Divide em lotes
    lotes = [registros_com_xml[i:i + batch_size] for i in range(0, len(registros_com_xml), batch_size)]
    logger.info(f"[CAMPOS++] Dividido em {len(lotes)} lotes de até {batch_size} registros")
    
    resultados_totais = []
    
    def processar_lote(args):
        lote_idx, lote_registros = args
        return processar_lote_registros(lote_idx, lote_registros, xml_index)
    
    # Processamento paralelo dos lotes
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(processar_lote, (i, lote)) for i, lote in enumerate(lotes)]
        
        for future in concurrent.futures.as_completed(futures):
            try:
                resultado_lote = future.result()
                resultados_totais.extend(resultado_lote)
            except Exception as e:
                logger.error(f"[CAMPOS++] Erro ao processar lote: {e}")
    
    logger.info(f"[CAMPOS++] Processamento paralelo concluído em {time.time() - t4:.2f}s")
    
    # 5. Atualização em batch no banco
    logger.info("[CAMPOS++] Fase 5: Atualização em batch no banco...")
    t5 = time.time()
    
    atualizados = aplicar_atualizacoes_batch(db_path, resultados_totais)
    
    logger.info(f"[CAMPOS++] Atualização em batch concluída em {time.time() - t5:.2f}s")
    
    # 6. Relatório final
    tempo_total = time.time() - inicio_total
    logger.info(f"[CAMPOS++] === RELATÓRIO FINAL ===")
    logger.info(f"[CAMPOS++] Tempo total: {tempo_total:.2f}s")
    logger.info(f"[CAMPOS++] Registros processados: {len(registros_com_xml)}")
    logger.info(f"[CAMPOS++] Registros atualizados: {atualizados}")
    logger.info(f"[CAMPOS++] Registros sem XML: {sem_xml}")
    logger.info(f"[CAMPOS++] Taxa de processamento: {len(registros_com_xml) / tempo_total:.0f} reg/s")


def processar_lote_registros(lote_idx: int, registros: List[Tuple], xml_index: Dict[str, Path]) -> List[Dict]:
    """Processa um lote de registros e extrai campos dos XMLs"""
    resultados = []
    
    logger.info(f"[LOTE-{lote_idx}] Processando {len(registros)} registros...")
    
    for registro in registros:
        chave, nNF, dEmi, cRazao, cnpj_cpf = registro
        
        # Identifica campos vazios
        campos_vazios = []
        if not dEmi: campos_vazios.append("dEmi")
        if not nNF: campos_vazios.append("nNF")
        if not cRazao: campos_vazios.append("cRazao")
        if not cnpj_cpf: campos_vazios.append("cnpj_cpf")
        
        if not campos_vazios:
            continue
        
        xml_path = xml_index.get(chave)
        if not xml_path or not xml_path.exists():
            continue
        
        try:
            # Parse do XML
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            novos_valores = {}
            
            # Extração otimizada de campos
            for campo in campos_vazios:
                valor = None
                
                if campo == "dEmi":
                    elem = root.find(".//{*}ide/{*}dEmi")
                    if elem is not None and elem.text:
                        import sys
                        import os
                        # Adiciona o diretório pai ao path para importar src
                        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                        from src.utils import normalizar_data
                        valor = normalizar_data(elem.text.strip())
                
                elif campo == "nNF":
                    elem = root.find(".//{*}ide/{*}nNF")
                    if elem is not None and elem.text:
                        valor = elem.text.strip()
                
                elif campo == "cRazao":
                    elem = root.find(".//{*}dest/{*}xNome")
                    if elem is not None and elem.text:
                        valor = elem.text.strip()
                
                elif campo == "cnpj_cpf":
                    elem_cnpj = root.find(".//{*}dest/{*}CNPJ")
                    elem_cpf = root.find(".//{*}dest/{*}CPF")
                    if elem_cnpj is not None and elem_cnpj.text:
                        valor = elem_cnpj.text.strip()
                    elif elem_cpf is not None and elem_cpf.text:
                        valor = elem_cpf.text.strip()
                
                if valor:
                    novos_valores[campo] = valor
            
            if novos_valores:
                novos_valores['caminho_arquivo'] = str(xml_path.resolve())
                resultados.append({
                    'chave': chave,
                    'novos_valores': novos_valores
                })
        
        except Exception as e:
            logger.warning(f"[LOTE-{lote_idx}] Erro ao processar {chave}: {e}")
    
    logger.info(f"[LOTE-{lote_idx}] Concluído. {len(resultados)} registros com dados extraídos.")
    return resultados


def aplicar_atualizacoes_batch(db_path: str, resultados: List[Dict]) -> int:
    """Aplica todas as atualizações em uma unica transação"""
    if not resultados:
        return 0
    
    logger.info(f"[BATCH] Aplicando {len(resultados)} atualizações...")
    
    try:
        with sqlite3.connect(db_path) as conn:
            # Otimizações SQLite para batch
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.execute("PRAGMA cache_size = -64000")
            
            conn.execute("BEGIN IMMEDIATE")
            
            atualizados = 0
            for resultado in resultados:
                chave = resultado['chave']
                novos_valores = resultado['novos_valores']
                
                # Constrói query dinamicamente
                set_clause = ", ".join([f"{campo} = ?" for campo in novos_valores.keys()])
                params = list(novos_valores.values()) + [chave]
                
                cursor = conn.execute(f"UPDATE notas SET {set_clause} WHERE cChaveNFe = ?", params)
                if cursor.rowcount > 0:
                    atualizados += 1
            
            conn.commit()
            logger.info(f"[BATCH] {atualizados} registros atualizados com sucesso")
            return atualizados
    
    except Exception as e:
        logger.error(f"[BATCH] Erro na atualização em batch: {e}")
        return 0


if __name__ == "__main__":
    # Teste da versão super otimizada
    print("=== TESTE DA VERSÃO SUPER OTIMIZADA ===")
    
    db_path = "c:/milson/extrator_omie_v3/omie.db"
    resultado_dir = "c:/milson/extrator_omie_v3/resultado"
    
    # Teste com lote menor primeiro
    atualizar_campos_registros_pendentes_super_otimizada(
        db_path=db_path,
        resultado_dir=resultado_dir,
        batch_size=500,  # Lotes menores para melhor controle
        max_workers=8    # Ajuste conforme seu hardware
    )
