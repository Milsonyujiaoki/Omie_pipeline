# Módulo: verificador_xmls.py — Guia Técnico para IAs/Agentes

## Função do Módulo
Verifica a existência e integridade dos arquivos XML no disco, atualizando o banco de dados para marcar quais notas estão baixadas e válidas.

## Patterns e Estruturas
- Paralelismo com ThreadPoolExecutor
- Busca eficiente de arquivos no disco
- Atualização em lote do status no banco
- Logging detalhado de progresso e estatísticas

## Principais Funções
- **verificar_arquivo_no_disco**: valida existência e integridade de XML
- **verificar_arquivos_existentes**: pipeline de verificação paralela
- **atualizar_status_no_banco**: update batch de status xml_baixado
- **verificar**: pipeline completo (disco + banco)

## Fluxo de Chamadas
1. Carrega todas as chaves do banco
2. Verifica existência/integridade dos arquivos no disco (paralelo)
3. Atualiza status xml_baixado no banco em lote

## Boas Práticas
- Rodar após grandes downloads ou movimentações de arquivos
- Logging detalhado de progresso e estatísticas
- Usar batch_size adequado ao volume de dados

---

## Detalhamento das Funções e Suas Chamadas Internas

### 1. `verificar`
- Chama `verificar_arquivos_existentes` para pipeline de disco
- Chama `atualizar_status_no_banco` para update batch
- Logging de progresso

### 2. `verificar_arquivos_existentes`
- Consulta banco para obter chaves
- Usa `ThreadPoolExecutor` para paralelismo
- Para cada registro, chama `verificar_arquivo_no_disco`
- Coleta chaves válidas
- Logging de progresso e estatísticas

### 3. `verificar_arquivo_no_disco`
- Chama `gerar_xml_path` ou `gerar_xml_path_otimizado` (utils) para obter caminho
- Verifica existência e tamanho do arquivo
- Logging de erro em caso de falha

### 4. `atualizar_status_no_banco`
- Executa update batch de status xml_baixado
- Logging de progresso
