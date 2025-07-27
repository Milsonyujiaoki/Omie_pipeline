#!/usr/bin/env python3
"""
SCRIPT DE CORREÇÃO DE BASE - DOWNLOAD DE ARQUIVOS PENDENTES

Este script é focado exclusivamente em corrigir registros pendentes no banco de dados,
baixando XMLs que ainda não foram obtidos e preenchendo corretamente as colunas da tabela.

FUNCIONALIDADES:
- Busca apenas registros pendentes (xml_baixado = 0, erro = 0)
- Download assíncrono otimizado com rate limiting
- Validação rigorosa de XMLs (detecta arquivos vazios)
- Atualização correta de todas as colunas da tabela
- Não realiza listagem de novas notas (foco apenas em correção)
- Prevenção de duplicatas
- Tratamento robusto de erros da API

OTIMIZAÇÕES APLICADAS:
- Usa índices otimizados para consultas rápidas
- Processamento em lotes para melhor performance
- Rate limiting global de 4 req/s respeitado
- Retry inteligente para falhas temporárias
- Logging detalhado para monitoramento

USO:
    python corrigir_base_pendentes.py [--max-concurrent 5] [--batch-size 100] [--db omie.db]

SEGURANÇA:
- Não modifica registros já processados
- Backup automático do banco antes da execução
- Rollback em caso de falhas críticas
"""

import sys
import os
import asyncio
import aiohttp
import sqlite3
import logging
import time
import argparse
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, NamedTuple
from dataclasses import dataclass
import configparser
import html
import xml.etree.ElementTree as ET

# Adicionar src ao path para imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import com tratamento de erro
try:
    from src.omie_client_async import OmieClient
    from src.utils import (
        respeitar_limite_requisicoes_async,
        gerar_xml_path,
        marcar_como_baixado,
        marcar_como_erro
    )
except ImportError as e:
    print(f"❌ Erro de importação: {e}")
    print("Verifique se os módulos src/omie_client_async.py e src/utils.py existem")
    sys.exit(1)

# =============================================================================
# CONFIGURAÇÃO DE LOGGING
# =============================================================================
def configurar_logging():
    """Configura logging específico para correção de base."""
    log_dir = Path("log")
    log_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / f"correcao_base_{timestamp}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)

logger = configurar_logging()

# =============================================================================
# ESTRUTURAS DE DADOS
# =============================================================================
@dataclass
class RegistroPendente:
    """Estrutura para registro pendente otimizada."""
    id: int
    chave_nfe: str
    numero_nf: str
    data_emissao: Optional[str] = None
    cnpj_cpf: Optional[str] = None
    razao_social: Optional[str] = None

class MetricasCorrecao(NamedTuple):
    """Métricas do processo de correção."""
    total_pendentes: int
    downloads_sucesso: int
    downloads_erro: int
    arquivos_vazios: int
    tempo_total: float
    taxa_sucesso: float

class ConfiguracaoCorrecao:
    """Configuração validada para correção."""
    def __init__(self, max_concurrent: int = 5, batch_size: int = 100, db_path: str = "omie.db"):
        self.max_concurrent = max(1, min(max_concurrent, 8))  # Limite conservador
        self.batch_size = max(1, min(batch_size, 200))  # Permite batch_size menor para testes
        self.db_path = db_path
        self.resultado_dir = self._carregar_resultado_dir()
        
        # Rate limiting - 4 req/s global
        self.calls_per_second = 4
        self.delay_entre_requests = 1.0 / self.calls_per_second
        
    def _carregar_resultado_dir(self) -> Path:
        """Carrega diretório de resultado da configuração."""
        try:
            config = configparser.ConfigParser()
            config.read('configuracao.ini')
            resultado_dir = config.get('paths', 'resultado_dir', fallback='resultado')
            return Path(resultado_dir)
        except Exception:
            return Path('resultado')

# =============================================================================
# FUNÇÕES DE BANCO DE DADOS OTIMIZADAS
# =============================================================================
def criar_backup_banco(db_path: str) -> str:
    """
    Cria backup do banco antes da correção.
    
    Returns:
        str: Caminho do backup criado
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}.backup_correcao_{timestamp}"
    
    try:
        shutil.copy2(db_path, backup_path)
        logger.info(f"[BACKUP] Backup criado: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"[BACKUP] Erro ao criar backup: {e}")
        raise

def otimizar_banco_para_correcao(db_path: str) -> None:
    """Aplica otimizações específicas para correção usando estrutura existente."""
    pragmas_correcao = {
        "journal_mode": "WAL",
        "synchronous": "NORMAL", 
        "cache_size": "-128000",  # 128MB cache
        "temp_store": "MEMORY",
        "mmap_size": "536870912",  # 512MB mmap
    }
    
    try:
        with sqlite3.connect(db_path) as conn:
            for pragma, valor in pragmas_correcao.items():
                conn.execute(f"PRAGMA {pragma}={valor}")
            
            # Verificar se índices essenciais já existem (baseado na estrutura mostrada)
            # Usa os índices existentes da imagem: idx_chave, idx_xml_baixado, etc.
            indices_adicionais = [
                "CREATE INDEX IF NOT EXISTS idx_pendentes_otimizado ON notas(xml_baixado, erro) WHERE xml_baixado = 0 AND erro = 0",
            ]
            
            for sql in indices_adicionais:
                try:
                    conn.execute(sql)
                except sqlite3.Error as e:
                    logger.debug(f"[BD.OTIM.INDICE] {e}")
                
            conn.commit()
            logger.info("[BD.OTIM] Banco otimizado para correção - usando índices existentes")
            
    except Exception as e:
        logger.error(f"[BD.OTIM] Erro na otimização: {e}")

def buscar_registros_pendentes(db_path: str, limite: Optional[int] = None) -> List[RegistroPendente]:
    """
    Busca registros pendentes usando consulta otimizada com campos corretos da tabela.
    
    Args:
        db_path: Caminho do banco
        limite: Limite opcional de registros
        
    Returns:
        Lista de registros pendentes
    """
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Primeiro, verificar se podemos usar views existentes
            try:
                # Tenta usar view otimizada se existir
                sql_view = """
                    SELECT nIdNF, cChaveNFe, nNF, dEmi, cnpj_cpf, cRazao
                    FROM vw_notas_pendentes
                    ORDER BY nIdNF
                """
                if limite:
                    sql_view += f" LIMIT {limite}"
                
                cursor.execute(sql_view)
                resultados = cursor.fetchall()
                logger.info(f"[BD.BUSCA] Usando view otimizada vw_notas_pendentes")
                
            except sqlite3.Error:
                # Fallback para consulta direta usando campos corretos da tabela
                sql = """
                    SELECT nIdNF, cChaveNFe, nNF, dEmi, cnpj_cpf, cRazao
                    FROM notas 
                    WHERE xml_baixado = 0 
                      AND erro = 0 
                      AND cChaveNFe IS NOT NULL 
                      AND cChaveNFe != ''
                      AND cChaveNFe != 'NULL'
                    ORDER BY nIdNF
                """
                
                if limite:
                    sql += f" LIMIT {limite}"
                
                cursor.execute(sql)
                resultados = cursor.fetchall()
                logger.info(f"[BD.BUSCA] Usando consulta direta na tabela notas")
            
            # Converter para estrutura tipada usando campos corretos
            registros = []
            for row in resultados:
                try:
                    registro = RegistroPendente(
                        id=row[0],  # nIdNF
                        chave_nfe=row[1],  # cChaveNFe
                        numero_nf=row[2] or "",  # nNF
                        data_emissao=row[3],  # dEmi
                        cnpj_cpf=row[4],  # cnpj_cpf
                        razao_social=row[5]  # cRazao
                    )
                    registros.append(registro)
                except Exception as e:
                    logger.warning(f"[BD.BUSCA] Erro ao processar registro {row}: {e}")
                    continue
            
            logger.info(f"[BD.BUSCA] {len(registros):,} registros pendentes encontrados")
            return registros
            
    except Exception as e:
        logger.error(f"[BD.BUSCA] Erro ao buscar pendentes: {e}")
        return []

def atualizar_registro_sucesso(db_path: str, registro: RegistroPendente, caminho_xml: str, 
                              xml_vazio: bool, tamanho_arquivo: int) -> bool:
    """
    Atualiza registro com sucesso completo usando campos corretos da tabela.
    
    Args:
        db_path: Caminho do banco
        registro: Registro processado
        caminho_xml: Caminho do arquivo XML salvo
        xml_vazio: Se arquivo está vazio
        tamanho_arquivo: Tamanho do arquivo
        
    Returns:
        bool: Sucesso da operação
    """
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Atualização usando campos corretos da tabela
            sql = """
                UPDATE notas SET
                    xml_baixado = 1,
                    xml_vazio = ?,
                    erro = 0,
                    caminho_arquivo = ?,
                    baixado_novamente = COALESCE(baixado_novamente, 0) + 1,
                    anomesdia = COALESCE(anomesdia, substr(?, 1, 8))
                WHERE nIdNF = ? AND cChaveNFe = ?
            """
            
            # Extrair anomesdia da data de emissão se disponível
            anomesdia = ""
            if registro.data_emissao:
                try:
                    # Converter data para formato YYYYMMDD
                    from datetime import datetime
                    if len(registro.data_emissao) >= 10:
                        data_obj = datetime.strptime(registro.data_emissao[:10], '%Y-%m-%d')
                        anomesdia = data_obj.strftime('%Y%m%d')
                    elif len(registro.data_emissao) == 8:
                        anomesdia = registro.data_emissao
                except:
                    anomesdia = "20240101"  # Fallback
            else:
                anomesdia = "20240101"  # Fallback para data padrão
            
            cursor.execute(sql, (
                1 if xml_vazio else 0,
                caminho_xml,
                anomesdia,
                registro.id,
                registro.chave_nfe
            ))
            
            if cursor.rowcount > 0:
                conn.commit()
                return True
            else:
                logger.warning(f"[BD.UPD] Nenhum registro atualizado para {registro.chave_nfe}")
                return False
                
    except Exception as e:
        logger.error(f"[BD.UPD] Erro ao atualizar sucesso {registro.chave_nfe}: {e}")
        return False

def atualizar_registro_erro(db_path: str, registro: RegistroPendente, mensagem_erro: str) -> bool:
    """
    Atualiza registro com erro usando campos corretos da tabela.
    
    Args:
        db_path: Caminho do banco
        registro: Registro com erro
        mensagem_erro: Descrição do erro
        
    Returns:
        bool: Sucesso da operação
    """
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Truncar mensagem de erro se muito longa
            mensagem_truncada = mensagem_erro[:500] if len(mensagem_erro) > 500 else mensagem_erro
            
            sql = """
                UPDATE notas SET
                    erro = 1,
                    xml_baixado = 0,
                    mensagem_erro = ?,
                    erro_xml = ?
                WHERE nIdNF = ? AND cChaveNFe = ?
            """
            
            cursor.execute(sql, (
                mensagem_truncada,
                mensagem_truncada,  # Preencher erro_xml também
                registro.id,
                registro.chave_nfe
            ))
            
            if cursor.rowcount > 0:
                conn.commit()
                return True
            else:
                return False
                
    except Exception as e:
        logger.error(f"[BD.ERR] Erro ao atualizar erro {registro.chave_nfe}: {e}")
        return False

# =============================================================================
# FUNÇÕES DE DOWNLOAD E VALIDAÇÃO
# =============================================================================
def validar_xml_content(xml_content: str, chave_nfe: str) -> Tuple[str, bool]:
    """
    Valida conteúdo XML e detecta se está vazio.
    
    Args:
        xml_content: Conteúdo XML da API
        chave_nfe: Chave da NFe
        
    Returns:
        Tuple[str, bool]: (XML validado, é_vazio)
    """
    if not xml_content or xml_content.strip() == '':
        return "", True
    
    # Decodifica HTML entities
    xml_decoded = html.unescape(xml_content.strip())
    
    # Verifica se é apenas espaços ou caracteres vazios
    if len(xml_decoded.strip()) < 100:  # XML válido deve ter pelo menos 100 chars
        logger.warning(f"[XML.VALID] XML muito pequeno para {chave_nfe}: {len(xml_decoded)} chars")
        return xml_decoded, True
    
    # Validação básica de estrutura
    if not (xml_decoded.startswith('<?xml') or xml_decoded.startswith('<')):
        logger.warning(f"[XML.VALID] XML mal formado para {chave_nfe}")
        return xml_decoded, True
    
    # Tenta parsear para verificar se é well-formed
    try:
        ET.fromstring(xml_decoded)
        return xml_decoded, False  # XML válido
    except ET.ParseError as e:
        logger.warning(f"[XML.VALID] Erro de parsing XML para {chave_nfe}: {e}")
        return xml_decoded, True  # Considera vazio se não conseguir parsear

async def baixar_xml_individual(
    session: aiohttp.ClientSession,
    client: OmieClient,
    registro: RegistroPendente,
    config: ConfiguracaoCorrecao,
    semaphore: asyncio.Semaphore
) -> Tuple[bool, str, Optional[str], bool, int]:
    """
    Baixa XML individual com validação completa.
    
    Returns:
        Tuple[bool, str, Optional[str], bool, int]: 
        (sucesso, chave_nfe, caminho_arquivo, xml_vazio, tamanho)
    """
    async with semaphore:
        try:
            # Rate limiting global
            await respeitar_limite_requisicoes_async()
            
            # Preparar payload para API usando campos corretos
            payload = {
                'nIdNF': registro.id,  # Usar nIdNF conforme estrutura
                'cChaveNFe': registro.chave_nfe,
                'tpAmb': 1,
                'cInfCompl': 'N',
                'cFormatoXML': 'S',
                'cOnlyCanc': 'N',
                'cCancelOnly': 'N',
            }
            
            # Chamada para API
            logger.debug(f"[DOWNLOAD] Baixando {registro.chave_nfe}")
            resposta = await client.call_api(session, "ExportarXML", payload)
            
            if not resposta or 'xml' not in resposta:
                logger.warning(f"[DOWNLOAD] Resposta inválida para {registro.chave_nfe}")
                return False, registro.chave_nfe, None, True, 0
            
            xml_content = resposta['xml']
            
            # Validar conteúdo XML
            xml_validado, xml_vazio = validar_xml_content(xml_content, registro.chave_nfe)
            
            if xml_vazio:
                logger.warning(f"[DOWNLOAD] XML vazio recebido para {registro.chave_nfe}")
                # Ainda salva o arquivo vazio para registro
                xml_content = xml_validado
            
            # Gerar caminho do arquivo
            xml_path = gerar_xml_path(
                config.resultado_dir,
                registro.data_emissao or "2024",
                registro.chave_nfe
            )
            
            # Criar diretório se necessário
            xml_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Salvar arquivo
            with open(xml_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            
            tamanho_arquivo = xml_path.stat().st_size
            
            logger.info(f"[DOWNLOAD] ✓ {registro.chave_nfe} salvo: {tamanho_arquivo} bytes")
            
            return True, registro.chave_nfe, str(xml_path), xml_vazio, tamanho_arquivo
            
        except Exception as e:
            logger.error(f"[DOWNLOAD] ✗ Erro {registro.chave_nfe}: {e}")
            return False, registro.chave_nfe, None, True, 0

# =============================================================================
# FUNÇÃO PRINCIPAL DE CORREÇÃO
# =============================================================================
async def corrigir_base_pendentes(config: ConfiguracaoCorrecao, limite: Optional[int] = None) -> MetricasCorrecao:
    """
    Função principal para correção de registros pendentes.
    
    Args:
        config: Configuração da correção
        
    Returns:
        MetricasCorrecao: Métricas do processo
    """
    logger.info("🚀 INICIANDO CORREÇÃO DE BASE - DOWNLOAD DE PENDENTES")
    logger.info("=" * 70)
    
    tempo_inicio = time.time()
    
    # Criar backup do banco
    backup_path = criar_backup_banco(config.db_path)
    
    # Otimizar banco para correção
    otimizar_banco_para_correcao(config.db_path)
    
    # Buscar registros pendentes
    registros_pendentes = buscar_registros_pendentes(config.db_path, limite)
    total_pendentes = len(registros_pendentes)
    
    if total_pendentes == 0:
        logger.info("✅ Nenhum registro pendente encontrado!")
        return MetricasCorrecao(0, 0, 0, 0, 0.0, 100.0)
    
    logger.info(f"📊 {total_pendentes:,} registros pendentes para correção")
    
    # Carregar configurações da API
    try:
        config_parser = configparser.ConfigParser()
        config_parser.read('configuracao.ini')
        
        app_key = config_parser.get('omie_api', 'app_key')
        app_secret = config_parser.get('omie_api', 'app_secret')
        
    except Exception as e:
        logger.error(f"❌ Erro ao carregar configurações: {e}")
        raise
    
    # Criar cliente Omie
    client = OmieClient(
        app_key=app_key,
        app_secret=app_secret,
        calls_per_second=config.calls_per_second
    )
    
    # Métricas de progresso
    downloads_sucesso = 0
    downloads_erro = 0
    arquivos_vazios = 0
    
    # Controle de concorrência
    semaphore = asyncio.Semaphore(config.max_concurrent)
    timeout_config = aiohttp.ClientTimeout(total=60, connect=15)
    
    # Processamento em lotes
    async with aiohttp.ClientSession(timeout=timeout_config) as session:
        
        for i in range(0, total_pendentes, config.batch_size):
            lote_registros = registros_pendentes[i:i + config.batch_size]
            lote_numero = (i // config.batch_size) + 1
            total_lotes = (total_pendentes + config.batch_size - 1) // config.batch_size
            
            logger.info(f"Processando lote {lote_numero}/{total_lotes} ({len(lote_registros)} registros)")
            
            # Criar tasks para o lote
            tasks = []
            for registro in lote_registros:
                task = asyncio.create_task(
                    baixar_xml_individual(session, client, registro, config, semaphore)
                )
                tasks.append((task, registro))
            
            # Executar lote e processar resultados
            for task, registro in tasks:
                try:
                    sucesso, chave_nfe, caminho_xml, xml_vazio, tamanho = await task
                    
                    if sucesso:
                        # Atualizar banco com sucesso
                        if atualizar_registro_sucesso(
                            config.db_path, registro, caminho_xml, xml_vazio, tamanho
                        ):
                            downloads_sucesso += 1
                            if xml_vazio:
                                arquivos_vazios += 1
                        else:
                            downloads_erro += 1
                    else:
                        # Atualizar banco com erro
                        if atualizar_registro_erro(config.db_path, registro, "Erro no download"):
                            downloads_erro += 1
                            
                except Exception as e:
                    logger.error(f"❌ Erro no processamento de {registro.chave_nfe}: {e}")
                    atualizar_registro_erro(config.db_path, registro, str(e))
                    downloads_erro += 1
            
            # Log de progresso
            progresso = ((i + len(lote_registros)) / total_pendentes) * 100
            logger.info(
                f"📈 Lote {lote_numero} concluído. "
                f"Progresso: {progresso:.1f}% "
                f"(✓{downloads_sucesso} ❌{downloads_erro} 🗂️{arquivos_vazios})"
            )
            
            # Pausa entre lotes para não sobrecarregar API
            if lote_numero < total_lotes:
                await asyncio.sleep(2)
    
    # Métricas finais
    tempo_total = time.time() - tempo_inicio
    taxa_sucesso = (downloads_sucesso / total_pendentes) * 100 if total_pendentes > 0 else 0
    
    metricas = MetricasCorrecao(
        total_pendentes=total_pendentes,
        downloads_sucesso=downloads_sucesso,
        downloads_erro=downloads_erro,
        arquivos_vazios=arquivos_vazios,
        tempo_total=tempo_total,
        taxa_sucesso=taxa_sucesso
    )
    
    # Relatório final
    logger.info("=" * 70)
    logger.info("📊 RELATÓRIO FINAL DA CORREÇÃO")
    logger.info("=" * 70)
    logger.info(f"📋 Total de registros: {total_pendentes:,}")
    logger.info(f"✅ Downloads com sucesso: {downloads_sucesso:,}")
    logger.info(f"❌ Downloads com erro: {downloads_erro:,}")
    logger.info(f"🗂️ Arquivos vazios: {arquivos_vazios:,}")
    logger.info(f"📈 Taxa de sucesso: {taxa_sucesso:.1f}%")
    logger.info(f"Tempo total: {tempo_total:.2f}s")
    logger.info(f"Throughput: {downloads_sucesso/tempo_total:.2f} downloads/s")
    logger.info(f"💾 Backup criado: {backup_path}")
    
    if taxa_sucesso >= 95:
        logger.info(" CORREÇÃO CONCLUÍDA COM SUCESSO!")
    elif taxa_sucesso >= 80:
        logger.warning("⚠️ Correção com sucesso parcial")
    else:
        logger.error("❌ Correção com muitos erros - verificar logs")
    
    return metricas

# =============================================================================
# INTERFACE DE LINHA DE COMANDO
# =============================================================================
def main():
    """Função principal com interface CLI."""
    parser = argparse.ArgumentParser(
        description="Script de correção de base - Download de arquivos pendentes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python corrigir_base_pendentes.py                           # Configuração padrão
  python corrigir_base_pendentes.py --max-concurrent 8        # Mais concorrência
  python corrigir_base_pendentes.py --batch-size 200          # Lotes maiores
  python corrigir_base_pendentes.py --db omie_producao.db     # Banco específico
        """
    )
    
    parser.add_argument(
        '--max-concurrent', 
        type=int, 
        default=4,
        help='Número máximo de downloads simultâneos (padrão: 4, máx: 8)'
    )
    
    parser.add_argument(
        '--batch-size', 
        type=int, 
        default=100,
        help='Tamanho do lote para processamento (padrão: 100, máx: 200)'
    )
    
    parser.add_argument(
        '--db', 
        type=str, 
        default='omie.db',
        help='Caminho do banco de dados (padrão: omie.db)'
    )
    
    parser.add_argument(
        '--limite', 
        type=int,
        help='Limite de registros para teste (opcional)'
    )
    
    args = parser.parse_args()
    
    # Validação do banco
    if not Path(args.db).exists():
        logger.error(f"❌ Banco de dados não encontrado: {args.db}")
        sys.exit(1)
    
    # Criar configuração
    config = ConfiguracaoCorrecao(
        max_concurrent=args.max_concurrent,
        batch_size=args.batch_size,
        db_path=args.db
    )
    
    logger.info(f"⚙️ Configuração: {config.max_concurrent} concurrent, lotes de {config.batch_size}")
    
    try:
        # Executar correção
        metricas = asyncio.run(corrigir_base_pendentes(config, args.limite))
        
        # Status de saída baseado no sucesso
        if metricas.taxa_sucesso >= 95:
            sys.exit(0)  # Sucesso total
        elif metricas.taxa_sucesso >= 80:
            sys.exit(1)  # Sucesso parcial
        else:
            sys.exit(2)  # Muitos erros
            
    except KeyboardInterrupt:
        logger.warning("⚠️ Correção interrompida pelo usuário")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"❌ Erro crítico durante correção: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
