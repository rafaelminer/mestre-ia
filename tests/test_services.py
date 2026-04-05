import pytest
from database.db import init_db, insert_default_data
from services.vendas_service import total_vendas, registrar_venda, listar_vendas
from services.checklist_service import listar_checklist, adicionar_checklist, atualizar_status
from services.estoque_service import listar_estoque, atualizar_item_estoque, itens_estoque_baixo
from ai.analise import AIOperacional


@pytest.fixture(scope='module', autouse=True)
def setup_db():
    init_db()
    insert_default_data()


def test_total_vendas_eh_numerico():
    total = total_vendas('Japatê')
    assert isinstance(total, float)


def test_registrar_venda_novo_item():
    before = len(listar_vendas('Japatê'))
    registrar_venda('Japatê', '2026-04-04', 'Temaki', 1, 30.0)
    after = len(listar_vendas('Japatê'))
    assert after == before + 1


def test_checklist_adicionar_e_atualizar():
    adicionar_checklist('Japatê', 'operacao', 'testar item', 'pendente', '2026-04-04', 'Teste')
    itens = listar_checklist('Japatê', 'operacao')
    assert any(item['tarefa'] == 'testar item' for item in itens)
    item_id = [item['id'] for item in itens if item['tarefa'] == 'testar item'][0]
    atualizar_status(item_id, 'concluido')
    updated = [item for item in listar_checklist('Japatê', 'operacao') if item['id'] == item_id][0]
    assert updated['status'] == 'concluido'


def test_estoque_atualizar_e_verificar_baixo():
    items = listar_estoque('Japatê')
    assert len(items) > 0
    item_id = items[0]['id']
    atualizar_item_estoque(item_id, 1, 10)
    baixo = itens_estoque_baixo('Japatê')
    assert any(i['id'] == item_id for i in baixo)


def test_ai_analisar_dados():
    resultado = AIOperacional.analisar_dados('Japatê')
    assert 'insights' in resultado and 'recomendacoes' in resultado
    assert isinstance(resultado['insights'], list)
