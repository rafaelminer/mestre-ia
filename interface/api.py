from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional
from services.vendas_service import listar_vendas, registrar_venda, total_vendas, vendas_por_item
from services.estoque_service import listar_estoque, atualizar_item_estoque, itens_estoque_baixo
from services.checklist_service import listar_checklist, atualizar_status, adicionar_checklist
from services.empresa_service import obter_empresas, obter_empresas_completas, criar_empresa
from services.log_service import log_info
from services.whatsapp_service import enviar_mensagem_whatsapp
from ai.analise import AIOperacional
from database.db import init_db, insert_default_data
import threading
import time
import json
import os
from database.queries import get_external_cache
from services.external_service import fetch_and_cache_impact
from services.alert_service import check_and_notify_company, check_and_notify_all

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    insert_default_data()
    log_info('sistema', 'API inicializada')
    # iniciar worker de cache em background (rodará a cada hora)
    stop_event = threading.Event()

    def cache_worker():
        # primeiro ciclo imediato
        while not stop_event.is_set():
            try:
                empresas = obter_empresas_completas()
                for e in empresas:
                    nome = e.get('nome')
                    try:
                        fetch_and_cache_impact(nome)
                        log_info(nome, 'Cache de impacto atualizado')
                        try:
                            check_and_notify_company(nome, radius_km=1.0)
                        except Exception as exc2:
                            log_info(nome, f'Erro alert_service: {exc2}')
                    except Exception as exc:
                        log_info(nome, f'Erro cache impacto: {exc}')
            except Exception as exc:
                log_info('sistema', f'Erro worker cache: {exc}')
            # aguarda X segundos (configurável via ENV) ou até stop_event
            try:
                interval = int(os.environ.get('EXTERNAL_WORKER_INTERVAL_SECONDS', '300'))
            except Exception:
                interval = 300
            log_info('sistema', f'External cache worker sleeping for {interval} seconds')
            stop_event.wait(interval)

    thread = threading.Thread(target=cache_worker, daemon=True, name='external-cache-worker')
    thread.start()
    app.state.external_cache_stop = stop_event
    app.state.external_cache_thread = thread
    yield
    # shutdown: sinalizar e aguardar
    try:
        stop_event.set()
        thread.join(timeout=2)
    except Exception:
        pass

app = FastAPI(
    title='DOJO OS API',
    description='API de gestão operacional para restaurantes',
    version='1.0',
    lifespan=lifespan,
)


class VendaIn(BaseModel):
    empresa: str
    data: str
    item: str
    quantidade: int
    total: float


class EstoqueUpdateIn(BaseModel):
    item_id: int
    quantidade: int
    minimo: int


class ChecklistIn(BaseModel):
    empresa: str
    tipo: str
    tarefa: str
    status: str
    data: str
    responsavel: Optional[str] = None


class EmpresaIn(BaseModel):
    nome: str
    tipo: Optional[str] = 'restaurante'
    ativa: Optional[bool] = True


class WhatsAppIn(BaseModel):
    numero: str
    mensagem: str
    empresa: Optional[str] = None


@app.get('/health')
def health_check():
    return {'status': 'ok', 'message': 'DOJO OS API funcionando'}


@app.get('/vendas')
def api_listar_vendas(empresa: Optional[str] = None):
    return listar_vendas(empresa)


@app.post('/vendas')
def api_registrar_venda(venda: VendaIn):
    registrar_venda(venda.empresa, venda.data, venda.item, venda.quantidade, venda.total)
    log_info(venda.empresa, f'Venda API registrada: {venda.item} x{venda.quantidade} R${venda.total:.2f}')
    return {'status': 'ok'}


@app.get('/vendas/total')
def api_total_vendas(empresa: Optional[str] = None):
    return {'total': total_vendas(empresa)}


@app.get('/vendas/por-item')
def api_vendas_por_item(empresa: Optional[str] = None):
    return vendas_por_item(empresa)


@app.get('/estoque')
def api_listar_estoque(empresa: Optional[str] = None):
    return listar_estoque(empresa)


@app.patch('/estoque')
def api_atualizar_estoque(payload: EstoqueUpdateIn):
    atualizar_item_estoque(payload.item_id, payload.quantidade, payload.minimo)
    log_info('sistema', f'Estoque API atualizado: item_id={payload.item_id} quantidade={payload.quantidade}')
    return {'status': 'ok'}


@app.get('/estoque/baixo')
def api_estoque_baixo(empresa: Optional[str] = None):
    return itens_estoque_baixo(empresa)


@app.get('/checklist')
def api_listar_checklist(empresa: Optional[str] = None, tipo: Optional[str] = None):
    return listar_checklist(empresa, tipo)


@app.patch('/checklist/{item_id}/status')
def api_atualizar_status(item_id: int, status: str):
    try:
        atualizar_status(item_id, status)
        log_info('sistema', f'Checklist API atualizado: id={item_id} status={status}')
        return {'status': 'ok'}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post('/checklist')
def api_adicionar_checklist(item: ChecklistIn):
    adicionar_checklist(item.empresa, item.tipo, item.tarefa, item.status, item.data, item.responsavel)
    log_info(item.empresa, f'Checklist API adicionado: {item.tarefa}')
    return {'status': 'ok'}


@app.get('/empresas')
def api_listar_empresas():
    return obter_empresas()


@app.get('/empresas/detalhes')
def api_listar_empresas_detalhes():
    return obter_empresas_completas()


@app.post('/empresas')
def api_criar_empresa(payload: EmpresaIn):
    criar_empresa(payload.nome, payload.tipo, payload.ativa)
    log_info(payload.nome, f'Empresa criada: {payload.nome}')
    return {'status': 'ok'}


@app.post('/whatsapp/send')
def api_enviar_whatsapp(payload: WhatsAppIn):
    resultado = enviar_mensagem_whatsapp(payload.numero, payload.mensagem, payload.empresa)
    return resultado


@app.get('/analise')
def api_analisar(empresa: Optional[str] = None):
    resultado = AIOperacional.analisar_dados(empresa)
    log_info(empresa or 'sistema', 'Análise IA API executada')
    return resultado


@app.get('/external/impact')
def api_external_impact(empresa: Optional[str] = None, force_refresh: bool = False):
    """Retorna o impacto avaliado (clima+eventos) para uma empresa.

    Se `force_refresh=true`, força recálculo; caso contrário tenta retornar cache (1h validade).
    """
    if not empresa:
        raise HTTPException(status_code=400, detail='Informe o parâmetro `empresa`.')

    # tentar cache
    if not force_refresh:
        cached = get_external_cache(empresa, 'impact')
        if cached:
            try:
                updated = cached.get('updated_at')
                if updated:
                    from datetime import datetime
                    updated_dt = datetime.fromisoformat(updated)
                    age = (datetime.now() - updated_dt).total_seconds()
                    if age < 3600:
                        return json.loads(cached.get('payload'))
            except Exception:
                # fallback para retornar payload
                try:
                    return json.loads(cached.get('payload'))
                except Exception:
                    pass

    # caso contrário recalcule e cache
    result = fetch_and_cache_impact(empresa)
    if isinstance(result, dict) and result.get('error'):
        raise HTTPException(status_code=500, detail=result.get('error'))
    return result


@app.get('/external/action_plan')
def api_external_action_plan(empresa: Optional[str] = None, force_refresh: bool = False):
    """Retorna o plano de ação gerado a partir do impacto (clima+eventos) para uma empresa.

    Se `force_refresh=true` força recálculo; caso contrário tenta usar cache (1h).
    """
    if not empresa:
        raise HTTPException(status_code=400, detail='Informe o parâmetro `empresa`.')

    try:
        impact = None
        if not force_refresh:
            cached = get_external_cache(empresa, 'impact')
            if cached:
                try:
                    payload = json.loads(cached.get('payload'))
                    updated = cached.get('updated_at')
                    if updated:
                        from datetime import datetime
                        updated_dt = datetime.fromisoformat(updated)
                        age = (datetime.now() - updated_dt).total_seconds()
                        if age < 3600:
                            impact = payload
                    else:
                        impact = payload
                except Exception:
                    impact = None

        if impact is None:
            from services.external_service import fetch_and_cache_impact
            impact = fetch_and_cache_impact(empresa)
            if isinstance(impact, dict) and impact.get('error'):
                raise HTTPException(status_code=500, detail=impact.get('error'))

        from services.external_service import generate_action_plan
        plan = generate_action_plan(impact, empresa)
        return plan
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post('/external/alerts')
def api_trigger_alerts(radius_km: float = 1.0):
    """Dispara a checagem de eventos e notificações para todas as empresas.

    Retorna resumo por empresa com notificações enviadas.
    """
    try:
        resultados = check_and_notify_all(radius_km=radius_km)
        return {'status': 'ok', 'resultados': resultados}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class TokenPayload(BaseModel):
    token: str


@app.post('/admin/eventbrite')
def api_set_eventbrite_token(payload: TokenPayload):
    """Salvar token do Eventbrite para habilitar buscas de eventos reais.

    Salva em `.env` e atualiza o ambiente do processo atual.
    """
    try:
        from services.config_service import set_env_var
        set_env_var('EVENTBRITE_TOKEN', payload.token)
        log_info('sistema', 'Eventbrite token atualizado via API')
        return {'status': 'ok', 'message': 'Eventbrite token salvo'}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post('/vision/detect')
async def api_vision_detect(file: UploadFile = File(...), empresa: Optional[str] = None):
    """Recebe uma imagem e retorna contagem/anotações.
    Usa `ai.vision.detect_and_count` (fallback PIL) internamente.
    """
    content = await file.read()
    # import local para evitar dependência pesada em import-time
    from ai.vision import detect_and_count
    resultado = detect_and_count(content)
    log_info(empresa or 'sistema', f'Visão detectou {resultado.get("total_count",0)} objetos')
    return resultado
