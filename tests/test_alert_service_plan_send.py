import json

import services.alert_service as alerts


def test_send_plan_on_strong_impact(monkeypatch):
    empresa = {'id':1, 'nome':'LojaTeste', 'latitude': -23.55, 'longitude': -46.63, 'cidade':'Cidade X', 'contato': '+551199999999', 'auto_send_plan': 1}
    monkeypatch.setattr('services.alert_service.obter_empresas_completas', lambda: [empresa])
    monkeypatch.setattr('services.alert_service.obter_empresa', lambda nome: empresa if nome == 'LojaTeste' else None)
    monkeypatch.setattr('services.alert_service.get_events_with_coords', lambda city, lat, lon: [{'id':'ev100', 'name':'Show', 'distance_km': 0.3}])
    monkeypatch.setattr('services.alert_service.get_external_cache', lambda emp, key: None)

    captured = {}
    def fake_set_cache(emp, key, payload):
        captured['cache'] = (emp, key, json.loads(payload))
    monkeypatch.setattr('services.alert_service.set_external_cache', fake_set_cache)

    def fake_fetch(empresa_name):
        return {'impact_score': 0.6, 'reasons':['evento'], 'weather':{}, 'events':[{'name': 'Show', 'distance_km':0.3}]}
    monkeypatch.setattr('services.alert_service.fetch_and_cache_impact', fake_fetch)

    def fake_generate(impact, empresa_name=None):
        return {'impact_score': 0.6, 'impact_summary':'Aumento forte', 'actions_preparation':['A1'], 'actions_immediate':['A2'], 'templates':{}}
    monkeypatch.setattr('services.alert_service.generate_action_plan', fake_generate)

    sent = {}
    def fake_whatsapp(number, message, empresa_name=None):
        sent['number'] = number
        sent['message'] = message
        return {'status':'ok'}
    monkeypatch.setattr('services.alert_service.enviar_mensagem_whatsapp', fake_whatsapp)

    res = alerts.check_and_notify_company('LojaTeste', radius_km=1.0)
    assert sent.get('number') == '+551199999999'
    assert 'Plano de Ação' in sent.get('message')
    assert 'Ações no dia' in sent.get('message') or 'Antes do dia' in sent.get('message')
