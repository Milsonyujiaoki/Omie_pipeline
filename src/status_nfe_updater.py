# status_nfe_updater.py
"""
SISTEMA DE ATUALIZAÇÃO DE STATUS DE NFE - OMIE PIPELINE V3
Consulta e atualiza o status das notas fiscais usando diferentes endpoints da API Omie.
"""

import asyncio
import aiohttp
import sqlite3
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, NamedTuple
from dataclasses import dataclass
import configparser

# Importações do projeto
from src.omie_client_async import OmieClient, carregar_configuracoes_client
from src.utils import conexao_otimizada, respeitar_limite_requisicoes_async

logger = logging.getLogger(__name__)

@dataclass
class EstatisticasStatus:
    """Estatísticas da operação de atualização de status."""
    total_processados: int = 0
    status_atualizados: int = 0
    status_cancelados: int = 0
    status_autorizados: int = 0
    status_rejeitados: int = 0
    status_outros: int = 0
    erros: int = 0
    tempo_execucao_segundos: float = 0.0
    detalhes_erro: List[str] = None
    
    def __post_init__(self):
        if self.detalhes_erro is None:
            self.detalhes_erro = []

class StatusNFeUpdater:
    """
    Sistema para consulta e atualização de status das NFe.
    
    Utiliza diferentes endpoints da API Omie para obter informações
    atualizadas sobre o status das notas fiscais.
    """
    
    def __init__(self, config_path: str = "configuracao.ini"):
        """
        Inicializa o atualizador com configurações.
        
        Args:
            config_path: Caminho para arquivo de configuração
        """
        self.config_path = config_path
        self.config = self._carregar_config()
        
        # Cliente Omie
        config_client = carregar_configuracoes_client()
        self.client = OmieClient(
            app_key=config_client["app_key"],
            app_secret=config_client["app_secret"],
            calls_per_second=config_client.get("calls_per_second", 4),
            base_url_nf=config_client["base_url_nf"],
            base_url_xml=config_client["base_url_xml"]
        )
        
        # Paths
        self.db_path = self.config.get('paths', 'db_path', fallback='omie.db')
        
        # Configurações de execução
        self.max_concurrent = 3  # Limite conservador para evitar rate limit
        self.batch_size = 100    # Tamanho do lote para processamento
        
        # Estatísticas
        self.stats = EstatisticasStatus()
        
    def _carregar_config(self) -> configparser.ConfigParser:
        """Carrega arquivo de configuração."""
        config = configparser.ConfigParser()
        
        # Busca em vários locais possíveis
        locais_possiveis = [
            Path(self.config_path),
            Path(__file__).parent.parent / self.config_path,
            Path.cwd() / self.config_path,
        ]
        
        for local in locais_possiveis:
            if local.exists():
                config.read(local, encoding='utf-8')
                logger.info(f"[STATUS.CONFIG] Configuração carregada: {local}")
                return config
                
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {self.config_path}")
    
    async def consultar_status_nfe_emitidas(
        self, 
        session: aiohttp.ClientSession,
        filtros: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Consulta o endpoint de NFe emitidas para obter status.
        
        Args:
            session: Sessão HTTP ativa
            filtros: Filtros para consulta (data, página, etc.)
            
        Returns:
            Dict com resposta da API ou None em caso de erro
        """
        try:
            async with self.client.semaphore:
                await respeitar_limite_requisicoes_async()
                
                payload = {
                    "app_key": self.client.app_key,
                    "app_secret": self.client.app_secret,
                    "call": "ListarNFesEmitidas",
                    "param": filtros
                }
                
                async with session.post(
                    "https://app.omie.com.br/api/v1/nfe/", 
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    if "faultstring" in data:
                        logger.error(f"[STATUS.API.ERRO] Erro na API: {data['faultstring']}")
                        return None
                    
                    return data
                    
        except asyncio.TimeoutError:
            logger.warning("[STATUS.API.TIMEOUT] Timeout na consulta de status")
            self.stats.erros += 1
            return None
            
        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                logger.warning("[STATUS.API.RATE_LIMIT] Rate limit atingido")
                await asyncio.sleep(2)  # Espera antes de continuar
            else:
                logger.error(f"[STATUS.API.HTTP] Erro HTTP {e.status}: {e}")
            self.stats.erros += 1
            return None
            
        except Exception as e:
            logger.error(f"[STATUS.API.ERRO] Erro inesperado: {e}")
            self.stats.erros += 1
            self.stats.detalhes_erro.append(f"Erro API: {e}")
            return None
    
    async def consultar_status_nfe_individual(
        self,
        session: aiohttp.ClientSession,
        chave_nfe: str,
        nid_nf: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Consulta status individual de uma NFe usando ObterNfe.
        
        Args:
            session: Sessão HTTP ativa
            chave_nfe: Chave da nota fiscal
            nid_nf: ID interno Omie (opcional, preferencial)
            
        Returns:
            Dict com dados da NFe ou None em caso de erro
        """
        try:
            async with self.client.semaphore:
                await respeitar_limite_requisicoes_async()
                
                # Prioriza nIdNF se disponível, senão usa chave
                if nid_nf:
                    filtro = {"nIdNF": nid_nf}
                else:
                    filtro = {"cChaveNFe": chave_nfe}
                
                payload = {
                    "app_key": self.client.app_key,
                    "app_secret": self.client.app_secret,
                    "call": "ObterNfe",
                    "param": [filtro]
                }
                
                async with session.post(
                    self.client.base_url_nf,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    if "faultstring" in data:
                        if "não encontrado" in data['faultstring'].lower():
                            logger.debug(f"[STATUS.INDIVIDUAL] NFe não encontrada: {chave_nfe[:20]}...")
                            return None
                        logger.error(f"[STATUS.INDIVIDUAL.ERRO] {data['faultstring']}")
                        return None
                    
                    return data
                    
        except Exception as e:
            logger.debug(f"[STATUS.INDIVIDUAL.ERRO] Erro para {chave_nfe[:20]}...: {e}")
            return None
    
    def extrair_status_nfe(self, dados_nfe: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """
        Extrai status da NFe dos dados retornados pela API.
        
        Args:
            dados_nfe: Dados da NFe retornados pela API
            
        Returns:
            Tupla (status, detalhes_extras)
        """
        detalhes = {}
        
        # Tenta extrair status de diferentes campos possíveis
        status_possivel = None
        
        # Campo 'situacao' (mais comum)
        if "situacao" in dados_nfe:
            status_possivel = dados_nfe["situacao"]
            detalhes["situacao_original"] = status_possivel
        
        # Campo 'cSitNFe' (código de situação)
        if "cSitNFe" in dados_nfe:
            detalhes["codigo_situacao"] = dados_nfe["cSitNFe"]
            
        # Campo 'xMotivo' (motivo/descrição)
        if "xMotivo" in dados_nfe:
            detalhes["motivo"] = dados_nfe["xMotivo"]
            if not status_possivel:
                status_possivel = dados_nfe["xMotivo"]
        
        # Campo 'tpNF' (tipo de NFe)
        if "tpNF" in dados_nfe:
            detalhes["tipo_nf"] = dados_nfe["tpNF"]
            
        # Campo 'tpAmb' (ambiente)
        if "tpAmb" in dados_nfe:
            detalhes["ambiente"] = dados_nfe["tpAmb"]
            
        # Normaliza status
        if status_possivel:
            status_normalizado = self._normalizar_status(status_possivel)
        else:
            status_normalizado = "INDEFINIDO"
            
        return status_normalizado, detalhes
    
    def _normalizar_status(self, status_raw: str) -> str:
        """
        Normaliza o status da NFe para formato padronizado.
        
        Args:
            status_raw: Status bruto da API
            
        Returns:
            Status normalizado
        """
        if not status_raw:
            return "INDEFINIDO"
            
        status_lower = status_raw.lower().strip()
        
        # Mapeamento de status conhecidos
        mapeamentos = {
            "cancelada": "CANCELADA",
            "cancelled": "CANCELADA", 
            "autorizada": "AUTORIZADA",
            "authorized": "AUTORIZADA",
            "rejeitada": "REJEITADA",
            "rejected": "REJEITADA",
            "denegada": "DENEGADA",
            "denied": "DENEGADA",
            "inutilizada": "INUTILIZADA",
            "inutilized": "INUTILIZADA",
            "processando": "PROCESSANDO",
            "processing": "PROCESSANDO",
            "pendente": "PENDENTE",
            "pending": "PENDENTE",
        }
        
        # Busca por correspondência parcial
        for palavra_chave, status_norm in mapeamentos.items():
            if palavra_chave in status_lower:
                return status_norm
                
        # Se não encontrou correspondência, retorna original em maiúsculo
        return status_raw.upper()
    
    def is_cancelada(self, status: str, detalhes: Dict[str, Any] = None) -> bool:
        """
        Verifica se a nota está cancelada.
        
        Args:
            status: Status normalizado
            detalhes: Detalhes adicionais (opcional)
            
        Returns:
            True se a nota estiver cancelada
        """
        return status in ["CANCELADA", "INUTILIZADA"]
    
    async def obter_notas_para_atualizacao(self, limite: int = 1000) -> List[Tuple[str, Optional[int]]]:
        """
        Obtém lista de notas que precisam de atualização de status.
        
        Args:
            limite: Máximo de notas para processar por execução
            
        Returns:
            Lista de tuplas (chave_nfe, nid_nf)
        """
        try:
            with conexao_otimizada(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Busca notas sem status ou com status indefinido
                # Prioriza notas mais recentes
                cursor.execute("""
                    SELECT cChaveNFe, nIdNF 
                    FROM notas 
                    WHERE (status IS NULL OR status = 'INDEFINIDO' OR status = '')
                      AND xml_baixado = 1  -- Apenas notas já processadas
                      AND erro = 0         -- Sem erros
                    ORDER BY dEmi DESC
                    LIMIT ?
                """, (limite,))
                
                resultados = cursor.fetchall()
                
                logger.info(f"[STATUS.CONSULTA] {len(resultados)} notas encontradas para atualização")
                
                return [(row[0], row[1]) for row in resultados]
                
        except Exception as e:
            logger.error(f"[STATUS.CONSULTA.ERRO] Erro ao consultar notas: {e}")
            return []
    
    async def atualizar_status_banco(
        self,
        chave_nfe: str,
        status: str,
        detalhes: Dict[str, Any] = None
    ) -> bool:
        """
        Atualiza o status da NFe no banco de dados.
        
        Args:
            chave_nfe: Chave da nota fiscal
            status: Status normalizado
            detalhes: Detalhes adicionais (opcional)
            
        Returns:
            True se atualizado com sucesso
        """
        try:
            with conexao_otimizada(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Monta dados para atualização
                dados_atualizacao = {
                    "status": status,
                    "data_status_update": datetime.now().isoformat()
                }
                
                # Adiciona detalhes se disponíveis
                if detalhes:
                    if "motivo" in detalhes:
                        dados_atualizacao["status_motivo"] = detalhes["motivo"][:500]  # Limita tamanho
                    if "codigo_situacao" in detalhes:
                        dados_atualizacao["codigo_situacao"] = detalhes["codigo_situacao"]
                
                # SQL de atualização
                sql = """
                    UPDATE notas 
                    SET status = ?, 
                        mensagem_erro = CASE 
                            WHEN ? != 'AUTORIZADA' AND ? IS NOT NULL 
                            THEN ? 
                            ELSE mensagem_erro 
                        END
                    WHERE cChaveNFe = ?
                """
                
                motivo = detalhes.get("motivo") if detalhes else None
                cursor.execute(sql, (
                    status,
                    status, motivo, motivo,
                    chave_nfe
                ))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    logger.debug(f"[STATUS.UPDATE] Atualizado: {chave_nfe[:20]}... -> {status}")
                    return True
                else:
                    logger.warning(f"[STATUS.UPDATE] Nenhum registro encontrado para {chave_nfe[:20]}...")
                    return False
                    
        except Exception as e:
            logger.error(f"[STATUS.UPDATE.ERRO] Erro ao atualizar {chave_nfe[:20]}...: {e}")
            return False
    
    async def processar_lote_status(
        self,
        session: aiohttp.ClientSession,
        notas: List[Tuple[str, Optional[int]]]
    ) -> None:
        """
        Processa um lote de notas para atualização de status.
        
        Args:
            session: Sessão HTTP ativa
            notas: Lista de tuplas (chave_nfe, nid_nf)
        """
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def processar_nota(chave_nfe: str, nid_nf: Optional[int]):
            async with semaphore:
                try:
                    # Consulta status individual
                    dados_nfe = await self.consultar_status_nfe_individual(
                        session, chave_nfe, nid_nf
                    )
                    
                    self.stats.total_processados += 1
                    
                    if dados_nfe:
                        status, detalhes = self.extrair_status_nfe(dados_nfe)
                        
                        # Atualiza no banco
                        sucesso = await self.atualizar_status_banco(chave_nfe, status, detalhes)
                        
                        if sucesso:
                            self.stats.status_atualizados += 1
                            
                            # Estatísticas por tipo
                            if status == "CANCELADA":
                                self.stats.status_cancelados += 1
                            elif status == "AUTORIZADA":
                                self.stats.status_autorizados += 1
                            elif status == "REJEITADA":
                                self.stats.status_rejeitados += 1
                            else:
                                self.stats.status_outros += 1
                    
                except Exception as e:
                    logger.debug(f"[STATUS.LOTE.ERRO] Erro ao processar {chave_nfe[:20]}...: {e}")
                    self.stats.erros += 1
        
        # Executa processamento paralelo do lote
        await asyncio.gather(*[
            processar_nota(chave, nid) for chave, nid in notas
        ])
    
    async def executar_atualizacao_status(
        self,
        limite_notas: int = 1000,
        modo_dry_run: bool = False
    ) -> EstatisticasStatus:
        """
        Executa atualização completa de status das NFe.
        
        Args:
            limite_notas: Máximo de notas para processar
            modo_dry_run: Se True, apenas simula sem atualizar
            
        Returns:
            EstatisticasStatus: Estatísticas da operação
        """
        tempo_inicio = time.time()
        
        logger.info(f"[STATUS] {'🧪 SIMULAÇÃO' if modo_dry_run else '🔄 EXECUÇÃO'} - "
                   f"Atualização de status de NFe iniciada")
        logger.info(f"[STATUS] Limite de processamento: {limite_notas:,} notas")
        
        try:
            # Obtém notas para atualização
            notas_pendentes = await self.obter_notas_para_atualizacao(limite_notas)
            
            if not notas_pendentes:
                logger.info("[STATUS] ✅ Nenhuma nota pendente de atualização de status")
                self.stats.tempo_execucao_segundos = time.time() - tempo_inicio
                return self.stats
            
            logger.info(f"[STATUS] Processando {len(notas_pendentes)} notas...")
            
            # Processa em lotes
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=300, connect=30)
            ) as session:
                
                for i in range(0, len(notas_pendentes), self.batch_size):
                    lote = notas_pendentes[i:i + self.batch_size]
                    lote_num = (i // self.batch_size) + 1
                    total_lotes = (len(notas_pendentes) + self.batch_size - 1) // self.batch_size
                    
                    logger.info(f"[STATUS.LOTE] Processando lote {lote_num}/{total_lotes} "
                               f"({len(lote)} notas)")
                    
                    if not modo_dry_run:
                        await self.processar_lote_status(session, lote)
                    else:
                        # Simulação
                        self.stats.total_processados += len(lote)
                        self.stats.status_atualizados += len(lote)
                        self.stats.status_autorizados += int(len(lote) * 0.7)  # Simula 70% autorizadas
                        self.stats.status_cancelados += int(len(lote) * 0.1)   # Simula 10% canceladas
                        self.stats.status_outros += len(lote) - self.stats.status_autorizados - self.stats.status_cancelados
                    
                    # Pequena pausa entre lotes
                    if not modo_dry_run:
                        await asyncio.sleep(1)
            
            # Estatísticas finais
            self.stats.tempo_execucao_segundos = time.time() - tempo_inicio
            
            logger.info(f"[STATUS] {'🧪 SIMULAÇÃO' if modo_dry_run else '✅ ATUALIZAÇÃO'} concluída:")
            logger.info(f"  • Notas processadas: {self.stats.total_processados}")
            logger.info(f"  • Status atualizados: {self.stats.status_atualizados}")
            logger.info(f"  • Autorizadas: {self.stats.status_autorizados}")
            logger.info(f"  • Canceladas: {self.stats.status_cancelados}")
            logger.info(f"  • Rejeitadas: {self.stats.status_rejeitados}")
            logger.info(f"  • Outros: {self.stats.status_outros}")
            logger.info(f"  • Erros: {self.stats.erros}")
            logger.info(f"  • Tempo execução: {self.stats.tempo_execucao_segundos:.2f}s")
            
            if self.stats.detalhes_erro:
                logger.warning(f"  • Primeiros 5 erros:")
                for erro in self.stats.detalhes_erro[:5]:
                    logger.warning(f"    - {erro}")
            
        except Exception as e:
            erro = f"Erro crítico na atualização de status: {e}"
            self.stats.detalhes_erro.append(erro)
            logger.error(f"[STATUS] {erro}")
        
        return self.stats


# Função de conveniência para uso externo
async def executar_atualizacao_status_nfe(
    config_path: str = "configuracao.ini",
    limite_notas: int = 1000000,
    dry_run: bool = False
) -> bool:
    """
    Função de conveniência para executar atualização de status.
    
    Args:
        config_path: Caminho para arquivo de configuração
        limite_notas: Máximo de notas para processar
        dry_run: Se True, apenas simula sem atualizar
        
    Returns:
        bool: True se executou com sucesso
    """
    try:
        updater = StatusNFeUpdater(config_path)
        stats = await updater.executar_atualizacao_status(limite_notas, dry_run)
        
        # Considera sucesso se procesou sem erros críticos
        return stats.erros < (stats.total_processados * 0.1)  # Menos de 10% de erros
        
    except Exception as e:
        logger.error(f"[STATUS] Erro ao executar atualização: {e}")
        return False


# Função síncrona para compatibilidade
def executar_atualizacao_status_nfe_sync(
    config_path: str = "configuracao.ini",
    limite_notas: int = 1000000,
    dry_run: bool = False
) -> bool:
    """Versão síncrona da função de atualização."""
    return asyncio.run(executar_atualizacao_status_nfe(config_path, limite_notas, dry_run))


if __name__ == "__main__":
    # Teste do sistema de atualização de status
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Parâmetros da linha de comando
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    limite = 100 if "--test" in sys.argv else 10000000
    
    print("🔄 Sistema de Atualização de Status NFe")
    print("=" * 50)
    
    # Executa atualização
    sucesso = executar_atualizacao_status_nfe_sync(dry_run=dry_run, limite_notas=limite)
    
    if sucesso:
        print(f"\n✅ {'Simulação' if dry_run else 'Atualização'} executada com sucesso!")
        if dry_run:
            print("💡 Para executar efetivamente, rode sem --dry-run")
    else:
        print(f"\n❌ {'Simulação' if dry_run else 'Atualização'} falhou!")
        sys.exit(1)
