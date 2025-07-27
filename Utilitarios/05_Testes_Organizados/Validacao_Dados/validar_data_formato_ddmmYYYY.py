def validar_data_formato(data: str, formato: str) -> bool:
    """
    Valida se uma data esta no formato especificado.
    
    Args:
        data: String da data para validacoo
        formato: Formato esperado (ex: '%Y-%m-%d', '%d/%m/%Y')
        
    Returns:
        True se a data esta no formato correto, False caso contrario
        
    Examples:
        >>> validar_data_formato("2025-07-17", "%Y-%m-%d")
        True
        >>> validar_data_formato("17/07/2025", "%Y-%m-%d")
        False
    """
    if not data or not formato:
        return False
    
    try:
        datetime.strptime(data, formato)
        return True
    except ValueError:
        return False
    except Exception as e:
        logger.warning(f"[DATA] Erro na validacoo de formato: {e}")
        return False
