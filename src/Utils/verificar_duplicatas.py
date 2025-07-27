#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para verificação de duplicatas de arquivos XML.

Este módulo analisa duplicatas em duas frentes:
1. Arquivos locais: verifica duplicatas por cChaveNfe e nome de arquivo
2. Banco de dados: identifica registros duplicados por cChaveNFe

Funcionalidades:
- Varredura recursiva de diretórios XML
- Extração de cChaveNFe de arquivos XML
- Detecção de duplicatas por nome de arquivo
- Análise de duplicatas no banco de dados SQLite
- Geração de relatórios detalhados
- Logging estruturado com métricas de performance

Uso:
    python verificar_duplicatas.py --pasta resultado --banco omie.db
    python verificar_duplicatas.py --apenas-banco
    python verificar_duplicatas.py --apenas-arquivos --pasta resultado
"""

import argparse
import logging
import sqlite3
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

# =============================================================================
# Configuração de logging
# =============================================================================

def configurar_logging() -> logging.Logger:
    """
    Configura sistema de logging para o verificador de duplicatas.
    
    Returns:
        logging.Logger: Logger configurado
    """
    # Criar diretório de logs se não existir
    log_dir = Path("log")
    log_dir.mkdir(exist_ok=True)
    
    # Timestamp para arquivo de log único
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / f"verificar_duplicatas_{timestamp}.log"
    
    # Configuração do logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ],
        force=True
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"[SETUP] Logging configurado - Arquivo: {log_file}")
    
    return logger


# =============================================================================
# Estruturas de dados
# =============================================================================

@dataclass
class ArquivoXML:
    """Representa um arquivo XML com suas informações principais."""
    caminho: Path
    nome: str
    chave_nfe: Optional[str]
    tamanho: int
    data_modificacao: datetime
    
    def __post_init__(self) -> None:
        """Validação pós-inicialização."""
        if not self.caminho.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {self.caminho}")


@dataclass
class DuplicataLocal:
    """Representa uma duplicata encontrada nos arquivos locais."""
    tipo: str  # 'chave_nfe' ou 'nome_arquivo'
    valor: str  # chave NFe ou nome do arquivo
    arquivos: List[ArquivoXML]
    
    @property
    def quantidade(self) -> int:
        """Retorna quantidade de arquivos duplicados."""
        return len(self.arquivos)


@dataclass
class DuplicataBanco:
    """Representa uma duplicata encontrada no banco de dados."""
    chave_nfe: str
    registros: List[Dict[str, Union[str, int]]]
    
    @property
    def quantidade(self) -> int:
        """Retorna quantidade de registros duplicados."""
        return len(self.registros)


@dataclass
class RelatorioCompleto:
    """Relatório completo de duplicatas encontradas."""
    duplicatas_locais_chave: List[DuplicataLocal]
    duplicatas_locais_nome: List[DuplicataLocal]
    duplicatas_banco: List[DuplicataBanco]
    total_arquivos_analisados: int
    total_registros_banco: int
    tempo_execucao: float
    arquivos_removidos: int = 0
    duplicatas_resolvidas: int = 0
    
    @property
    def tem_duplicatas(self) -> bool:
        """Verifica se foram encontradas duplicatas."""
        return bool(
            self.duplicatas_locais_chave or 
            self.duplicatas_locais_nome or 
            self.duplicatas_banco
        )


# =============================================================================
# Analisador de arquivos XML locais
# =============================================================================

class AnalisadorArquivosLocais:
    """Analisa arquivos XML locais em busca de duplicatas."""
    
    def __init__(self, logger: logging.Logger) -> None:
        """
        Inicializa o analisador.
        
        Args:
            logger: Logger para registrar operações
        """
        self.logger = logger
        self._cache_chaves: Dict[Path, Optional[str]] = {}
    
    def analisar_pasta(self, pasta: Union[str, Path]) -> Tuple[List[DuplicataLocal], List[DuplicataLocal], int]:
        """
        Analisa pasta em busca de duplicatas por chave NFe e nome.
        
        Args:
            pasta: Caminho da pasta para análise
            
        Returns:
            Tuple com (duplicatas_chave, duplicatas_nome, total_arquivos)
            
        Raises:
            FileNotFoundError: Se pasta não existe
            PermissionError: Se sem permissão de leitura
        """
        pasta_obj = Path(pasta)
        
        if not pasta_obj.exists():
            raise FileNotFoundError(f"Pasta não encontrada: {pasta}")
        
        if not pasta_obj.is_dir():
            raise NotADirectoryError(f"Caminho não é uma pasta: {pasta}")
        
        self.logger.info(f"[ARQUIVOS] Iniciando análise da pasta: {pasta}")
        
        # Localizar todos os arquivos XML
        arquivos_xml = self._localizar_arquivos_xml(pasta_obj)
        total_arquivos = len(arquivos_xml)
        
        if total_arquivos == 0:
            self.logger.warning("[ARQUIVOS] Nenhum arquivo XML encontrado")
            return [], [], 0
        
        self.logger.info(f"[ARQUIVOS] Encontrados {total_arquivos:,} arquivos XML")
        
        # Analisar duplicatas por chave NFe
        duplicatas_chave = self._analisar_duplicatas_chave(arquivos_xml)
        
        # Analisar duplicatas por nome
        duplicatas_nome = self._analisar_duplicatas_nome(arquivos_xml)
        
        return duplicatas_chave, duplicatas_nome, total_arquivos
    
    def _localizar_arquivos_xml(self, pasta: Path) -> List[ArquivoXML]:
        """
        Localiza recursivamente todos os arquivos XML na pasta.
        
        Args:
            pasta: Pasta para varredura
            
        Returns:
            Lista de objetos ArquivoXML
        """
        arquivos = []
        
        try:
            # Usar rglob para busca recursiva otimizada
            caminhos_xml = list(pasta.rglob("*.xml"))
            
            self.logger.info(f"[ARQUIVOS] Processando {len(caminhos_xml):,} arquivos XML")
            
            for caminho in caminhos_xml:
                try:
                    if not caminho.is_file():
                        continue
                    
                    stat_info = caminho.stat()
                    
                    arquivo = ArquivoXML(
                        caminho=caminho,
                        nome=caminho.name,
                        chave_nfe=None,  # Será preenchido conforme necessário
                        tamanho=stat_info.st_size,
                        data_modificacao=datetime.fromtimestamp(stat_info.st_mtime)
                    )
                    
                    arquivos.append(arquivo)
                    
                except (OSError, PermissionError) as e:
                    self.logger.warning(f"[ARQUIVOS] Erro ao processar {caminho}: {e}")
                    continue
            
        except Exception as e:
            self.logger.error(f"[ARQUIVOS] Erro durante varredura: {e}")
            raise
        
        return arquivos
    
    def _extrair_chave_nfe(self, arquivo: ArquivoXML) -> Optional[str]:
        """
        Extrai chave NFe de um arquivo XML.
        
        Args:
            arquivo: Objeto ArquivoXML
            
        Returns:
            Chave NFe ou None se não encontrada
        """
        # Verificar cache primeiro
        if arquivo.caminho in self._cache_chaves:
            return self._cache_chaves[arquivo.caminho]
        
        try:
            # Verificar se arquivo não está vazio
            if arquivo.tamanho == 0:
                self._cache_chaves[arquivo.caminho] = None
                return None
            
            # Tentar parsing do XML
            tree = ET.parse(arquivo.caminho)
            root = tree.getroot()
            
            # Buscar chave NFe em diferentes namespaces/estruturas
            chave_nfe = self._buscar_chave_nfe_xml(root)
            
            # Armazenar no cache
            self._cache_chaves[arquivo.caminho] = chave_nfe
            
            return chave_nfe
            
        except ET.ParseError as e:
            self.logger.debug(f"[ARQUIVOS] XML malformado {arquivo.caminho}: {e}")
            self._cache_chaves[arquivo.caminho] = None
            return None
        except Exception as e:
            self.logger.debug(f"[ARQUIVOS] Erro ao extrair chave de {arquivo.caminho}: {e}")
            self._cache_chaves[arquivo.caminho] = None
            return None
    
    def _buscar_chave_nfe_xml(self, root: ET.Element) -> Optional[str]:
        """
        Busca chave NFe no XML usando diferentes estratégias.
        
        Args:
            root: Elemento raiz do XML
            
        Returns:
            Chave NFe se encontrada
        """
        # Estratégia 1: Buscar por tag 'chNFe'
        for elem in root.iter():
            if elem.tag.endswith('chNFe') and elem.text:
                chave = elem.text.strip()
                if len(chave) == 44 and chave.isdigit():
                    return chave
        
        # Estratégia 2: Buscar atributo 'Id' que contenha chave
        for elem in root.iter():
            id_attr = elem.get('Id', '')
            if id_attr.startswith('NFe') and len(id_attr) == 47:
                chave = id_attr[3:]  # Remove 'NFe' do início
                if chave.isdigit():
                    return chave
        
        # Estratégia 3: Buscar texto que pareça com chave NFe (44 dígitos)
        for elem in root.iter():
            if elem.text and len(elem.text.strip()) == 44:
                texto = elem.text.strip()
                if texto.isdigit():
                    return texto
        
        return None
    
    def _analisar_duplicatas_chave(self, arquivos: List[ArquivoXML]) -> List[DuplicataLocal]:
        """
        Analisa duplicatas por chave NFe.
        
        Args:
            arquivos: Lista de arquivos para análise
            
        Returns:
            Lista de duplicatas encontradas
        """
        self.logger.info("[ARQUIVOS] Analisando duplicatas por chave NFe")
        
        # Agrupar por chave NFe
        chaves_arquivos: Dict[str, List[ArquivoXML]] = defaultdict(list)
        arquivos_sem_chave = 0
        
        for arquivo in arquivos:
            chave_nfe = self._extrair_chave_nfe(arquivo)
            
            if chave_nfe:
                arquivo.chave_nfe = chave_nfe
                chaves_arquivos[chave_nfe].append(arquivo)
            else:
                arquivos_sem_chave += 1
        
        if arquivos_sem_chave > 0:
            self.logger.warning(f"[ARQUIVOS] {arquivos_sem_chave:,} arquivos sem chave NFe válida")
        
        # Identificar duplicatas
        duplicatas = []
        for chave_nfe, lista_arquivos in chaves_arquivos.items():
            if len(lista_arquivos) > 1:
                duplicata = DuplicataLocal(
                    tipo='chave_nfe',
                    valor=chave_nfe,
                    arquivos=lista_arquivos
                )
                duplicatas.append(duplicata)
        
        self.logger.info(f"[ARQUIVOS] Encontradas {len(duplicatas)} duplicatas por chave NFe")
        
        return duplicatas
    
    def _analisar_duplicatas_nome(self, arquivos: List[ArquivoXML]) -> List[DuplicataLocal]:
        """
        Analisa duplicatas por nome de arquivo.
        
        Args:
            arquivos: Lista de arquivos para análise
            
        Returns:
            Lista de duplicatas encontradas
        """
        self.logger.info("[ARQUIVOS] Analisando duplicatas por nome de arquivo")
        
        # Agrupar por nome
        nomes_arquivos: Dict[str, List[ArquivoXML]] = defaultdict(list)
        
        for arquivo in arquivos:
            nomes_arquivos[arquivo.nome].append(arquivo)
        
        # Identificar duplicatas
        duplicatas = []
        for nome, lista_arquivos in nomes_arquivos.items():
            if len(lista_arquivos) > 1:
                duplicata = DuplicataLocal(
                    tipo='nome_arquivo',
                    valor=nome,
                    arquivos=lista_arquivos
                )
                duplicatas.append(duplicata)
        
        self.logger.info(f"[ARQUIVOS] Encontradas {len(duplicatas)} duplicatas por nome")
        
        return duplicatas
    
    def resolver_duplicatas_automaticamente(self, duplicatas_nome: List[DuplicataLocal]) -> Tuple[int, int]:
        """
        Remove automaticamente arquivos duplicados da pasta principal do dia,
        mantendo apenas os arquivos nas subpastas (XX_pasta_Y).
        
        Regra: Para arquivos duplicados entre pasta do dia e subpasta,
               remove o da pasta do dia e mantém o da subpasta.
        
        Args:
            duplicatas_nome: Lista de duplicatas por nome
            
        Returns:
            Tuple com (arquivos_removidos, duplicatas_resolvidas)
        """
        self.logger.info("[LIMPEZA] Iniciando resolução automática de duplicatas")
        
        arquivos_removidos = 0
        duplicatas_resolvidas = 0
        
        for duplicata in duplicatas_nome:
            try:
                # Verificar se é duplicata entre pasta do dia e subpasta
                if self._e_duplicata_pasta_dia_vs_subpasta(duplicata):
                    # Remover arquivo da pasta principal do dia
                    arquivo_removido = self._remover_arquivo_pasta_dia(duplicata)
                    if arquivo_removido:
                        arquivos_removidos += 1
                        duplicatas_resolvidas += 1
                        self.logger.info(f"[LIMPEZA] Removido: {arquivo_removido}")
                    
            except Exception as e:
                self.logger.error(f"[LIMPEZA] Erro ao processar duplicata {duplicata.valor}: {e}")
                continue
        
        self.logger.info(f"[LIMPEZA] Resolução concluída: {arquivos_removidos} arquivos removidos, {duplicatas_resolvidas} duplicatas resolvidas")
        
        return arquivos_removidos, duplicatas_resolvidas
    
    def _e_duplicata_pasta_dia_vs_subpasta(self, duplicata: DuplicataLocal) -> bool:
        """
        Verifica se é duplicata entre pasta do dia e subpasta.
        
        Args:
            duplicata: Duplicata para análise
            
        Returns:
            True se é duplicata pasta do dia vs subpasta
        """
        if duplicata.quantidade != 2:
            return False
        
        # Separar arquivos por tipo de localização
        arquivo_pasta_dia = None
        arquivo_subpasta = None
        
        for arquivo in duplicata.arquivos:
            caminho_str = str(arquivo.caminho)
            
            # Verificar se está em subpasta (padrão: XX_pasta_Y)
            if self._esta_em_subpasta(caminho_str):
                arquivo_subpasta = arquivo
            else:
                # Verificar se está diretamente na pasta do dia
                if self._esta_na_pasta_dia(caminho_str):
                    arquivo_pasta_dia = arquivo
        
        # É duplicata resolvível se temos exatamente um de cada tipo
        return arquivo_pasta_dia is not None and arquivo_subpasta is not None
    
    def _esta_em_subpasta(self, caminho: str) -> bool:
        """
        Verifica se arquivo está em subpasta com padrão XX_pasta_Y.
        
        Args:
            caminho: Caminho do arquivo
            
        Returns:
            True se está em subpasta
        """
        import re
        
        # Padrão para subpastas: números seguidos de _pasta_ seguidos de números
        # Exemplos: 18_pasta_1, 21_pasta_1, etc.
        padrao_subpasta = r'\\(\d+)_pasta_(\d+)\\'
        
        return re.search(padrao_subpasta, caminho) is not None
    
    def _esta_na_pasta_dia(self, caminho: str) -> bool:
        """
        Verifica se arquivo está diretamente na pasta do dia.
        
        Args:
            caminho: Caminho do arquivo
            
        Returns:
            True se está na pasta do dia
        """
        import re
        
        # Padrão: resultado\YYYY\MM\DD\arquivo.xml (sem subpasta)
        # Não deve conter padrão de subpasta após a data
        padrao_pasta_dia = r'\\resultado\\(\d{4})\\(\d{2})\\(\d{2})\\[^\\]+\.xml$'
        
        return re.search(padrao_pasta_dia, caminho) is not None
    
    def _remover_arquivo_pasta_dia(self, duplicata: DuplicataLocal) -> Optional[str]:
        """
        Remove o arquivo que está na pasta do dia.
        
        Args:
            duplicata: Duplicata para processar
            
        Returns:
            Caminho do arquivo removido ou None se não removeu
        """
        for arquivo in duplicata.arquivos:
            caminho_str = str(arquivo.caminho)
            
            # Se está na pasta do dia (não em subpasta), remove
            if self._esta_na_pasta_dia(caminho_str):
                try:
                    arquivo.caminho.unlink()  # Remove o arquivo
                    return caminho_str
                except Exception as e:
                    self.logger.error(f"[LIMPEZA] Erro ao remover {caminho_str}: {e}")
                    return None
        
        return None


# =============================================================================
# Analisador de banco de dados
# =============================================================================

class AnalisadorBancoDados:
    """Analisa duplicatas no banco de dados SQLite."""
    
    def __init__(self, logger: logging.Logger) -> None:
        """
        Inicializa o analisador.
        
        Args:
            logger: Logger para registrar operações
        """
        self.logger = logger
    
    def analisar_banco(self, caminho_banco: Union[str, Path]) -> Tuple[List[DuplicataBanco], int]:
        """
        Analisa duplicatas no banco de dados.
        
        Args:
            caminho_banco: Caminho para o banco SQLite
            
        Returns:
            Tuple com (duplicatas, total_registros)
            
        Raises:
            FileNotFoundError: Se banco não existe
            sqlite3.Error: Erros de banco de dados
        """
        banco_path = Path(caminho_banco)
        
        if not banco_path.exists():
            raise FileNotFoundError(f"Banco de dados não encontrado: {caminho_banco}")
        
        self.logger.info(f"[BANCO] Analisando duplicatas no banco: {caminho_banco}")
        
        try:
            with sqlite3.connect(banco_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Verificar se tabela existe
                if not self._verificar_tabela_notas(conn):
                    raise ValueError("Tabela 'notas' não encontrada no banco")
                
                # Contar total de registros
                total_registros = self._contar_registros_total(conn)
                self.logger.info(f"[BANCO] Total de registros: {total_registros:,}")
                
                # Buscar duplicatas
                duplicatas = self._buscar_duplicatas_chave_nfe(conn)
                
                return duplicatas, total_registros
                
        except sqlite3.Error as e:
            self.logger.error(f"[BANCO] Erro de banco de dados: {e}")
            raise
        except Exception as e:
            self.logger.error(f"[BANCO] Erro inesperado: {e}")
            raise
    
    def _verificar_tabela_notas(self, conn: sqlite3.Connection) -> bool:
        """
        Verifica se a tabela 'notas' existe.
        
        Args:
            conn: Conexão com banco
            
        Returns:
            True se tabela existe
        """
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='notas'"
        )
        return cursor.fetchone() is not None
    
    def _contar_registros_total(self, conn: sqlite3.Connection) -> int:
        """
        Conta total de registros na tabela notas.
        
        Args:
            conn: Conexão com banco
            
        Returns:
            Número total de registros
        """
        cursor = conn.execute("SELECT COUNT(*) FROM notas")
        return cursor.fetchone()[0]
    
    def _buscar_duplicatas_chave_nfe(self, conn: sqlite3.Connection) -> List[DuplicataBanco]:
        """
        Busca duplicatas por chave NFe no banco.
        
        Args:
            conn: Conexão com banco
            
        Returns:
            Lista de duplicatas encontradas
        """
        # Query para encontrar chaves NFe duplicadas
        query = """
        SELECT cChaveNFe, COUNT(*) as quantidade
        FROM notas 
        WHERE cChaveNFe IS NOT NULL 
            AND cChaveNFe != ''
        GROUP BY cChaveNFe 
        HAVING COUNT(*) > 1
        ORDER BY quantidade DESC, cChaveNFe
        """
        
        cursor = conn.execute(query)
        chaves_duplicadas = cursor.fetchall()
        
        if not chaves_duplicadas:
            self.logger.info("[BANCO] Nenhuma duplicata encontrada")
            return []
        
        self.logger.info(f"[BANCO] Encontradas {len(chaves_duplicadas)} chaves NFe duplicadas")
        
        # Buscar detalhes de cada duplicata
        duplicatas = []
        for row in chaves_duplicadas:
            chave_nfe = row['cChaveNFe']
            quantidade = row['quantidade']
            
            # Buscar todos os registros desta chave
            registros = self._buscar_registros_chave(conn, chave_nfe)
            
            duplicata = DuplicataBanco(
                chave_nfe=chave_nfe,
                registros=registros
            )
            duplicatas.append(duplicata)
            
            self.logger.debug(f"[BANCO] Chave {chave_nfe}: {quantidade} duplicatas")
        
        return duplicatas
    
    def _buscar_registros_chave(self, conn: sqlite3.Connection, chave_nfe: str) -> List[Dict[str, Union[str, int]]]:
        """
        Busca todos os registros de uma chave NFe específica.
        
        Args:
            conn: Conexão com banco
            chave_nfe: Chave NFe para buscar
            
        Returns:
            Lista de registros encontrados
        """
        # Selecionar campos relevantes
        query = """
        SELECT rowid, cChaveNFe, nNF, dEmi, xml_baixado, erro, 
               arquivo_caminho, mensagem_erro
        FROM notas 
        WHERE cChaveNFe = ?
        ORDER BY rowid
        """
        
        cursor = conn.execute(query, (chave_nfe,))
        rows = cursor.fetchall()
        
        # Converter para lista de dicts
        registros = []
        for row in rows:
            registro = {
                'rowid': row['rowid'],
                'cChaveNFe': row['cChaveNFe'],
                'nNF': row['nNF'],
                'dEmi': row['dEmi'],
                'xml_baixado': row['xml_baixado'],
                'erro': row['erro'],
                'arquivo_caminho': row['arquivo_caminho'],
                'mensagem_erro': row['mensagem_erro']
            }
            registros.append(registro)
        
        return registros


# =============================================================================
# Gerador de relatórios
# =============================================================================

class GeradorRelatorio:
    """Gera relatórios detalhados das duplicatas encontradas."""
    
    def __init__(self, logger: logging.Logger) -> None:
        """
        Inicializa o gerador.
        
        Args:
            logger: Logger para registrar operações
        """
        self.logger = logger
    
    def gerar_relatorio_completo(self, relatorio: RelatorioCompleto) -> None:
        """
        Gera relatório completo das duplicatas.
        
        Args:
            relatorio: Dados do relatório
        """
        self.logger.info("[RELATORIO] Gerando relatório completo de duplicatas")
        
        # Cabeçalho do relatório
        self._imprimir_cabecalho(relatorio)
        
        # Relatório de arquivos locais
        if relatorio.duplicatas_locais_chave or relatorio.duplicatas_locais_nome:
            self._relatorio_arquivos_locais(relatorio)
        
        # Relatório de banco de dados
        if relatorio.duplicatas_banco:
            self._relatorio_banco_dados(relatorio)
        
        # Resumo final
        self._imprimir_resumo(relatorio)
    
    def _imprimir_cabecalho(self, relatorio: RelatorioCompleto) -> None:
        """Imprime cabeçalho do relatório."""
        print("\n" + "="*80)
        print("RELATÓRIO DE VERIFICAÇÃO DE DUPLICATAS")
        print("="*80)
        print(f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"Tempo de execução: {relatorio.tempo_execucao:.2f} segundos")
        print(f"Arquivos analisados: {relatorio.total_arquivos_analisados:,}")
        print(f"Registros no banco: {relatorio.total_registros_banco:,}")
        
        if relatorio.arquivos_removidos > 0:
            print(f"🧹 Arquivos removidos: {relatorio.arquivos_removidos:,}")
            print(f"✅ Duplicatas resolvidas: {relatorio.duplicatas_resolvidas:,}")
        
        print()
    
    def _relatorio_arquivos_locais(self, relatorio: RelatorioCompleto) -> None:
        """Gera relatório de duplicatas em arquivos locais."""
        print("DUPLICATAS EM ARQUIVOS LOCAIS")
        print("-" * 50)
        
        # Duplicatas por chave NFe
        if relatorio.duplicatas_locais_chave:
            print(f"\n🔑 DUPLICATAS POR CHAVE NFE: {len(relatorio.duplicatas_locais_chave)}")
            for i, dup in enumerate(relatorio.duplicatas_locais_chave, 1):
                print(f"\n  {i}. Chave NFe: {dup.valor}")
                print(f"     Arquivos duplicados: {dup.quantidade}")
                for arquivo in dup.arquivos:
                    print(f"     - {arquivo.caminho}")
                    print(f"       Tamanho: {arquivo.tamanho:,} bytes")
                    print(f"       Modificado: {arquivo.data_modificacao.strftime('%d/%m/%Y %H:%M:%S')}")
        
        # Duplicatas por nome
        if relatorio.duplicatas_locais_nome:
            print(f"\n📁 DUPLICATAS POR NOME DE ARQUIVO: {len(relatorio.duplicatas_locais_nome)}")
            for i, dup in enumerate(relatorio.duplicatas_locais_nome, 1):
                print(f"\n  {i}. Nome: {dup.valor}")
                print(f"     Arquivos duplicados: {dup.quantidade}")
                for arquivo in dup.arquivos:
                    print(f"     - {arquivo.caminho}")
                    print(f"       Chave NFe: {arquivo.chave_nfe or 'N/A'}")
                    print(f"       Tamanho: {arquivo.tamanho:,} bytes")
    
    def _relatorio_banco_dados(self, relatorio: RelatorioCompleto) -> None:
        """Gera relatório de duplicatas no banco de dados."""
        print("\nDUPLICATAS NO BANCO DE DADOS")
        print("-" * 50)
        
        print(f"\n💾 DUPLICATAS POR CHAVE NFE: {len(relatorio.duplicatas_banco)}")
        
        for i, dup in enumerate(relatorio.duplicatas_banco, 1):
            print(f"\n  {i}. Chave NFe: {dup.chave_nfe}")
            print(f"     Registros duplicados: {dup.quantidade}")
            
            for j, registro in enumerate(dup.registros, 1):
                print(f"     {j}. Row ID: {registro['rowid']}")
                print(f"        Número NF: {registro['nNF']}")
                print(f"        Data Emissão: {registro['dEmi']}")
                print(f"        XML Baixado: {'Sim' if registro['xml_baixado'] else 'Não'}")
                if registro['erro']:
                    print(f"        Erro: {registro['mensagem_erro']}")
                if registro['arquivo_caminho']:
                    print(f"        Caminho: {registro['arquivo_caminho']}")
    
    def _imprimir_resumo(self, relatorio: RelatorioCompleto) -> None:
        """Imprime resumo final do relatório."""
        print("\nRESUMO EXECUTIVO")
        print("-" * 30)
        
        total_duplicatas_locais = (
            len(relatorio.duplicatas_locais_chave) + 
            len(relatorio.duplicatas_locais_nome)
        )
        
        print(f"Duplicatas locais (chave NFe): {len(relatorio.duplicatas_locais_chave)}")
        print(f"Duplicatas locais (nome): {len(relatorio.duplicatas_locais_nome)}")
        print(f"Duplicatas no banco: {len(relatorio.duplicatas_banco)}")
        print(f"Total de problemas: {total_duplicatas_locais + len(relatorio.duplicatas_banco)}")
        
        if relatorio.arquivos_removidos > 0:
            print(f"\n🧹 LIMPEZA REALIZADA:")
            print(f"   Arquivos removidos: {relatorio.arquivos_removidos:,}")
            print(f"   Duplicatas resolvidas: {relatorio.duplicatas_resolvidas:,}")
        
        if relatorio.tem_duplicatas:
            print("\n⚠️  ATENÇÃO: Duplicatas encontradas! Revise os resultados acima.")
        else:
            print("\n✅ Nenhuma duplicata encontrada. Sistema íntegro.")
        
        print("\n" + "="*80 + "\n")


# =============================================================================
# Função principal
# =============================================================================

def _processar_limpeza_com_confirmacao(analisador: 'AnalisadorArquivosLocais', 
                                     duplicatas_nome: List[DuplicataLocal], 
                                     logger: logging.Logger) -> Tuple[int, int]:
    """
    Processa limpeza de duplicatas com confirmação do usuário.
    
    Args:
        analisador: Instância do analisador de arquivos
        duplicatas_nome: Lista de duplicatas por nome
        logger: Logger para registrar operações
        
    Returns:
        Tuple com (arquivos_removidos, duplicatas_resolvidas)
    """
    arquivos_removidos = 0
    duplicatas_resolvidas = 0
    
    logger.info(f"[LIMPEZA] Modo com confirmação: {len(duplicatas_nome)} duplicatas para revisar")
    
    for i, duplicata in enumerate(duplicatas_nome, 1):
        if not analisador._e_duplicata_pasta_dia_vs_subpasta(duplicata):
            continue
            
        # Identificar arquivos
        arquivo_pasta_dia = None
        arquivo_subpasta = None
        
        for arquivo in duplicata.arquivos:
            if analisador._esta_na_pasta_dia(str(arquivo.caminho)):
                arquivo_pasta_dia = arquivo
            elif analisador._esta_em_subpasta(str(arquivo.caminho)):
                arquivo_subpasta = arquivo
        
        if arquivo_pasta_dia and arquivo_subpasta:
            print(f"\n[{i}/{len(duplicatas_nome)}] Duplicata encontrada:")
            print(f"  Arquivo: {duplicata.valor}")
            print(f"  📁 Pasta do dia: {arquivo_pasta_dia.caminho}")
            print(f"  📂 Subpasta:     {arquivo_subpasta.caminho}")
            
            resposta = input("  Remover arquivo da pasta do dia? (s/N): ").strip().lower()
            
            if resposta in ['s', 'sim', 'y', 'yes']:
                try:
                    arquivo_pasta_dia.caminho.unlink()
                    arquivos_removidos += 1
                    duplicatas_resolvidas += 1
                    logger.info(f"[LIMPEZA] Removido: {arquivo_pasta_dia.caminho}")
                    print("  ✅ Arquivo removido")
                except Exception as e:
                    logger.error(f"[LIMPEZA] Erro ao remover: {e}")
                    print(f"  ❌ Erro: {e}")
            else:
                print("  ⏭️  Ignorado")
    
    return arquivos_removidos, duplicatas_resolvidas


def main() -> None:
    """
    Função principal do verificador de duplicatas.
    
    Executa análise completa de duplicatas em arquivos locais e banco de dados,
    gerando relatório detalhado dos problemas encontrados.
    """
    # Configurar argumentos da linha de comando
    parser = argparse.ArgumentParser(
        description="Verificador de duplicatas de arquivos XML",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python verificar_duplicatas.py --pasta resultado --banco omie.db
  python verificar_duplicatas.py --apenas-banco --banco omie.db
  python verificar_duplicatas.py --apenas-arquivos --pasta resultado
  python verificar_duplicatas.py --pasta resultado --limpar-duplicatas
  python verificar_duplicatas.py --pasta resultado --limpar-duplicatas --confirmar-remocao
        """
    )
    
    parser.add_argument(
        '--pasta', 
        type=str, 
        default='resultado',
        help='Pasta para análise de arquivos XML (padrão: resultado)'
    )
    
    parser.add_argument(
        '--banco', 
        type=str, 
        default='omie.db',
        help='Caminho do banco de dados SQLite (padrão: omie.db)'
    )
    
    parser.add_argument(
        '--apenas-arquivos', 
        action='store_true',
        help='Analisar apenas arquivos locais'
    )
    
    parser.add_argument(
        '--apenas-banco', 
        action='store_true',
        help='Analisar apenas banco de dados'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Modo verboso (mais detalhes no log)'
    )
    
    parser.add_argument(
        '--limpar-duplicatas',
        action='store_true',
        help='Remove automaticamente arquivos duplicados da pasta do dia (mantém os das subpastas)'
    )
    
    parser.add_argument(
        '--confirmar-remocao',
        action='store_true',
        help='Solicita confirmação antes de remover cada arquivo duplicado'
    )
    
    args = parser.parse_args()
    
    # Configurar logging
    logger = configurar_logging()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("[SETUP] Modo verboso ativado")
    
    try:
        # Timestamp de início
        inicio = time.time()
        
        logger.info("[INICIO] Verificador de duplicatas iniciado")
        logger.info(f"[CONFIG] Pasta: {args.pasta}")
        logger.info(f"[CONFIG] Banco: {args.banco}")
        logger.info(f"[CONFIG] Apenas arquivos: {args.apenas_arquivos}")
        logger.info(f"[CONFIG] Apenas banco: {args.apenas_banco}")
        logger.info(f"[CONFIG] Limpar duplicatas: {args.limpar_duplicatas}")
        logger.info(f"[CONFIG] Confirmar remoção: {args.confirmar_remocao}")
        
        # Inicializar analisadores
        analisador_arquivos = AnalisadorArquivosLocais(logger)
        analisador_banco = AnalisadorBancoDados(logger)
        gerador_relatorio = GeradorRelatorio(logger)
        
        # Variáveis para resultados
        duplicatas_chave_local = []
        duplicatas_nome_local = []
        duplicatas_banco = []
        total_arquivos = 0
        total_registros = 0
        arquivos_removidos = 0
        duplicatas_resolvidas = 0
        
        # Análise de arquivos locais
        if not args.apenas_banco:
            try:
                logger.info("[FASE] Iniciando análise de arquivos locais")
                duplicatas_chave_local, duplicatas_nome_local, total_arquivos = (
                    analisador_arquivos.analisar_pasta(args.pasta)
                )
                
                # Limpeza automática de duplicatas se solicitada
                if args.limpar_duplicatas and duplicatas_nome_local:
                    logger.info("[FASE] Iniciando limpeza automática de duplicatas")
                    
                    if args.confirmar_remocao:
                        # Modo com confirmação
                        arquivos_removidos, duplicatas_resolvidas = (
                            _processar_limpeza_com_confirmacao(analisador_arquivos, duplicatas_nome_local, logger)
                        )
                    else:
                        # Modo automático
                        arquivos_removidos, duplicatas_resolvidas = (
                            analisador_arquivos.resolver_duplicatas_automaticamente(duplicatas_nome_local)
                        )
                    
                    # Re-analisar após limpeza para atualizar estatísticas
                    if arquivos_removidos > 0:
                        logger.info("[FASE] Re-analisando após limpeza")
                        duplicatas_chave_local, duplicatas_nome_local, total_arquivos = (
                            analisador_arquivos.analisar_pasta(args.pasta)
                        )
                
                logger.info("[FASE] Análise de arquivos locais concluída")
                
            except (FileNotFoundError, NotADirectoryError) as e:
                logger.error(f"[ERRO] Problema com pasta: {e}")
                if not args.apenas_arquivos:
                    logger.info("[CONTINUACAO] Continuando apenas com análise do banco")
                else:
                    return
            except Exception as e:
                logger.exception(f"[ERRO] Erro durante análise de arquivos: {e}")
                if args.apenas_arquivos:
                    return
        
        # Análise do banco de dados
        if not args.apenas_arquivos:
            try:
                logger.info("[FASE] Iniciando análise do banco de dados")
                duplicatas_banco, total_registros = (
                    analisador_banco.analisar_banco(args.banco)
                )
                logger.info("[FASE] Análise do banco de dados concluída")
                
            except FileNotFoundError as e:
                logger.error(f"[ERRO] Banco não encontrado: {e}")
                if args.apenas_banco:
                    return
            except Exception as e:
                logger.exception(f"[ERRO] Erro durante análise do banco: {e}")
                if args.apenas_banco:
                    return
        
        # Calcular tempo total
        fim = time.time()
        tempo_execucao = fim - inicio
        
        # Criar relatório completo
        relatorio = RelatorioCompleto(
            duplicatas_locais_chave=duplicatas_chave_local,
            duplicatas_locais_nome=duplicatas_nome_local,
            duplicatas_banco=duplicatas_banco,
            total_arquivos_analisados=total_arquivos,
            total_registros_banco=total_registros,
            tempo_execucao=tempo_execucao,
            arquivos_removidos=arquivos_removidos,
            duplicatas_resolvidas=duplicatas_resolvidas
        )
        
        # Gerar relatório
        gerador_relatorio.gerar_relatorio_completo(relatorio)
        
        # Log final
        logger.info(f"[SUCESSO] Verificação concluída em {tempo_execucao:.2f} segundos")
        
        # Código de saída baseado nos resultados
        if relatorio.tem_duplicatas:
            logger.warning("[RESULTADO] Duplicatas encontradas - código de saída 1")
            exit(1)
        else:
            logger.info("[RESULTADO] Nenhuma duplicata encontrada - código de saída 0")
            exit(0)
            
    except KeyboardInterrupt:
        logger.warning("[INTERRUPCAO] Execução interrompida pelo usuário")
        exit(130)
        
    except Exception as e:
        logger.exception(f"[ERRO] Erro crítico inesperado: {e}")
        exit(1)


if __name__ == "__main__":
    main()
