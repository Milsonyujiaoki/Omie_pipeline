# 🔧 Correção e Manutenção

Scripts para correção de problemas e manutenção do sistema.

## Scripts Disponíveis

### `corrigir_erros_utils.py`
**Propósito**: Corrige erros específicos no código fonte (ex: coluna 'status')  
**Uso**: Quando há erros relacionados a colunas inexistentes no banco  
**Correções**:
- Remove referências à coluna 'status' inexistente
- Corrige queries SQL problemáticas
- Comenta código que causa erros
- Aplica patches de correção

### `padronizar_formato_datas.py`
**Propósito**: Padroniza formato de datas no banco de dados  
**Uso**: Para uniformizar formatos de data inconsistentes  
**Características**:
- Converte diferentes formatos para dd/mm/yyyy
- Suporta múltiplos formatos de entrada
- Backup automático antes da correção
- Validação de dados antes da alteração

### `verificar_integridade_xmls.py`
**Propósito**: Verifica a integridade dos arquivos XML baixados  
**Uso**: Para validar se XMLs existem e são válidos  
**Verificações**:
- Existência física dos arquivos
- Integridade do conteúdo XML
- Correspondência com registros do banco
- Identificação de arquivos corrompidos

## Ordem de Execução Recomendada

### Para Correção de Erros de Sistema:
1. **corrigir_erros_utils.py** - Corrige erros de código
2. **padronizar_formato_datas.py** - Uniformiza datas
3. **verificar_integridade_xmls.py** - Valida arquivos

## Scripts por Problema

### ❌ Erro "no such column: status"
```bash
python corrigir_erros_utils.py
```

### 📅 Datas em Formatos Inconsistentes
```bash
python padronizar_formato_datas.py
```

### 📄 XMLs Possivelmente Corrompidos
```bash
python verificar_integridade_xmls.py
```

## Detalhes dos Scripts

### corrigir_erros_utils.py
**Problemas que resolve**:
- Erro "no such column: status" em utils.py
- Queries SQL que referenciam colunas inexistentes
- Código comentado incorretamente

**Backup automático**: ✅ Cria backup antes das alterações

### padronizar_formato_datas.py
**Formatos suportados**:
- dd/mm/yyyy → dd/mm/yyyy (mantém)
- yyyy-mm-dd → dd/mm/yyyy (converte)
- dd-mm-yyyy → dd/mm/yyyy (converte)
- dd/mm/yy → dd/mm/yyyy (expande ano)

**Backup automático**: ✅ Cria backup do banco antes das alterações

### verificar_integridade_xmls.py
**Verificações realizadas**:
- Arquivo existe no sistema de arquivos
- Arquivo não está vazio
- Conteúdo é XML válido
- Headers XML corretos
- Tamanho mínimo esperado

## Segurança e Backup

### 🛡️ Todos os scripts de correção:
- Criam backup automático antes das alterações
- Validam dados antes de modificar
- Registram log detalhado das operações
- Permitem rollback em caso de problemas

### 📋 Logs de Operação
Todos os scripts geram logs detalhados em:
- Console (output imediato)
- Arquivos de log (histórico permanente)

## Manutenção Preventiva

### Execução Regular Recomendada:

**Semanal**:
```bash
python verificar_integridade_xmls.py
```

**Mensal**:
```bash
python padronizar_formato_datas.py
```

**Quando necessário**:
```bash
python corrigir_erros_utils.py
```
