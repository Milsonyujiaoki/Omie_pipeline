# Módulo: compactador_resultado.py — Guia Técnico para IAs/Agentes

## Função do Módulo
Realiza a compactação em lotes dos XMLs processados, organizando em subpastas persistentes e gerando arquivos ZIP otimizados para upload.

## Patterns e Estruturas
- Processamento em lotes (batch)
- Uso de ThreadPoolExecutor para paralelismo
- Subpastas persistentes para cada lote (ex: 24_lote_0001)
- Logging detalhado de performance
- Controle de concorrência com lockfiles

## Principais Funções
- **compactar_pasta_otimizada**: organiza, copia e compacta lotes
- **criar_zip_otimizado**: compactação robusta com validação
- **processar_multiplas_pastas**: paralelismo de lotes
- **obter_pastas_para_compactar**: busca hierárquica eficiente
- **compactar_resultados**: pipeline completo, com upload opcional

## Detalhamento das Funções e Suas Chamadas Internas

### 1. `compactar_resultados`
- Chama `obter_pastas_para_compactar`
- Chama `processar_multiplas_pastas`
- (Opcional) Chama `fazer_upload_lote` (upload_onedrive)
- Logging de cada etapa

### 2. `obter_pastas_para_compactar`
- Percorre diretórios com `Path.iterdir`
- Aplica filtros e logging

### 3. `processar_multiplas_pastas`
- Usa `ThreadPoolExecutor` para paralelismo
- Para cada pasta, chama `compactar_pasta_otimizada`
- Coleta resultados e logging

### 4. `compactar_pasta_otimizada`
- Cria lockfile (`criar_lockfile` do utils)
- Divide arquivos em lotes
- Para cada lote:
    - Cria subpasta persistente
    - Copia arquivos (shutil.copy2)
    - Chama `criar_zip_otimizado`
- Remove lockfile ao final
- Logging detalhado

### 5. `criar_zip_otimizado`
- Usa `zipfile.ZipFile` para compactar
- Valida integridade do ZIP
- Logging de sucesso/erro

## Fluxo de Chamadas
1. Busca pastas/dias a compactar
2. Para cada pasta, divide em lotes e cria subpastas persistentes
3. Compacta cada subpasta em ZIP
4. (Opcional) Faz upload dos ZIPs

## Boas Práticas
- Nunca mover arquivos originais, apenas copiar
- Garantir atomicidade com lockfiles
- Logging em cada etapa crítica
- Processar em paralelo para grandes volumes
