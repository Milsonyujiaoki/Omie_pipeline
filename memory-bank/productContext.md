# Product Context

Describe the product.

## Overview

Provide a high-level overview of the project.

## Core Features

- Feature 1
- Feature 2

## Technical Stack

- Tech 1
- Tech 2

## Project Description

Atualização do pipeline de descoberta de arquivos XML para uso de busca recursiva otimizada com multithreading, melhorando performance em grandes volumes e estruturas de pastas dinâmicas.



## Architecture

O módulo atualizar_caminhos_arquivos.py agora utiliza uma função utilitária listar_arquivos_xml_em baseada em os.scandir e ThreadPoolExecutor para busca recursiva paralela de XMLs, tornando a descoberta de arquivos mais eficiente e escalável. O pipeline principal foi atualizado para usar essa abordagem, com logging detalhado de tempo e quantidade de arquivos encontrados.



## Technologies

- Python 3.x
- ThreadPoolExecutor
- logging estruturado



## Libraries and Dependencies

- os.scandir
- pathlib.Path
- concurrent.futures.ThreadPoolExecutor

