# Módulo: report_arquivos_vazios.py — Guia Técnico para IAs/Agentes

## Função do Módulo
Detecta, reporta e remove arquivos XML vazios ou corrompidos, gerando relatórios detalhados para análise e auditoria.

## Patterns e Estruturas
- Processamento em lotes para grandes volumes
- Paralelismo com ThreadPoolExecutor
- Detecção otimizada de arquivos vazios (chunks)
- Logging detalhado e relatórios em Excel

## Principais Funções
- **is_text_file_empty**: detecção eficiente de arquivos vazios
- **verificar_arquivo_rapido**: validação rápida de arquivos
- **encontrar_arquivos_vazios_ou_zero_otimizado**: busca otimizada
- **remover_duplicatas_existentes**: filtro de relatórios
- **salvar_relatorio_otimizado**: geração de relatório Excel

## Fluxo de Chamadas
1. Busca todos os arquivos no diretório
2. Processa em lotes para detecção de vazios/corrompidos
3. Gera relatório detalhado (Excel)
4. (Opcional) Remove duplicatas e atualiza banco

## Boas Práticas
- Rodar periodicamente para garantir integridade
- Logging detalhado de cada etapa
- Relatórios sempre salvos antes de remoção em massa

---

## Detalhamento das Funções e Suas Chamadas Internas

### 1. `gerar_relatorio`
- Chama `encontrar_arquivos_vazios_ou_zero_otimizado` para busca
- Chama `remover_duplicatas_existentes` para filtrar
- Chama `salvar_relatorio_otimizado` para salvar Excel
- Logging detalhado

### 2. `encontrar_arquivos_vazios_ou_zero_otimizado`
- Busca arquivos com `Path.rglob`
- Processa em lotes (batches)
- Usa `ThreadPoolExecutor` para paralelismo
- Para cada arquivo, chama `verificar_arquivo_rapido`
- Logging de progresso

### 3. `verificar_arquivo_rapido`
- Verifica tamanho e conteúdo do arquivo
- Chama `is_text_file_empty` para detecção eficiente
- Logging de arquivos problemáticos

### 4. `is_text_file_empty`
- Lê arquivo em chunks
- Verifica se só há espaços/brancos
- Logging de erro em caso de exceção

### 5. `remover_duplicatas_existentes`
- Lê relatório anterior (Excel)
- Filtra registros já reportados

### 6. `salvar_relatorio_otimizado`
- Salva relatório Excel
- Logging de sucesso/erro
