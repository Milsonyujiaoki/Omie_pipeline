# 🚀 Download e Execução

Scripts para execução de downloads e operações automáticas.

## Scripts Disponíveis

### `baixar_xmls_data_especifica.py`
**Propósito**: Download de XMLs para uma data específica (ex: 01/05/2025)  
**Uso**: Quando precisa baixar XMLs de uma data específica  
**Características**:
- Foca em uma data específica
- Download sequencial dos XMLs
- Controle de progresso
- Tratamento de erros por arquivo

### `executar_download_automatico.py`
**Propósito**: Execução automática de download de registros pendentes  
**Uso**: Para automação de downloads em lote  
**Características**:
- Criação de arquivo com IDs pendentes
- Execução automática do pipeline
- Preparação de dados para processamento
- Integração com sistema principal

### `resolver_registros_pendentes.py` ⭐ **PRINCIPAL**
**Propósito**: Solução completa para registros pendentes com menu interativo  
**Uso**: Script principal para resolver problemas de registros pendentes  
**Características**:
- Interface interativa com opções
- Diagnóstico automático
- Download automático via pipeline
- Solução completa end-to-end

## Ordem de Execução Recomendada

### Para Resolução Completa:
1. **resolver_registros_pendentes.py** - Script principal (recomendado)

### Para Casos Específicos:
1. **baixar_xmls_data_especifica.py** - Para datas específicas
2. **executar_download_automatico.py** - Para automação customizada

## Scripts por Cenário

### ✅ Cenário 1: Problema Geral com Registros Pendentes
```bash
python resolver_registros_pendentes.py
# Escolha opção 1 no menu para download automático
```

### ✅ Cenário 2: Download para Data Específica
```bash
python baixar_xmls_data_especifica.py
```

### ✅ Cenário 3: Automação Customizada
```bash
python executar_download_automatico.py
```

## Menu do resolver_registros_pendentes.py

O script principal oferece estas opções:

1. **📥 Baixar XMLs automaticamente via pipeline**
   - Configura data_especifica=01/05/2025
   - Executa pipeline completo automaticamente
   - Recomendado para maioria dos casos

2. **📋 Criar arquivo com IDs pendentes**
   - Gera lista de IDs para processamento manual
   - Útil para análise ou processamento customizado

3. ** Apenas diagnóstico**
   - Analisa o problema sem executar downloads
   - Útil para investigação inicial

## Configurações Importantes

### Arquivo configuracao.ini
O script `resolver_registros_pendentes.py` modifica automaticamente:
```ini
[DOWNLOAD]
data_especifica = 01/05/2025
```

### Restore Automático
Após execução, a configuração é restaurada automaticamente.

## Monitoramento

Durante execução dos downloads, use o script de monitoramento:
```bash
# Em outra janela de terminal
python ../01_Analise_e_Diagnostico/monitor_progresso_pipeline.py
```
