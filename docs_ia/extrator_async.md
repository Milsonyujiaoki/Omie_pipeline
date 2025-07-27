# Módulo: extrator_async.py — Guia Técnico para IAs/Agentes

## Função do Módulo
Orquestra a extração assíncrona de dados da API Omie, salvando notas fiscais e XMLs no banco e disco. Utiliza asyncio, aiohttp e aiosqlite para máxima performance em I/O.

## Patterns e Estruturas
- Funções assíncronas para todas operações de rede e banco
- Rate limiting com semáforo e sleeps
- Uso de `aiosqlite` para updates em lote
- Logging detalhado por etapa
- Manipulação de dados em memória é síncrona

## Principais Funções
- **listar_nfs**: lista notas fiscais da API e salva no banco
- **baixar_xmls**: baixa XMLs pendentes em paralelo
- **baixar_xml_individual**: download e update de status
- **atualizar_anomesdia**: update assíncrono do campo anomesdia
- **call_api_com_retentativa**: wrapper robusto para chamadas API com retry

## Fluxo de Chamadas
1. `main` carrega config, inicializa banco e client Omie
2. Chama `listar_nfs` (API → banco)
3. Chama `atualizar_anomesdia` (update datas no banco)
4. Chama `baixar_xmls` (API → disco → banco)

## Boas Práticas
- Sempre await em funções de I/O
- Tratar exceções de API e banco com logging
- Usar semáforo para limitar concorrência
- Não tornar funções utilitárias assíncronas sem necessidade

## Exemplo de Fluxo
- `main` → `listar_nfs` → `atualizar_anomesdia` → `baixar_xmls` → `baixar_xml_individual`

---

## Detalhamento das Funções e Suas Chamadas Internas

### 1. `main`
- Carrega configurações (`carregar_configuracoes` do omie_client_async)
- Inicializa banco (`iniciar_db` do utils)
- Cria client Omie (`OmieClient`)
- Chama:
    - `listar_nfs`
    - `atualizar_anomesdia`
    - `baixar_xmls`

### 2. `listar_nfs`
- Loop de páginas:
    - Chama `call_api_com_retentativa` (API Omie)
    - Para cada nota:
        - Chama `normalizar_nota` (transforma dict)
    - Chama `salvar_varias_notas` (utils) para inserir no banco
- Pode chamar `_verificar_views_e_indices_disponiveis` (utils) para otimizações

### 3. `atualizar_anomesdia`
- Consulta registros sem anomesdia usando `aiosqlite`
- Para cada registro:
    - Chama `normalizar_data` (utils)
    - Monta valor anomesdia
- Executa update batch no banco

### 4. `baixar_xmls`
- Consulta pendências no banco (`conexao_otimizada` do utils)
- Para cada registro:
    - Chama `baixar_xml_individual` (em paralelo)

### 5. `baixar_xml_individual`
- Chama `gerar_pasta_xml_path` (utils) para obter caminho
- Chama `call_api_com_retentativa` (API Omie)
- Salva XML no disco
- Chama `atualizar_status_xml` (utils) para atualizar banco

### 6. `call_api_com_retentativa`
- Chama `client.call_api` (OmieClient)
- Implementa retry/backoff

---

> Todas as funções de I/O (API, banco, disco) são await/assíncronas. Funções utilitárias de manipulação de dados são síncronas e centralizadas em `utils.py`.
