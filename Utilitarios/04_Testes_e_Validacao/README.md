# 🧪 Testes e Validação

Scripts para testes de conectividade e validação do sistema.

## Scripts Disponíveis

### `testar_conectividade_api.py`
**Propósito**: Testa a conectividade e funcionamento da API Omie  
**Uso**: Para verificar se a API está funcionando corretamente  
**Testes realizados**:
- Conectividade com endpoint da API
- Autenticação com app_key e app_secret
- Resposta válida da API
- Tempo de resposta
- Estrutura de dados retornada

### `verificar_status_simples.py`
**Propósito**: Verificação rápida e simples do status do banco  
**Uso**: Para check-up rápido sem detalhes extensos  
**Verificações**:
- Total de registros no banco
- Registros baixados vs pendentes
- Status específico para data 01/05/2025
- Percentual de conclusão

## Quando Usar Cada Script

### 🌐 Problemas de Conectividade
```bash
python testar_conectividade_api.py
```
**Use quando**:
- Downloads estão falhando
- Suspeita de problemas na API
- Validar credenciais
- Verificar configuração de rede

### 📊 Verificação Rápida de Status
```bash
python verificar_status_simples.py
```
**Use quando**:
- Precisa de status rápido
- Verificação pré-execução
- Check-up pós-execução
- Monitoramento básico

## Detalhes dos Testes

### testar_conectividade_api.py

**Configurações testadas**:
- URL base da API
- Credenciais (app_key/app_secret)
- Timeout de conexão
- Formato de payload

**Resultados do teste**:
- ✅ **Sucesso**: API funcionando corretamente
- ⚠️ **Aviso**: API funcionando com problemas menores
- ❌ **Erro**: API não funcionando

**Exemplo de saída**:
```
=== TESTE DE CONECTIVIDADE API OMIE ===
✅ Conectividade: OK
✅ Autenticação: OK  
✅ Resposta: Válida
Tempo de resposta: 1.2s
📊 Dados retornados: 150 registros
```

### verificar_status_simples.py

**Métricas exibidas**:
- Total de registros no banco
- Registros com XML baixado
- Registros pendentes
- Foco específico em 01/05/2025
- Percentual de progresso

**Exemplo de saída**:
```
=== STATUS DOS REGISTROS ===
Total: 810,768
Baixados: 777,397 (95.9%)
Pendentes: 33,371 (4.1%)

Data: 01/05/2025
Total: 33,371
Baixados: 0 (0.0%)
Pendentes: 33,371 (100.0%)
```

## Diagnóstico de Problemas

###  Fluxo de Diagnóstico

1. **Verificação básica**:
   ```bash
   python verificar_status_simples.py
   ```

2. **Se há registros pendentes, testar API**:
   ```bash
   python testar_conectividade_api.py
   ```

3. **Se API está OK, ir para análise detalhada**:
   ```bash
   python ../01_Analise_e_Diagnostico/analise_registros_pendentes.py
   ```

### 🚨 Problemas Comuns

**API não responde**:
- Verificar conexão de internet
- Validar credenciais no arquivo configuracao.ini
- Verificar se endpoint mudou

**Registros pendentes altos**:
- Executar análise detalhada
- Verificar logs de erro
- Usar scripts de download específicos

**Performance ruim**:
- Verificar tempo de resposta da API
- Analisar logs de execução
- Considerar ajuste de concorrência

## Automação de Testes

### Script de Teste Completo
Você pode criar um teste completo combinando ambos:

```bash
#!/bin/bash
echo "=== TESTE COMPLETO DO SISTEMA ==="
echo "1. Verificando status..."
python verificar_status_simples.py

echo -e "\n2. Testando API..."
python testar_conectividade_api.py

echo -e "\n=== TESTE CONCLUÍDO ==="
```

### Agendamento de Testes
Recomenda-se executar os testes:
- **Diariamente**: verificar_status_simples.py
- **Semanalmente**: testar_conectividade_api.py
- **Antes de operações críticas**: ambos
