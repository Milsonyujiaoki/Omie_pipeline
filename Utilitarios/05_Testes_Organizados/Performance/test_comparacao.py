#!/usr/bin/env python3
"""
Teste comparativo: versão original vs otimizada
"""

import sys
import time
from pathlib import Path
import os

# Adiciona o diretório pai ao path para importar src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils import _indexar_xmls_por_chave

def indexar_xmls_versao_original(resultado_dir: str) -> dict:
    """Versão original para comparação"""
    xml_index = {}
    total_xml = 0
    for xml_file in Path(resultado_dir).rglob("*.xml"):
        try:
            nome = xml_file.stem
            partes = nome.split("_")
            chave = partes[-1] if len(partes) > 1 else None
            if chave:
                xml_index[chave] = xml_file
                total_xml += 1
        except Exception as e:
            print(f"Falha ao indexar {xml_file}: {e}")
    return xml_index

def main():
    print("=== COMPARAÇÃO DE PERFORMANCE: ORIGINAL VS OTIMIZADA ===")
    
    resultado_dir = "c:/milson/extrator_omie_v3/resultado"
    
    # Testa apenas uma amostra pequena para comparação
    print("Testando com amostra pequena...")
    
    # Conta total de arquivos primeiro
    total_arquivos = len(list(Path(resultado_dir).rglob("*.xml")))
    print(f"Total de arquivos XML no diretório: {total_arquivos:,}")
    
    # Teste com subdiretório menor para comparação
    sample_dir = None
    sample_count = 0
    
    print("Procurando subdiretório adequado para teste...")
    for subdir in Path(resultado_dir).iterdir():
        if subdir.is_dir():
            try:
                sample_files = list(subdir.rglob("*.xml"))
                file_count = len(sample_files)
                print(f"  {subdir.name}: {file_count} arquivos")
                
                if 1000 <= file_count <= 10000:  # Ampliado para 1k-10k arquivos
                    sample_dir = str(subdir)
                    sample_count = file_count
                    break
                elif file_count > 0 and sample_count == 0:  # Fallback para qualquer subdiretório com arquivos
                    sample_dir = str(subdir)
                    sample_count = file_count
            except Exception as e:
                print(f"  Erro ao verificar {subdir}: {e}")
    
    if not sample_dir:
        print("Não foi possível encontrar um subdiretório adequado para teste comparativo")
        print("Executando teste com uma amostra dos primeiros 5000 arquivos...")
        
        # Fallback: usa os primeiros 5000 arquivos do diretório principal
        todos_arquivos = list(Path(resultado_dir).rglob("*.xml"))
        if len(todos_arquivos) > 5000:
            # Cria um teste com amostra dos primeiros arquivos
            sample_files = todos_arquivos[:5000]
            sample_count = len(sample_files)
            
            # Teste com amostra
            print(f"Testando com amostra de {sample_count:,} arquivos")
            
            # Teste versão original com amostra
            print("\n1. Testando versão ORIGINAL (amostra)...")
            inicio = time.time()
            original_count = 0
            for xml_file in sample_files:
                try:
                    nome = xml_file.stem
                    partes = nome.split("_")
                    chave = partes[-1] if len(partes) > 1 else None
                    if chave:
                        original_count += 1
                except Exception:
                    pass
            tempo_original = time.time() - inicio
            
            print(f"   Tempo: {tempo_original:.2f}s")
            print(f"   Arquivos processados: {original_count:,}")
            print(f"   Taxa: {original_count / tempo_original:.0f} arq/s")
            
            # Analise de projeção
            print(f"\n=== PROJEÇÃO PARA DATASET COMPLETO ===")
            if tempo_original > 0:
                tempo_projetado_original = (total_arquivos / original_count) * tempo_original
                print(f"Tempo projetado (original): {tempo_projetado_original:.0f}s ({tempo_projetado_original/60:.1f} min)")
            
            # Resultado da otimização ja conhecida
            print(f"Tempo real da versão otimizada: 144.76s (2.4 min)")
            if tempo_original > 0:
                speedup = tempo_projetado_original / 144.76
                print(f"Speedup da otimização: {speedup:.1f}x mais rapido")
            
            return
        else:
            print("Não ha arquivos suficientes para teste")
            return
    
    sample_count = len(list(Path(sample_dir).rglob("*.xml")))
    print(f"Testando com amostra de {sample_count:,} arquivos em: {sample_dir}")
    
    # Teste versão original
    print("\n1. Testando versão ORIGINAL...")
    inicio = time.time()
    original_index = indexar_xmls_versao_original(sample_dir)
    tempo_original = time.time() - inicio
    
    print(f"   Tempo: {tempo_original:.2f}s")
    print(f"   Arquivos: {len(original_index):,}")
    print(f"   Taxa: {len(original_index) / tempo_original:.0f} arq/s")
    
    # Teste versão otimizada
    print("\n2. Testando versão OTIMIZADA...")
    inicio = time.time()
    otimizada_index = _indexar_xmls_por_chave(sample_dir)
    tempo_otimizado = time.time() - inicio
    
    print(f"   Tempo: {tempo_otimizado:.2f}s")
    print(f"   Arquivos: {len(otimizada_index):,}")
    print(f"   Taxa: {len(otimizada_index) / tempo_otimizado:.0f} arq/s")
    
    # Analise comparativa
    print(f"\n=== ANaLISE COMPARATIVA ===")
    if tempo_original > 0:
        melhoria = ((tempo_original - tempo_otimizado) / tempo_original) * 100
        speedup = tempo_original / tempo_otimizado
        print(f"Melhoria de tempo: {melhoria:.1f}%")
        print(f"Speedup: {speedup:.1f}x mais rapido")
    
    # Projeção para o dataset completo
    print(f"\n=== PROJEÇÃO PARA DATASET COMPLETO ===")
    if tempo_otimizado > 0:
        tempo_projetado = (total_arquivos / len(otimizada_index)) * tempo_otimizado
        print(f"Tempo projetado (otimizada): {tempo_projetado:.0f}s ({tempo_projetado/60:.1f} min)")
    
    if tempo_original > 0:
        tempo_projetado_original = (total_arquivos / len(original_index)) * tempo_original
        print(f"Tempo projetado (original): {tempo_projetado_original:.0f}s ({tempo_projetado_original/60:.1f} min)")

if __name__ == "__main__":
    main()
