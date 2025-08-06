# Contexto de Assincronia e Paralelismo no Pipeline Omie V3

## Visão Geral do Pipeline
O pipeline principal do projeto Omie V3 orquestra as seguintes etapas:
1. Carregamento e validação de configurações
2. Atualização de campos essenciais dos registros pendentes
3. Execução do pipeline principal (extração, processamento, download de XMLs)
4. Verificação de integridade dos XMLs
5. Atualização de caminhos no banco
6. Compactação dos resultados
7. Upload para OneDrive
8. Geração de relatórios

## O que faz sentido ser assíncrono?
- **Extração de dados da API Omie**: 
  - Listagem de notas fiscais (`listar_nfs`) e download de XMLs (`baixar_xmls`) são operações I/O-bound (HTTP requests, escrita em disco) e se beneficiam fortemente de código assíncrono (async/await, aiohttp, aiosqlite, aiofiles).
  - O pipeline assíncrono já está implementado em `src/extrator_async.py` e chamado via `asyncio.run()`.
- **Operações de escrita/leitura em disco em lote**:
  - Download e escrita de arquivos XML (com `aiofiles`) e leitura de grandes volumes de arquivos podem ser assíncronos.
- **Operações de banco de dados**:
  - Atualizações em lote podem ser feitas com `aiosqlite` para não bloquear o event loop.

## O que NÃO faz sentido ser assíncrono?
- **Compactação de arquivos (ZIP)**:
  - O processo de compactação é CPU/disk-bound e já é paralelizado via `ThreadPoolExecutor`. Tornar assíncrono não traz ganhos reais, pois o GIL do Python limita o paralelismo puro em operações CPU-bound.
- **Upload em lote para OneDrive**:
  - Pode ser feito em paralelo (thread pool/process pool), mas não necessariamente precisa ser assíncrono, a não ser que a biblioteca de upload suporte nativamente async.
- **Atualização de caminhos, verificação de arquivos, geração de relatórios**:
  - São operações batch, muitas vezes envolvendo I/O de disco e podem ser paralelizadas, mas não precisam ser async/await se já usam threads/processos.
- **Configuração, logging, validação de parâmetros**:
  - São operações rápidas, não I/O-bound, e não precisam de async.

## Resumo do fluxo ideal
- **Assíncrono**: Tudo que envolve chamadas HTTP, escrita/leitura de arquivos em grande volume, e operações de banco de dados em lote.
- **Paralelo (ThreadPool/ProcessPool)**: Compactação, upload em lote, varredura de arquivos, tarefas CPU/disk-bound.
- **Síncrono**: Configuração, logging, validação, controle de fluxo principal.

## Sugestão de arquitetura para IA
- Mantenha o pipeline principal síncrono, mas delegue etapas I/O-bound para funções assíncronas ou paralelas.
- Use `asyncio.run()` para orquestrar pipelines assíncronos.
- Use `ThreadPoolExecutor` para etapas CPU/disk-bound.
- Separe claramente funções assíncronas (async def) das funções paralelas (usando threads/processos).
- Documente no início de cada função se ela é I/O-bound (async), CPU-bound (thread/process), ou síncrona.

## Exemplo de fluxo (simplificado)
```python
# Síncrono
main() {
    carregar_configuracoes()
    atualizar_campos_registros_pendentes()
    asyncio.run(pipeline_assincrono())
    executar_compactador_resultado()  # ThreadPool
    executar_upload_resultado_onedrive()  # ThreadPool
    executar_relatorio_arquivos_vazios()
}

# Assíncrono
async def pipeline_assincrono():
    await listar_nfs(...)
    await baixar_xmls(...)
    # ...
```

## Observações finais
- O uso de async/await é recomendado para etapas que fazem muitas chamadas externas (API, disco, banco).
- O uso de threads/processos é recomendado para etapas que processam muitos arquivos ou fazem compressão/upload.
- O controle de fluxo principal deve ser simples e síncrono, apenas orquestrando as etapas.

---
Este arquivo serve como referência para IAs e desenvolvedores entenderem rapidamente onde aplicar assincronia, paralelismo e manter o código limpo, eficiente e escalável.
