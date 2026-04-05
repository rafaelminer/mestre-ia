from typing import List, Dict, Optional
import json
from datetime import datetime

from database.queries import get_external_cache, set_external_cache
from services.external_service import get_events_with_coords, fetch_and_cache_impact, generate_action_plan
from services.empresa_service import obter_empresas_completas, obter_empresa
from services.whatsapp_service import enviar_mensagem_whatsapp
from services.log_service import log_info, log_warning


def check_and_notify_company(empresa_nome: str, radius_km: float = 1.0) -> Dict:
    """Checa eventos próximos à empresa e notifica (via WhatsApp stub) se necessário.

    Retorna resumo com número de notificações enviadas.
    """
    sent = []
    emp = obter_empresa(empresa_nome)
    if not emp:
        return {'empresa': empresa_nome, 'sent': sent}

    lat = emp.get('latitude')
    lon = emp.get('longitude')
    city = emp.get('cidade')
    contato = emp.get('contato')

    if not city and (lat is None or lon is None):
        return {'empresa': empresa_nome, 'sent': sent, 'reason': 'no location info'}

    # checar preferência de envio automático configurada por empresa
    auto_send_enabled = bool(emp.get('auto_send_plan'))

    try:
        events = get_events_with_coords(city, lat, lon)
        # Se não houver eventos, ainda verificamos impacto por clima e enviamos plano se necessário
        if not events:
            try:
                impact = fetch_and_cache_impact(empresa_nome)
                if isinstance(impact, dict) and impact.get('error'):
                    raise Exception(impact.get('error'))
                plan = generate_action_plan(impact, empresa_nome)
                score = plan.get('impact_score', 0) or 0
                if abs(score) >= 0.35:
                    # chave por data para evitar envios repetidos
                    key = f"notified:impact:{datetime.utcnow().date().isoformat()}"
                    cached = get_external_cache(empresa_nome, key)
                    if not cached:
                        # construir mensagem resumida do plano
                        mensagem = f"Plano de Ação ({empresa_nome}) - impacto {plan.get('impact_score')}\n{plan.get('impact_summary')}\n"
                        if plan.get('actions_immediate'):
                            mensagem += '\nAções no dia:\n' + '\n'.join(plan.get('actions_immediate'))
                        if plan.get('actions_preparation'):
                            mensagem += '\nAntes do dia:\n' + '\n'.join(plan.get('actions_preparation'))
                        if auto_send_enabled:
                            if contato:
                                try:
                                    enviar_mensagem_whatsapp(contato, mensagem, empresa_nome)
                                    log_info(empresa_nome, 'Plano de ação enviado via WhatsApp')
                                except Exception as exc:
                                    log_warning(empresa_nome, f'Falha ao enviar plano por WhatsApp: {exc}')
                            else:
                                log_info(empresa_nome, 'Plano de ação preparado (sem contato configurado).')
                        else:
                            log_info(empresa_nome, 'Auto-send desabilitado para esta empresa; plano gerado mas não enviado automaticamente.')
                        try:
                            set_external_cache(empresa_nome, key, json.dumps({'plan': plan, 'sent_at': datetime.now().isoformat()}))
                        except Exception:
                            pass
                        sent.append({'event': None, 'plan_sent': auto_send_enabled and bool(contato), 'score': score})
            except Exception as exc:
                log_warning(empresa_nome, f'Erro ao avaliar impacto sem eventos: {exc}')
            return {'empresa': empresa_nome, 'sent': sent}

        for ev in events:
            dist = ev.get('distance_km')
            event_id = ev.get('id') or ev.get('name')
            if dist is None:
                continue
            if dist <= radius_km:
                key = f'notified:{event_id}'
                cached = get_external_cache(empresa_nome, key)
                if cached:
                    continue

                # obter impacto e plano antes de enviar
                try:
                    impact = fetch_and_cache_impact(empresa_nome)
                    if isinstance(impact, dict) and impact.get('error'):
                        raise Exception(impact.get('error'))
                    plan = generate_action_plan(impact, empresa_nome)
                except Exception:
                    plan = None

                nome_ev = ev.get('name') or 'evento'

                # se houver plano e score forte, enviar plano; caso contrário enviar notificação simples
                sent_plan = False
                if plan:
                    score = plan.get('impact_score', 0) or 0
                    if abs(score) >= 0.35:
                        mensagem = f"Plano de Ação - {empresa_nome} - Evento: {nome_ev} ({dist} km) - impacto {score}\n{plan.get('impact_summary')}\n"
                        if plan.get('actions_immediate'):
                            mensagem += '\nAções no dia:\n' + '\n'.join(plan.get('actions_immediate'))
                        if plan.get('actions_preparation'):
                            mensagem += '\nAntes do dia:\n' + '\n'.join(plan.get('actions_preparation'))
                        if auto_send_enabled:
                            if contato:
                                try:
                                    enviar_mensagem_whatsapp(contato, mensagem, empresa_nome)
                                    log_info(empresa_nome, f'Plano de ação enviado via WhatsApp sobre {nome_ev}')
                                except Exception as exc:
                                    log_warning(empresa_nome, f'Falha ao enviar plano por WhatsApp: {exc}')
                            else:
                                log_info(empresa_nome, f'Plano pronto para {nome_ev} (sem contato).')
                            sent_plan = True
                        else:
                            log_info(empresa_nome, f'Auto-send desabilitado para {nome_ev}; plano gerado mas não enviado automaticamente.')
                            sent_plan = False

                if not sent_plan:
                    mensagem = f"Evento próximo detectado: {nome_ev} ({dist} km). Ajustar operação conforme necessário."
                    if contato:
                        try:
                            enviar_mensagem_whatsapp(contato, mensagem, empresa_nome)
                            log_info(empresa_nome, f'Notificação enviada via WhatsApp para {contato} sobre {nome_ev}')
                        except Exception as exc:
                            log_warning(empresa_nome, f'Falha ao enviar WhatsApp para {contato}: {exc}')
                    else:
                        log_info(empresa_nome, f'Evento próximo: {nome_ev} a {dist} km (sem contato configurado).')

                # marcar como notificado/planejado
                try:
                    set_external_cache(empresa_nome, key, json.dumps({'event': ev, 'notified_at': datetime.now().isoformat(), 'plan_sent': sent_plan}))
                except Exception:
                    pass
                sent.append({'event': event_id, 'name': nome_ev, 'distance_km': dist, 'plan_sent': sent_plan})
    except Exception as exc:
        log_warning(empresa_nome, f'Erro ao checar eventos: {exc}')

    return {'empresa': empresa_nome, 'sent': sent}


def check_and_notify_all(radius_km: float = 1.0) -> List[Dict]:
    resultados = []
    empresas = obter_empresas_completas()
    for e in empresas:
        nome = e.get('nome')
        try:
            r = check_and_notify_company(nome, radius_km=radius_km)
            resultados.append(r)
        except Exception as exc:
            log_warning(nome, f'Erro global ao notificar: {exc}')
    return resultados
