# Extrator Omie V3 — Guia de Contexto para IAs e Agentes

## Visão Geral do Projeto
O Extrator Omie V3 é um pipeline robusto para extração, processamento, compactação e upload de dados fiscais (XMLs de NFe) provenientes da API Omie. O sistema foi projetado para alta performance, escalabilidade, resiliência a falhas e fácil manutenção, utilizando padrões modernos de Python, concorrência, logging estruturado e integração com serviços externos (OneDrive/SharePoint).

### Principais Componentes
- **extração assíncrona** de dados da API Omie
- **processamento e validação** de XMLs
- **compactação** em lotes otimizados
- **upload automático** para OneDrive/SharePoint
- **atualização e verificação** de banco de dados SQLite
- **relatórios e métricas** detalhadas

### Arquitetura e Patterns
- Modularização por responsabilidade (cada módulo é autocontido)
- Uso extensivo de funções utilitárias centralizadas (`utils.py`)
- Concorrência: `asyncio` para I/O-bound, `ThreadPoolExecutor` para CPU-bound
- Logging estruturado e contextualizado
- Configuração via INI e variáveis de ambiente
- Operações batch e paralelismo para performance
- Tratamento robusto de erros e fallback seguro
- Testes e validações em múltiplas camadas

### Estilo de Programação
- PEP 8, PEP 20 (Zen of Python)
- Type hints em todas as funções públicas
- Docstrings Google/NumPy
- Funções puras e side-effects controlados
- Preferência por funções de ordem superior, comprehensions, context managers
- Uso de dataclasses para estruturas de dados

### Fluxo Global de Execução
1. **Carregamento de configurações** (`configuracao.ini`, `.env`)
2. **Extração assíncrona** de notas fiscais e XMLs (`extrator_async.py`)
3. **Processamento e validação** dos XMLs (`verificador_xmls.py`, `utils.py`)
4. **Compactação** dos arquivos em lotes (`compactador_resultado.py`)
5. **Upload** dos lotes para OneDrive (`upload_onedrive.py`)
6. **Atualização de caminhos** e status no banco (`atualizar_caminhos_arquivos.py`)
7. **Geração de relatórios** e métricas (`report_arquivos_vazios.py`)

### SCHEMA do Banco de Dados (notas)
```sql
CREATE TABLE IF NOT EXISTS notas (
    cChaveNFe TEXT PRIMARY KEY,
    nIdNF INTEGER,
    nIdPedido INTEGER,
    dCan TEXT,
    dEmi TEXT,
    dInut TEXT,
    dReg TEXT,
    dSaiEnt TEXT,
    hEmi TEXT,
    hSaiEnt TEXT,
    mod TEXT,
    nNF TEXT,
    serie TEXT,
    tpAmb TEXT,
    tpNF TEXT,
    cnpj_cpf TEXT,
    cRazao TEXT,
    vNF REAL,
    anomesdia INTEGER DEFAULT NULL,
    xml_vazio INTEGER DEFAULT 0,
    xml_baixado BOOLEAN DEFAULT 0,
    baixado_novamente BOOLEAN DEFAULT 0,
    status TEXT DEFAULT NULL,
    erro BOOLEAN DEFAULT 0,
    erro_xml TEXT DEFAULT NULL,
    mensagem_erro TEXT DEFAULT NULL,
    caminho_arquivo TEXT DEFAULT NULL
)
```

### Boas Práticas e Regras Gerais
- Sempre validar entradas e saídas de funções
- Logging detalhado em cada etapa crítica
- Operações de banco de dados em transações e context managers
- Compactação e upload em lotes para evitar gargalos
- Uso de índices e pragmas otimizados no SQLite
- Separação clara entre lógica de negócio, I/O e utilitários
- Testes unitários e de integração recomendados para cada módulo

---

## Índice dos Documentos de Contexto por Módulo
- [utils.md](./utils.md)
- [extrator_async.md](./extrator_async.md)
- [compactador_resultado.md](./compactador_resultado.md)
- [upload_onedrive.md](./upload_onedrive.md)
- [atualizar_caminhos_arquivos.md](./atualizar_caminhos_arquivos.md)
- [verificador_xmls.md](./verificador_xmls.md)
- [report_arquivos_vazios.md](./report_arquivos_vazios.md)
