from typing import List, Optional
from database.queries import listar_empresas, listar_empresas_completas, adicionar_empresa
from database.queries import obter_empresa_por_nome, atualizar_local_empresa_por_id, atualizar_local_empresa_por_nome, atualizar_contato_empresa_por_nome


def obter_empresas() -> List[str]:
    return listar_empresas()


def obter_empresas_completas() -> List[dict]:
    return listar_empresas_completas()


def criar_empresa(nome: str, tipo: str = 'restaurante', ativa: bool = True):
    adicionar_empresa(nome, tipo, ativa)


def obter_empresa(nome: str) -> Optional[dict]:
    return obter_empresa_por_nome(nome)


def atualizar_local_empresa(empresa_id: int = None, nome: str = None, latitude: float = None, longitude: float = None, cidade: str = None, endereco: str = None):
    if empresa_id:
        atualizar_local_empresa_por_id(empresa_id, latitude, longitude, cidade, endereco)
    elif nome:
        atualizar_local_empresa_por_nome(nome, latitude, longitude, cidade, endereco)
    else:
        raise ValueError('Informe empresa_id ou nome para atualizar a localização')


def atualizar_contato_empresa(nome: str = None, contato: str = None):
    if not nome:
        raise ValueError('Informe o nome da empresa para atualizar contato')
    atualizar_contato_empresa_por_nome(nome, contato)


def atualizar_auto_send_empresa(nome: str, enabled: bool):
    if not nome:
        raise ValueError('Informe o nome da empresa para atualizar configuração')
    from database.queries import atualizar_auto_send_empresa_por_nome
    atualizar_auto_send_empresa_por_nome(nome, enabled)
