# 📊 Análise e Diagnóstico

Scripts para análise detalhada e diagnóstico dos dados no banco de dados.

## Scripts Disponíveis

### `analise_registros_pendentes.py`
**Propósito**: Análise detalhada dos registros pendentes com estatísticas completas  
**Uso**: Quando precisa de uma visão geral completa dos registros pendentes  
**Saída**: Relatório detalhado com:
- Estatísticas gerais do banco
- Distribuição de registros por data
- Análise de registros pendentes
- Identificação de padrões e problemas

### `diagnostico_registros_pendentes.py`
**Propósito**: Diagnóstico específico e profundo dos registros pendentes  
**Uso**: Para investigação detalhada de problemas específicos  
**Saída**: Diagnóstico completo com:
- Análise por período de data
- Distribuição temporal
- Identificação de lacunas nos dados
- Recomendações de ação

### `monitor_progresso_pipeline.py`
**Propósito**: Monitoramento em tempo real do progresso do pipeline  
**Uso**: Durante execução do pipeline para acompanhar progresso  
**Saída**: Monitoramento contínuo com:
- Status atual do banco
- Progresso de downloads
- Taxa de sucesso/erro
- Estimativas de tempo

### `verificar_status_banco.py`
**Propósito**: Verificação rápida do status geral do banco  
**Uso**: Para check-up rápido antes de iniciar operações  
**Saída**: Status resumido com:
- Total de registros
- Registros baixados vs pendentes
- Status por data específica
- Saúde geral do banco

## Ordem de Execução Recomendada

1. **verificar_status_banco.py** - Para visão geral inicial
2. **analise_registros_pendentes.py** - Para análise detalhada
3. **diagnostico_registros_pendentes.py** - Para investigação profunda
4. **monitor_progresso_pipeline.py** - Durante execução de operações

## Exemplos de Uso

```bash
# Verificação rápida inicial
python verificar_status_banco.py

# Análise completa
python analise_registros_pendentes.py

# Diagnóstico específico
python diagnostico_registros_pendentes.py

# Monitoramento (em outra janela durante execução)
python monitor_progresso_pipeline.py
```
