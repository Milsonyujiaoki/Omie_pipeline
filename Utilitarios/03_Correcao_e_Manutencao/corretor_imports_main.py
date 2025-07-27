# =============================================================================
# SCRIPT DE CORREÇÃO DE IMPORTS - MAIN.PY REFATORADO
# =============================================================================
"""
Script para atualizar imports do main.py para usar a nova estrutura refatorada.

Este script substitui as importações do utils.py monolítico pelas
importações específicas dos novos módulos organizados.
"""

import logging

logger = logging.getLogger(__name__)

def atualizar_imports_main():
    """
    Atualiza imports do main.py para usar nova estrutura.
    """
    try:
        main_path = "c:\\milson\\extrator_omie_v3\\main.py"
        
        # Lê conteúdo atual
        with open(main_path, 'r', encoding='utf-8') as f:
            conteudo = f.read()
        
        # Substitui import do utils antigo
        import_antigo = """from src_novo.utils.utils import (
    iniciar_db, 
    atualizar_anomesdia,
    atualizar_campos_registros_pendentes,
    formatar_tempo_total
)"""
        
        import_novo = """# Importações dos novos módulos refatorados
from src_novo.infrastructure.database import SQLiteRepository
from src_novo.application.services import (
    RepositoryService,
    NotaFiscalService,
    MetricsService,
    XMLProcessingService,
    TemporalIndexingService
)
from src_novo.utils import formatar_tempo_total"""
        
        conteudo = conteudo.replace(import_antigo, import_novo)
        
        # Atualiza chamadas de função para usar serviços
        substituicoes = [
            ("iniciar_db(\"omie.db\")", 
             "SQLiteRepository(\"omie.db\")"),
            
            ("atualizar_campos_registros_pendentes(\"omie.db\", self.config['resultado_dir'])",
             """repository = SQLiteRepository(\"omie.db\")
            xml_service = XMLProcessingService(repository)
            xml_service.atualizar_campos_registros_pendentes(self.config['resultado_dir'])"""),
            
            ("atualizar_anomesdia(\"omie.db\")",
             """repository = SQLiteRepository(\"omie.db\")
            temporal_service = TemporalIndexingService(repository)
            temporal_service.atualizar_anomesdia()""")
        ]
        
        for antigo, novo in substituicoes:
            conteudo = conteudo.replace(antigo, novo)
        
        # Salva arquivo atualizado
        with open(main_path, 'w', encoding='utf-8') as f:
            f.write(conteudo)
        
        logger.info("[CORRETOR] Imports do main.py atualizados com sucesso")
        return True
        
    except Exception as e:
        logger.error(f"[CORRETOR] Erro ao atualizar imports: {e}")
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    atualizar_imports_main()
