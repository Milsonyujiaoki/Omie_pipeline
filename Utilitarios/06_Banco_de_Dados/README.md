# 🗄️ Banco de Dados

Scripts para manipulação, diagnóstico e correção de banco de dados

## 📋 Arquivos Disponíveis

| Arquivo | Funcionalidade | Classes | Funções |
|---------|----------------|---------|---------|
| `corrigir_view.py` | Script para corrigir a view vw_notas_pendentes adicionando a coluna nIdNF. |  | corrigir_view_notas_pendentes |
| `diagnostico_db.py` | Script de diagnóstico e debugging |  |  |
| `organizador_testes.py` | organizador_testes.py | ArquivoTeste, OrganizadorTestes | configurar_logging, main, __init__... |
| `organizador_utilitarios_completo.py` | Organizador Completo de Utilitários - Extrator Omie v3 | ArquivoUtilitario, EstatisticasOrganizacao, AnalisadorCodigo... | configurar_logging, main, __post_init__... |
| `report_arquivos_vazios.py` | Utilitário para report arquivos vazios |  | is_text_file_empty, verificar_arquivo_rapido, encontrar_arquivos_vazios_ou_zero_otimizado... |
| `utils.py` | Módulo de utilitários centralizados para o pipeline de extração de dados do Omie... | DatabaseConfig, ResultadoSalvamento, DatabaseError... | obter_registros_pendentes, obter_registros_filtrados, marcar_registros_invalidos_e_listar_dias... |
| `verificar_duplicatas.py` | Script para verificação de duplicatas de arquivos XML. | ArquivoXML, DuplicataLocal, DuplicataBanco... | configurar_logging, _processar_limpeza_com_confirmacao, main... |

## 🚀 Como Usar

Todos os scripts podem ser executados do diretório raiz do projeto:

```bash
# Navegue para o diretório raiz
cd ../../..

# Execute um script específico
python Utilitarios/06_Banco_de_Dados/nome_do_script.py
```

## 📁 Estrutura

```
06_Banco_de_Dados/
├── README.md (este arquivo)
├── corrigir_view.py
├── diagnostico_db.py
├── organizador_testes.py
├── organizador_utilitarios_completo.py
├── report_arquivos_vazios.py
├── utils.py
├── verificar_duplicatas.py
```

## 🔗 Links Relacionados

- [Menu Principal](../menu_principal.py)
- [Documentação Geral](../README_ORGANIZACAO_UTILITARIOS.md)
- [Testes Organizados](../05_Testes_Organizados/)

---
*Documentação gerada automaticamente pelo Organizador de Utilitários*
