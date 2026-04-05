import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import math
import json

import httpx
from urllib.parse import quote as urlquote

LAST_WEATHER_ERROR = None
LAST_EVENTS_ERROR = None
LAST_GEOCODE_ERROR = None


def get_weather_forecast(latitude: float, longitude: float, days: int = 3) -> Dict:
    """Consulta previsões do Open-Meteo (sem necessidade de chave).

    Retorna um resumo diário com temperatura máxima/mínima e precipitação.
    Em caso de erro de rede, retorna um dicionário com 'source': 'simulated'.
    """
    global LAST_WEATHER_ERROR
    LAST_WEATHER_ERROR = None
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={latitude}&longitude={longitude}"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_mean"
            f"&forecast_days={days}&timezone=auto"
        )
        resp = httpx.get(url, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        daily = []
        dates = data.get('daily', {}).get('time', [])
        tmax = data.get('daily', {}).get('temperature_2m_max', [])
        tmin = data.get('daily', {}).get('temperature_2m_min', [])
        prec = data.get('daily', {}).get('precipitation_sum', [])
        prec_prob = data.get('daily', {}).get('precipitation_probability_mean', [])
        for i, d in enumerate(dates):
            daily.append({
                'date': d,
                'temp_max': float(tmax[i]) if i < len(tmax) else None,
                'temp_min': float(tmin[i]) if i < len(tmin) else None,
                'precipitation_sum': float(prec[i]) if i < len(prec) else 0.0,
                'precipitation_probability_mean': float(prec_prob[i]) if i < len(prec_prob) else 0.0,
            })
        return {'source': 'open-meteo', 'daily': daily}
    except Exception as exc:
        LAST_WEATHER_ERROR = str(exc)
        # fallback simulado
        today = datetime.utcnow().date()
        daily = []
        for i in range(days):
            d = today + timedelta(days=i)
            daily.append({'date': d.isoformat(), 'temp_max': 30.0, 'temp_min': 20.0, 'precipitation_sum': 0.0, 'precipitation_probability_mean': 10.0})
        return {'source': 'simulated', 'daily': daily, 'error': str(exc)}


def get_city_events(city: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
    """Tenta recuperar eventos públicos para uma cidade usando Eventbrite (token opcional).

    Se `EVENTBRITE_TOKEN` não estiver definido, retorna lista vazia.
    """
    global LAST_EVENTS_ERROR
    LAST_EVENTS_ERROR = None
    token = os.environ.get('EVENTBRITE_TOKEN')
    if not token:
        return []

    # preparar datas
    if not start_date:
        start_date = datetime.utcnow().date().isoformat()
    if not end_date:
        end_date = (datetime.utcnow().date() + timedelta(days=7)).isoformat()

    try:
        url = (
            "https://www.eventbriteapi.com/v3/events/search/"
                f"?location.address={urlquote(city)}"
            f"&start_date.range_start={start_date}T00:00:00&start_date.range_end={end_date}T23:59:59"
        )
        headers = {'Authorization': f'Bearer {token}'}
        resp = httpx.get(url, headers=headers, timeout=10.0)
        resp.raise_for_status()
        payload = resp.json()
        events = []
        for ev in payload.get('events', []):
            events.append({
                'id': ev.get('id'),
                'name': ev.get('name', {}).get('text'),
                'start': ev.get('start', {}).get('local'),
                'end': ev.get('end', {}).get('local'),
                'url': ev.get('url')
            })
        return events
    except Exception as exc:
        LAST_EVENTS_ERROR = str(exc)
        return []


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> Optional[float]:
    """Calcula distância haversine entre dois pontos em quilômetros."""
    try:
        if None in (lat1, lon1, lat2, lon2):
            return None
        # converter para radianos
        rlat1, rlon1, rlat2, rlon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = rlat2 - rlat1
        dlon = rlon2 - rlon1
        a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        R = 6371.0
        return R * c
    except Exception:
        return None


def geocode_with_cache(query: str) -> Optional[Dict]:
    """Geocodifica um texto usando Nominatim e salva/recupera do cache `external_cache`.

    A chave de cache é armazenada sob empresa='geo' e key='query:{query}'.
    """
    if not query:
        return None
    try:
        from database.queries import get_external_cache, set_external_cache
        key = f'query:{query}'
        cached = get_external_cache('geo', key)
        if cached:
            try:
                return json.loads(cached.get('payload'))
            except Exception:
                pass
        geo = geocode_address(query)
        if geo:
            try:
                set_external_cache('geo', key, json.dumps(geo))
            except Exception:
                pass
        return geo
    except Exception:
        return geocode_address(query)


def get_events_with_coords(city: str, store_lat: Optional[float] = None, store_lon: Optional[float] = None) -> List[Dict]:
    """Recupera eventos pela cidade, tenta geocodificar cada evento (cache) e calcula distância até a loja quando possível."""
    events = get_city_events(city)
    out = []
    if not events:
        return out
    for ev in events:
        name = ev.get('name') or ev.get('title') or ''
        query = f"{name} {city}".strip()
        geo = geocode_with_cache(query)
        if geo:
            ev['latitude'] = geo.get('latitude')
            ev['longitude'] = geo.get('longitude')
            if store_lat is not None and store_lon is not None and ev.get('latitude') is not None:
                try:
                    ev['distance_km'] = round(haversine(store_lat, store_lon, float(ev['latitude']), float(ev['longitude'])), 2)
                except Exception:
                    ev['distance_km'] = None
        else:
            ev['latitude'] = None
            ev['longitude'] = None
            ev['distance_km'] = None
        out.append(ev)
    return out


def geocode_address(address: str) -> Optional[Dict]:
    """Retorna {'latitude': float, 'longitude': float, 'display_name': str} usando Nominatim (OpenStreetMap).

    Retorna None em caso de falha ou se não encontrado.
    """
    global LAST_GEOCODE_ERROR
    LAST_GEOCODE_ERROR = None
    if not address or not address.strip():
        return None
    try:
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={urlquote(address.strip())}&limit=1"
        headers = {'User-Agent': 'dojo-os/1.0 (+https://example.com)'}
        resp = httpx.get(url, headers=headers, timeout=10.0)
        resp.raise_for_status()
        arr = resp.json()
        if not arr:
            return None
        first = arr[0]
        return {'latitude': float(first.get('lat')), 'longitude': float(first.get('lon')), 'display_name': first.get('display_name')}
    except Exception as exc:
        LAST_GEOCODE_ERROR = str(exc)
        return None


def assess_location_impact(latitude: Optional[float], longitude: Optional[float], city: Optional[str], days: int = 3) -> Dict:
    """Avalia impacto potencial no movimento com base em clima e eventos.

    Retorna um score entre -1 (forte redução) e +1 (forte aumento) com razões.
    """
    reasons = []
    score = 0.0

    weather = None
    events = []
    errors = []
    if latitude is not None and longitude is not None:
        weather = get_weather_forecast(latitude, longitude, days=days)
        if isinstance(weather, dict) and weather.get('error'):
            errors.append(f"weather: {weather.get('error')}")
        elif LAST_WEATHER_ERROR:
            errors.append(f"weather: {LAST_WEATHER_ERROR}")
        # avaliar precipitação média
        daily = weather.get('daily', [])
        for d in daily:
            prob = d.get('precipitation_probability_mean', 0) or 0
            prec_sum = d.get('precipitation_sum', 0) or 0
            if prob >= 60 or prec_sum > 5:
                reasons.append(f"Chuva prevista em {d.get('date')} (prob {prob}%, {prec_sum}mm) — pode reduzir o movimento.")
                score -= 0.3
            elif prob >= 30:
                reasons.append(f"Chance de chuva moderada em {d.get('date')} (prob {prob}%) — atenção.")
                score -= 0.1

    if city:
        # obter eventos com geocodificação e distância quando possível
        events = get_events_with_coords(city, latitude, longitude)
        if LAST_EVENTS_ERROR:
            errors.append(f"events: {LAST_EVENTS_ERROR}")
        if events:
            nearby_count = 0
            for ev in events:
                dist = ev.get('distance_km')
                name = ev.get('name') or ev.get('title') or 'evento'
                if dist is not None:
                    if dist <= 1:
                        reasons.append(f"Evento '{name}' muito próximo ({dist} km) — forte aumento esperado.")
                        score += 0.35
                        nearby_count += 1
                    elif dist <= 5:
                        reasons.append(f"Evento '{name}' próximo ({dist} km) — aumento provável.")
                        score += 0.2
                        nearby_count += 1
                    elif dist <= 20:
                        reasons.append(f"Evento '{name}' na região ({dist} km) — possível aumento.")
                        score += 0.1
                        nearby_count += 1
                    else:
                        reasons.append(f"Evento '{name}' distante ({dist} km) — impacto limitado.")
                else:
                    reasons.append(f"Evento '{name}' listado — localização não geocodificada.")
                    score += 0.05
                    nearby_count += 1
            if nearby_count > 0:
                # bonus limitado por quantidade
                score += min(0.5, 0.05 * nearby_count)
        else:
            # fallback sem coordenadas
            events = get_city_events(city)
            if events:
                reasons.append(f"{len(events)} eventos públicos próximos — pode aumentar movimento local.")
                score += min(0.5, 0.1 * len(events))
            if LAST_EVENTS_ERROR:
                errors.append(f"events: {LAST_EVENTS_ERROR}")

    # normalizar score entre -1 e 1
    if score > 1:
        score = 1.0
    if score < -1:
        score = -1.0

    return {'impact_score': round(score, 2), 'reasons': reasons, 'weather': weather, 'events': events, 'errors': errors}


def fetch_and_cache_impact(empresa_name: str, days: int = 3) -> Dict:
    """Busca impacto para uma empresa (por nome), faz cache no DB e retorna o resultado.

    Usa `assess_location_impact` internamente e salva em `external_cache` com key 'impact'.
    """
    try:
        from services.empresa_service import obter_empresa
        from database.queries import set_external_cache
        import json

        emp = obter_empresa(empresa_name)
        if not emp:
            return {'error': 'empresa not found'}

        lat = emp.get('latitude')
        lon = emp.get('longitude')
        city = emp.get('cidade')
        result = assess_location_impact(lat, lon, city, days=days)
        # salvar no cache
        set_external_cache(empresa_name, 'impact', json.dumps(result))
        return result
    except Exception as exc:
        return {'error': str(exc)}


def generate_action_plan(impact_result: Dict, empresa_name: Optional[str] = None) -> Dict:
    """Gera um plano de ação (pré-dia e no-dia) com base na avaliação de impacto.

    Retorna um dicionário com resumo do impacto, lista de razões e ações práticas
    organizadas em `actions_preparation` (o que fazer antes do dia) e
    `actions_immediate` (o que executar no dia do evento).
    """
    score = impact_result.get('impact_score', 0) or 0
    reasons = impact_result.get('reasons') or []
    events = impact_result.get('events') or []
    weather = None
    if isinstance(impact_result.get('weather'), dict):
        weather = impact_result.get('weather').get('daily', []) or []

    actions_preparation = []
    actions_immediate = []
    templates = {}

    # sumarizar impacto
    if score >= 0.35:
        impact_summary = 'Expectativa de forte aumento de movimento — oportunidade para capturar demanda.'
    elif score >= 0.15:
        impact_summary = 'Aumento provável de movimento — prepare-se para maior fluxo.'
    elif score <= -0.35:
        impact_summary = 'Expectativa de forte redução de movimento — preparar mitigação e foco em delivery.'
    elif score <= -0.15:
        impact_summary = 'Redução provável de movimento — redirecionar operações para delivery e reduzir desperdício.'
    else:
        impact_summary = 'Impacto limitado ou incerto — monitorar e ajustar conforme necessário.'

    # ações gerais para aumento de fluxo (captura)
    if score >= 0.15:
        actions_preparation.extend([
            'Aumentar equipe nos horários de pico (caixas e cozinha).',
            'Reservar estoque extra para itens rápidos (pães, bebidas, pratos prontos).',
            'Planejar combos/grab-and-go para agilizar atendimento.',
            'Preparar comunicação (WhatsApp/Stories) com oferta relâmpago para participantes.'
        ])

        # ações imediatas dependendo da proximidade do evento
        for ev in events:
            dist = ev.get('distance_km')
            name = ev.get('name') or ev.get('title') or 'evento'
            # checar proximidade
            if dist is not None and dist <= 1:
                actions_immediate.append(f"Evento '{name}' muito próximo ({dist} km): alocar equipe extra no horário do evento e priorizar vendas rápidas.")
                actions_immediate.append('Ativar sinalização externa e pontos de venda rápidos (take-away).')
                break
            elif dist is not None and dist <= 5:
                actions_immediate.append(f"Evento '{name}' próximo ({dist} km): preparar combos e 1-2 funcionários adicionais para pico.")
                break

    # ações para redução de movimento (mitigação)
    if score <= -0.15:
        actions_preparation.extend([
            'Fortalecer canais de delivery e parcerias (apps/tele-entrega).',
            'Criar promoção de incentivo ao delivery/retirada (cupom, frete grátis).',
            'Reduzir produção de perecíveis para evitar desperdício.',
            'Ajustar escala de funcionários para reduzir custos em períodos de baixa.'
        ])
        actions_immediate.append('No dia: priorizar entregas e ofertas online; manter atendimento enxuto presencialmente.')

    # condições meteorológicas (chuva) — foco em delivery
    if weather:
        for d in weather:
            prob = d.get('precipitation_probability_mean', 0) or 0
            prec_sum = d.get('precipitation_sum', 0) or 0
            date_str = d.get('date')
            if prob >= 60 or prec_sum > 5:
                actions_preparation.append(f'Promoção para delivery no dia {date_str}: preparar embalagens à prova d\'água e comunicar desconto para entregas.')
                actions_immediate.append('No dia: divulgar promoção de entrega e agilizar rotas dos motoboys/entregadores.')
                templates['delivery_message'] = (
                    f"Promoção hoje ({date_str}): desconto especial no delivery! Peça pelo WhatsApp e receba rápido."
                )
                break

    # orientação para eventos sem geocodificação
    if events and all(ev.get('distance_km') is None for ev in events):
        actions_preparation.append('Há eventos listados mas sem localização precisa — monitore e prepare-se para aumento de demanda.')

    # mensagens modelo
    if score >= 0.15:
        templates['whatsapp_positive'] = (
            'Olá! Hoje temos eventos próximos — aproveite nosso combo rápido com 15% de desconto para participantes. Peça já pelo WhatsApp.'
        )
    if score <= -0.15:
        templates['whatsapp_negative'] = (
            'Olá! Hoje movimento mais baixo previsto — aproveite 15% de desconto no delivery. Peça pelo WhatsApp.'
        )

    # deduplicar e limitar tamanho
    def clean_list(items):
        out = []
        for i in items:
            if i not in out:
                out.append(i)
        return out[:10]

    return {
        'impact_score': round(score, 2),
        'impact_summary': impact_summary,
        'reasons': reasons,
        'actions_preparation': clean_list(actions_preparation),
        'actions_immediate': clean_list(actions_immediate),
        'templates': templates,
    }
