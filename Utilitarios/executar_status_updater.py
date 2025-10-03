"""
UTILITÁRIO PARA ATUALIZAÇÃO DE STATUS NFE
Executa atualização de status das notas fiscais usando a API Omie.
"""

import sys
import asyncio
import logging
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.status_nfe_updater import executar_atualizacao_status_nfe


async def main():
    """Função principal para execução do utilitário."""
    
    # Configuração de logging
    log_dir = Path("log")
    log_dir.mkdir(exist_ok=True)
    
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / f"status_updater_{timestamp}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    
    print("🔄 SISTEMA DE ATUALIZAÇÃO DE STATUS NFE")
    print("=" * 60)
    print(f"Log: {log_file}")
    print()
    
    # Parâmetros da linha de comando
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    test_mode = "--test" in sys.argv
    limite = 100 if test_mode else 10000000
    
    if dry_run:
        print("🧪 MODO SIMULAÇÃO ATIVADO")
        print("   (Nenhum dado será alterado no banco)")
        print()
    
    if test_mode:
        print(f"🔬 MODO TESTE ATIVADO - Processando apenas {limite} registros")
        print()
    
    try:
        logger.info("Iniciando atualização de status das NFe...")
        
        # Executa atualização
        sucesso = await executar_atualizacao_status_nfe(
            limite_notas=limite,
            dry_run=dry_run
        )
        
        if sucesso:
            print("✅ Atualização concluída com sucesso!")
            if dry_run:
                print("\n💡 Para executar efetivamente, execute novamente sem --dry-run")
        else:
            print("❌ Atualização falhou! Verifique os logs para detalhes.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️  Operação cancelada pelo usuário")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Erro crítico: {e}")
        print(f"❌ Erro crítico: {e}")
        sys.exit(1)


def show_help():
    """Mostra ajuda sobre o uso do utilitário."""
    print("""
🔄 UTILITÁRIO DE ATUALIZAÇÃO DE STATUS NFE
==========================================

DESCRIÇÃO:
  Consulta a API Omie para atualizar o status das notas fiscais
  no banco de dados local. Útil para identificar notas canceladas,
  rejeitadas ou com outros status específicos.

FUNCIONALIDADES:
  ✓ Consulta endpoints da API Omie para obter status atual
  ✓ Normaliza diferentes formatos de status
  ✓ Atualiza banco de dados SQLite local
  ✓ Processa em lotes para otimização
  ✓ Controle de taxa para respeitar limites da API
  ✓ Logging detalhado com estatísticas

USAGE:
  python executar_status_updater.py [opções]

OPÇÕES:
  --dry-run, -n    Executa em modo simulação (não altera dados)
  --test           Processa apenas 100 registros (modo teste)
  --help, -h       Mostra esta ajuda

EXEMPLOS:
  # Execução normal
  python executar_status_updater.py
  
  # Simulação (não altera dados)
  python executar_status_updater.py --dry-run
  
  # Teste com poucos registros
  python executar_status_updater.py --test --dry-run

CONFIGURAÇÃO:
  O utilitário usa o arquivo 'configuracao.ini' na raiz do projeto
  para obter credenciais da API Omie e configurações do banco.

LOGS:
  Os logs são salvos em 'log/status_updater_YYYYMMDD_HHMMSS.log'
  
STATUS SUPORTADOS:
  • AUTORIZADA   - NFe autorizada pela SEFAZ
  • CANCELADA    - NFe cancelada
  • REJEITADA    - NFe rejeitada pela SEFAZ  
  • DENEGADA     - NFe denegada
  • INUTILIZADA  - NFe inutilizada
  • PROCESSANDO  - NFe em processamento
  • PENDENTE     - NFe pendente
  • INDEFINIDO   - Status não identificado

ENDPOINTS UTILIZADOS:
  • ListarNFesEmitidas - Para consultas em lote
  • ObterNfe          - Para consultas individuais
""")


if __name__ == "__main__":
    if "--help" in sys.argv or "-h" in sys.argv:
        show_help()
        sys.exit(0)
    
    asyncio.run(main())
