#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de verificacao de Compatibilidade entre Modulos
=====================================================

Este script verifica a compatibilidade entre os modulos modificados e as funcões
utilitarias existentes, identificando possiveis problemas de tipos de dados,
funcões faltantes ou redundantes.

Funcionalidades:
- Verifica se todas as funcões importadas existem
- Analisa compatibilidade de tipos de dados
- Identifica funcões redundantes
- Gera relatorio detalhado
"""

import ast
import sys
from pathlib import Path
from typing import Dict, List, Set, Any, Optional, Tuple
import inspect
import importlib.util

# Configuracões
MODULOS_PARA_VERIFICAR = [
    "src/omie_client_async.py",
    "src/extrator_async.py", 
    "src/upload_onedrive.py",
    "src/compactador_resultado.py"
]

UTILS_PATH = "src/utils.py"

class CompatibilityChecker:
    """Verificador de compatibilidade entre modulos."""
    
    def __init__(self):
        self.utils_functions: Dict[str, Any] = {}
        self.imports_map: Dict[str, List[str]] = {}
        self.missing_functions: List[str] = []
        self.type_issues: List[str] = []
        self.redundant_functions: List[str] = []
        
    def extract_function_signatures(self, file_path: str) -> Dict[str, Any]:
        """Extrai assinaturas de funcões de um arquivo Python."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            functions = {}
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Extrai informacões da funcao
                    func_info = {
                        'name': node.name,
                        'args': [arg.arg for arg in node.args.args],
                        'defaults': len(node.args.defaults),
                        'returns': ast.unparse(node.returns) if node.returns else None,
                        'decorators': [ast.unparse(d) for d in node.decorators],
                        'lineno': node.lineno
                    }
                    
                    # Extrai type hints dos argumentos
                    arg_types = {}
                    for arg in node.args.args:
                        if arg.annotation:
                            arg_types[arg.arg] = ast.unparse(arg.annotation)
                    func_info['arg_types'] = arg_types
                    
                    functions[node.name] = func_info
            
            return functions
            
        except Exception as e:
            print(f"Erro ao analisar {file_path}: {e}")
            return {}
    
    def extract_imports(self, file_path: str) -> List[str]:
        """Extrai importacões de um arquivo Python."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and ('utils' in node.module or node.module == 'utils'):
                        for alias in node.names:
                            imports.append(alias.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if 'utils' in alias.name:
                            imports.append(alias.name)
            
            return imports
            
        except Exception as e:
            print(f"Erro ao extrair imports de {file_path}: {e}")
            return []
    
    def check_function_compatibility(self, func1: Dict[str, Any], func2: Dict[str, Any]) -> List[str]:
        """Verifica compatibilidade entre duas funcões."""
        issues = []
        
        # Verifica numero de argumentos
        if len(func1['args']) != len(func2['args']):
            issues.append(f"Numero de argumentos diferente: {len(func1['args'])} vs {len(func2['args'])}")
        
        # Verifica tipos de argumentos
        for arg in func1['args']:
            if arg in func1['arg_types'] and arg in func2['arg_types']:
                if func1['arg_types'][arg] != func2['arg_types'][arg]:
                    issues.append(f"Tipo do argumento '{arg}' diferente: {func1['arg_types'][arg]} vs {func2['arg_types'][arg]}")
        
        # Verifica tipo de retorno
        if func1['returns'] != func2['returns']:
            issues.append(f"Tipo de retorno diferente: {func1['returns']} vs {func2['returns']}")
        
        return issues
    
    def analyze_data_flow(self, file_path: str) -> Dict[str, List[str]]:
        """Analisa fluxo de dados entre funcões."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            data_flow = {}
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                        if func_name not in data_flow:
                            data_flow[func_name] = []
                        
                        # Analisa argumentos passados
                        for arg in node.args:
                            if isinstance(arg, ast.Name):
                                data_flow[func_name].append(f"arg:{arg.id}")
                            elif isinstance(arg, ast.Constant):
                                data_flow[func_name].append(f"const:{type(arg.value).__name__}")
            
            return data_flow
            
        except Exception as e:
            print(f"Erro ao analisar fluxo de dados de {file_path}: {e}")
            return {}
    
    def run_compatibility_check(self) -> Dict[str, Any]:
        """Executa verificacao completa de compatibilidade."""
        print("=== verificacao DE COMPATIBILIDADE ENTRE MoDULOS ===")
        print()
        
        # 1. Extrai funcões do utils.py
        print("1. Analisando utils.py...")
        utils_functions = self.extract_function_signatures(UTILS_PATH)
        print(f"   Encontradas {len(utils_functions)} funcões em utils.py")
        
        # 2. Verifica cada modulo
        results = {}
        
        for module_path in MODULOS_PARA_VERIFICAR:
            print(f"\n2. Analisando {module_path}...")
            
            # Extrai importacões
            imports = self.extract_imports(module_path)
            print(f"   Imports do utils encontrados: {imports}")
            
            # Verifica se funcões existem
            missing = []
            for func_name in imports:
                if func_name not in utils_functions:
                    missing.append(func_name)
            
            if missing:
                print(f"   ⚠️  FUNcÕES FALTANTES: {missing}")
                self.missing_functions.extend(missing)
            else:
                print(f"   ✅ Todas as funcões importadas existem")
            
            # Analisa fluxo de dados
            data_flow = self.analyze_data_flow(module_path)
            
            results[module_path] = {
                'imports': imports,
                'missing_functions': missing,
                'data_flow': data_flow
            }
        
        # 3. Verifica compatibilidade de tipos
        print("\n3. Verificando compatibilidade de tipos...")
        self.check_type_compatibility(results, utils_functions)
        
        # 4. Identifica possiveis redundâncias
        print("\n4. Verificando redundâncias...")
        self.check_redundancies(results, utils_functions)
        
        return results
    
    def check_type_compatibility(self, results: Dict[str, Any], utils_functions: Dict[str, Any]):
        """Verifica compatibilidade de tipos entre modulos."""
        
        # Verifica tipos especificos conhecidos
        type_checks = {
            'gerar_xml_path': {
                'expected_return': 'Tuple[Path, Path]',
                'expected_args': ['str', 'str', 'str', 'str']
            },
            'marcar_como_erro': {
                'expected_return': 'None',
                'expected_args': ['str', 'str', 'str']
            },
            'marcar_como_baixado': {
                'expected_return': 'None', 
                'expected_args': ['str', 'str', 'Path', 'bool', 'int']
            }
        }
        
        for func_name, expected in type_checks.items():
            if func_name in utils_functions:
                actual = utils_functions[func_name]
                
                # Verifica tipo de retorno
                if actual['returns'] != expected['expected_return']:
                    issue = f"Tipo de retorno incompativel em {func_name}: esperado {expected['expected_return']}, atual {actual['returns']}"
                    self.type_issues.append(issue)
                    print(f"   ⚠️  {issue}")
                
                # Verifica argumentos basicos
                if len(actual['args']) < len(expected['expected_args']) - 1:  # -1 para argumentos opcionais
                    issue = f"Numero de argumentos insuficiente em {func_name}: esperado minimo {len(expected['expected_args'])-1}, atual {len(actual['args'])}"
                    self.type_issues.append(issue)
                    print(f"   ⚠️  {issue}")
        
        if not self.type_issues:
            print("   ✅ Nenhum problema de compatibilidade de tipos encontrado")
    
    def check_redundancies(self, results: Dict[str, Any], utils_functions: Dict[str, Any]):
        """Verifica possiveis redundâncias entre modulos."""
        
        # Funcões que podem ser redundantes
        all_defined_functions = set()
        
        for module_path in MODULOS_PARA_VERIFICAR:
            try:
                module_functions = self.extract_function_signatures(module_path)
                all_defined_functions.update(module_functions.keys())
            except Exception:
                continue
        
        # Verifica se ha funcões similares em utils
        similar_functions = []
        for func_name in all_defined_functions:
            for utils_func in utils_functions.keys():
                if func_name.lower() in utils_func.lower() or utils_func.lower() in func_name.lower():
                    if func_name != utils_func:
                        similar_functions.append((func_name, utils_func))
        
        if similar_functions:
            print(f"   ⚠️  Possiveis redundâncias encontradas:")
            for func1, func2 in similar_functions:
                print(f"      - {func1} <-> {func2}")
                self.redundant_functions.append(f"{func1} <-> {func2}")
        else:
            print("   ✅ Nenhuma redundância obvia encontrada")
    
    def generate_report(self, results: Dict[str, Any]) -> str:
        """Gera relatorio detalhado da verificacao."""
        
        report = []
        report.append("=" * 80)
        report.append("RELAToRIO DE COMPATIBILIDADE ENTRE MoDULOS")
        report.append("=" * 80)
        report.append("")
        
        # Resumo executivo
        report.append("RESUMO EXECUTIVO:")
        report.append(f"- Modulos verificados: {len(MODULOS_PARA_VERIFICAR)}")
        report.append(f"- Funcões faltantes: {len(self.missing_functions)}")
        report.append(f"- Problemas de tipo: {len(self.type_issues)}")
        report.append(f"- Possiveis redundâncias: {len(self.redundant_functions)}")
        report.append("")
        
        # Problemas criticos
        if self.missing_functions:
            report.append("🔴 PROBLEMAS CRiTICOS - FUNcÕES FALTANTES:")
            for func in self.missing_functions:
                report.append(f"   - {func}")
            report.append("")
        
        # Problemas de tipo
        if self.type_issues:
            report.append("🟡 PROBLEMAS DE COMPATIBILIDADE DE TIPOS:")
            for issue in self.type_issues:
                report.append(f"   - {issue}")
            report.append("")
        
        # Redundâncias
        if self.redundant_functions:
            report.append("🔵 POSSiVEIS REDUNDÂNCIAS:")
            for redundancy in self.redundant_functions:
                report.append(f"   - {redundancy}")
            report.append("")
        
        # Detalhes por modulo
        report.append("DETALHES POR MoDULO:")
        report.append("-" * 40)
        
        for module_path, data in results.items():
            report.append(f"\n{module_path}:")
            report.append(f"   Imports: {data['imports']}")
            report.append(f"   Funcões faltantes: {data['missing_functions']}")
            
            if data['data_flow']:
                report.append(f"   Fluxo de dados (top 5):")
                for func, calls in list(data['data_flow'].items())[:5]:
                    report.append(f"      {func}: {calls}")
        
        # Recomendacões
        report.append("\n" + "=" * 80)
        report.append("RECOMENDAcÕES:")
        report.append("=" * 80)
        
        if self.missing_functions:
            report.append("\n1. CORRIGIR FUNcÕES FALTANTES:")
            report.append("   - Implementar funcões faltantes no utils.py")
            report.append("   - Ou atualizar imports nos modulos")
        
        if self.type_issues:
            report.append("\n2. CORRIGIR INCOMPATIBILIDADES DE TIPOS:")
            report.append("   - Verificar e ajustar type hints")
            report.append("   - Garantir consistência nos tipos de retorno")
        
        if self.redundant_functions:
            report.append("\n3. AVALIAR REDUNDÂNCIAS:")
            report.append("   - Considerar consolidar funcões similares")
            report.append("   - Centralizar funcionalidades em utils.py")
        
        report.append("\n✅ STATUS: " + ("APROVADO" if not self.missing_functions and not self.type_issues else "REQUER ATENcoO"))
        
        return "\n".join(report)

def main():
    """funcao principal do script."""
    checker = CompatibilityChecker()
    results = checker.run_compatibility_check()
    
    # Gera relatorio
    report = checker.generate_report(results)
    
    # Salva relatorio em arquivo
    report_path = Path("relatorio_compatibilidade.txt")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n📄 Relatorio salvo em: {report_path}")
    print("\n" + "=" * 80)
    print(report)

if __name__ == "__main__":
    main()
