import sqlite3
import os

def verificar_status():
    print("=== STATUS DOS REGISTROS ===")
    
    # Verificar banco de dados
    if os.path.exists("omie.db"):
        conn = sqlite3.connect("omie.db")
        cursor = conn.cursor()
        
        # Contar registros de 01/05/2025
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN xml_baixado = 1 THEN 1 ELSE 0 END) as baixados,
                SUM(CASE WHEN xml_baixado = 0 THEN 1 ELSE 0 END) as pendentes
            FROM notas 
            WHERE strftime('%d/%m/%Y', data_emissao) = '01/05/2025'
        """)
        
        resultado = cursor.fetchone()
        total, baixados, pendentes = resultado
        
        print(f"Data: 01/05/2025")
        print(f"Total: {total:,}")
        print(f"Baixados: {baixados:,}")
        print(f"Pendentes: {pendentes:,}")
        
        conn.close()
    else:
        print("Banco de dados não encontrado!")
    
    # Verificar arquivos XML
    resultado_dir = "C:/milson/extrator_omie_v3/resultado"
    if os.path.exists(resultado_dir):
        xml_count = 0
        for root, dirs, files in os.walk(resultado_dir):
            xml_count += len([f for f in files if f.endswith('.xml')])
        print(f"Arquivos XML: {xml_count:,}")
    else:
        print("Diretório resultado não encontrado!")

if __name__ == "__main__":
    verificar_status()
