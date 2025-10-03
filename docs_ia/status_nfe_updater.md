# Sistema de Atualização de Status das NFe

## 📋 Visão Geral

O **Sistema de Atualização de Status das NFe** é uma nova funcionalidade integrada ao Omie Pipeline V3 que consulta a API Omie para obter e atualizar o status atual das notas fiscais no banco de dados local.

### 🎯 Objetivos

- **Identificar notas canceladas**: Detecta NFe que foram canceladas após o download
- **Acompanhar status**: Monitora situação das NFe (autorizada, rejeitada, denegada, etc.)
- **Manter dados atualizados**: Sincroniza status local com informações da SEFAZ via Omie
- **Facilitar análises**: Permite filtros e relatórios baseados no status das notas

## 🚀 Funcionalidades

### ✅ Status Suportados

| Status | Descrição | Ação Recomendada |
|--------|-----------|------------------|
| `AUTORIZADA` | NFe autorizada pela SEFAZ | ✅ Processamento normal |
| `CANCELADA` | NFe cancelada | ⚠️ Ignorar nos cálculos |
| `REJEITADA` | NFe rejeitada pela SEFAZ | ❌ Verificar erros |
| `DENEGADA` | NFe denegada | ❌ Verificar irregularidades |
| `INUTILIZADA` | Numeração inutilizada | ⚠️ Ignorar nos cálculos |
| `PROCESSANDO` | NFe em processamento | ⏳ Aguardar conclusão |
| `PENDENTE` | NFe pendente | ⏳ Aguardar processamento |
| `INDEFINIDO` | Status não identificado | 🔍 Investigar manualmente |

### 🔧 Recursos Técnicos

- **Processamento assíncrono** para melhor performance
- **Controle de rate limiting** respeitando limites da API Omie
- **Processamento em lotes** otimizado
- **Retry automático** para falhas temporárias
- **Logging detalhado** com métricas de progresso
- **Modo simulação** para testes seguros

## 📁 Estrutura dos Arquivos

```
Omie_pipeline/
├── src/
│   ├── status_nfe_updater.py          # 🔧 Módulo principal
│   └── omie_client_async.py           # 🌐 Cliente API (já existente)
├── Utilitarios/
│   ├── executar_status_updater.py     # 🚀 Script executável
│   └── teste_status_updater.py        # 🧪 Script de testes
├── main_old.py                        # 🏗️ Pipeline principal (modificado)
└── configuracao.ini                   # ⚙️ Configurações (já existente)
```

## 🛠️ Como Usar

### 1️⃣ Execução Standalone

```bash
# Navegue até o diretório Utilitarios
cd Utilitarios

# Simulação (não altera dados)
python executar_status_updater.py --dry-run

# Execução real
python executar_status_updater.py

# Teste com poucos registros
python executar_status_updater.py --test
```

### 2️⃣ Integração no Pipeline

A funcionalidade foi **automaticamente integrada** no pipeline principal (`main_old.py`) como **Fase 6.5**.

```bash
# Executa pipeline completo (inclui atualização de status)
python main_old.py
```

A atualização de status acontece após:
- ✅ Download dos XMLs
- ✅ Verificação de integridade  
- ✅ Compactação dos resultados
- ✅ Atualização de caminhos no banco

### 3️⃣ Testes e Validação

```bash
# Testa todas as funcionalidades (modo seguro)
python teste_status_updater.py

# Teste real com poucos dados (altera banco!)
python teste_status_updater.py --real

# Ajuda sobre os testes
python teste_status_updater.py --help
```

## ⚙️ Configuração

### Arquivo `configuracao.ini`

O sistema usa as **mesmas configurações** já existentes no pipeline:

```ini
[omie_api]
app_key = SUA_APP_KEY_AQUI
app_secret = SEU_APP_SECRET_AQUI
base_url_nf = https://app.omie.com.br/api/v1/produtos/nfconsultar/
calls_per_second = 4

[paths]
db_path = omie.db
```

### Banco de Dados

O sistema usa a **coluna `status`** na tabela `notas`. Se não existir, será criada automaticamente:

```sql
-- Coluna adicionada automaticamente se necessário
ALTER TABLE notas ADD COLUMN status TEXT DEFAULT NULL;
```

## 📊 Endpoints da API Utilizados

### 1. `ListarNFesEmitidas`
- **URL**: `https://app.omie.com.br/api/v1/nfe/`
- **Uso**: Consultas em lote para múltiplas NFe
- **Vantagem**: Eficiente para volumes grandes

### 2. `ObterNfe`  
- **URL**: `https://app.omie.com.br/api/v1/produtos/nfconsultar/`
- **Uso**: Consultas individuais detalhadas
- **Vantagem**: Informações mais completas

## 📈 Performance e Limites

### Configurações Recomendadas

| Parâmetro | Valor | Descrição |
|-----------|-------|-----------|
| `calls_per_second` | 4 | Requisições por segundo |
| `max_concurrent` | 2 | Requisições simultâneas |
| `batch_size` | 100 | Registros por lote |
| `limite_notas` | 500 | Máximo por execução |

### Estimativa de Tempo

- **500 notas**: ~2-3 minutos
- **1.000 notas**: ~4-6 minutos  
- **5.000 notas**: ~20-30 minutos

## 🔍 Troubleshooting

### Problemas Comuns

#### ❌ Erro 403 (Forbidden)
```
Solução: Verificar app_key e app_secret no configuracao.ini
```

#### ❌ Erro 429 (Rate Limit)
```
Solução: Sistema tem retry automático. Aguarde ou diminua calls_per_second
```

#### ❌ Coluna 'status' não existe
```
Solução: Execute o teste que criará a coluna automaticamente:
python teste_status_updater.py
```

#### ❌ Timeout nas requisições
```
Solução: Verifique conexão de internet e status da API Omie
```

### Logs Importantes

```
[STATUS.API.RATE_LIMIT] - Rate limit da API atingido
[STATUS.UPDATE] - Status atualizado no banco
[STATUS.INDIVIDUAL] - Consulta individual executada
[STATUS.LOTE] - Processamento de lote iniciado
```

## 🧪 Testes e Validação

### Scripts de Teste

1. **`teste_status_updater.py`**
   - ✅ Verifica estrutura do banco
   - ✅ Testa configurações da API
   - ✅ Valida conexão com Omie
   - ✅ Executa funcionalidade completa

2. **Modo Simulação (`--dry-run`)**
   - 🧪 Executa sem alterar dados
   - 📊 Gera estatísticas simuladas
   - ✅ Valida toda a lógica

### Validação Manual

```sql
-- Ver distribuição de status
SELECT status, COUNT(*) as quantidade
FROM notas 
WHERE status IS NOT NULL 
GROUP BY status 
ORDER BY quantidade DESC;

-- Ver notas sem status
SELECT COUNT(*) as sem_status
FROM notas 
WHERE status IS NULL OR status = '';

-- Ver últimas atualizações
SELECT cChaveNFe, status, mensagem_erro
FROM notas 
WHERE status IS NOT NULL 
ORDER BY rowid DESC 
LIMIT 10;
```

## 📋 Roadmap e Melhorias Futuras

### Versão Atual (V1.0)
- ✅ Atualização básica de status
- ✅ Integração no pipeline principal
- ✅ Controle de rate limiting
- ✅ Modo simulação

### Próximas Versões
- 🔮 **V1.1**: Agendamento automático
- 🔮 **V1.2**: Dashboard de status
- 🔮 **V1.3**: Notificações por email
- 🔮 **V1.4**: Histórico de mudanças de status

## 🤝 Contribuição

Para contribuir com melhorias:

1. 🧪 Execute os testes: `python teste_status_updater.py`
2. 📝 Documente mudanças no código
3. 🔍 Teste em ambiente de desenvolvimento
4. 📊 Valide impacto na performance

## 📞 Suporte

Em caso de dúvidas ou problemas:

1. 📋 Consulte os logs em `log/status_updater_*.log`
2. 🧪 Execute `python teste_status_updater.py` para diagnóstico
3. 🔍 Verifique configurações em `configuracao.ini`
4. 📊 Analise métricas do banco de dados

---

**Status do Sistema**: ✅ **Pronto para Produção**  
**Última Atualização**: Setembro 2025  
**Compatibilidade**: Omie Pipeline V3+
