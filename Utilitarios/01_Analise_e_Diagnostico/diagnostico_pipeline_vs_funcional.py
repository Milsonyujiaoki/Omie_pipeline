#!/usr/bin/env python3
"""
Configurações otimizadas para resolver erros 425/500 na pipeline
"""

# =============================================================================
# CONFIGURAÇÕES CORRIGIDAS PARA EVITAR ERROS 425/500
# =============================================================================

# PROBLEMA IDENTIFICADO:
# - Pipeline complexa usa concorrência excessiva (4 simultâneas + 10 downloads)
# - Extrator funcional usa execução sequencial (1 por vez)
# - API Omie tem rate limit rigoroso que a pipeline excede

# SOLUÇÕES PROPOSTAS:

### 1. REDUZIR CONCORRÊNCIA DRASTICAMENTE
CONFIGURACAO_CONSERVADORA = {
    "calls_per_second": 1,           # Apenas 1 call simultâneo (não 4)
    "max_concurrent_downloads": 1,   # Apenas 1 download simultâneo (não 10)
    "delay_entre_requests": 2.0,     # 2 segundos entre requests
    "max_retries": 2,                # Menos retries (não 3+)
    "timeout": 30                    # Timeout menor
}

### 2. IMPLEMENTAR RATE LIMITING REAL
CONFIGURACAO_RATE_LIMITED = {
    "calls_per_second": 0.5,         # 1 call a cada 2 segundos
    "burst_control": True,           # Controle de burst
    "adaptive_delay": True,          # Delay adaptativo baseado em resposta
    "circuit_breaker": True          # Circuit breaker para erros consecutivos
}

### 3. USAR ESTRATÉGIA DO EXTRATOR FUNCIONAL
CONFIGURACAO_SEQUENCIAL = {
    "modo_execucao": "sequencial",   # Força execução sequencial
    "async_disabled": True,          # Desabilita processamento assíncrono
    "batch_size": 50,                # Lotes menores (não 500)
    "delay_fixo": 1.0               # Delay fixo como no funcional
}

### 4. CONFIGURAÇÃO HÍBRIDA (RECOMENDADA)
CONFIGURACAO_OTIMIZADA = {
    "calls_per_second": 2,           # Máximo 2 simultâneas
    "max_concurrent_downloads": 2,   # Máximo 2 downloads
    "delay_minimo": 1.5,            # Mínimo 1.5s entre calls
    "exponential_backoff": True,     # Backoff exponencial em erros
    "fail_fast": True,               # Falha rápida em erros 425
    "health_check": True             # Monitoramento de saúde da API
}

# =============================================================================
# MUDANÇAS ESPECÍFICAS NO CÓDIGO
# =============================================================================

print("=== MUDANÇAS RECOMENDADAS ===")
print()

print("1. ARQUIVO: configuracao.ini")
print("   [api_speed]")
print("   calls_per_second = 1  # REDUZIR DE 4 PARA 1")
print()

print("2. ARQUIVO: src/omie_client_async.py")
print("   # ALTERAR:")
print("   self.semaphore = asyncio.Semaphore(1)  # Apenas 1 simultâneo")
print()

print("3. ARQUIVO: src/extrator_async.py")
print("   # ALTERAR:")
print("   MAX_CONCURRENT_DOWNLOADS = 1  # Apenas 1 download")
print()

print("4. ADICIONALMENTE:")
print("   - Implementar delay mínimo de 2 segundos entre requisições")
print("   - Desabilitar retry agressivo")
print("   - Monitorar erros 425 e pausar temporariamente")
print()

# =============================================================================
# IMPLEMENTAÇÃO PRÁTICA
# =============================================================================

def criar_configuracao_conservadora():
    """Cria arquivo de configuração conservadora"""
    config_text = """[omie_api]
app_key = 5702859630468
app_secret = 1cf8d99fa820c9cc7af243162331d0bf
base_url_nf = https://app.omie.com.br/api/v1/produtos/nfconsultar/
base_url_xml = https://app.omie.com.br/api/v1/produtos/dfedocs/

[query_params]
start_date = 19/07/2025
end_date = 31/07/2025
records_per_page = 100

[api_speed]
calls_per_second = 1

[paths]
resultado_dir = C:/milson/extrator_omie_v3/resultado
db_name = omie.db
caminho_config_ini = configuracao.ini

[compactador]
arquivos_por_pasta = 10000
max_workers = 1

[ONEDRIVE]
upload_onedrive = True
pasta_destino = Documentos Compartilhados
upload_max_retries = 3
upload_backoff_factor = 2.0
upload_retry_status = 429,500,502,503,504

[pipeline]
batch_size = 100
max_workers = 1
modo_hibrido_ativo = false
min_erros_para_reprocessamento = 50000
reprocessar_automaticamente = false
apenas_normal = true
"""
    
    with open('configuracao_conservadora.ini', 'w', encoding='utf-8') as f:
        f.write(config_text)
    
    print("✅ Arquivo 'configuracao_conservadora.ini' criado")
    print("   Use: python main.py --config configuracao_conservadora.ini")

if __name__ == "__main__":
    print("🔧 DIAGNÓSTICO: Pipeline vs Extrator Funcional")
    print("=" * 60)
    print()
    
    print("❌ PIPELINE COMPLEXA (FALHA):")
    print("   • 4 requisições simultâneas")
    print("   • 10 downloads paralelos") 
    print("   • Retry agressivo")
    print("   • Total: até 14 operações simultâneas")
    print()
    
    print("✅ EXTRATOR FUNCIONAL (FUNCIONA):")
    print("   • 1 requisição sequencial")
    print("   • Delay simples entre calls")
    print("   • Retry básico")
    print("   • Total: 1 operação por vez")
    print()
    
    print("🎯 CONCLUSÃO:")
    print("   A API Omie NÃO suporta alta concorrência")
    print("   Rate limit rigoroso causa erros 425/500")
    print("   Solução: Reduzir drasticamente a concorrência")
    print()
    
    criar_configuracao_conservadora()
