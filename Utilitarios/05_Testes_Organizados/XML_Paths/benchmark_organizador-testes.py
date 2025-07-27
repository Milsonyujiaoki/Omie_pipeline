#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
organizador_testes.py

Script para organizar automaticamente todos os arquivos de teste do projeto,
categorizando-os por funcionalidade e renomeando com padrões descritivos.

Funcionalidades:
- Análise automática de arquivos de teste
- Categorização por tipo de funcionalidade
- Renomeação com padrões descritivos
- Migração para estrutura organizada
- Geração de documentação automática
- Backup dos arquivos originais

Uso:
    python organizador_testes.py
    python organizador_testes.py --dry-run  # Apenas simula sem executar
    python organizador_testes.py --backup   # Faz backup antes de mover
"""

import argparse
import logging
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import ast

# =============================================================================
# Configuração de logging
# =============================================================================

def configurar_logging(verbose: bool = False) -> logging.Logger:
    """Configura sistema de logging"""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('organizador_testes.log', encoding='utf-8')
        ],
        force=True
    )
    
    return logging.getLogger(__name__)

# =============================================================================
# Estruturas de dados
# =============================================================================

class ArquivoTeste:
    """Representa um arquivo de teste com suas características"""
    
    def __init__(self, caminho: Path):
        self.caminho = caminho
        self.nome_original = caminho.name
        self.conteudo = self._ler_conteudo()
        self.categoria = self._determinar_categoria()
        self.funcionalidade = self._extrair_funcionalidade()
        self.tipo_teste = self._determinar_tipo_teste()
        self.novo_nome = self._gerar_novo_nome()
        self.descricao = self._extrair_descricao()
    
    def _ler_conteudo(self) -> str:
        """Lê o conteúdo do arquivo"""
        try:
            with open(self.caminho, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return ""
    
    def _determinar_categoria(self) -> str:
        """Determina a categoria baseada no conteúdo e nome"""
        nome_lower = self.nome_original.lower()
        conteudo_lower = self.conteudo.lower()
        
        # Padrões para XML/Paths
        if any(x in nome_lower for x in ['xml', 'path', 'chave', 'nfe']):
            return "XML_Paths"
        if any(x in conteudo_lower for x in ['gerar_xml_path', 'chave_nfe', 'cchavenfie']):
            return "XML_Paths"
        
        # Padrões para Performance
        if any(x in nome_lower for x in ['performance', 'benchmark', 'comparacao', 'otimizado']):
            return "Performance"
        if any(x in conteudo_lower for x in ['time.perf_counter', 'benchmark', 'performance', 'otimizada']):
            return "Performance"
        
        # Padrões para Integração
        if any(x in nome_lower for x in ['verificador', 'integration', 'script']):
            return "Integracao"
        if any(x in conteudo_lower for x in ['verificador_xmls', 'integration', 'verificar_arquivo']):
            return "Integracao"
        
        # Padrões para Configuração
        if any(x in nome_lower for x in ['config', 'main', 'configuracao']):
            return "Configuracao"
        if any(x in conteudo_lower for x in ['configuracao.ini', 'carregar_configuracoes', 'config']):
            return "Configuracao"
        
        # Padrões para Validação de Dados
        if any(x in nome_lower for x in ['validacao', 'dados', 'estrutura', 'banco']):
            return "Validacao_Dados"
        if any(x in conteudo_lower for x in ['sqlite3', 'banco', 'estrutura', 'validacao']):
            return "Validacao_Dados"
        
        # Padrões para Funcionalidade específica
        if any(x in nome_lower for x in ['extrator', 'pipeline', 'funcional']):
            return "Funcionalidade"
        if any(x in conteudo_lower for x in ['extractor', 'pipeline', 'funcional']):
            return "Funcionalidade"
        
        # Default
        return "Funcionalidade"
    
    def _extrair_funcionalidade(self) -> str:
        """Extrai a funcionalidade principal do teste"""
        nome_base = self.nome_original.replace('.py', '').replace('teste_', '').replace('test_', '')
        
        # Mapeamento de funcionalidades conhecidas
        funcionalidades = {
            'xml': 'xml_path',
            'path': 'xml_path', 
            'gerar_xml': 'xml_path',
            'comparativo': 'comparacao',
            'performance': 'performance',
            'benchmark': 'benchmark',
            'verificador': 'verificador',
            'main': 'configuracao_main',
            'config': 'configuracao',
            'banco': 'estrutura_banco',
            'dados': 'validacao_dados',
            'estrutura': 'estrutura',
            'normalizacao': 'normalizacao',
            'chave': 'chave_nfe',
            'nomenclatura': 'nomenclatura',
            'duplicatas': 'duplicatas',
            'consistencia': 'consistencia'
        }
        
        for palavra_chave, funcionalidade in funcionalidades.items():
            if palavra_chave in nome_base.lower():
                return funcionalidade
        
        # Se não encontrou, usa o nome base limpo
        return nome_base.replace('_', '-')
    
    def _determinar_tipo_teste(self) -> str:
        """Determina o tipo de teste"""
        nome_lower = self.nome_original.lower()
        conteudo_lower = self.conteudo.lower()
        
        if any(x in nome_lower for x in ['benchmark', 'performance']):
            return "benchmark"
        if any(x in conteudo_lower for x in ['time.perf_counter', 'benchmark']):
            return "benchmark"
        
        if any(x in nome_lower for x in ['integration', 'verificador']):
            return "integration"
        if any(x in conteudo_lower for x in ['verificador_xmls', 'integration']):
            return "integration"
        
        if any(x in nome_lower for x in ['validation', 'validacao']):
            return "validation"
        if any(x in conteudo_lower for x in ['validation', 'validacao']):
            return "validation"
        
        return "test"
    
    def _gerar_novo_nome(self) -> str:
        """Gera novo nome descritivo"""
        return f"{self.tipo_teste}_{self.funcionalidade}.py"
    
    def _extrair_descricao(self) -> str:
        """Extrai descrição do docstring ou comentários"""
        try:
            # Tentar extrair docstring
            tree = ast.parse(self.conteudo)
            if (tree.body and isinstance(tree.body[0], ast.Expr) and 
                isinstance(tree.body[0].value, ast.Constant)):
                docstring = tree.body[0].value.value
                # Primeira linha não vazia
                for linha in docstring.split('\n'):
                    linha = linha.strip()
                    if linha and not linha.startswith('"""'):
                        return linha
        except:
            pass
        
        # Fallback: procurar comentário descritivo
        linhas = self.conteudo.split('\n')[:10]  # Primeiras 10 linhas
        for linha in linhas:
            linha = linha.strip()
            if linha.startswith('#') and len(linha) > 10:
                return linha[1:].strip()
        
        return f"Teste para {self.funcionalidade.replace('_', ' ')}"

# =============================================================================
# Organizador principal
# =============================================================================

class OrganizadorTestes:
    """Organizador principal de arquivos de teste"""
    
    def __init__(self, diretorio_raiz: Path, logger: logging.Logger):
        self.diretorio_raiz = Path(diretorio_raiz)
        self.logger = logger
        self.pasta_destino = self.diretorio_raiz / "Utilitarios" / "05_Testes_Organizados"
        self.arquivos_encontrados: List[ArquivoTeste] = []
        self.movimentacoes: List[Tuple[Path, Path]] = []
        
    def executar_organizacao(self, dry_run: bool = False, fazer_backup: bool = False) -> None:
        """Executa todo o processo de organização"""
        self.logger.info("🚀 INICIANDO ORGANIZAÇÃO DE TESTES")
        self.logger.info("="*60)
        
        # 1. Localizar arquivos de teste
        self._localizar_arquivos_teste()
        
        # 2. Analisar arquivos
        self._analisar_arquivos()
        
        # 3. Planejar movimentações
        self._planejar_movimentacoes()
        
        # 4. Criar estrutura de pastas
        if not dry_run:
            self._criar_estrutura_pastas()
        
        # 5. Fazer backup se solicitado
        if fazer_backup and not dry_run:
            self._fazer_backup()
        
        # 6. Executar movimentações
        if not dry_run:
            self._executar_movimentacoes()
        else:
            self._mostrar_simulacao()
        
        # 7. Gerar documentação
        if not dry_run:
            self._gerar_documentacao()
        
        # 8. Relatório final
        self._relatorio_final(dry_run)
    
    def _localizar_arquivos_teste(self) -> None:
        """Localiza todos os arquivos de teste"""
        self.logger.info(" Localizando arquivos de teste...")
        
        # Padrões de arquivos de teste
        padroes = [
            "teste_*.py",
            "test_*.py", 
            "*teste*.py",
            "*test*.py"
        ]
        
        arquivos_encontrados = set()
        
        # Buscar na raiz
        for padrao in padroes:
            arquivos_encontrados.update(self.diretorio_raiz.glob(padrao))
        
        # Buscar na pasta de utilitários existente
        pasta_testes_antiga = self.diretorio_raiz / "Utilitarios" / "04_Testes_e_Validacao"
        if pasta_testes_antiga.exists():
            for padrao in padroes:
                arquivos_encontrados.update(pasta_testes_antiga.glob(padrao))
        
        # Buscar em outras subpastas
        for subpasta in ["DEV", "PROD", "src", "Backup"]:
            pasta = self.diretorio_raiz / subpasta
            if pasta.exists():
                for padrao in padroes:
                    arquivos_encontrados.update(pasta.rglob(padrao))
        
        # Filtrar arquivos válidos
        arquivos_validos = []
        for arquivo in arquivos_encontrados:
            if (arquivo.is_file() and 
                arquivo.suffix == '.py' and 
                arquivo.stat().st_size > 0):
                arquivos_validos.append(arquivo)
        
        self.logger.info(f"📋 Encontrados {len(arquivos_validos)} arquivos de teste")
        
        # Criar objetos ArquivoTeste
        for arquivo in arquivos_validos:
            try:
                self.arquivos_encontrados.append(ArquivoTeste(arquivo))
            except Exception as e:
                self.logger.warning(f"⚠️  Erro ao processar {arquivo}: {e}")
    
    def _analisar_arquivos(self) -> None:
        """Analisa e categoriza os arquivos"""
        self.logger.info("🧩 Analisando e categorizando arquivos...")
        
        categorias = {}
        for arquivo in self.arquivos_encontrados:
            categoria = arquivo.categoria
            if categoria not in categorias:
                categorias[categoria] = []
            categorias[categoria].append(arquivo)
        
        # Log das categorias
        for categoria, arquivos in categorias.items():
            self.logger.info(f"   📁 {categoria}: {len(arquivos)} arquivos")
            for arquivo in arquivos:
                self.logger.debug(f"      - {arquivo.nome_original} → {arquivo.novo_nome}")
    
    def _planejar_movimentacoes(self) -> None:
        """Planeja as movimentações de arquivos"""
        self.logger.info("📋 Planejando movimentações...")
        
        for arquivo in self.arquivos_encontrados:
            pasta_categoria = self.pasta_destino / arquivo.categoria
            destino = pasta_categoria / arquivo.novo_nome
            
            # Resolver conflitos de nome
            contador = 1
            destino_original = destino
            while destino in [mov[1] for mov in self.movimentacoes]:
                base = destino_original.stem
                extensao = destino_original.suffix
                destino = destino_original.parent / f"{base}_{contador:02d}{extensao}"
                contador += 1
            
            self.movimentacoes.append((arquivo.caminho, destino))
    
    def _criar_estrutura_pastas(self) -> None:
        """Cria a estrutura de pastas necessária"""
        self.logger.info("🏗️  Criando estrutura de pastas...")
        
        # Pasta principal
        self.pasta_destino.mkdir(parents=True, exist_ok=True)
        
        # Subpastas por categoria
        categorias = set(arquivo.categoria for arquivo in self.arquivos_encontrados)
        for categoria in categorias:
            pasta_categoria = self.pasta_destino / categoria
            pasta_categoria.mkdir(exist_ok=True)
            self.logger.debug(f"   ✅ Pasta criada: {categoria}")
    
    def _fazer_backup(self) -> None:
        """Faz backup dos arquivos originais"""
        self.logger.info("💾 Criando backup dos arquivos originais...")
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        pasta_backup = self.diretorio_raiz / f"backup_testes_{timestamp}"
        pasta_backup.mkdir(exist_ok=True)
        
        for origem, _ in self.movimentacoes:
            try:
                # Manter estrutura relativa no backup
                caminho_relativo = origem.relative_to(self.diretorio_raiz)
                destino_backup = pasta_backup / caminho_relativo
                destino_backup.parent.mkdir(parents=True, exist_ok=True)
                
                shutil.copy2(origem, destino_backup)
                self.logger.debug(f"   💾 Backup: {origem.name}")
            except Exception as e:
                self.logger.warning(f"⚠️  Erro no backup de {origem}: {e}")
        
        self.logger.info(f"💾 Backup criado em: {pasta_backup}")
    
    def _executar_movimentacoes(self) -> None:
        """Executa as movimentações planejadas"""
        self.logger.info("📦 Executando movimentações...")
        
        sucesso = 0
        erros = 0
        
        for origem, destino in self.movimentacoes:
            try:
                # Copiar arquivo (mantém original por segurança)
                shutil.copy2(origem, destino)
                self.logger.debug(f"   ✅ {origem.name} → {destino}")
                sucesso += 1
            except Exception as e:
                self.logger.error(f"   ❌ Erro ao mover {origem}: {e}")
                erros += 1
        
        self.logger.info(f"📦 Movimentações: {sucesso} sucessos, {erros} erros")
    
    def _mostrar_simulacao(self) -> None:
        """Mostra simulação das movimentações"""
        self.logger.info("🎭 SIMULAÇÃO - Movimentações planejadas:")
        
        for origem, destino in self.movimentacoes:
            origem_rel = origem.relative_to(self.diretorio_raiz)
            destino_rel = destino.relative_to(self.diretorio_raiz)
            self.logger.info(f"   📄 {origem_rel} → {destino_rel}")
    
    def _gerar_documentacao(self) -> None:
        """Gera documentação automática"""
        self.logger.info("📚 Gerando documentação...")
        
        # README principal
        self._gerar_readme_principal()
        
        # README por categoria
        categorias = set(arquivo.categoria for arquivo in self.arquivos_encontrados)
        for categoria in categorias:
            self._gerar_readme_categoria(categoria)
    
    def _gerar_readme_principal(self) -> None:
        """Gera README principal da pasta de testes"""
        conteudo = f"""# 📂 TESTES ORGANIZADOS - PROJETO OMIE V3

## 🎯 Objetivo
Esta pasta contém todos os testes organizados automaticamente por categoria e funcionalidade.

## 📅 Organização
- **Data da organização:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
- **Total de arquivos organizados:** {len(self.arquivos_encontrados)}
- **Script utilizado:** organizador_testes.py

## 📁 Estrutura de Categorias

"""
        
        # Estatísticas por categoria
        categorias = {}
        for arquivo in self.arquivos_encontrados:
            categoria = arquivo.categoria
            if categoria not in categorias:
                categorias[categoria] = []
            categorias[categoria].append(arquivo)
        
        # Descrições das categorias
        descricoes_categorias = {
            "Performance": "🚀 Testes focados em medição de performance e benchmarks",
            "XML_Paths": "📄 Testes para geração e validação de caminhos XML",
            "Integracao": "🔗 Testes de integração entre módulos",
            "Configuracao": "🔧 Testes relacionados a configurações do sistema",
            "Validacao_Dados": "✅ Testes de validação e consistência de dados",
            "Funcionalidade": "⚙️ Testes de funcionalidades específicas"
        }
        
        for categoria, arquivos in sorted(categorias.items()):
            descricao = descricoes_categorias.get(categoria, "📋 Testes diversos")
            conteudo += f"### {categoria}/\n"
            conteudo += f"{descricao}\n"
            conteudo += f"- **Arquivos:** {len(arquivos)}\n"
            conteudo += f"- **Tipos:** {', '.join(set(arq.tipo_teste for arq in arquivos))}\n\n"
        
        conteudo += """## 🏷️ Convenção de Nomenclatura

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
"""
        
        arquivo_readme = self.pasta_destino / "README.md"
        with open(arquivo_readme, 'w', encoding='utf-8') as f:
            f.write(conteudo)
    
    def _gerar_readme_categoria(self, categoria: str) -> None:
        """Gera README específico para uma categoria"""
        arquivos_categoria = [arq for arq in self.arquivos_encontrados if arq.categoria == categoria]
        
        # Mapear descrições das categorias
        descricoes = {
            "Performance": "Esta pasta contém testes focados em medição de performance, comparação de algoritmos e benchmarks de funcionalidades críticas do sistema.",
            "XML_Paths": "Testes específicos para geração, validação e otimização de caminhos XML, incluindo comparações entre diferentes implementações.",
            "Integracao": "Testes que verificam a integração entre diferentes módulos e componentes do sistema.",
            "Configuracao": "Testes relacionados ao carregamento, validação e uso de configurações do sistema.",
            "Validacao_Dados": "Testes que validam integridade, consistência e estrutura de dados no banco e arquivos.",
            "Funcionalidade": "Testes de funcionalidades específicas e regras de negócio do sistema."
        }
        
        conteudo = f"""# 📂 {categoria}

## 📋 Descrição
{descricoes.get(categoria, 'Testes diversos para esta categoria')}

## 📄 Arquivos ({len(arquivos_categoria)})

"""
        
        for arquivo in sorted(arquivos_categoria, key=lambda x: x.novo_nome):
            conteudo += f"### {arquivo.novo_nome}\n"
            conteudo += f"**Arquivo original:** `{arquivo.nome_original}`\n\n"
            conteudo += f"**Descrição:** {arquivo.descricao}\n\n"
            conteudo += f"**Tipo:** {arquivo.tipo_teste}\n\n"
            conteudo += f"**Funcionalidade:** {arquivo.funcionalidade}\n\n"
            conteudo += "---\n\n"
        
        conteudo += f"""## 🚀 Execução

Para executar todos os testes desta categoria:
```bash
# Individual
python [nome_do_teste].py

# Em lote (implementar conforme necessário)
# python run_all_{categoria.lower()}_tests.py
```

---
*Categoria organizada automaticamente em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*
"""
        
        pasta_categoria = self.pasta_destino / categoria
        arquivo_readme = pasta_categoria / "README.md"
        with open(arquivo_readme, 'w', encoding='utf-8') as f:
            f.write(conteudo)
    
    def _relatorio_final(self, dry_run: bool) -> None:
        """Gera relatório final da organização"""
        self.logger.info("📊 RELATÓRIO FINAL DA ORGANIZAÇÃO")
        self.logger.info("="*60)
        
        if dry_run:
            self.logger.info("🎭 MODO SIMULAÇÃO - Nenhuma alteração foi feita")
        else:
            self.logger.info("✅ ORGANIZAÇÃO CONCLUÍDA COM SUCESSO")
        
        # Estatísticas
        categorias = {}
        tipos = {}
        
        for arquivo in self.arquivos_encontrados:
            # Por categoria
            categoria = arquivo.categoria
            if categoria not in categorias:
                categorias[categoria] = 0
            categorias[categoria] += 1
            
            # Por tipo
            tipo = arquivo.tipo_teste
            if tipo not in tipos:
                tipos[tipo] = 0
            tipos[tipo] += 1
        
        self.logger.info(f"📋 Total de arquivos processados: {len(self.arquivos_encontrados)}")
        self.logger.info(f"📁 Categorias criadas: {len(categorias)}")
        
        self.logger.info("\n📊 Distribuição por categoria:")
        for categoria, count in sorted(categorias.items()):
            self.logger.info(f"   {categoria}: {count} arquivos")
        
        self.logger.info("\n🏷️  Distribuição por tipo:")
        for tipo, count in sorted(tipos.items()):
            self.logger.info(f"   {tipo}: {count} arquivos")
        
        if not dry_run:
            self.logger.info(f"\n📂 Pasta destino: {self.pasta_destino}")
            self.logger.info("📚 Documentação gerada automaticamente")
        
        self.logger.info("\n" + "="*60)

# =============================================================================
# Função principal
# =============================================================================

def main():
    """Função principal do organizador"""
    parser = argparse.ArgumentParser(
        description="Organizador automático de arquivos de teste",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python organizador_testes.py                    # Organização completa
  python organizador_testes.py --dry-run          # Simula sem executar
  python organizador_testes.py --backup           # Faz backup antes
  python organizador_testes.py --verbose          # Modo verboso
        """
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simula a organização sem executar alterações'
    )
    
    parser.add_argument(
        '--backup',
        action='store_true',
        help='Faz backup dos arquivos originais antes de mover'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Modo verboso (mais detalhes no log)'
    )
    
    parser.add_argument(
        '--diretorio',
        type=str,
        default='.',
        help='Diretório raiz do projeto (padrão: diretório atual)'
    )
    
    args = parser.parse_args()
    
    # Configurar logging
    logger = configurar_logging(args.verbose)
    
    try:
        # Verificar se estamos no diretório correto
        diretorio_raiz = Path(args.diretorio).absolute()
        
        if not (diretorio_raiz / "main.py").exists() and not (diretorio_raiz / "src").exists():
            logger.warning("⚠️  Não parece ser o diretório raiz do projeto Omie")
            logger.warning("   Verifique se está no diretório correto")
        
        # Executar organização
        organizador = OrganizadorTestes(diretorio_raiz, logger)
        organizador.executar_organizacao(
            dry_run=args.dry_run,
            fazer_backup=args.backup
        )
        
        if args.dry_run:
            logger.info("🎭 Para executar de verdade, rode sem --dry-run")
        else:
            logger.info("✅ Organização concluída! Verifique a pasta Utilitarios/05_Testes_Organizados/")
    
    except KeyboardInterrupt:
        logger.warning("❌ Execução interrompida pelo usuário")
        sys.exit(130)
    
    except Exception as e:
        logger.exception(f"❌ Erro crítico: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
