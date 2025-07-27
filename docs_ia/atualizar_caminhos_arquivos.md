# Módulo: atualizar_caminhos_arquivos.py — Guia Técnico para IAs/Agentes

## Função do Módulo
Atualiza o banco SQLite com os caminhos corretos dos arquivos XML/ZIP no disco, marcando status de baixado e detectando arquivos vazios.

## Patterns e Estruturas
- Busca recursiva otimizada de arquivos
- Atualização em lote no banco
- Uso de views e índices otimizados
- Logging detalhado de progresso e em entrada e saida de funçõse criticas
- CLI para execução independente

## Principais Funções
- **atualizar_caminhos_no_banco**: pipeline principal de atualização
- **carregar_resultado_dir**: resolve path do diretório de resultados
- **listar_arquivos_xml_em**: busca recursiva eficiente
- **_atualizar_banco_otimizado**: update batch de caminhos/status
- **_verificar_arquivo_vazio**: detecção de arquivos inválidos

## Fluxo de Chamadas
1. Busca todos os arquivos XML/ZIP no disco
2. Mapeia chaves fiscais para caminhos
3. Atualiza status/caminho no banco em lote
4. Gera relatório final de execução

## Boas Práticas
- Sempre rodar após compactação/upload
- Logging detalhado de cada etapa
- Atualizar índices/views antes de grandes operações

---

## Detalhamento das Funções e Suas Chamadas Internas

### 1. `atualizar_caminhos_no_banco`
- Chama `carregar_resultado_dir` para obter path
- Chama `listar_arquivos_xml_em` (utils) para buscar arquivos
- Mapeia chaves fiscais para caminhos
- Chama `_atualizar_banco_otimizado` para update batch
- Chama `_gerar_relatorio_final` ao final
- Logging detalhado de cada etapa

### 2. `carregar_resultado_dir`
- Lê arquivo INI com `ConfigParser`
- Resolve path absoluto

### 3. `listar_arquivos_xml_em`
- Busca recursiva eficiente (utils)

### 4. `_atualizar_banco_otimizado`
- Executa update batch de caminhos/status
- Chama `_criar_indices_otimizados` se necessário
- Logging de progresso

### 5. `_verificar_arquivo_vazio`
- Verifica tamanho/conteúdo do arquivo
- Logging de arquivos problemáticos

### 6. `_gerar_relatorio_final`
- Consulta banco e gera estatísticas
- Logging de tempo e status
