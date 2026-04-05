import json

import pytest

import services.alert_service as alerts


def test_check_and_notify_all(monkeypatch):
    # preparar empresa de teste
    empresa = {'id': 1, 'nome': 'LojaTeste', 'latitude': -23.55, 'longitude': -46.63, 'cidade': 'Cidade X', 'contato': '+551199999999', 'auto_send_plan': 1}

    # mockar funções importadas dentro do módulo alert_service
    monkeypatch.setattr('services.alert_service.obter_empresas_completas', lambda: [empresa])
    monkeypatch.setattr('services.alert_service.obter_empresa', lambda nome: empresa if nome == 'LojaTeste' else None)

    # mockar eventos próximos (método usado internamente por alert_service)
    monkeypatch.setattr('services.alert_service.get_events_with_coords', lambda city, lat, lon: [
        {'id': 'ev1', 'name': 'Feira Teste', 'distance_km': 0.5}
    ])

    called = {'sent': False, 'cache': None}

    def fake_get_cache(emp, key):
        return None

    def fake_set_cache(emp, key, payload):
        called['cache'] = (emp, key, json.loads(payload))

    def fake_whatsapp(number, message, empresa_name=None):
        called['sent'] = True
        return {'status': 'ok', 'to': number}

    monkeypatch.setattr('services.alert_service.get_external_cache', fake_get_cache)
    monkeypatch.setattr('services.alert_service.set_external_cache', fake_set_cache)
    monkeypatch.setattr('services.alert_service.enviar_mensagem_whatsapp', fake_whatsapp)

    resultados = alerts.check_and_notify_all(radius_km=1.0)
    assert isinstance(resultados, list)
    assert any(r.get('empresa') == 'LojaTeste' for r in resultados)
    assert called['sent'] is True
    assert called['cache'] is not None
