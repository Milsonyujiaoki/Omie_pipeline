# Módulo: utils.py — Guia Técnico para IAs/Agentes

## Função do Módulo
Centraliza utilitários para manipulação de dados, arquivos, banco de dados e validações. É a espinha dorsal do pipeline, garantindo padronização, robustez e performance.

## Estruturas e Patterns
- Funções puras e side-effects controlados
- Uso de dataclasses para configs/resultados
- Context managers para conexões SQLite
- Logging contextualizado
- Type hints e docstrings detalhadas

## Principais Funções
- **normalizar_data**: converte datas de múltiplos formatos para dd/mm/YYYY
- **normalizar_valor_nf**: robusto para valores numéricos
- **transformar_em_tuple**: prepara dict para insert otimizado
- **descobrir_todos_xmls**: busca recursiva eficiente
- **criar_lockfile**: controle de concorrência
- **listar_arquivos_xml_em**: listagem otimizada
- **respeitar_limite_requisicoes**: rate limiting
- **iniciar_db**: inicialização robusta do banco
- **atualizar_status_xml**: update seguro de status
- **salvar_varias_notas**: insert batch com validação

## Detalhamento das Funções e Suas Chamadas Internas

### 1. `normalizar_data`
- Recebe string de data
- Tenta múltiplos formatos usando `datetime.strptime`
- Logging de warning em caso de falha

### 2. `normalizar_valor_nf`
- Recebe valor (str, float, int)
- Limpa, converte e trata erros
- Logging de warning em caso de valor inválido

### 3. `transformar_em_tuple`
- Recebe dict de nota
- Chama `normalizar_data`, `normalizar_valor_nf`, funções auxiliares internas
- Logging de erro em caso de campos ausentes

### 4. `descobrir_todos_xmls`
- Usa `Path.rglob` para busca recursiva

### 5. `criar_lockfile`
- Cria arquivo `.lock` na pasta
- Usa métodos de `Path` para criar diretórios/arquivos

### 6. `listar_arquivos_xml_em`
- Usa `Path.rglob` ou `Path.iterdir` para listar arquivos
- Logging de warning se pasta não existe

### 7. `respeitar_limite_requisicoes`
- Usa `monotonic` e `sleep` para controlar intervalo

### 8. `iniciar_db`
- Chama `validar_parametros_banco`, `criar_schema_base`, `criar_indices_otimizados`
- Usa context manager para conexão
- Logging de cada etapa

### 9. `atualizar_status_xml`
- Atualiza campos no banco
- Logging de erro em caso de falha

### 10. `salvar_varias_notas`
- Valida e transforma cada registro com `transformar_em_tuple`
- Executa insert batch
- Logging de sucesso/erro

## Fluxo de Chamadas
- Usado por praticamente todos os módulos
- Funções de manipulação de arquivos e banco são wrappers para garantir atomicidade e logging
- Funções de normalização são chamadas em todos os fluxos de ETL

## SCHEMA do Banco (ver README_PROJETO_GERAL.md)

## Boas Práticas
- Sempre usar context managers para conexões
- Validar todos os dados antes de inserir/atualizar
- Logging em todos os erros e warnings
- Preferir funções utilitárias deste módulo para manipulação de arquivos/dados

## Exemplo de Fluxo
1. Recebe dict de nota fiscal
2. Chama `normalizar_data` e `normalizar_valor_nf`
3. Usa `transformar_em_tuple` para preparar para insert
4. Insere com `salvar_varias_notas`
5. Atualiza status com `atualizar_status_xml`
