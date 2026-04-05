from datetime import datetime, timedelta

from services.vendas_service import total_vendas, vendas_por_item, resumo_vendas_periodo, vendas_por_hora
from services.estoque_service import itens_estoque_baixo


def indicadores_empresa(empresa=None):
    faturamento_total = total_vendas(empresa)
    vendas_item = vendas_por_item(empresa)
    estoque_baixo = itens_estoque_baixo(empresa)
    hoje = datetime.now().date()
    inicio_atual = (hoje - timedelta(days=6)).isoformat()
    inicio_anterior = (hoje - timedelta(days=13)).isoformat()
    fim_anterior = (hoje - timedelta(days=7)).isoformat()

    periodo_atual = resumo_vendas_periodo(empresa, inicio_atual, hoje.isoformat())
    periodo_anterior = resumo_vendas_periodo(empresa, inicio_anterior, fim_anterior)
    pedidos = periodo_atual.get('pedidos') or 0
    ticket_medio = (periodo_atual.get('faturamento') or 0.0) / pedidos if pedidos else 0.0
    faturamento_anterior = periodo_anterior.get('faturamento') or 0.0
    variacao = 0.0
    if faturamento_anterior:
        variacao = ((periodo_atual.get('faturamento') or 0.0) - faturamento_anterior) / faturamento_anterior * 100
    horario_pico = vendas_por_hora(empresa)

    return {
        'faturamento_total': faturamento_total,
        'vendas_por_item': vendas_item,
        'estoque_baixo': estoque_baixo,
        'pedidos_periodo': pedidos,
        'ticket_medio': ticket_medio,
        'variacao_periodo': variacao,
        'horario_pico': horario_pico[0] if horario_pico else None,
    }
