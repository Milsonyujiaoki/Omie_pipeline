#!/usr/bin/env python3
"""
Teste para verificar consistência entre as duas funções de carregamento de configurações.
"""

import sys
from pathlib import Path

# Adicionar o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

def testar_consistencia_configuracoes():
    """Testa se as duas funções de carregamento retornam os mesmos valores"""
    
    print(" Testando consistência entre carregar_configuracoes...")
    
    try:
        # Importar as duas funções
        from main import carregar_configuracoes as carregar_main
        from src.omie_client_async import carregar_configuracoes as carregar_omie
        
        print("✅ Ambas as funções importadas com sucesso")
        
        # Carregar configurações de ambas as fontes
        print("\n📊 Carregando configurações do main.py...")
        config_main = carregar_main()
        
        print("📊 Carregando configurações do omie_client_async.py...")
        config_omie = carregar_omie()
        
        # Comparar chaves comuns
        chaves_comuns = set(config_main.keys()) & set(config_omie.keys())
        print(f"\n🔑 Chaves comuns encontradas: {len(chaves_comuns)}")
        for chave in sorted(chaves_comuns):
            print(f"  - {chave}")
        
        # Verificar consistência dos valores
        print("\n Verificando consistência dos valores:")
        inconsistencias = []
        
        for chave in chaves_comuns:
            valor_main = config_main[chave]
            valor_omie = config_omie[chave]
            
            if valor_main == valor_omie:
                print(f"  ✅ {chave}: CONSISTENTE ({valor_main})")
            else:
                print(f"  ❌ {chave}: INCONSISTENTE")
                print(f"    main.py: {valor_main}")
                print(f"    omie_client: {valor_omie}")
                inconsistencias.append(chave)
        
        # Verificar chaves exclusivas
        main_exclusivo = set(config_main.keys()) - set(config_omie.keys())
        omie_exclusivo = set(config_omie.keys()) - set(config_main.keys())
        
        if main_exclusivo:
            print(f"\n📝 Chaves exclusivas do main.py: {sorted(main_exclusivo)}")
            
        if omie_exclusivo:
            print(f"\n📝 Chaves exclusivas do omie_client.py: {sorted(omie_exclusivo)}")
        
        # Resultado final
        if inconsistencias:
            print(f"\n❌ PROBLEMA: {len(inconsistencias)} inconsistências encontradas: {inconsistencias}")
            return False
        elif main_exclusivo or omie_exclusivo:
            print(f"\n⚠️  AVISO: Chaves diferentes entre as funções, mas valores consistentes")
            print("   (Isso pode estar causando o KeyError)")
            return False
        else:
            print(f"\n✅ SUCESSO: Todas as configurações são consistentes!")
            return True
            
    except Exception as e:
        print(f"❌ ERRO durante teste: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    sucesso = testar_consistencia_configuracoes()
    if not sucesso:
        print("\n💡 RECOMENDAÇÃO: Unificar o carregamento de configurações para evitar inconsistências")
