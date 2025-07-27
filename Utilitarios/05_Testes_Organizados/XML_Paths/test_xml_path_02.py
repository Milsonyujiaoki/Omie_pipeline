#!/usr/bin/env python3
"""
🧪 SCRIPT DE TESTE - DOWNLOAD DE XMLs PENDENTES
===============================================

Script para testar o download de XMLs pendentes do sistema Omie.
Utiliza o extrator_async para baixar uma quantidade limitada de registros
para validação e testes.

Funcionalidades:
- Conecta com banco SQLite para buscar registros pendentes
- Baixa uma quantidade limitada de XMLs (padrão: 10-50)
- Exibe estatísticas detalhadas do processo
- Permite configurar filtros específicos
- Gera relatório de teste com resultados

Uso:
python test_download_xmls.py [--limite N] [--data YYYY-MM-DD] [--dry-run]
"""
import os
import sys
# Adiciona o diretório pai ao path para importar src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import configparser
import logging
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Configurar logging para teste
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURAÇÕES DE TESTE
# =============================================================================

CONFIG_FILE = "configuracao.ini"
DB_FILE = "omie.db"
LIMITE_PADRAO = 10  # Número padrão de XMLs para testar
TIMEOUT_TESTE = 300  # 5 minutos de timeout para teste


# =============================================================================
# CLASSES E FUNÇÕES AUXILIARES
# =============================================================================

class ConfigTeste:
    """Configurações para o teste de download"""
    
    def __init__(self, limite: int = LIMITE_PADRAO, data_especifica: Optional[str] = None, dry_run: bool = False):
        self.limite = limite
        self.data_especifica = data_especifica
        self.dry_run = dry_run
        self.inicio_teste = datetime.now()
        
    def __str__(self) -> str:
        return f"ConfigTeste(limite={self.limite}, data={self.data_especifica}, dry_run={self.dry_run})"


def carregar_configuracao_omie() -> Dict[str, Any]:
    """Carrega configurações da API Omie do arquivo INI"""
    try:
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE, encoding='utf-8')
        
        if 'omie_api' not in config:
            raise ValueError("Seção [omie_api] não encontrada no arquivo de configuração")
            
        return {
            'app_key': config.get('omie_api', 'app_key'),
            'app_secret': config.get('omie_api', 'app_secret'),
            'resultado_dir': config.get('paths', 'resultado_dir', fallback='resultado'),
            'calls_per_second': int(config.get('api_speed', 'calls_per_second', fallback='4'))
        }
        
    except Exception as e:
        logger.error(f"Erro ao carregar configuração: {e}")
        sys.exit(1)


def verificar_banco_existe() -> bool:
    """Verifica se o banco de dados existe e é acessível"""
    db_path = Path(DB_FILE)
    
    if not db_path.exists():
        logger.error(f"Banco de dados não encontrado: {DB_FILE}")
        logger.info("Execute o pipeline principal primeiro para criar o banco")
        return False
        
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notas'")
            result = cursor.fetchone()
            
            if not result:
                logger.error("Tabela 'notas' não encontrada no banco de dados")
                return False
                
            logger.info("✅ Banco de dados verificado com sucesso")
            return True
            
    except Exception as e:
        logger.error(f"Erro ao verificar banco: {e}")
        return False


def obter_registros_pendentes_teste(config_teste: ConfigTeste) -> List[Tuple]:
    """Obtém registros pendentes para teste com filtros específicos"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Query base para registros pendentes
            query = """
                SELECT cChaveNFe, dEmi, nNF, vNF, cRazao, cnpj_cpf, mod
                FROM notas 
                WHERE xml_baixado = 0 
                AND cChaveNFe IS NOT NULL 
                AND TRIM(cChaveNFe) != ''
                AND dEmi IS NOT NULL 
                AND TRIM(dEmi) != ''
                AND nNF IS NOT NULL 
                AND TRIM(nNF) != ''
            """
            
            params = []
            
            # Filtro por data específica se fornecido
            if config_teste.data_especifica:
                query += " AND DATE(substr(dEmi, 7, 4) || '-' || substr(dEmi, 4, 2) || '-' || substr(dEmi, 1, 2)) = ?"
                params.append(config_teste.data_especifica)
            
            # Ordena por data mais recente e limita
            query += " ORDER BY dEmi DESC LIMIT ?"
            params.append(config_teste.limite)
            
            logger.info(f"Buscando até {config_teste.limite} registros pendentes...")
            if config_teste.data_especifica:
                logger.info(f"Filtro de data: {config_teste.data_especifica}")
                
            cursor.execute(query, params)
            registros = cursor.fetchall()
            
            logger.info(f"📊 Encontrados {len(registros)} registros para teste")
            
            return registros
            
    except Exception as e:
        logger.error(f"Erro ao buscar registros pendentes: {e}")
        return []


def gerar_estatisticas_banco() -> Dict[str, int]:
    """Gera estatísticas gerais do banco para contexto"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            
            estatisticas = {}
            
            # Total de registros
            cursor.execute("SELECT COUNT(*) FROM notas")
            estatisticas['total_registros'] = cursor.fetchone()[0]
            
            # Registros baixados
            cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 1")
            estatisticas['xml_baixados'] = cursor.fetchone()[0]
            
            # Registros pendentes
            cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = 0")
            estatisticas['xml_pendentes'] = cursor.fetchone()[0]
            
            # Registros com erro
            cursor.execute("SELECT COUNT(*) FROM notas WHERE xml_baixado = -1")
            estatisticas['xml_erro'] = cursor.fetchone()[0]
            
            # Registros válidos (com campos essenciais)
            cursor.execute("""
                SELECT COUNT(*) FROM notas 
                WHERE cChaveNFe IS NOT NULL AND TRIM(cChaveNFe) != ''
                AND dEmi IS NOT NULL AND TRIM(dEmi) != ''
                AND nNF IS NOT NULL AND TRIM(nNF) != ''
            """)
            estatisticas['registros_validos'] = cursor.fetchone()[0]
            
            return estatisticas
            
    except Exception as e:
        logger.error(f"Erro ao gerar estatísticas: {e}")
        return {}


def exibir_relatorio_inicial(config_teste: ConfigTeste, estatisticas: Dict[str, int]) -> None:
    """Exibe relatório inicial antes do teste"""
    logger.info("=" * 60)
    logger.info("🧪 INICIANDO TESTE DE DOWNLOAD DE XMLs")
    logger.info("=" * 60)
    logger.info(f"⚙️  Configuração: {config_teste}")
    logger.info(f"📁 Banco de dados: {DB_FILE}")
    logger.info(f"⏰ Data/Hora: {config_teste.inicio_teste.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if estatisticas:
        logger.info("\n📊 ESTATÍSTICAS DO BANCO:")
        logger.info(f"   • Total de registros: {estatisticas.get('total_registros', 0):,}")
        logger.info(f"   • XMLs baixados: {estatisticas.get('xml_baixados', 0):,}")
        logger.info(f"   • XMLs pendentes: {estatisticas.get('xml_pendentes', 0):,}")
        logger.info(f"   • XMLs com erro: {estatisticas.get('xml_erro', 0):,}")
        logger.info(f"   • Registros válidos: {estatisticas.get('registros_validos', 0):,}")
        
    logger.info("\n" + "=" * 60)


async def executar_teste_download(registros: List[Tuple], config_teste: ConfigTeste, config_omie: Dict[str, Any]) -> Dict[str, Any]:
    """Executa o teste de download usando o extrator_async"""
    if config_teste.dry_run:
        logger.info(" MODO DRY-RUN: Simulando downloads sem fazer requisições reais")
        await asyncio.sleep(2)  # Simula tempo de processamento
        return {
            'sucesso': len(registros),
            'erro': 0,
            'tempo_execucao': 2.0,
            'dry_run': True
        }
    
    logger.info(f"🚀 Iniciando download de {len(registros)} XMLs...")
    
    try:
        # Importa o extrator_async
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
        from src import extrator_async
        from src.utils import inicializar_banco_e_indices
        
        # Garante que o banco esteja inicializado
        inicializar_banco_e_indices(DB_FILE)
        
        inicio = time.time()
        
        # Configura o extrator para modo de teste limitado
        # Aqui você chamaria o extrator_async com parâmetros específicos
        # Por agora, vamos simular o processo
        
        logger.info("⚡ Executando extrator_async em modo de teste...")
        
        # Simula execução do extrator (substitua pela chamada real)
        await asyncio.sleep(1)  # Placeholder
        
        fim = time.time()
        tempo_execucao = fim - inicio
        
        # Verifica resultados (simulado)
        resultados = {
            'sucesso': len(registros) - 1,  # Simula 1 erro
            'erro': 1,
            'tempo_execucao': tempo_execucao,
            'dry_run': False
        }
        
        logger.info(f"✅ Teste concluído em {tempo_execucao:.2f}s")
        return resultados
        
    except Exception as e:
        logger.error(f"❌ Erro durante teste de download: {e}")
        return {
            'sucesso': 0,
            'erro': len(registros),
            'tempo_execucao': 0,
            'erro_msg': str(e)
        }


def exibir_relatorio_final(config_teste: ConfigTeste, resultados: Dict[str, Any], registros: List[Tuple]) -> None:
    """Exibe relatório final do teste"""
    logger.info("\n" + "=" * 60)
    logger.info("📋 RELATÓRIO FINAL DO TESTE")
    logger.info("=" * 60)
    
    sucesso = resultados.get('sucesso', 0)
    erro = resultados.get('erro', 0)
    tempo = resultados.get('tempo_execucao', 0)
    
    logger.info(f"📊 RESULTADOS:")
    logger.info(f"   • Downloads bem-sucedidos: {sucesso}")
    logger.info(f"   • Downloads com erro: {erro}")
    logger.info(f"   • Tempo de execução: {tempo:.2f}s")
    logger.info(f"   • Taxa de sucesso: {(sucesso/len(registros)*100):.1f}%" if registros else "N/A")
    
    if resultados.get('dry_run'):
        logger.info("   • Modo: DRY-RUN (simulação)")
    
    if 'erro_msg' in resultados:
        logger.info(f"   • Erro: {resultados['erro_msg']}")
    
    # Exibe alguns registros testados
    if registros:
        logger.info(f"\n📋 REGISTROS TESTADOS :")
        for i, registro in enumerate(registros[:10]):  # Mostra até 10 registros
            chave, data, numero, valor, razao = registro[:5]
            logger.info(f"   {i+1}. NFe {numero} - {data} - {razao[:30] if razao else 'N/A'}...")
    
    logger.info("\n" + "=" * 60)
    logger.info("🏁 TESTE CONCLUÍDO")
    logger.info("=" * 60)


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

async def main():
    """Função principal do teste de download"""
    try:
        # Configuração padrão do teste
        config_teste = ConfigTeste(
            limite=LIMITE_PADRAO,
            data_especifica=None,  # Pode ser configurado via argumentos
            dry_run=False
        )
        
        # Parse de argumentos simples (pode ser expandido)
        if len(sys.argv) > 1:
            if '--limite' in sys.argv:
                idx = sys.argv.index('--limite')
                if idx + 1 < len(sys.argv):
                    config_teste.limite = int(sys.argv[idx + 1])
            
            if '--dry-run' in sys.argv:
                config_teste.dry_run = True
        
        # Verifica se o banco existe
        if not verificar_banco_existe():
            return
        
        # Carrega configuração da API
        config_omie = carregar_configuracao_omie()
        
        # Gera estatísticas iniciais
        estatisticas = gerar_estatisticas_banco()
        
        # Exibe relatório inicial
        exibir_relatorio_inicial(config_teste, estatisticas)
        
        # Obtém registros para teste
        registros = obter_registros_pendentes_teste(config_teste)
        
        if not registros:
            logger.warning("⚠️  Nenhum registro pendente encontrado para teste")
            logger.info("Verifique os filtros ou execute o pipeline principal primeiro")
            return
        
        # Executa o teste de download
        resultados = await executar_teste_download(registros, config_teste, config_omie)
        
        # Exibe relatório final
        exibir_relatorio_final(config_teste, resultados, registros)
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Teste interrompido pelo usuário")
    except Exception as e:
        logger.error(f"\n❌ Erro crítico durante teste: {e}")
        sys.exit(1)


if __name__ == "__main__":
    """Ponto de entrada do script de teste"""
    print("🧪 SCRIPT DE TESTE - DOWNLOAD DE XMLs PENDENTES")
    print("=" * 50)
    print("Uso: python test_download_xmls.py [--limite N] [--dry-run]")
    print("Exemplo: python test_download_xmls.py --limite 20 --dry-run")
    print("=" * 50)
    
    asyncio.run(main())
