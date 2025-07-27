#!/usr/bin/env python3
"""
teste_simples_xml.py

Teste rápido e simples para comparar gerar_xml_path vs gerar_xml_path_otimizado
"""

import sys
import time
from pathlib import Path

# Adiciona src ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

try:
    from src.utils import gerar_xml_path, gerar_xml_path_otimizado
except ImportError:
    # Fallback se executando do diretório raiz
    from src.utils import gerar_xml_path, gerar_xml_path_otimizado

def teste_simples():
    """Teste básico e rápido das duas funções"""
    
    print("🧪 TESTE SIMPLES - Comparação das funções XML")
    print("="*50)
    
    # Dados de teste
    teste_dados = [
        ("35250714200166000196550010000123451234567890", "17/07/2025", "123"),
        ("35250714200166000196550010000123461234567891", "18/07/2025", "124"),
        ("35250714200166000196550010000123471234567892", "2025-07-19", "125"),
    ]
    
    print(f"📊 Testando {len(teste_dados)} casos...")
    
    # Teste função original
    print("\n1️⃣ Testando função ORIGINAL...")
    inicio = time.perf_counter()
    resultados_orig = []
    
    for chave, dEmi, num_nfe in teste_dados:
        try:
            pasta, arquivo = gerar_xml_path(chave, dEmi, num_nfe)
            resultados_orig.append(str(arquivo))
            print(f"   ✅ {chave[:20]}... -> {arquivo.name}")
        except Exception as e:
            print(f"   ❌ {chave[:20]}... -> ERRO: {e}")
            resultados_orig.append(f"ERRO: {e}")
    
    tempo_orig = time.perf_counter() - inicio
    
    # Teste função otimizada
    print("\n2️⃣ Testando função OTIMIZADA...")
    inicio = time.perf_counter()
    resultados_otim = []
    
    for chave, dEmi, num_nfe in teste_dados:
        try:
            pasta, arquivo = gerar_xml_path_otimizado(chave, dEmi, num_nfe)
            resultados_otim.append(str(arquivo))
            print(f"   ✅ {chave[:20]}... -> {arquivo.name}")
        except Exception as e:
            print(f"   ❌ {chave[:20]}... -> ERRO: {e}")
            resultados_otim.append(f"ERRO: {e}")
    
    tempo_otim = time.perf_counter() - inicio
    
    # Comparação
    print("\n3️⃣ COMPARAÇÃO:")
    print(f"    Original: {tempo_orig:.4f}s")
    print(f"    Otimizada: {tempo_otim:.4f}s")
    
    if tempo_orig > 0:
        melhoria = ((tempo_orig - tempo_otim) / tempo_orig) * 100
        print(f"   📈 Melhoria: {melhoria:+.1f}%")
    
    # Verificar consistência
    identicos = sum(1 for a, b in zip(resultados_orig, resultados_otim) if a == b)
    print(f"   ✅ Resultados idênticos: {identicos}/{len(teste_dados)}")
    
    if identicos != len(teste_dados):
        print("\n⚠️  DIVERGÊNCIAS ENCONTRADAS:")
        for i, (orig, otim) in enumerate(zip(resultados_orig, resultados_otim)):
            if orig != otim:
                chave = teste_dados[i][0]
                print(f"   - {chave[:20]}...")
                print(f"     Original: {orig}")
                print(f"     Otimizada: {otim}")
    
    print("\n" + "="*50)
    print("✅ Teste concluído!")

if __name__ == "__main__":
    teste_simples()
