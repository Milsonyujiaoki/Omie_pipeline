"""
UTILITÁRIO DE PATHS PORTÁVEIS - OMIE PIPELINE V3
Resolve paths de forma portável entre diferentes computadores/ambientes.
"""

import configparser
from pathlib import Path
from typing import Dict, Any
import os
import logging

logger = logging.getLogger(__name__)

class PathResolver:
    """
    Classe para resolver paths de forma portável baseado no arquivo de configuração.
    """
    
    def __init__(self, config_path: str = "configuracao.ini"):
        """
        Inicializa o resolver com o arquivo de configuração.
        
        Args:
            config_path: Caminho para o arquivo de configuração INI
        """
        self.config_path = Path(config_path)
        self.config = configparser.ConfigParser()
        
        # Busca o arquivo de configuração em vários locais
        self.config_file = self._encontrar_arquivo_config()
        self._carregar_configuracao()
        
        # Define diretório base do projeto
        self.projeto_base = self._resolver_base_dir()
        
    def _encontrar_arquivo_config(self) -> Path:
        """Encontra o arquivo de configuração em vários locais possíveis."""
        locais_possiveis = [
            Path(self.config_path),  # Caminho fornecido
            Path(__file__).parent / self.config_path,  # Ao lado deste arquivo
            Path(__file__).parent.parent / self.config_path,  # Raiz do projeto
            Path.cwd() / self.config_path,  # Diretório atual
        ]
        
        for local in locais_possiveis:
            if local.exists():
                logger.info(f"[PATH.RESOLVER] Arquivo config encontrado: {local}")
                return local
                
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {self.config_path}")
    
    def _carregar_configuracao(self) -> None:
        """Carrega o arquivo de configuração."""
        try:
            self.config.read(self.config_file, encoding='utf-8')
            logger.info(f"[PATH.RESOLVER] Configuração carregada: {self.config_file}")
        except Exception as e:
            raise RuntimeError(f"Erro ao carregar configuração: {e}")
    
    def _resolver_base_dir(self) -> Path:
        """Resolve o diretório base do projeto."""
        base_config = self.config.get('paths', 'projeto_base_dir', fallback='.')
        
        # Se for path absoluto, usa diretamente
        if Path(base_config).is_absolute():
            base_dir = Path(base_config)
        else:
            # Se for relativo, resolve baseado na localização do arquivo config
            base_dir = self.config_file.parent / base_config
        
        # Resolve para path absoluto
        base_dir = base_dir.resolve()
        
        # Cria o diretório se não existir
        base_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"[PATH.RESOLVER] Diretório base do projeto: {base_dir}")
        return base_dir
    
    def get_path(self, secao: str, chave: str, fallback: str = None, criar: bool = True) -> Path:
        """
        Resolve um path baseado na configuração.
        
        Args:
            secao: Seção do arquivo INI
            chave: Chave da configuração
            fallback: Valor padrão se não encontrar
            criar: Se deve criar o diretório se não existir
            
        Returns:
            Path: Caminho resolvido
        """
        valor = self.config.get(secao, chave, fallback=fallback)
        if not valor:
            raise ValueError(f"Path não configurado: [{secao}] {chave}")
        
        # Se é path absoluto, usa diretamente
        if Path(valor).is_absolute():
            path = Path(valor)
        else:
            # Se é relativo, resolve baseado no diretório base
            path = self.projeto_base / valor
        
        # Resolve para path absoluto
        path = path.resolve()
        
        # Cria o diretório se solicitado e for um diretório
        if criar and not path.suffix:  # Sem extensão = diretório
            path.mkdir(parents=True, exist_ok=True)
        elif criar and path.suffix:  # Com extensão = arquivo, cria pasta pai
            path.parent.mkdir(parents=True, exist_ok=True)
        
        return path
    
    def get_db_path(self) -> Path:
        """Retorna o caminho completo do banco de dados."""
        return self.get_path('paths', 'db_path', fallback='omie.db', criar=False)
    
    def get_resultado_dir(self) -> Path:
        """Retorna o diretório de resultados."""
        return self.get_path('paths', 'resultado_dir', fallback='resultado')
    
    def get_log_dir(self) -> Path:
        """Retorna o diretório de logs."""
        return self.get_path('paths', 'log_dir', fallback='log')
    
    def get_temp_dir(self) -> Path:
        """Retorna o diretório temporário."""
        return self.get_path('paths', 'temp_dir', fallback='temp')
    
    def get_cache_dir(self) -> Path:
        """Retorna o diretório de cache."""
        return self.get_path('paths', 'cache_dir', fallback='cache')
    
    def get_backup_dir(self) -> Path:
        """Retorna o diretório de backup."""
        return self.get_path('paths', 'backup_dir', fallback='backup')
    
    def get_relatorio_arquivos_vazios(self) -> Path:
        """Retorna o caminho do relatório de arquivos vazios."""
        return self.get_path('paths', 'relatorio_arquivos_vazios', fallback='relatorio_arquivos_vazios.xlsx', criar=False)
    
    def get_path_by_key(self, key: str) -> Path:
        """
        Método de conveniência para obter paths pelos nomes das chaves.
        
        Args:
            key: Nome da chave (db_name, resultado_dir, etc.)
            
        Returns:
            Path resolvido
        """
        # Mapeamento para compatibilidade
        method_mapping = {
            'db_name': self.get_db_path,
            'resultado_dir': self.get_resultado_dir,
            'log_dir': self.get_log_dir,
            'temp_dir': self.get_temp_dir,
            'cache_dir': self.get_cache_dir,
            'backup_dir': self.get_backup_dir,
            'relatorio_arquivos_vazios': self.get_relatorio_arquivos_vazios,
        }
        
        if key in method_mapping:
            return method_mapping[key]()
        else:
            raise ValueError(f"Chave de path não reconhecida: {key}")
    
    def validar_ambiente(self) -> Dict[str, Any]:
        """
        Valida se o ambiente está configurado corretamente.
        
        Returns:
            Dict com status da validação
        """
        resultado = {
            'valido': True,
            'erros': [],
            'avisos': [],
            'paths': {}
        }
        
        # Verifica paths essenciais
        try:
            paths_essenciais = {
                'projeto_base': self.projeto_base,
                'resultado_dir': self.get_resultado_dir(),
                'db_path': self.get_db_path(),
                'log_dir': self.get_log_dir(),
            }
            
            for nome, path in paths_essenciais.items():
                resultado['paths'][nome] = str(path)
                
                if nome != 'db_path':  # DB pode não existir ainda
                    if not path.exists():
                        if nome == 'resultado_dir':
                            resultado['avisos'].append(f"{nome}: {path} não existe (será criado)")
                        else:
                            resultado['erros'].append(f"{nome}: {path} não existe")
                            resultado['valido'] = False
                    elif not os.access(path, os.R_OK | os.W_OK):
                        resultado['erros'].append(f"{nome}: {path} sem permissões de leitura/escrita")
                        resultado['valido'] = False
                        
        except Exception as e:
            resultado['erros'].append(f"Erro na validação: {e}")
            resultado['valido'] = False
        
        return resultado


# Função de conveniência para uso direto
_resolver_global = None

def get_path_resolver(config_path: str = "configuracao.ini") -> PathResolver:
    """Retorna uma instância singleton do PathResolver."""
    global _resolver_global
    if _resolver_global is None:
        _resolver_global = PathResolver(config_path)
    return _resolver_global

def validar_ambiente_projeto(config_path: str = "configuracao.ini") -> bool:
    """
    Valida se o ambiente do projeto está configurado corretamente.
    
    Args:
        config_path: Caminho para o arquivo de configuração
        
    Returns:
        bool: True se ambiente válido
    """
    try:
        resolver = get_path_resolver(config_path)
        resultado = resolver.validar_ambiente()
        
        if resultado['valido']:
            logger.info("[AMBIENTE] ✅ Ambiente validado com sucesso")
            for nome, path in resultado['paths'].items():
                logger.info(f"  {nome}: {path}")
        else:
            logger.error("[AMBIENTE] ❌ Problemas encontrados no ambiente:")
            for erro in resultado['erros']:
                logger.error(f"  - {erro}")
        
        for aviso in resultado['avisos']:
            logger.warning(f"  ⚠️ {aviso}")
            
        return resultado['valido']
        
    except Exception as e:
        logger.error(f"[AMBIENTE] Erro na validação: {e}")
        return False


if __name__ == "__main__":
    # Teste do sistema de paths
    import logging
    logging.basicConfig(level=logging.INFO)
    
    try:
        print("🔧 Teste do Sistema de Paths Portáveis")
        print("=" * 50)
        
        # Testa validação do ambiente
        ambiente_ok = validar_ambiente_projeto()
        
        if ambiente_ok:
            resolver = get_path_resolver()
            print(f"\n📁 Paths resolvidos:")
            print(f"  Base do projeto: {resolver.projeto_base}")
            print(f"  Resultados: {resolver.get_resultado_dir()}")
            print(f"  Banco de dados: {resolver.get_db_path()}")
            print(f"  Logs: {resolver.get_log_dir()}")
            print(f"  Cache: {resolver.get_cache_dir()}")
            
        print(f"\n{'✅ SUCESSO' if ambiente_ok else '❌ FALHA'}")
        
    except Exception as e:
        print(f"❌ ERRO: {e}")
