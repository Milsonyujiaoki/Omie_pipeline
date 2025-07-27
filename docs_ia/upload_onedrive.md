# Módulo: upload_onedrive.py — Guia Técnico para IAs/Agentes

## Função do Módulo
Gerencia upload em lote de arquivos ZIP para OneDrive/SharePoint, com autenticação OAuth2, controle de duplicatas e cache de estrutura de pastas.

## Patterns e Estruturas
- Autenticação OAuth2 (client credentials)
- Upload em lote com retry e backoff
- Cache de pastas para performance
- Logging detalhado de progresso e falhas
- Configuração via .env e INI

## Principais Funções
- **fazer_upload_lote**: upload em lote, controle de sucesso/erro
- **upload_arquivo_unico**: upload individual, usado internamente
- **validar_configuracao_onedrive**: sanity check de variáveis
- **OneDriveClient**: cliente de API com métodos de upload

## Fluxo de Chamadas
1. Recebe lista de ZIPs a enviar
2. Autentica e valida estrutura
3. Faz upload em lote, com retry/backoff
4. Atualiza cache/histórico de uploads

## Boas Práticas
- Sempre validar variáveis de ambiente antes de iniciar
- Logging detalhado de cada upload
- Retry automático para falhas temporárias
- Nunca sobrescrever arquivos sem versionamento

---

## Detalhamento das Funções e Suas Chamadas Internas

### 1. `fazer_upload_lote`
- Recebe lista de arquivos
- Para cada arquivo:
    - Chama `upload_arquivo_unico`
    - Atualiza histórico/cache
- Logging de sucesso/erro

### 2. `upload_arquivo_unico`
- Chama métodos do `OneDriveClient` para autenticação e upload
- Implementa retry/backoff
- Logging detalhado

### 3. `validar_configuracao_onedrive`
- Verifica variáveis de ambiente e INI
- Logging de erro se faltar algo

### 4. `OneDriveClient`
- Métodos para autenticação OAuth2
- Métodos para upload de arquivos (chunked ou simples)
- Gerencia cache de pastas
- Logging em cada etapa
