from database.queries import (
    obter_vendas,
    obter_total_vendas,
    obter_vendas_por_item,
    obter_vendas_recentes,
    obter_resumo_vendas_periodo,
    obter_vendas_por_hora,
    adicionar_venda,
    adicionar_vendas_em_lote,
    adicionar_vendas_detalhadas_em_lote,
)


def listar_vendas(empresa=None):
    return obter_vendas(empresa)


def total_vendas(empresa=None):
    return obter_total_vendas(empresa)


def vendas_por_item(empresa=None):
    return obter_vendas_por_item(empresa)


def registrar_venda(empresa, data, item, quantidade, total):
    adicionar_venda(empresa, data, item, quantidade, total)


def registrar_vendas_em_lote(vendas):
    return adicionar_vendas_em_lote(vendas)


def listar_vendas_recentes(empresa=None, limite=20):
    return obter_vendas_recentes(empresa, limite)


def registrar_vendas_detalhadas(vendas):
    return adicionar_vendas_detalhadas_em_lote(vendas)


def resumo_vendas_periodo(empresa=None, data_inicio=None, data_fim=None):
    return obter_resumo_vendas_periodo(empresa, data_inicio, data_fim)


def vendas_por_hora(empresa=None):
    return obter_vendas_por_hora(empresa)
