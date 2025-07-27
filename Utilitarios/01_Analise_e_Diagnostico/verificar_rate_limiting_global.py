#!/usr/bin/env python3
"""
Analisador de Rate Limiting Global - Extrator Omie V3

Este script verifica se todos os modos de extração respeitam o limite global
de 4 requisições por segundo de maneira consistente e adequada.

Análise realizada:
1. Verificação de implementação de rate limiting em todos os extratores
2. Análise da configuração de calls_per_second
3. Validação do uso correto das funções de controle
4. Detecção de problemas de concorrência
5. Recomendações de melhorias

Resultados:
- Relatório detalhado de conformidade
- Identificação de problemas críticos  
- Sugestões de otimização
- Validação de implementação global

Uso:
    python verificar_rate_limiting_global.py
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set
from dataclasses import dataclass

# Adicionar diretório do projeto ao Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

@dataclass
class RateLimitingAnalysis:
    """Resultado da análise de rate limiting para um arquivo."""
    arquivo: str
    tem_rate_limiting: bool
    funcoes_usadas: List[str]
    calls_per_second_configs: List[str]
    problemas: List[str]
    recomendacoes: List[str]
    score_conformidade: int  # 0-100

@dataclass
class ConcurrencyConfig:
    """Configuração de concorrência encontrada."""
    arquivo: str
    max_concurrent: int
    calls_per_second: int
    adequacao: str  # "ADEQUADO", "PROBLEMÁTICO", "CRÍTICO"

class RateLimitingVerifier:
    """Verificador de conformidade de rate limiting global."""
    
    def __init__(self, workspace_path: str):
        self.workspace_path = Path(workspace_path)
        self.arquivos_analisados = []
        self.problemas_criticos = []
        self.configs_concorrencia = []
        
    def analisar_arquivo(self, arquivo_path: Path) -> RateLimitingAnalysis:
        """Analisa um arquivo Python para verificar rate limiting."""
        try:
            content = arquivo_path.read_text(encoding='utf-8')
            
            # Busca por funções de rate limiting
            funcoes_rate_limiting = []
            if 'respeitar_limite_requisicoes_async' in content:
                funcoes_rate_limiting.append('respeitar_limite_requisicoes_async')
            if 'respeitar_limite_requisicoes' in content and 'async' not in funcoes_rate_limiting:
                funcoes_rate_limiting.append('respeitar_limite_requisicoes')
            if 'await asyncio.sleep' in content:
                funcoes_rate_limiting.append('asyncio.sleep')
            if 'time.sleep' in content:
                funcoes_rate_limiting.append('time.sleep')
            
            # Busca por configurações de calls_per_second
            calls_configs = []
            calls_patterns = [
                r'calls_per_second[\\s]*=[\\s]*([\\d]+)',
                r'"calls_per_second"[\\s]*:[\\s]*([\\d]+)',
                r'[\'"]calls_per_second[\'"][\\s]*,[\\s]*([\\d]+)',
            ]
            
            for pattern in calls_patterns:
                matches = re.findall(pattern, content)
                calls_configs.extend(matches)
            
            # Busca por max_concurrent
            concurrent_configs = []
            concurrent_patterns = [
                r'max_concurrent[\\s]*=[\\s]*([\\d]+)',
                r'MAX_CONCURRENT[\\w_]*[\\s]*=[\\s]*([\\d]+)',
                r'Semaphore\\(([\\d]+)\\)',
            ]
            
            for pattern in concurrent_patterns:
                matches = re.findall(pattern, content)
                concurrent_configs.extend(matches)
            
            # Análise de problemas
            problemas = []
            recomendacoes = []
            
            # Verifica se tem algum tipo de rate limiting
            tem_rate_limiting = len(funcoes_rate_limiting) > 0
            
            if not tem_rate_limiting and ('client.call_api' in content or 'session.post' in content):
                problemas.append("CRÍTICO: Faz chamadas API sem rate limiting")
            
            # Verifica configurações inadequadas
            for config in calls_configs:
                try:
                    valor = int(config)
                    if valor > 4:
                        problemas.append(f"ALERTA: calls_per_second={valor} excede limite recomendado de 4")
                    elif valor == 0:
                        problemas.append(f"CRÍTICO: calls_per_second={valor} é inválido")
                except ValueError:
                    problemas.append(f"ERRO: calls_per_second inválido: {config}")
            
            # Verifica concorrência alta sem rate limiting adequado
            for config in concurrent_configs:
                try:
                    valor = int(config)
                    if valor > 8 and 'respeitar_limite_requisicoes_async' not in content:
                        problemas.append(f"CRÍTICO: max_concurrent={valor} alto sem rate limiting assíncrono")
                    elif valor > 15:
                        problemas.append(f"CRÍTICO: max_concurrent={valor} excessivamente alto")
                except ValueError:
                    continue
            
            # Verifica uso incorreto de sleep sem rate limiting estruturado
            if 'asyncio.sleep' in content and 'respeitar_limite_requisicoes' not in content:
                if 'call_api' in content:
                    problemas.append("ALERTA: Usa asyncio.sleep mas sem função de rate limiting estruturada")
            
            # Recomendações baseadas na análise
            if not tem_rate_limiting:
                recomendacoes.append("Implementar respeitar_limite_requisicoes_async() para chamadas API")
            
            if len(calls_configs) == 0 and 'call_api' in content:
                recomendacoes.append("Definir calls_per_second explicitamente (recomendado: 4)")
            
            if len(concurrent_configs) > 0 and len(calls_configs) == 0:
                recomendacoes.append("Sincronizar max_concurrent com calls_per_second")
            
            # Calcula score de conformidade
            score = 100
            score -= len([p for p in problemas if 'CRÍTICO' in p]) * 30
            score -= len([p for p in problemas if 'ALERTA' in p]) * 15
            score -= len([p for p in problemas if 'ERRO' in p]) * 20
            score = max(0, score)
            
            return RateLimitingAnalysis(
                arquivo=str(arquivo_path.relative_to(self.workspace_path)),
                tem_rate_limiting=tem_rate_limiting,
                funcoes_usadas=funcoes_rate_limiting,
                calls_per_second_configs=calls_configs,
                problemas=problemas,
                recomendacoes=recomendacoes,
                score_conformidade=score
            )
            
        except Exception as e:
            return RateLimitingAnalysis(
                arquivo=str(arquivo_path.relative_to(self.workspace_path)),
                tem_rate_limiting=False,
                funcoes_usadas=[],
                calls_per_second_configs=[],
                problemas=[f"ERRO: Falha ao analisar arquivo: {e}"],
                recomendacoes=["Verificar sintaxe do arquivo"],
                score_conformidade=0
            )
    
    def analisar_concorrencia_global(self) -> List[ConcurrencyConfig]:
        """Analisa configurações de concorrência em todos os arquivos."""
        configs = []
        
        # Arquivos principais para análise
        arquivos_principais = [
            "main.py",
            "src/extrator_async.py", 
            "src/omie_client_async.py",
            "extrator_funcional.py",
            "pipeline_adaptativo.py"
        ]
        
        for arquivo_nome in arquivos_principais:
            arquivo_path = self.workspace_path / arquivo_nome
            if not arquivo_path.exists():
                continue
                
            try:
                content = arquivo_path.read_text(encoding='utf-8')
                
                # Extrai configurações
                max_concurrent = self._extrair_max_concurrent(content)
                calls_per_second = self._extrair_calls_per_second(content)
                
                if max_concurrent or calls_per_second:
                    adequacao = self._avaliar_adequacao(max_concurrent, calls_per_second)
                    
                    configs.append(ConcurrencyConfig(
                        arquivo=arquivo_nome,
                        max_concurrent=max_concurrent or 0,
                        calls_per_second=calls_per_second or 0,
                        adequacao=adequacao
                    ))
                    
            except Exception as e:
                print(f"Erro ao analisar {arquivo_nome}: {e}")
        
        return configs
    
    def _extrair_max_concurrent(self, content: str) -> int:
        """Extrai valor de max_concurrent do conteúdo."""
        patterns = [
            r'max_concurrent[\\s]*=[\\s]*([\\d]+)',
            r'MAX_CONCURRENT[\\w_]*[\\s]*=[\\s]*([\\d]+)',
            r'Semaphore\\(([\\d]+)\\)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            if matches:
                try:
                    return max(int(m) for m in matches)
                except ValueError:
                    continue
        return 0
    
    def _extrair_calls_per_second(self, content: str) -> int:
        """Extrai valor de calls_per_second do conteúdo."""
        patterns = [
            r'calls_per_second[\\s]*=[\\s]*([\\d]+)',
            r'"calls_per_second"[\\s]*:[\\s]*([\\d]+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            if matches:
                try:
                    return max(int(m) for m in matches)
                except ValueError:
                    continue
        return 0
    
    def _avaliar_adequacao(self, max_concurrent: int, calls_per_second: int) -> str:
        """Avalia se a configuração é adequada."""
        if calls_per_second > 4:
            return "CRÍTICO"
        
        if max_concurrent == 0 and calls_per_second == 0:
            return "PROBLEMÁTICO"
        
        # Regra: max_concurrent não deve exceder muito calls_per_second
        if max_concurrent > 0 and calls_per_second > 0:
            ratio = max_concurrent / calls_per_second
            if ratio > 4:  # Mais de 4x pode sobrecarregar
                return "PROBLEMÁTICO"
        
        if max_concurrent > 20:  # Muito alto independentemente
            return "CRÍTICO"
        
        return "ADEQUADO"
    
    def gerar_relatorio(self) -> str:
        """Gera relatório completo da análise."""
        # Analisa arquivos Python relevantes
        python_files = []
        for pattern in ["*.py", "src/*.py", "**/*.py"]:
            python_files.extend(self.workspace_path.glob(pattern))
        
        # Remove arquivos de teste e backup
        python_files = [f for f in python_files if not any(x in str(f) for x in ['test_', '__pycache__', '.pyc', 'Backup/', 'backup'])]
        
        analises = []
        for arquivo in python_files[:20]:  # Limita para os primeiros 20 arquivos
            analise = self.analisar_arquivo(arquivo)
            if analise.tem_rate_limiting or analise.problemas or 'client' in arquivo.read_text(encoding='utf-8', errors='ignore').lower():
                analises.append(analise)
        
        # Analisa concorrência
        configs_concorrencia = self.analisar_concorrencia_global()
        
        # Gera relatório
        relatorio = []
        relatorio.append(" RELATÓRIO DE ANÁLISE DE RATE LIMITING GLOBAL")
        relatorio.append("=" * 70)
        relatorio.append("")
        
        # Resumo executivo
        total_arquivos = len(analises)
        com_rate_limiting = len([a for a in analises if a.tem_rate_limiting])
        com_problemas_criticos = len([a for a in analises if any('CRÍTICO' in p for p in a.problemas)])
        score_medio = sum(a.score_conformidade for a in analises) / max(1, len(analises))
        
        relatorio.append("📊 RESUMO EXECUTIVO")
        relatorio.append(f"   📁 Arquivos analisados: {total_arquivos}")
        relatorio.append(f"   ✅ Com rate limiting: {com_rate_limiting}/{total_arquivos}")
        relatorio.append(f"   ❌ Com problemas críticos: {com_problemas_criticos}")
        relatorio.append(f"   🎯 Score médio de conformidade: {score_medio:.1f}/100")
        relatorio.append("")
        
        # Status geral
        if score_medio >= 90:
            status = "🟢 EXCELENTE"
        elif score_medio >= 70:
            status = "🟡 BOM"
        elif score_medio >= 50:
            status = "🟠 PRECISA MELHORAR"
        else:
            status = "🔴 CRÍTICO"
        
        relatorio.append(f"🏆 STATUS GERAL: {status}")
        relatorio.append("")
        
        # Análise de configurações de concorrência
        relatorio.append("⚙️ CONFIGURAÇÕES DE CONCORRÊNCIA")
        relatorio.append("-" * 50)
        
        for config in configs_concorrencia:
            icon = "✅" if config.adequacao == "ADEQUADO" else "⚠️" if config.adequacao == "PROBLEMÁTICO" else "❌"
            relatorio.append(f"{icon} {config.arquivo}")
            relatorio.append(f"    Max Concurrent: {config.max_concurrent}")
            relatorio.append(f"    Calls/Second: {config.calls_per_second}")
            relatorio.append(f"    Status: {config.adequacao}")
            relatorio.append("")
        
        # Análise detalhada por arquivo
        relatorio.append("📋 ANÁLISE DETALHADA POR ARQUIVO")
        relatorio.append("-" * 50)
        
        for analise in sorted(analises, key=lambda x: x.score_conformidade):
            icon = "✅" if analise.score_conformidade >= 80 else "⚠️" if analise.score_conformidade >= 60 else "❌"
            relatorio.append(f"{icon} {analise.arquivo} (Score: {analise.score_conformidade}/100)")
            
            if analise.funcoes_usadas:
                relatorio.append(f"    🔧 Funções: {', '.join(analise.funcoes_usadas)}")
            
            if analise.calls_per_second_configs:
                relatorio.append(f"    ⚡ Calls/s: {', '.join(analise.calls_per_second_configs)}")
            
            if analise.problemas:
                for problema in analise.problemas:
                    tipo_icon = "🚨" if "CRÍTICO" in problema else "⚠️" if "ALERTA" in problema else "ℹ️"
                    relatorio.append(f"    {tipo_icon} {problema}")
            
            if analise.recomendacoes:
                for rec in analise.recomendacoes:
                    relatorio.append(f"    💡 {rec}")
            
            relatorio.append("")
        
        # Recomendações globais
        relatorio.append("🎯 RECOMENDAÇÕES GLOBAIS")
        relatorio.append("-" * 30)
        
        # Análise de problemas comuns
        todos_problemas = [p for a in analises for p in a.problemas]
        problemas_criticos = [p for p in todos_problemas if 'CRÍTICO' in p]
        
        if problemas_criticos:
            relatorio.append("🚨 AÇÕES URGENTES NECESSÁRIAS:")
            for problema in set(problemas_criticos):
                relatorio.append(f"   • {problema}")
            relatorio.append("")
        
        relatorio.append("💡 MELHORIAS RECOMENDADAS:")
        relatorio.append("   • Padronizar calls_per_second=4 em todos os extratores")
        relatorio.append("   • Usar respeitar_limite_requisicoes_async() consistentemente")
        relatorio.append("   • Implementar rate limiting global compartilhado")
        relatorio.append("   • Monitorar taxa real de requisições em produção")
        relatorio.append("   • Considerar circuit breaker para alta concorrência")
        relatorio.append("")
        
        # Configuração ideal recomendada
        relatorio.append("⭐ CONFIGURAÇÃO IDEAL RECOMENDADA")
        relatorio.append("-" * 40)
        relatorio.append("   📌 calls_per_second: 4 (global)")
        relatorio.append("   📌 max_concurrent: 8 (balanceado)")
        relatorio.append("   📌 timeout: 45s (otimizado)")
        relatorio.append("   📌 rate_limiting: respeitar_limite_requisicoes_async()")
        relatorio.append("   📌 monitoring: métricas de taxa real")
        relatorio.append("")
        
        return "\\n".join(relatorio)

def main():
    """Função principal do verificador."""
    print("🚀 VERIFICADOR DE RATE LIMITING GLOBAL - OMIE V3")
    print("=" * 60)
    
    workspace_path = os.path.dirname(os.path.abspath(__file__))
    verificador = RateLimitingVerifier(workspace_path)
    
    try:
        relatorio = verificador.gerar_relatorio()
        
        # Salva relatório em arquivo
        relatorio_path = Path(workspace_path) / "RELATORIO_RATE_LIMITING.md"
        relatorio_path.write_text(relatorio, encoding='utf-8')
        
        # Mostra relatório
        print(relatorio)
        print(f"\\n💾 Relatório salvo em: {relatorio_path}")
        
        # Verifica se há problemas críticos
        if "🔴 CRÍTICO" in relatorio or "🚨" in relatorio:
            print("\\n⚠️  ATENÇÃO: Problemas críticos detectados! Revisar urgentemente.")
            return False
        else:
            print("\\n✅ Análise concluída. Sistema está em conformidade básica.")
            return True
            
    except Exception as e:
        print(f"❌ Erro durante análise: {e}")
        return False

if __name__ == "__main__":
    sucesso = main()
    sys.exit(0 if sucesso else 1)
