#!/usr/bin/env python3
"""
Teste rápido da função carregar_configuracoes do main.py
"""

try:
    from main import carregar_configuracoes
    
    print("Testando função carregar_configuracoes...")
    config = carregar_configuracoes()
    
    print("✅ Teste passou!")
    print(f"  📄 Records per page: {config['records_per_page']}")
    print(f"  📅 Start date: {config['start_date']}")
    print(f"  📅 End date: {config['end_date']}")
    print(f"  🌐 Base URL NF: {config['base_url_nf']}")
    print(f"  🌐 Base URL XML: {config['base_url_xml']}")
    
    # Verificar se todas as chaves necessárias estão presentes
    required_keys = ['app_key', 'app_secret', 'records_per_page', 'start_date', 'end_date', 'base_url_nf', 'base_url_xml']
    missing_keys = [key for key in required_keys if key not in config]
    
    if missing_keys:
        print(f"❌ Chaves ausentes: {missing_keys}")
    else:
        print(" Todas as chaves necessárias estão presentes!")
        
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()
