import pytest
from fastapi.testclient import TestClient
from interface.api import app


def test_health():
    with TestClient(app) as client:
        response = client.get('/health')
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'


def test_vendas_endpoints():
    with TestClient(app) as client:
        response = client.get('/vendas')
        assert response.status_code == 200

        response = client.post('/vendas', json={
            'empresa': 'Japatê',
            'data': '2026-04-05',
            'item': 'Teste',
            'quantidade': 2,
            'total': 50.0
        })
        assert response.status_code == 200

        response = client.get('/vendas/total', params={'empresa': 'Japatê'})
        assert response.status_code == 200
        assert 'total' in response.json()


def test_whatsapp_endpoint():
    with TestClient(app) as client:
        response = client.post('/whatsapp/send', json={
            'numero': '+5511999999999',
            'mensagem': 'Teste de alerta operacional',
            'empresa': 'Japatê'
        })
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'


def test_empresas_endpoint():
    with TestClient(app) as client:
        response = client.post('/empresas', json={
            'nome': 'Nova Empresa',
            'tipo': 'restaurante',
            'ativa': True
        })
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'

        response = client.get('/empresas')
        assert response.status_code == 200
        assert 'Nova Empresa' in response.json()

        response = client.get('/empresas/detalhes')
        assert response.status_code == 200
        assert any(item['nome'] == 'Nova Empresa' for item in response.json())


def test_analise_endpoint():
    with TestClient(app) as client:
        response = client.get('/analise', params={'empresa': 'Japatê'})
        assert response.status_code == 200
        assert 'insights' in response.json()


