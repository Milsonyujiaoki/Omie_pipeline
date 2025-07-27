#!/usr/bin/env python3
"""
Teste das funcões de formatação de tempo implementadas
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from main import formatar_tempo_total

def testar_formatacao_tempo():
    """Testa a função de formatação de tempo com diferentes valores"""
    
    testes = [
        (0, "0s"),
        (15, "15s"),
        (65, "1m 5s"),
        (125, "2m 5s"),
        (3661, "1h 1m 1s"),
        (7323, "2h 2m 3s"),
        (86400, "24h 0m 0s"),
        (90061, "25h 1m 1s"),
        (491.89, "8m 11s"),  # Exemplo do log do usuário
        (3600, "1h 0m 0s"),
        (1800, "30m 0s")
    ]
    
    print("=== TESTE DE FORMATAÇÃO DE TEMPO ===")
    print("Segundos\t→ Formatado")
    print("-" * 40)
    
    for segundos, esperado in testes:
        resultado = formatar_tempo_total(segundos)
        status = "✓" if resultado == esperado else "❌"
        print(f"{segundos:8.2f}s\t→ {resultado:12s} {status}")
        if resultado != esperado:
            print(f"         \t  Esperado: {esperado}")
    
    print("\n=== TESTE DE TAXA POR MILISSEGUNDO ===")
    
    # Simula cenários de taxa
    cenarios = [
        {"registros": 200, "tempo_s": 0.01, "descricao": "200 registros em 10ms (duplicatas)"},
        {"registros": 1000, "tempo_s": 0.5, "descricao": "1000 registros em 500ms"},
        {"registros": 37593, "tempo_s": 491.89, "descricao": "37593 registros em 8m 11s"}
    ]
    
    for cenario in cenarios:
        tempo_ms = cenario["tempo_s"] * 1000
        taxa_ms = cenario["registros"] / tempo_ms
        taxa_s = cenario["registros"] / cenario["tempo_s"]
        
        print(f"\n{cenario['descricao']}:")
        print(f"  Taxa antiga: {taxa_s:.0f} registros/segundo")
        print(f"  Taxa nova:   {taxa_ms:.2f} registros/milissegundo")

if __name__ == "__main__":
    testar_formatacao_tempo()
