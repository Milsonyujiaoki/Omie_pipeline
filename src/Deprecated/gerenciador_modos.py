#!/usr/bin/env python3
"""
🎯 SISTEMA DE MODOS DE EXECUÇÃO - EXTRATOR OMIE V3 REFATORADO
=============================================================

Sistema unificado para coordenar diferentes modos de execução do pipeline,
eliminando conflitos e redundâncias entre fluxos normais, específicos e reprocessamento.

Modos de Execução:
- NORMAL: Pipeline completo padrão (listagem + download + processamento)
- REPROCESSAMENTO: Reprocessamento de registros inválidos
- PENDENTES_GERAL: Download de todos os registros pendentes
- MANUTENCAO: Modo de manutenção e correção

Arquitetura:
- Detecção automática do modo baseado em configurações e estado do banco
- Configuração específica por modo para otimizar performance
- Evita conflitos entre execuções simultâneas
- Logging estruturado por modo
- Recovery automático de configurações temporárias
"""

import configparser
import json
import logging
import os
import sqlite3
import time
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class ModoExecucao(Enum):
    """Modos de execução disponíveis no sistema"""
    NORMAL = "normal"                    # Pipeline completo padrão
    REPROCESSAMENTO = "reprocessamento"  # Reprocessamento de registros inválidos
    PENDENTES_GERAL = "pendentes_geral"  # Download de todos os pendentes
    MANUTENCAO = "manutencao"           # Modo de manutenção e correção

@dataclass
class ConfiguracaoExecucao:
    """Configuração específica para cada modo de execução"""
    modo: ModoExecucao
    estrategia: str = "auto"
    dias_filtrar: Optional[List[str]] = None
    filtros: Optional[Dict[str, Any]] = None
    base_dir: str = "resultado"
    max_concurrent: int = 5
    incluir_listagem: bool = True
    incluir_download: bool = True
    incluir_verificacao: bool = True
    incluir_compactacao: bool = True
    incluir_upload: bool = True

class GerenciadorModos:
    """Gerenciador central dos modos de execução"""
    
    def __init__(self, config_path: str = "configuracao.ini"):
        self.config_path = config_path
        self.config = self._carregar_configuracao()
        self.modo_atual = self._detectar_modo()
        self.configuracao_execucao = self._gerar_configuracao_execucao()
    
    def _carregar_configuracao(self) -> configparser.ConfigParser:
        """Carrega configuração do arquivo INI"""
        config = configparser.ConfigParser()
        config.read(self.config_path, encoding='utf-8')
        return config
    
    def _detectar_modo(self) -> ModoExecucao:
        """Detecta automaticamente o modo de execução baseado na configuração"""
        
        # 1. Verifica se há registros inválidos pendentes
        if self._verificar_registros_invalidos():
            logger.info("[MODO] Detectado modo REPROCESSAMENTO: registros inválidos encontrados")
            return ModoExecucao.REPROCESSAMENTO
        
        # 2. Verifica se há muitos registros pendentes
        pendentes_count = self._contar_registros_pendentes()
        if pendentes_count > 1000:  # Threshold configurável
            logger.info(f"[MODO] Detectado modo PENDENTES_GERAL: {pendentes_count:,} registros pendentes")
            return ModoExecucao.PENDENTES_GERAL
        
        # 4. Modo normal (padrão)
        logger.info("[MODO] Usando modo NORMAL: pipeline padrão")
        return ModoExecucao.NORMAL
    
    def _verificar_registros_invalidos(self) -> bool:
        """Verifica se existem registros inválidos no banco"""
        try:
            with sqlite3.connect("omie.db") as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM notas 
                    WHERE (cChaveNFe IS NULL OR TRIM(cChaveNFe) = '' 
                           OR dEmi IS NULL OR TRIM(dEmi) = '' 
                           OR nNF IS NULL OR TRIM(nNF) = '')
                    AND xml_baixado = 0
                """)
                count = cursor.fetchone()[0]
                return count > 0
        except Exception as e:
            logger.warning(f"[MODO] Erro ao verificar registros inválidos: {e}")
            return False
    
    def _contar_registros_pendentes(self) -> int:
        """Conta registros pendentes no banco"""
        try:
            with sqlite3.connect("omie.db") as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 0")
                return cursor.fetchone()[0]
        except Exception as e:
            logger.warning(f"[MODO] Erro ao contar registros pendentes: {e}")
            return 0
    
    def _gerar_configuracao_execucao(self) -> ConfiguracaoExecucao:
        """Gera configuração específica baseada no modo detectado"""
        
        if self.modo_atual == ModoExecucao.REPROCESSAMENTO:
            return ConfiguracaoExecucao(
                modo=ModoExecucao.REPROCESSAMENTO,
                estrategia="filtro_registros_invalidos",
                filtros={"apenas_invalidos": True},
                base_dir="resultado_reprocessamento",
                max_concurrent=5,
                incluir_listagem=False,  # Não lista, só baixa
                incluir_download=True,
                incluir_verificacao=True,
                incluir_compactacao=False,
                incluir_upload=False
            )
        
        elif self.modo_atual == ModoExecucao.PENDENTES_GERAL:
            return ConfiguracaoExecucao(
                modo=ModoExecucao.PENDENTES_GERAL,
                estrategia="todos_pendentes",
                filtros={"apenas_pendentes": True},
                base_dir="resultado",
                max_concurrent=8,  # Balanceado para muitos registros
                incluir_listagem=False,  # Só baixa pendentes
                incluir_download=True,
                incluir_verificacao=True,
                incluir_compactacao=True,
                incluir_upload=True
            )
        
        else:  # NORMAL
            return ConfiguracaoExecucao(
                modo=ModoExecucao.NORMAL,
                estrategia="pipeline_completo",
                filtros=None,
                base_dir="resultado",
                max_concurrent=5,
                incluir_listagem=True,
                incluir_download=True,
                incluir_verificacao=True,
                incluir_compactacao=True,
                incluir_upload=True
            )
    
    def detectar_modo_execucao(self) -> ConfiguracaoExecucao:
        """
        Detecta o modo de execução e retorna a configuração apropriada.
        
        Returns:
            ConfiguracaoExecucao: Configuração específica para o modo detectado
        """
        # O modo já foi detectado no __init__, retorna a configuração
        return self.configuracao_execucao
    
    def obter_filtros_registros(self) -> Dict[str, Any]:
        """Retorna filtros para busca de registros baseado no modo"""
        
        if self.modo_atual == ModoExecucao.REPROCESSAMENTO:
            return {
                "apenas_invalidos": True,
                "apenas_pendentes": True
            }
        
        elif self.modo_atual == ModoExecucao.PENDENTES_GERAL:
            return {
                "apenas_pendentes": True
            }
        
        else:  # NORMAL
            return {
                "periodo_configurado": True
            }
    
    def deve_executar_fase(self, fase: str) -> bool:
        """Verifica se uma fase deve ser executada no modo atual"""
        fase_mapping = {
            "listagem": self.configuracao_execucao.incluir_listagem,
            "download": self.configuracao_execucao.incluir_download,
            "verificacao": self.configuracao_execucao.incluir_verificacao,
            "compactacao": self.configuracao_execucao.incluir_compactacao,
            "upload": self.configuracao_execucao.incluir_upload
        }
        
        return fase_mapping.get(fase, True)
    
    def gerar_relatorio_modo(self) -> str:
        """Gera relatório do modo de execução atual"""
        relatorio = [
            f"🎯 MODO DE EXECUÇÃO: {self.modo_atual.value.upper()}",
            f"📂 Diretório: {self.configuracao_execucao.base_dir}",
            f"⚡ Concorrência: {self.configuracao_execucao.max_concurrent}",
            f"📊 Estratégia: {self.configuracao_execucao.estrategia}",
        ]
        
        if self.configuracao_execucao.filtros:
            relatorio.append(f" Filtros: {self.configuracao_execucao.filtros}")
        
        # Fases habilitadas
        fases_habilitadas = []
        if self.configuracao_execucao.incluir_listagem:
            fases_habilitadas.append("Listagem")
        if self.configuracao_execucao.incluir_download:
            fases_habilitadas.append("Download")
        if self.configuracao_execucao.incluir_verificacao:
            fases_habilitadas.append("Verificação")
        if self.configuracao_execucao.incluir_compactacao:
            fases_habilitadas.append("Compactação")
        if self.configuracao_execucao.incluir_upload:
            fases_habilitadas.append("Upload")
        
        relatorio.append(f"✅ Fases habilitadas: {', '.join(fases_habilitadas)}")
        
        return "\n".join(relatorio)


async def executar_com_gerenciamento_modo(
    configuracao_execucao: ConfiguracaoExecucao,
    config: Dict[str, Any],
    db_path: str,
    resultado_dir: str
) -> bool:
    """
    Executa pipeline com base na configuração do modo detectado.
    
    Args:
        configuracao_execucao: Configuração específica do modo
        config: Configurações gerais do sistema
        db_path: Caminho do banco SQLite
        resultado_dir: Diretório de resultados
        
    Returns:
        True se execução foi bem-sucedida
    """
    try:
        # Importa módulos necessários
        from .omie_client_async import OmieClient
        from .extrator_async import baixar_xmls, main as extrator_main
        
        # Cria cliente Omie com credenciais do config
        app_key = config.get('app_key', '')
        app_secret = config.get('app_secret', '')
        
        if not app_key or not app_secret:
            raise ValueError("Credenciais app_key e app_secret não encontradas na configuração")
        
        client = OmieClient(app_key, app_secret)
        
        if configuracao_execucao.modo == ModoExecucao.NORMAL:
            # Modo normal: executa pipeline completo
            logger.info("[EXECUÇÃO] Modo NORMAL: pipeline completo")
            await extrator_main()
            
        elif configuracao_execucao.modo == ModoExecucao.PENDENTES_GERAL:
            # Modo pendentes gerais: download de todos os pendentes
            logger.info("[EXECUÇÃO] Modo PENDENTES_GERAL: todos os pendentes")
            
            await baixar_xmls(
                client=client,
                config=config,
                db_name=db_path,
                max_concurrent=configuracao_execucao.max_concurrent,
                base_dir=resultado_dir
            )
            
        elif configuracao_execucao.modo == ModoExecucao.REPROCESSAMENTO:
            # Modo reprocessamento: registros inválidos
            logger.info("[EXECUÇÃO] Modo REPROCESSAMENTO: registros inválidos")
            
            filtros = {
                "apenas_invalidos": True
            }
            
            await baixar_xmls(
                client=client,
                config=config,
                db_name=db_path,
                max_concurrent=configuracao_execucao.max_concurrent,
                base_dir=resultado_dir,
                filtros=filtros
            )
            
        else:
            logger.error(f"[EXECUÇÃO] Modo não suportado: {configuracao_execucao.modo}")
            return False
            
        logger.info(f"[EXECUÇÃO] ✓ Modo {configuracao_execucao.modo.value} executado com sucesso")
        return True
        
    except Exception as e:
        logger.exception(f"[EXECUÇÃO] Erro ao executar modo {configuracao_execucao.modo.value}: {e}")
        return False


if __name__ == "__main__":
    """Teste do gerenciador de modos"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    gerenciador = GerenciadorModos()
    config = gerenciador.detectar_modo_execucao()
    
    print(f"Modo detectado: {config.modo.value}")
    print(f"Estratégia: {config.estrategia}")
    print(f"Filtros: {config.filtros}")
