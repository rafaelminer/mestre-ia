from database.queries import obter_checklist, atualizar_status_checklist, adicionar_item_checklist


def listar_checklist(empresa=None, tipo=None):
    return obter_checklist(empresa, tipo)


def atualizar_status(item_id, status):
    if status not in ['pendente', 'em andamento', 'concluido']:
        raise ValueError('Status inválido')
    atualizar_status_checklist(item_id, status)


def adicionar_checklist(empresa, tipo, tarefa, status, data, responsavel=None):
    adicionar_item_checklist(empresa, tipo, tarefa, status, data, responsavel)
