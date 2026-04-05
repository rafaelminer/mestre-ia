from fastapi.testclient import TestClient
import json

from interface.api import app


def test_api_action_plan_endpoint(monkeypatch):
    sample_impact = {
        'impact_score': 0.5,
        'reasons': ['Evento próximo'],
        'weather': {'daily': []},
        'events': [{'name': 'Show', 'distance_km': 0.5}]
    }

    # monkeypatch the service that would call external APIs
    monkeypatch.setattr('services.external_service.fetch_and_cache_impact', lambda *a, **k: sample_impact)

    client = TestClient(app)
    resp = client.get('/external/action_plan', params={'empresa': 'MinhaEmpresa'})
    assert resp.status_code == 200
    data = resp.json()
    assert 'impact_score' in data
    assert data['impact_score'] == round(sample_impact['impact_score'], 2)
    assert 'actions_preparation' in data
    assert 'actions_immediate' in data
