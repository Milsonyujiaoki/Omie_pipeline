#!/usr/bin/env python3
import re

# Teste dos padrões de regex
caminho1 = r'c:\milson\extrator_omie_v3\resultado\2025\07\21\arquivo.xml'
caminho2 = r'c:\milson\extrator_omie_v3\resultado\2025\07\21\21_pasta_1\arquivo.xml'

# Padrões originais
padrao_pasta_dia = r'\\resultado\\(\d{4})\\(\d{2})\\(\d{2})\\[^\\]+\.xml$'
padrao_subpasta = r'\\(\d+)_pasta_(\d+)\\'

print('=== TESTE DOS PADRÕES ORIGINAIS ===')
print(f'Caminho 1: {caminho1}')
print(f'Pasta do dia match: {bool(re.search(padrao_pasta_dia, caminho1))}')

print(f'\nCaminho 2: {caminho2}')
print(f'Subpasta match: {bool(re.search(padrao_subpasta, caminho2))}')

# Padrões corrigidos
padrao_pasta_dia_novo = r'\\resultado\\(\d{4})\\(\d{2})\\(\d{2})\\[^\\]+\.xml$'
padrao_subpasta_novo = r'\\(\d+)_pasta_(\d+)\\'

print('\n=== TESTE DOS PADRÕES CORRIGIDOS ===')
print(f'Pasta do dia match (novo): {bool(re.search(padrao_pasta_dia_novo, caminho1))}')
print(f'Subpasta match (novo): {bool(re.search(padrao_subpasta_novo, caminho2))}')

# Teste com separadores corretos para Windows
caminho1_win = caminho1.replace('/', '\\')
caminho2_win = caminho2.replace('/', '\\')

print('\n=== TESTE COM CAMINHOS WINDOWS ===')
print(f'Caminho 1 (win): {caminho1_win}')
print(f'Caminho 2 (win): {caminho2_win}')

# Padrão mais específico para Windows
padrao_pasta_dia_win = r'resultado\\(\d{4})\\(\d{2})\\(\d{2})\\[^\\]+\.xml$'
padrao_subpasta_win = r'\\(\d+)_pasta_(\d+)\\'

print(f'Pasta do dia match (win): {bool(re.search(padrao_pasta_dia_win, caminho1_win))}')
print(f'Subpasta match (win): {bool(re.search(padrao_subpasta_win, caminho2_win))}')
