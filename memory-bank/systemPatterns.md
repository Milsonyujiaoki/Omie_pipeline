# System Patterns

## Architectural Patterns

- Pattern 1: Description

## Design Patterns

- Pattern 1: Description

## Common Idioms

- Idiom 1: Description

## Busca recursiva paralela de arquivos com os.scandir e ThreadPoolExecutor

Utiliza uma pilha de diretórios e executa a varredura de subpastas em paralelo, coletando arquivos XML de forma eficiente mesmo em estruturas profundas e dinâmicas. Permite logging detalhado e integração fácil com lógica customizada durante a busca.

### Examples

- listar_arquivos_xml_em(root: Path, max_workers=8) retorna todos os XMLs sob root usando multithreading.
