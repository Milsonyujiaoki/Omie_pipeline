#!/usr/bin/env python3
"""
Teste do Sistema Extrator Adaptativo Omie V3

Este script testa a funcionalidade de seleção automática de extrator
baseada no contexto do banco de dados e configurações.

Funcionalidades testadas:
1. Detecção automática do volume de dados
2. Seleção de estratégia de extração otimizada
3. Configuração dinâmica de parâmetros
4. Logging detalhado do processo de seleção

Uso:
    python teste_extrator_adaptativo.py [--modo_performance critico|auto]
"""

import sys
import os
import logging
import sqlite3
from pathlib import Path
from typing import Dict, Any

# Adicionar diretório do projeto ao Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import (
    escolher_extrator_otimo,
    executar_extrator_adaptativo,
    carregar_configuracoes,
    configurar_logging
)

def criar_banco_teste(db_path: str, num_registros: int, num_pendentes: int, num_erros: int) -> None:
    """
    Cria um banco de teste com dados simulados para testar a seleção.
    
    Args:
        db_path: Caminho do banco de dados
        num_registros: Total de registros
        num_pendentes: Registros pendentes (xml_baixado=0, erro=0)
        num_erros: Registros com erro (erro=1)
    """
    print(f"📊 Criando banco de teste: {num_registros:,} registros, {num_pendentes:,} pendentes, {num_erros:,} erros")
    
    # Remover banco existente
    if Path(db_path).exists():
        Path(db_path).unlink()
    
    # Criar banco e tabela
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Criar tabela
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notas (
                id INTEGER PRIMARY KEY,
                numero_nf TEXT,
                xml_baixado INTEGER DEFAULT 0,
                erro INTEGER DEFAULT 0,
                data_emissao TEXT,
                valor REAL
            )
        """)
        
        # Inserir registros simulados
        # Registros com XML baixado (sucesso)
        num_sucesso = num_registros - num_pendentes - num_erros
        if num_sucesso > 0:
            cursor.executemany(
                "INSERT INTO notas (numero_nf, xml_baixado, erro) VALUES (?, 1, 0)",
                [(f"NF-SUCESSO-{i:06d}",) for i in range(num_sucesso)]
            )
        
        # Registros pendentes
        if num_pendentes > 0:
            cursor.executemany(
                "INSERT INTO notas (numero_nf, xml_baixado, erro) VALUES (?, 0, 0)",
                [(f"NF-PENDENTE-{i:06d}",) for i in range(num_pendentes)]
            )
        
        # Registros com erro
        if num_erros > 0:
            cursor.executemany(
                "INSERT INTO notas (numero_nf, xml_baixado, erro) VALUES (?, 0, 1)",
                [(f"NF-ERRO-{i:06d}",) for i in range(num_erros)]
            )
        
        conn.commit()
    
    print(f"✅ Banco de teste criado com sucesso")


def testar_cenario(nome: str, num_registros: int, num_pendentes: int, num_erros: int, 
                  modo_performance: str = "auto") -> str:
    """
    Testa um cenário específico e retorna o tipo de extrator selecionado.
    
    Args:
        nome: Nome do cenário
        num_registros: Total de registros
        num_pendentes: Registros pendentes  
        num_erros: Registros com erro
        modo_performance: Modo de performance (auto, critico)
        
    Returns:
        str: Tipo de extrator selecionado
    """
    print(f"\n🧪 TESTANDO CENÁRIO: {nome}")
    print(f"   📈 Registros: {num_registros:,}")
    print(f"   ⏳ Pendentes: {num_pendentes:,}")
    print(f"   ❌ Erros: {num_erros:,}")
    print(f"   ⚡ Modo: {modo_performance}")
    
    # Criar banco de teste
    db_path = "teste_omie.db"
    criar_banco_teste(db_path, num_registros, num_pendentes, num_erros)
    
    # Configurar para teste
    config = {
        "modo_performance": modo_performance,
        "app_key": "test_key",
        "app_secret": "test_secret",
        "calls_per_second": 4
    }
    
    # Testar seleção
    tipo_selecionado = escolher_extrator_otimo(config, db_path)
    print(f"   🎯 SELECIONADO: {tipo_selecionado}")
    
    # Limpar banco de teste
    if Path(db_path).exists():
        Path(db_path).unlink()
    
    return tipo_selecionado


def main():
    """Função principal de teste."""
    print("🚀 SISTEMA DE TESTE DO EXTRATOR ADAPTATIVO OMIE V3")
    print("=" * 60)
    
    # Configurar logging
    configurar_logging()
    
    # Cenários de teste
    cenarios = [
        # Nome, Total, Pendentes, Erros, Modo
        ("Volume Baixo - Normal", 1000, 50, 10, "auto"),
        ("Volume Médio - Normal", 50000, 15000, 100, "auto"),
        ("Volume Alto - Normal", 200000, 120000, 500, "auto"),
        ("API Instável - Muitos Erros", 10000, 5000, 2000, "auto"),
        ("Performance Crítica", 50000, 30000, 100, "critico"),
        ("Primeira Execução", 0, 0, 0, "auto"),  # Banco não existe
    ]
    
    resultados = {}
    
    print("\n📋 EXECUTANDO CENÁRIOS DE TESTE...")
    
    for nome, total, pendentes, erros, modo in cenarios:
        try:
            if "Primeira Execução" in nome:
                # Testar com banco inexistente
                if Path("teste_omie.db").exists():
                    Path("teste_omie.db").unlink()
                config = {"modo_performance": modo}
                resultado = escolher_extrator_otimo(config, "teste_omie.db")
                print(f"\n🧪 TESTANDO CENÁRIO: {nome}")
                print(f"   🎯 SELECIONADO: {resultado}")
                resultados[nome] = resultado
            else:
                resultado = testar_cenario(nome, total, pendentes, erros, modo)
                resultados[nome] = resultado
                
        except Exception as e:
            print(f"   ❌ ERRO: {e}")
            resultados[nome] = f"ERRO: {e}"
    
    # Relatório final
    print(f"\n📊 RELATÓRIO FINAL DOS TESTES")
    print("=" * 60)
    
    for cenario, resultado in resultados.items():
        status = "✅" if not resultado.startswith("ERRO") else "❌"
        print(f"{status} {cenario:<30} → {resultado}")
    
    # Validação dos resultados esperados
    print(f"\n VALIDAÇÃO DOS RESULTADOS")
    print("-" * 40)
    
    validacoes = [
        ("Volume Baixo - Normal", "async_padrao"),
        ("Volume Médio - Normal", "async_otimizado"),
        ("Volume Alto - Normal", "async_otimizado"),
        ("API Instável - Muitos Erros", "sincrono_confiavel"),
        ("Performance Crítica", "async_maximo"),
        ("Primeira Execução", "async_padrao"),
    ]
    
    testes_corretos = 0
    total_testes = len(validacoes)
    
    for cenario, esperado in validacoes:
        obtido = resultados.get(cenario, "ERRO")
        correto = obtido == esperado
        
        if correto:
            testes_corretos += 1
            status = "✅"
        else:
            status = "❌"
        
        print(f"{status} {cenario:<30} | Esperado: {esperado:<20} | Obtido: {obtido}")
    
    # Resultado final
    print(f"\n🎯 RESULTADO FINAL: {testes_corretos}/{total_testes} testes corretos")
    
    if testes_corretos == total_testes:
        print(" TODOS OS TESTES PASSARAM! Sistema adaptativo funcionando perfeitamente.")
    else:
        print("⚠️  Alguns testes falharam. Verifique a lógica de seleção.")
    
    return testes_corretos == total_testes


if __name__ == "__main__":
    sucesso = main()
    sys.exit(0 if sucesso else 1)
