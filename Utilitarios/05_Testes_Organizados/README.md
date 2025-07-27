# 📂 TESTES ORGANIZADOS - PROJETO OMIE V3

## 🎯 Objetivo
Esta pasta contém todos os testes organizados automaticamente por categoria e funcionalidade.

## 📅 Organização
- **Data da organização:** 23/07/2025 01:02:29
- **Total de arquivos organizados:** 44
- **Script utilizado:** organizador_testes.py

## 📁 Estrutura de Categorias

### Configuracao/
🔧 Testes relacionados a configurações do sistema
- **Arquivos:** 15
- **Tipos:** test

### Funcionalidade/
⚙️ Testes de funcionalidades específicas
- **Arquivos:** 3
- **Tipos:** test

### Integracao/
🔗 Testes de integração entre módulos
- **Arquivos:** 4
- **Tipos:** integration

### Performance/
🚀 Testes focados em medição de performance e benchmarks
- **Arquivos:** 6
- **Tipos:** integration, test

### Validacao_Dados/
✅ Testes de validação e consistência de dados
- **Arquivos:** 5
- **Tipos:** test

### XML_Paths/
📄 Testes para geração e validação de caminhos XML
- **Arquivos:** 11
- **Tipos:** test, benchmark

## 🏷️ Convenção de Nomenclatura

### Formato dos Arquivos:
`[tipo]_[funcionalidade].py`

### Tipos de Teste:
- `benchmark_` - Testes de performance
- `test_` - Testes funcionais padrão
- `integration_` - Testes de integração
- `validation_` - Testes de validação

## 🚀 Como Executar

### Teste Individual:
```bash
cd Utilitarios/05_Testes_Organizados/[Categoria]
python [nome_do_teste].py
```

### Por Categoria:
```bash
# Implementar runners específicos conforme necessário
```

## 📝 Manutenção

Para reorganizar novamente no futuro:
```bash
python organizador_testes.py --backup
```

---
*Organização automática realizada em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*
