import json

import pytest

import services.external_service as ext


class DummyResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_get_weather_forecast_mocked(monkeypatch):
    payload = {
        'daily': {
            'time': ['2026-04-03', '2026-04-04'],
            'temperature_2m_max': [30, 31],
            'temperature_2m_min': [20, 21],
            'precipitation_sum': [0.0, 10.0],
            'precipitation_probability_mean': [5.0, 80.0],
        }
    }

    monkeypatch.setattr('services.external_service.httpx.get', lambda *a, **k: DummyResp(payload))
    res = ext.get_weather_forecast(12.34, 56.78, days=2)
    assert res['source'] == 'open-meteo'
    assert len(res['daily']) == 2
    assert res['daily'][1]['precipitation_sum'] == 10.0


def test_get_city_events_no_token(monkeypatch):
    # sem token Eventbrite deve retornar lista vazia
    monkeypatch.delenv('EVENTBRITE_TOKEN', raising=False)
    res = ext.get_city_events('São Paulo')
    assert res == []


def test_geocode_address_mocked(monkeypatch):
    payload = [{'lat': '12.34', 'lon': '56.78', 'display_name': 'Lugar Teste'}]
    monkeypatch.setattr('services.external_service.httpx.get', lambda *a, **k: DummyResp(payload))
    geo = ext.geocode_address('Rua Exemplo 123')
    assert geo is not None
    assert abs(geo['latitude'] - 12.34) < 1e-6
    assert 'display_name' in geo


def test_assess_location_impact_rain(monkeypatch):
    # forçar retorno de previsão com chuva forte
    monkeypatch.setattr('services.external_service.get_weather_forecast', lambda lat, lon, days=3: {
        'daily': [{'date': '2026-04-03', 'precipitation_sum': 12.0, 'precipitation_probability_mean': 75}]
    })
    monkeypatch.setattr('services.external_service.get_city_events', lambda city, start_date=None, end_date=None: [])
    res = ext.assess_location_impact(12.0, 34.0, 'Cidade X', days=1)
    assert res['impact_score'] < 0
    assert any('Chuva prevista' in r for r in res['reasons'])


def test_fetch_and_cache_impact(monkeypatch):
    # simular empresa retornada
    monkeypatch.setattr('services.empresa_service.obter_empresa', lambda nome: {'nome': nome, 'latitude': 12.0, 'longitude': 34.0, 'cidade': 'Cidade X'})
    # simular avaliação de impacto
    sample = {'impact_score': 0.2, 'reasons': ['evento teste'], 'weather': {}, 'events': []}
    monkeypatch.setattr('services.external_service.assess_location_impact', lambda lat, lon, city, days=3: sample)

    called = {}

    def fake_set_external_cache(empresa, key, payload):
        called['empresa'] = empresa
        called['key'] = key
        called['payload'] = payload

    monkeypatch.setattr('database.queries.set_external_cache', fake_set_external_cache)
    res = ext.fetch_and_cache_impact('MinhaEmpresa')
    assert res == sample
    assert called.get('empresa') == 'MinhaEmpresa'
    assert called.get('key') == 'impact'
    assert json.loads(called.get('payload')) == sample


def test_haversine_and_events_distance(monkeypatch):
    # haversine: distância pequena entre pontos próximos
    d = ext.haversine(-23.55, -46.63, -23.560, -46.640)
    assert d is not None
    assert 0 < d < 5

    # eventos: geocodificação mockada, o primeiro evento será geocodificado, o segundo não
    monkeypatch.setattr('services.external_service.get_city_events', lambda city, start_date=None, end_date=None: [
        {'id': '1', 'name': 'Evento A', 'start': None, 'end': None, 'url': None},
        {'id': '2', 'name': 'Evento B', 'start': None, 'end': None, 'url': None},
    ])

    def fake_geocode(query):
        if 'Evento A' in query:
            return {'latitude': -23.55, 'longitude': -46.63, 'display_name': 'Local A'}
        return None

    monkeypatch.setattr('services.external_service.geocode_with_cache', fake_geocode)
    evs = ext.get_events_with_coords('São Paulo', store_lat=-23.55, store_lon=-46.63)
    assert len(evs) == 2
    assert evs[0].get('distance_km') == 0.0
    assert evs[1].get('distance_km') is None
