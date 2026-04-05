import services.external_service as ext


def test_generate_action_plan_positive():
    impact = {
        'impact_score': 0.6,
        'reasons': ['Evento próximo'],
        'weather': {'daily': []},
        'events': [{'name': 'Feira', 'distance_km': 0.5, 'start': None}]
    }
    plan = ext.generate_action_plan(impact)
    assert 'aumento' in plan['impact_summary'].lower() or 'aument' in plan['impact_summary'].lower()
    combined = ' '.join(plan.get('actions_immediate', []) + plan.get('actions_preparation', []))
    assert any(x in combined.lower() for x in ['equipe', 'combo', 'combo', 'venda rápida', 'take-away'])


def test_generate_action_plan_rain_negative():
    impact = {
        'impact_score': -0.5,
        'reasons': ['Chuva prevista'],
        'weather': {'daily': [{'date': '2026-04-03', 'precipitation_sum': 12.0, 'precipitation_probability_mean': 80}]},
        'events': []
    }
    plan = ext.generate_action_plan(impact)
    assert 'redu' in plan['impact_summary'].lower() or 'redução' in plan['impact_summary'].lower()
    combined = ' '.join(plan.get('actions_immediate', []) + plan.get('actions_preparation', []))
    assert any(x in combined.lower() for x in ['delivery', 'entrega', 'perecíveis', 'reduzir'])
