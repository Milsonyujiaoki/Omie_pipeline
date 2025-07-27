# Organização dos Utilitários e Testes - Extrator Omie V3
## Relatórios Consolidados

Todos os relatórios de organização, testes e utilitários foram consolidados neste README. Relatórios antigos removidos do diretório principal:

- RELATORIO_ORGANIZACAO_TESTES.md
- RELATORIO_LOGS_ESTRUTURADOS_ATUALIZAR_CAMINHOS.md
- RELATORIO_DIVISAO_UTILS.md
- RELATORIO_COMPLETO_ORGANIZACAO.md

Consulte as seções abaixo para detalhes de estrutura, backup, critérios de organização e navegação.

## Estrutura Organizacional

### 📊 01_Analise_e_Diagnostico
Scripts para análise e diagnóstico dos dados no banco:

- **analise_registros_pendentes.py** - Análise detalhada dos registros pendentes com estatísticas completas
- **diagnostico_registros_pendentes.py** - Diagnóstico completo dos registros pendentes por data
- **verificar_status_banco.py** - Verificação rápida do status geral do banco
- **monitor_progresso_pipeline.py** - Monitoramento do progresso do pipeline em tempo real

### 🚀 02_Download_e_Execucao  
Scripts para download e execução de operações:

- **baixar_xmls_data_especifica.py** - Download de XMLs para data específica (ex: 01/05/2025)
- **executar_download_automatico.py** - Execução automática de download pendentes
- **resolver_registros_pendentes.py** - Solução completa para registros pendentes

### 🔧 03_Correcao_e_Manutencao
Scripts para correção e manutenção do sistema:

- **corrigir_erros_utils.py** - Correção de erros específicos no código (ex: coluna 'status')
- **padronizar_formato_datas.py** - Padronização do formato de datas no banco
- **verificar_integridade_xmls.py** - Verificação da integridade dos XMLs baixados

### 🧪 04_Testes_e_Validacao
Scripts para testes e validação:

- **testar_conectividade_api.py** - Teste de conectividade com a API Omie
- **verificar_status_simples.py** - Verificação simples e rápida do status

## Guia de Uso

### Para Análise Inicial
1. Execute `analise_registros_pendentes.py` para visão geral
2. Use `diagnostico_registros_pendentes.py` para análise detalhada
3. Monitore com `monitor_progresso_pipeline.py` durante execução

### Para Resolução de Problemas
1. Use `resolver_registros_pendentes.py` para solução automática
2. Execute `baixar_xmls_data_especifica.py` para datas específicas
3. Aplique `corrigir_erros_utils.py` para correções de código

### Para Manutenção
1. Padronize datas com `padronizar_formato_datas.py`
2. Verifique integridade com `verificar_integridade_xmls.py`
3. Teste conectividade com `testar_conectividade_api.py`

## Convenções de Nomenclatura

### Prefixos por Categoria:
- **analise_** - Scripts de análise de dados
- **diagnostico_** - Scripts de diagnóstico detalhado  
- **verificar_** - Scripts de verificação simples
- **monitor_** - Scripts de monitoramento
- **baixar_** - Scripts de download
- **executar_** - Scripts de execução automática
- **resolver_** - Scripts de resolução de problemas
- **corrigir_** - Scripts de correção
- **padronizar_** - Scripts de padronização
- **testar_** - Scripts de teste

### Sufixos Descritivos:
- **_registros_pendentes** - Foca em registros pendentes
- **_status_banco** - Verifica status do banco
- **_xmls** - Trabalha com arquivos XML
- **_datas** - Manipula formatação de datas
- **_api** - Interage com API externa
- **_automatico** - Execução automática
- **_simples** - Versão simplificada

## Melhorias Implementadas

1. **Organização por Função**: Scripts agrupados por propósito
2. **Nomenclatura Consistente**: Padrão de nomes descritivos
3. **Documentação Clara**: README explicativo para cada categoria
4. **Estrutura Escalável**: Fácil adição de novos scripts
5. **Navegação Intuitiva**: Numeração para ordem de uso comum

## Scripts Descontinuados/Redundantes

Alguns scripts foram identificados como redundantes:
- `check_status.py` e `verificar_status.py` fazem função similar
- Foram unificados em `verificar_status_simples.py`

## Próximos Passos

1. Mover arquivos para suas respectivas pastas
2. Renomear arquivos conforme nova convenção
3. Atualizar imports e referências
4. Criar scripts README.md específicos por categoria
