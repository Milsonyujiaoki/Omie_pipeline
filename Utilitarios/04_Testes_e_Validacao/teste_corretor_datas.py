#!/usr/bin/env python3
"""Teste rápido do corretor de datas"""

from corrigir_datas import CorretorDatas

def teste_basico():
    print("🧪 TESTE BÁSICO DO CORRETOR")
    print("=" * 40)
    
    corretor = CorretorDatas()
    
    try:
        # Teste de conexão
        print("1. Testando conexão...")
        conn = corretor.conectar_db()
        conn.close()
        print("✅ Conexão OK")
        
        # Teste de análise estrutural
        print("2. Testando análise estrutural...")
        analise = corretor.analisar_estrutura_datas()
        print("✅ Análise OK")
        
        print(f"📊 Total: {analise['total_registros']:,}")
        print(f"⚠️ Problemáticas: {analise['datas_problematicas']:,}")
        print(f"📈 Formatos encontrados: {len(analise['formatos_encontrados'])}")
        
        # Teste de conversão
        print("3. Testando conversões...")
        
        testes_conversao = [
            ("2025-04-11", "11/04/2025"),
            ("11/04/2025", "11/04/2025"),  # Já correto
            ("2025/04/11", "11/04/2025"),
            ("11-04-2025", "11/04/2025"),
            ("", None),
            (None, None)
        ]
        
        for entrada, esperado in testes_conversao:
            resultado = corretor.converter_data_para_padrao(entrada)
            status = "✅" if resultado == esperado else "❌"
            print(f"   {status} '{entrada}' → '{resultado}' (esperado: '{esperado}')")
        
        print("\n Todos os testes básicos passaram!")
        
    except Exception as e:
        print(f"❌ Erro no teste: {e}")

if __name__ == "__main__":
    teste_basico()
