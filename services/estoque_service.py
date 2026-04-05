from database.queries import obter_estoque, atualizar_estoque_item, verificar_estoque_baixo


def listar_estoque(empresa=None):
    return obter_estoque(empresa)


def atualizar_item_estoque(item_id, quantidade, minimo):
    atualizar_estoque_item(item_id, quantidade, minimo)


def itens_estoque_baixo(empresa=None):
    return verificar_estoque_baixo(empresa)
