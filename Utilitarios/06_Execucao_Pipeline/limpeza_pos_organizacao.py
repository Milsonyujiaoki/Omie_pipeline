#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
limpeza_pos_organizacao.py

Script para limpeza dos arquivos de teste após organização.
Remove arquivos duplicados mantendo apenas a versão organizada.

ATENÇÃO: Este script remove arquivos! Use com cuidado.
Certifique-se de que o backup foi criado corretamente antes de executar.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List

def configurar_logging(verbose: bool = False) -> logging.Logger:
    """Configura sistema de logging"""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('limpeza_pos_organizacao.log', encoding='utf-8')
        ],
        force=True
    )
    
    return logging.getLogger(__name__)

def obter_arquivos_para_remover(diretorio_raiz: Path) -> List[Path]:
    """Identifica arquivos de teste que podem ser removidos"""
    arquivos_remover = []
    
    # Padrões de arquivos de teste na raiz que foram organizados
    padroes_raiz = [
        "teste_*.py",
        "test_*.py"
    ]
    
    # Arquivos específicos que sabemos que foram organizados
    arquivos_especificos = [
        "teste_main.py",
        "teste_consistencia.py", 
        "teste_final_performance.py",
        "teste_gerar_xml_comparativo.py",
        "teste_nome_xml_final.py",
        "teste_normalizacao_chave.py",
        "teste_pratico_comparacao.py",
        "teste_script_verificador_xmls.py",
        "teste_simples_xml.py"
    ]
    
    # Buscar na raiz
    for padrao in padroes_raiz:
        arquivos_remover.extend(diretorio_raiz.glob(padrao))
    
    # Adicionar arquivos específicos
    for arquivo in arquivos_especificos:
        caminho = diretorio_raiz / arquivo
        if caminho.exists():
            arquivos_remover.append(caminho)
    
    # Excluir arquivos importantes que devem ser mantidos
    arquivos_manter = {
        "teste_config.py",  # Arquivo vazio, pode ser útil
        "organizador_testes.py",  # Script de organização
        "limpeza_pos_organizacao.py"  # Este script
    }
    
    arquivos_filtrados = []
    for arquivo in arquivos_remover:
        if arquivo.name not in arquivos_manter:
            arquivos_filtrados.append(arquivo)
    
    return list(set(arquivos_filtrados))  # Remove duplicatas

def main():
    """Função principal"""
    parser = argparse.ArgumentParser(
        description="Limpeza de arquivos após organização",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ATENÇÃO: Este script REMOVE arquivos permanentemente!

Certifique-se de que:
1. A organização foi executada com sucesso
2. O backup foi criado corretamente
3. Você verificou a pasta Utilitarios/05_Testes_Organizados/

Exemplos de uso:
  python limpeza_pos_organizacao.py --dry-run    # Simula sem remover
  python limpeza_pos_organizacao.py --confirmar  # Remove após confirmação
        """
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simula a limpeza sem executar remoções'
    )
    
    parser.add_argument(
        '--confirmar',
        action='store_true',
        help='Confirma que deseja remover os arquivos'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Modo verboso'
    )
    
    args = parser.parse_args()
    
    # Configurar logging
    logger = configurar_logging(args.verbose)
    
    try:
        diretorio_raiz = Path('.').absolute()
        
        # Verificar se a organização foi feita
        pasta_organizados = diretorio_raiz / "Utilitarios" / "05_Testes_Organizados"
        if not pasta_organizados.exists():
            logger.error("❌ Pasta de testes organizados não encontrada!")
            logger.error("   Execute primeiro: python organizador_testes.py")
            sys.exit(1)
        
        # Verificar se há backup
        backups = list(diretorio_raiz.glob("backup_testes_*"))
        if not backups:
            logger.warning("⚠️  Nenhum backup encontrado!")
            if not args.dry_run:
                resposta = input("Continuar sem backup? (digite 'SIM' para confirmar): ")
                if resposta != 'SIM':
                    logger.info("Operação cancelada pelo usuário")
                    sys.exit(0)
        else:
            logger.info(f"✅ Backup encontrado: {backups[-1].name}")
        
        # Obter arquivos para remover
        arquivos_remover = obter_arquivos_para_remover(diretorio_raiz)
        
        if not arquivos_remover:
            logger.info("✅ Nenhum arquivo para remover encontrado")
            sys.exit(0)
        
        logger.info(f"🗑️  Encontrados {len(arquivos_remover)} arquivos para remover:")
        for arquivo in sorted(arquivos_remover):
            logger.info(f"   - {arquivo.name}")
        
        if args.dry_run:
            logger.info("🎭 MODO SIMULAÇÃO - Nenhum arquivo foi removido")
            sys.exit(0)
        
        # Confirmação
        if not args.confirmar:
            logger.warning("⚠️  Para remover os arquivos, use --confirmar")
            logger.warning("   Exemplo: python limpeza_pos_organizacao.py --confirmar")
            sys.exit(0)
        
        # Confirmação adicional
        print("\n" + "="*60)
        print("⚠️  CONFIRMAÇÃO FINAL")
        print("="*60)
        print(f"Arquivos a serem REMOVIDOS: {len(arquivos_remover)}")
        print("Esta ação NÃO PODE ser desfeita!")
        print("Certifique-se de que o backup foi criado corretamente.")
        print("="*60)
        
        resposta = input("Digite 'REMOVER' para confirmar a remoção: ")
        if resposta != 'REMOVER':
            logger.info("Operação cancelada pelo usuário")
            sys.exit(0)
        
        # Executar remoção
        logger.info("🗑️  Iniciando remoção de arquivos...")
        
        removidos = 0
        erros = 0
        
        for arquivo in arquivos_remover:
            try:
                arquivo.unlink()
                logger.info(f"   ✅ Removido: {arquivo.name}")
                removidos += 1
            except Exception as e:
                logger.error(f"   ❌ Erro ao remover {arquivo.name}: {e}")
                erros += 1
        
        logger.info(f"🗑️  Limpeza concluída: {removidos} removidos, {erros} erros")
        
        if erros == 0:
            logger.info("✅ Limpeza concluída com sucesso!")
            logger.info("📂 Todos os testes estão agora organizados em:")
            logger.info(f"   {pasta_organizados}")
        
    except KeyboardInterrupt:
        logger.warning("❌ Operação interrompida pelo usuário")
        sys.exit(130)
    
    except Exception as e:
        logger.exception(f"❌ Erro crítico: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
