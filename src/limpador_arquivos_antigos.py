"""
SISTEMA DE LIMPEZA DE ARQUIVOS ANTIGOS - OMIE PIPELINE V3
Mantém apenas os últimos N meses de dados para economia de espaço.
"""

import sqlite3
import logging
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import configparser
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class EstatisticasLimpeza:
    """Estatísticas da limpeza executada."""
    diretorios_verificados: int = 0
    diretorios_removidos: int = 0
    arquivos_xml_removidos: int = 0
    arquivos_zip_removidos: int = 0
    espaco_liberado_bytes: int = 0
    registros_atualizados_db: int = 0
    tempo_execucao_segundos: float = 0.0
    erros: List[str] = None
    
    def __post_init__(self):
        if self.erros is None:
            self.erros = []

class LimpadorArquivosAntigos:
    """
    Sistema para limpeza automática de arquivos antigos baseado em configuração.
    """
    
    def __init__(self, config_path: str = "configuracao.ini"):
        """
        Inicializa o limpador com configurações.
        
        Args:
            config_path: Caminho para arquivo de configuração
        """
        self.config_path = config_path
        self.config = self._carregar_config()
        
        # Configurações de limpeza
        self.manter_meses = self.config.getint('manutencao', 'manter_ultimos_meses', fallback=2)
        self.limpeza_ativa = self.config.getboolean('manutencao', 'limpeza_automatica', fallback=False)
        self.backup_antes_remover = self.config.getboolean('manutencao', 'backup_antes_remover', fallback=True)
        self.comprimir_antigos = self.config.getboolean('manutencao', 'comprimir_arquivos_antigos', fallback=False)
        
        # Paths
        self.resultado_dir = Path(self.config.get('paths', 'resultado_dir', fallback='resultado'))
        self.db_path = self.config.get('paths', 'db_path', fallback='omie.db')
        self.backup_dir = Path(self.config.get('paths', 'backup_dir', fallback='backup'))
        
        # Estatísticas
        self.stats = EstatisticasLimpeza()
        
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
                logger.info(f"[LIMPEZA.CONFIG] Configuração carregada: {local}")
                return config
                
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {self.config_path}")
    
    def calcular_data_limite(self) -> datetime:
        """
        Calcula a data limite para manter arquivos.
        
        Returns:
            datetime: Data limite (arquivos mais antigos serão removidos)
        """
        hoje = datetime.now()
        # Calcula N meses atrás
        if hoje.month > self.manter_meses:
            mes_limite = hoje.month - self.manter_meses
            ano_limite = hoje.year
        else:
            mes_limite = 12 - (self.manter_meses - hoje.month)
            ano_limite = hoje.year - 1
        
        data_limite = datetime(ano_limite, mes_limite, 1)
        logger.info(f"[LIMPEZA] Data limite calculada: {data_limite.strftime('%Y-%m-%d')} "
                   f"(manter últimos {self.manter_meses} meses)")
        
        return data_limite
    
    def identificar_diretorios_antigos(self) -> List[Path]:
        """
        Identifica diretórios mais antigos que a data limite.
        
        Returns:
            List[Path]: Lista de diretórios para remoção
        """
        if not self.resultado_dir.exists():
            logger.warning(f"[LIMPEZA] Diretório resultado não encontrado: {self.resultado_dir}")
            return []
        
        data_limite = self.calcular_data_limite()
        diretorios_antigos = []
        
        logger.info(f"[LIMPEZA] Buscando diretórios antigos em: {self.resultado_dir}")
        
        # Busca estrutura hierárquica: ano/mes/dia
        try:
            for ano_dir in self.resultado_dir.iterdir():
                if not ano_dir.is_dir() or not ano_dir.name.isdigit():
                    continue
                    
                ano = int(ano_dir.name)
                self.stats.diretorios_verificados += 1
                
                for mes_dir in ano_dir.iterdir():
                    if not mes_dir.is_dir() or not mes_dir.name.isdigit():
                        continue
                        
                    mes = int(mes_dir.name)
                    self.stats.diretorios_verificados += 1
                    
                    # Compara com data limite
                    data_diretorio = datetime(ano, mes, 1)
                    
                    if data_diretorio < data_limite:
                        # Todo o mês é antigo, adiciona todos os dias
                        for dia_dir in mes_dir.iterdir():
                            if dia_dir.is_dir():
                                diretorios_antigos.append(dia_dir)
                                self.stats.diretorios_verificados += 1
                        logger.debug(f"[LIMPEZA] Mês antigo identificado: {ano}/{mes}")
                    else:
                        # Mês atual, verifica dias individualmente
                        for dia_dir in mes_dir.iterdir():
                            if not dia_dir.is_dir() or not dia_dir.name.isdigit():
                                continue
                                
                            dia = int(dia_dir.name)
                            self.stats.diretorios_verificados += 1
                            
                            try:
                                data_dia = datetime(ano, mes, dia)
                                if data_dia < data_limite:
                                    diretorios_antigos.append(dia_dir)
                                    logger.debug(f"[LIMPEZA] Dia antigo: {ano}/{mes}/{dia}")
                            except ValueError:
                                # Data inválida, pula
                                logger.debug(f"[LIMPEZA] Data inválida ignorada: {ano}/{mes}/{dia}")
                                continue
                                
        except Exception as e:
            self.stats.erros.append(f"Erro ao buscar diretórios antigos: {e}")
            logger.error(f"[LIMPEZA] Erro na busca: {e}")
        
        logger.info(f"[LIMPEZA] {len(diretorios_antigos)} diretórios antigos identificados "
                   f"de {self.stats.diretorios_verificados} verificados")
        
        return diretorios_antigos
    
    def calcular_espaco_diretorio(self, diretorio: Path) -> int:
        """
        Calcula o espaço ocupado por um diretório.
        
        Args:
            diretorio: Path do diretório
            
        Returns:
            int: Tamanho em bytes
        """
        tamanho_total = 0
        try:
            for arquivo in diretorio.rglob('*'):
                if arquivo.is_file():
                    tamanho_total += arquivo.stat().st_size
        except Exception as e:
            logger.debug(f"[LIMPEZA] Erro ao calcular tamanho de {diretorio}: {e}")
        
        return tamanho_total
    
    def fazer_backup_diretorio(self, diretorio: Path) -> Optional[Path]:
        """
        Faz backup de um diretório antes da remoção.
        
        Args:
            diretorio: Diretório a ser copiado
            
        Returns:
            Optional[Path]: Caminho do backup criado ou None se falhou
        """
        if not self.backup_antes_remover:
            return None
        
        try:
            # Cria estrutura de backup
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Nome do backup com timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            nome_backup = f"{diretorio.name}_{timestamp}"
            
            # Path relativo do diretório original (preserva estrutura)
            path_relativo = diretorio.relative_to(self.resultado_dir)
            backup_path = self.backup_dir / 'arquivos_antigos' / path_relativo.parent / nome_backup
            
            # Copia diretório
            shutil.copytree(diretorio, backup_path, dirs_exist_ok=True)
            
            logger.debug(f"[LIMPEZA.BACKUP] Backup criado: {backup_path}")
            return backup_path
            
        except Exception as e:
            erro = f"Erro ao fazer backup de {diretorio}: {e}"
            self.stats.erros.append(erro)
            logger.error(f"[LIMPEZA.BACKUP] {erro}")
            return None
    
    def remover_diretorio_seguro(self, diretorio: Path) -> bool:
        """
        Remove um diretório de forma segura.
        
        Args:
            diretorio: Diretório a ser removido
            
        Returns:
            bool: True se removido com sucesso
        """
        try:
            # Calcula espaço antes da remoção
            tamanho = self.calcular_espaco_diretorio(diretorio)
            
            # Conta arquivos por tipo
            xmls = list(diretorio.rglob('*.xml'))
            zips = list(diretorio.rglob('*.zip'))
            
            # Faz backup se configurado
            if self.backup_antes_remover:
                backup_path = self.fazer_backup_diretorio(diretorio)
                if backup_path is None:
                    logger.warning(f"[LIMPEZA] Pulando remoção de {diretorio} (falha no backup)")
                    return False
            
            # Remove diretório
            shutil.rmtree(diretorio)
            
            # Atualiza estatísticas
            self.stats.diretorios_removidos += 1
            self.stats.arquivos_xml_removidos += len(xmls)
            self.stats.arquivos_zip_removidos += len(zips)
            self.stats.espaco_liberado_bytes += tamanho
            
            logger.info(f"[LIMPEZA] Removido: {diretorio.name} "
                       f"({len(xmls)} XMLs, {len(zips)} ZIPs, {tamanho/1024/1024:.1f} MB)")
            
            return True
            
        except Exception as e:
            erro = f"Erro ao remover {diretorio}: {e}"
            self.stats.erros.append(erro)
            logger.error(f"[LIMPEZA] {erro}")
            return False
    
    def atualizar_banco_dados(self, diretorios_removidos: List[Path]) -> None:
        """
        Atualiza banco de dados marcando registros de diretórios removidos.
        
        Args:
            diretorios_removidos: Lista de diretórios que foram removidos
        """
        if not diretorios_removidos:
            return
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                registros_atualizados = 0
                
                for diretorio in diretorios_removidos:
                    try:
                        # Extrai ano/mes/dia do path
                        partes = diretorio.parts
                        if len(partes) >= 3:
                            ano, mes, dia = partes[-3], partes[-2], partes[-1]
                            
                            # Constrói padrão da data para busca no banco
                            data_padrao = f"{ano}-{mes.zfill(2)}-{dia.zfill(2)}"
                            
                            # Atualiza registros que correspondem a esta data
                            cursor.execute("""
                                UPDATE notas 
                                SET xml_baixado = 0, 
                                    caminho_arquivo = NULL,
                                    observacoes = COALESCE(observacoes, '') || 
                                                  CASE WHEN COALESCE(observacoes, '') = '' 
                                                       THEN 'Arquivo removido por limpeza automática' 
                                                       ELSE '; Arquivo removido por limpeza automática' 
                                                  END
                                WHERE dEmi LIKE ? 
                                   OR caminho_arquivo LIKE ?
                            """, (f"{data_padrao}%", f"%{ano}/{mes}/{dia}%"))
                            
                            rows_affected = cursor.rowcount
                            if rows_affected > 0:
                                registros_atualizados += rows_affected
                                logger.debug(f"[LIMPEZA.DB] {rows_affected} registros atualizados para {data_padrao}")
                                
                    except Exception as e:
                        erro = f"Erro ao atualizar registros para {diretorio}: {e}"
                        self.stats.erros.append(erro)
                        logger.error(f"[LIMPEZA.DB] {erro}")
                
                conn.commit()
                self.stats.registros_atualizados_db = registros_atualizados
                
                logger.info(f"[LIMPEZA.DB] {registros_atualizados} registros marcados para re-download")
                
        except Exception as e:
            erro = f"Erro ao atualizar banco de dados: {e}"
            self.stats.erros.append(erro)
            logger.error(f"[LIMPEZA.DB] {erro}")
    
    def executar_limpeza(self, modo_dry_run: bool = False) -> EstatisticasLimpeza:
        """
        Executa a limpeza de arquivos antigos.
        
        Args:
            modo_dry_run: Se True, apenas simula a limpeza sem remover arquivos
            
        Returns:
            EstatisticasLimpeza: Estatísticas da operação
        """
        tempo_inicio = time.time()
        
        logger.info(f"[LIMPEZA] {'🧪 SIMULAÇÃO' if modo_dry_run else '🧹 EXECUÇÃO'} - "
                   f"Limpeza de arquivos antigos iniciada")
        logger.info(f"[LIMPEZA] Manter últimos {self.manter_meses} meses")
        
        try:
            # Identifica diretórios antigos
            diretorios_antigos = self.identificar_diretorios_antigos()
            
            if not diretorios_antigos:
                logger.info("[LIMPEZA] ✅ Nenhum diretório antigo encontrado")
                self.stats.tempo_execucao_segundos = time.time() - tempo_inicio
                return self.stats
            
            diretorios_removidos = []
            
            # Processa cada diretório
            for i, diretorio in enumerate(diretorios_antigos, 1):
                logger.info(f"[LIMPEZA] Processando {i}/{len(diretorios_antigos)}: {diretorio.name}")
                
                if modo_dry_run:
                    # Apenas simula
                    tamanho = self.calcular_espaco_diretorio(diretorio)
                    xmls = len(list(diretorio.rglob('*.xml')))
                    zips = len(list(diretorio.rglob('*.zip')))
                    
                    self.stats.diretorios_removidos += 1
                    self.stats.arquivos_xml_removidos += xmls
                    self.stats.arquivos_zip_removidos += zips
                    self.stats.espaco_liberado_bytes += tamanho
                    
                    logger.info(f"[LIMPEZA.DRY] SIMULARIA remoção: {diretorio.name} "
                               f"({xmls} XMLs, {zips} ZIPs, {tamanho/1024/1024:.1f} MB)")
                else:
                    # Remove efetivamente
                    if self.remover_diretorio_seguro(diretorio):
                        diretorios_removidos.append(diretorio)
            
            # Atualiza banco de dados se não for simulação
            if not modo_dry_run and diretorios_removidos:
                self.atualizar_banco_dados(diretorios_removidos)
            
            # Estatísticas finais
            self.stats.tempo_execucao_segundos = time.time() - tempo_inicio
            
            logger.info(f"[LIMPEZA] {'🧪 SIMULAÇÃO' if modo_dry_run else '✅ LIMPEZA'} concluída:")
            logger.info(f"  • Diretórios removidos: {self.stats.diretorios_removidos}")
            logger.info(f"  • XMLs removidos: {self.stats.arquivos_xml_removidos}")
            logger.info(f"  • ZIPs removidos: {self.stats.arquivos_zip_removidos}")
            logger.info(f"  • Espaço liberado: {self.stats.espaco_liberado_bytes/1024/1024:.1f} MB")
            logger.info(f"  • Registros atualizados: {self.stats.registros_atualizados_db}")
            logger.info(f"  • Tempo execução: {self.stats.tempo_execucao_segundos:.2f}s")
            
            if self.stats.erros:
                logger.warning(f"  • Erros encontrados: {len(self.stats.erros)}")
                for erro in self.stats.erros[:5]:  # Mostra apenas os primeiros 5
                    logger.warning(f"    - {erro}")
            
        except Exception as e:
            erro = f"Erro crítico na limpeza: {e}"
            self.stats.erros.append(erro)
            logger.error(f"[LIMPEZA] {erro}")
        
        return self.stats


def executar_limpeza_arquivos_antigos(config_path: str = "configuracao.ini", dry_run: bool = False) -> bool:
    """
    Função de conveniência para executar limpeza.
    
    Args:
        config_path: Caminho para arquivo de configuração
        dry_run: Se True, apenas simula sem remover arquivos
        
    Returns:
        bool: True se executou com sucesso
    """
    try:
        limpador = LimpadorArquivosAntigos(config_path)
        
        # Verifica se limpeza está ativada (exceto em modo dry_run)
        if not dry_run and not limpador.limpeza_ativa:
            logger.info("[LIMPEZA] Limpeza automática desativada na configuração")
            return True
        
        stats = limpador.executar_limpeza(modo_dry_run=dry_run)
        
        return len(stats.erros) == 0
        
    except Exception as e:
        logger.error(f"[LIMPEZA] Erro ao executar limpeza: {e}")
        return False


if __name__ == "__main__":
    # Teste do sistema de limpeza
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Parâmetros da linha de comando
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    
    print("🧹 Sistema de Limpeza de Arquivos Antigos")
    print("=" * 50)
    
    # Executa limpeza
    sucesso = executar_limpeza_arquivos_antigos(dry_run=dry_run)
    
    if sucesso:
        print(f"\n✅ {'Simulação' if dry_run else 'Limpeza'} executada com sucesso!")
        if dry_run:
            print("💡 Para executar efetivamente, rode sem --dry-run")
    else:
        print(f"\n❌ {'Simulação' if dry_run else 'Limpeza'} falhou!")
        sys.exit(1)
