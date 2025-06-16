from datetime import datetime, timedelta

def nota_fiscal_excedeu_5_dias(data_emissao_str):
    """
    Verifica se a data de emissão da nota fiscal excedeu 5 dias em relação à data atual.

    Args:
        data_emissao_str (str): A data de emissão da nota fiscal no formato 'AAAA-MM-DD'.

    Returns:
        bool: True se a data excedeu 5 dias, False caso contrário.
              Retorna False se a data for inválida.
    """
    try:
        data_emissao = datetime.strptime(data_emissao_str, '%Y-%m-%d').date()
        hoje = datetime.now().date()
        diferenca = hoje - data_emissao
        return diferenca > timedelta(days=5)
    except ValueError:
        return False # Data inválida