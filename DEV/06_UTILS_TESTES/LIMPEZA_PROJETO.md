# LIMPEZA DO PROJETO EXTRATOR OMIE V3
# ====================================

## ✅ CONCLUÍDO - MAIN.PY
- ❌ Removida lógica do pipeline híbrido
- ❌ Removidas funções:
  - executar_pipeline_hibrido()
  - _exibir_status_final_hibrido()
- ❌ Removidas referências ao pipeline adaptativo
- ✅ Simplificada função _determinar_modo_execucao()
- ✅ Simplificado executar_pipeline_download()
- ✅ Simplificado executar_extrator_funcional_seguro()

## PENDENTE - LIMPEZA DE MÓDULOS

### 1. SRC/EXTRATOR_ASYNC.PY
**Funcionalidades não utilizadas para remover:**
- listar_nfs() - função assíncrona complexa não usada
- baixar_xmls() assíncrono - não sendo usado
- Classes complexas de metrics e validação
- Decorators de retry assíncrono
- Configurações de download paralelo

**Manter apenas:**
- Funcões básicas de utilidade se houver dependências

### 2. SRC/UTILS.PY
**Funcionalidades não utilizadas para remover:**
- Funções de processamento de registros inválidos complexas
- marcar_registros_invalidos_e_listar_dias()
- buscar_registros_invalidos_para_reprocessar()
- limpar_registros_invalidos_reprocessados()
- Funções de análise detalhada não usadas
- Validações excessivamente complexas

**Manter:**
- Funcões básicas de banco de dados
- Validações essenciais
- Operações CRUD básicas
- Rate limiting
- Funcões usadas pelo extrator_funcional.py

### 3. SRC/UPLOAD_ONEDRIVE.PY
**Verificar se está sendo usado:**
- Se não estiver sendo usado, remover completamente
- Se estiver, manter apenas funcionalidades básicas

### 4. SRC/REPORT_ARQUIVOS_VAZIOS.PY
**Simplificar:**
- Remover funcionalidades de limpeza automática se não usadas
- Manter apenas geração básica de relatórios

### 5. SRC/COMPACTADOR_RESULTADO.PY
**Simplificar:**
- Remover paralelização excessiva se não necessária
- Manter apenas compactação básica

## 🎯 OBJETIVO
Manter apenas as funcionalidades que são efetivamente utilizadas pelo fluxo principal:
1. extrator_funcional.py (core)
2. utils.py (básico)
3. Módulos auxiliares simplificados

## 📋 PRÓXIMOS PASSOS
1. Analisar dependências reais de cada módulo
2. Remover funcões não utilizadas
3. Simplificar funcões complexas
4. Testar integridade do funcionamento
5. Documentar o fluxo final simplificado
