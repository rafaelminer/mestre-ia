import base64
from pathlib import Path

import pandas as pd
import streamlit as st

from ai.analise import AIOperacional
from ai.vision import analyze_checklist_from_image
from database.db import init_db, insert_default_data
from database.queries import listar_insights_ia_historico, listar_uploads_historico, obter_logs
from logs.logger import error, info, warning
from modules.dashboard import indicadores_empresa
from services.chefweb_analytics_service import analisar_operacao_importada, registrar_analise_operacional
from services.chefweb_service import list_import_history, process_chefweb_upload
from services.checklist_service import listar_checklist
from services.empresa_service import (
    atualizar_contato_empresa,
    atualizar_local_empresa,
    criar_empresa,
    obter_empresa,
    obter_empresas,
    obter_empresas_completas,
)
from services.estoque_service import atualizar_item_estoque, itens_estoque_baixo, listar_estoque
from services.external_service import assess_location_impact, geocode_address
from services.vendas_service import listar_vendas_recentes
from services.vision_inventory_service import (
    analisar_contagem_estoque,
    historico_contagens_estoque,
    listar_referencias_visuais,
    salvar_modelo_visual_estoque,
)
PAGINAS = {
    'inicio': 'Início',
    'painel_operacional': 'Painel Operacional',
    'importar_dados': 'Importar Dados',
    'inteligencia': 'Inteligência',
    'estoque': 'Estoque',
    'configuracoes': 'Configurações',
}

ASSETS_DIR = Path(__file__).resolve().parent.parent / 'assets'
DOJO_LOGO = ASSETS_DIR / 'dojo.png'
EMPRESA_BRAND = {
    'Japatê': {
        'display_name': 'Japatê',
        'subtitle': 'Restaurante Japonês',
        'logo': ASSETS_DIR / 'japate.png',
    },
    'Rellicário': {
        'display_name': 'Rellicário',
        'subtitle': 'Cafeteria e Doceria',
        'logo': ASSETS_DIR / 'rellicario.png',
    },
}


def get_brand_config(empresa: str) -> dict:
    return EMPRESA_BRAND.get(
        empresa,
        {
            'display_name': empresa,
            'subtitle': 'Operação DOJO',
            'logo': DOJO_LOGO,
        },
    )


def render_global_style():
    st.markdown(
        """
        <style>
        :root {
            --dojo-ink: #ecf3ff;
            --dojo-muted: #9cb0c7;
            --dojo-card: #1c1f26;
            --dojo-card-soft: rgba(28, 31, 38, 0.92);
            --dojo-border: rgba(148, 163, 184, 0.16);
            --dojo-sidebar: #0b1220;
            --dojo-panel: #111a2b;
        }
        .stApp {
            background:
                radial-gradient(circle at top right, rgba(249, 115, 22, 0.16), transparent 18%),
                radial-gradient(circle at bottom left, rgba(14, 165, 233, 0.10), transparent 24%),
                linear-gradient(180deg, #0E1117 0%, #11161f 48%, #141a24 100%);
            color: var(--dojo-ink);
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #08101d 0%, #0d1728 45%, #14243b 100%);
            border-right: 1px solid rgba(255, 255, 255, 0.06);
        }
        [data-testid="stSidebar"] * {
            color: #edf2fb;
        }
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
        }
        h1, h2, h3, h4, h5, h6, p, label, div, span {
            color: var(--dojo-ink);
        }
        [data-testid="stMetricValue"] {
            color: #f8fbff;
        }
        [data-testid="stMetricLabel"] {
            color: #94a3b8;
        }
        div[data-testid="metric-container"] {
            background: var(--dojo-card);
            border: 1px solid var(--dojo-border);
            border-radius: 18px;
            padding: 1rem 1.15rem;
            box-shadow: 0 16px 40px rgba(0, 0, 0, 0.22);
        }
        .top-brand {
            background: var(--dojo-card-soft);
            border: 1px solid var(--dojo-border);
            border-radius: 24px;
            padding: 1rem 1.2rem;
            box-shadow: 0 14px 34px rgba(0, 0, 0, 0.18);
            margin-bottom: 1rem;
        }
        .hero-card {
            background:
                radial-gradient(circle at top right, rgba(249,115,22,0.12), transparent 24%),
                linear-gradient(135deg, rgba(17, 26, 43, 0.98), rgba(23, 49, 79, 0.94));
            border-radius: 28px;
            padding: 1.5rem 1.6rem;
            color: #f8f3eb;
            box-shadow: 0 24px 48px rgba(0, 0, 0, 0.28);
            margin-bottom: 1.2rem;
        }
        .hero-card h1 {
            margin: 0;
            font-size: 2.35rem;
            line-height: 1.08;
        }
        .hero-card p {
            margin: 0.55rem 0 0 0;
            color: rgba(248, 243, 235, 0.84);
            font-size: 1rem;
        }
        .eyebrow {
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: #8ea7c3;
            font-size: 0.74rem;
            font-weight: 700;
        }
        .content-logo-card {
            background: var(--dojo-card-soft);
            border: 1px solid var(--dojo-border);
            border-radius: 24px;
            padding: 1rem;
            box-shadow: 0 14px 34px rgba(0, 0, 0, 0.18);
            min-height: 180px;
        }
        .insight-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 0.85rem;
            margin: 0.6rem 0 1rem 0;
        }
        .insight-card {
            background: var(--dojo-card);
            border: 1px solid var(--dojo-border);
            border-radius: 20px;
            padding: 1rem 1.05rem;
            box-shadow: 0 10px 26px rgba(0,0,0,0.16);
        }
        .insight-card strong {
            display: block;
            margin-bottom: 0.35rem;
            font-size: 0.95rem;
        }
        .insight-card p {
            margin: 0;
            color: #c6d3e3;
            font-size: 0.92rem;
            line-height: 1.4;
        }
        .tone-warning {
            border-left: 5px solid #d97706;
            background: linear-gradient(180deg, rgba(82, 45, 10, 0.96), rgba(24, 24, 24, 0.88));
        }
        .tone-success {
            border-left: 5px solid #15803d;
            background: linear-gradient(180deg, rgba(10, 61, 35, 0.96), rgba(24, 24, 24, 0.88));
        }
        .tone-info {
            border-left: 5px solid #2563eb;
            background: linear-gradient(180deg, rgba(11, 37, 82, 0.96), rgba(24, 24, 24, 0.88));
        }
        .section-card {
            background: var(--dojo-card-soft);
            border: 1px solid var(--dojo-border);
            border-radius: 22px;
            padding: 1rem 1.1rem;
            box-shadow: 0 12px 30px rgba(0,0,0,0.14);
            margin-bottom: 1rem;
        }
        .section-title {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 0.85rem;
        }
        .section-title h3 {
            margin: 0;
            font-size: 1.15rem;
        }
        .section-title p {
            margin: 0.15rem 0 0 0;
            color: var(--dojo-muted);
            font-size: 0.9rem;
        }
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 0.9rem;
            margin: 0.8rem 0 1rem 0;
        }
        .kpi-card {
            background: linear-gradient(180deg, rgba(28,31,38,0.98), rgba(18,22,30,0.96));
            border: 1px solid rgba(148, 163, 184, 0.14);
            border-radius: 20px;
            padding: 1rem 1rem 0.95rem 1rem;
            box-shadow: 0 14px 32px rgba(0, 0, 0, 0.28);
        }
        .kpi-card span {
            display: block;
            color: #8ea7c3;
            font-size: 0.82rem;
            margin-bottom: 0.5rem;
        }
        .kpi-card strong {
            display: block;
            color: #f8fbff;
            font-size: 1.9rem;
            font-weight: 700;
            line-height: 1;
        }
        .kpi-card small {
            display: block;
            margin-top: 0.55rem;
            color: #94a3b8;
            font-size: 0.82rem;
        }
        .ia-callout {
            background: linear-gradient(135deg, rgba(34, 44, 66, 0.96), rgba(23, 31, 46, 0.98));
            border: 1px solid rgba(96, 165, 250, 0.24);
            border-radius: 22px;
            padding: 1rem 1.1rem;
            box-shadow: 0 18px 36px rgba(0,0,0,0.22);
            margin-bottom: 1rem;
        }
        .ia-callout h3 {
            margin: 0 0 0.35rem 0;
            color: #dbeafe;
        }
        .ia-callout p {
            margin: 0;
            color: #bfd2ea;
        }
        div[data-testid="stDataFrame"], div[data-testid="stTable"] {
            border-radius: 16px;
            overflow: hidden;
            border: 1px solid var(--dojo-border);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(empresa: str, title: str, subtitle: str):
    brand = get_brand_config(empresa)
    if not hasattr(st, 'columns'):
        if hasattr(st, 'header'):
            st.header(title)
        if hasattr(st, 'caption'):
            st.caption(subtitle)
        return
    left, right = st.columns([1.45, 0.9])
    with left:
        st.markdown('<div class="top-brand">', unsafe_allow_html=True)
        dojo_col, text_col = st.columns([0.2, 0.8])
        with dojo_col:
            if DOJO_LOGO.exists():
                st.image(str(DOJO_LOGO), use_container_width=True)
        with text_col:
            st.markdown('<div class="eyebrow">Sistema Operacional DOJO</div>', unsafe_allow_html=True)
            st.markdown("## DOJO OS")
            st.caption("Gestão Inteligente de Operações")
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="hero-card"><h1>{title}</h1><p>{subtitle}</p></div>',
            unsafe_allow_html=True,
        )
    with right:
        st.markdown('<div class="content-logo-card">', unsafe_allow_html=True)
        logo_path = Path(brand['logo'])
        if logo_path.exists():
            st.image(str(logo_path), use_container_width=True)
        elif DOJO_LOGO.exists():
            st.image(str(DOJO_LOGO), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)


def render_divider():
    if hasattr(st, 'divider'):
        st.divider()
    else:
        st.markdown('---')


def build_sales_timeseries(empresa: str, limit: int = 90) -> pd.DataFrame:
    rows = [dict(row) for row in listar_vendas_recentes(empresa, limite=limit)]
    if not rows:
        return pd.DataFrame(columns=['data_ref', 'total'])
    df = pd.DataFrame(rows)
    df['data_dt'] = pd.to_datetime(df['data'], errors='coerce')
    df['total'] = pd.to_numeric(df['total'], errors='coerce').fillna(0.0)
    df = df.dropna(subset=['data_dt'])
    if df.empty:
        return pd.DataFrame(columns=['data_ref', 'total'])
    df['data_ref'] = df['data_dt'].dt.strftime('%Y-%m-%d')
    return df.groupby('data_ref', as_index=False)['total'].sum().sort_values('data_ref')


def collect_operational_alerts(empresa: str, indicadores: dict, analise_importada: dict, checklist: list) -> list[dict]:
    alerts = []
    estoque_baixo = indicadores.get('estoque_baixo') or []
    pendentes = len(
        [
            item
            for item in checklist
            if (dict(item).get('status') if not isinstance(item, dict) else item.get('status')) == 'pendente'
        ]
    )
    variacao = indicadores.get('variacao_periodo', 0.0) or 0.0

    if estoque_baixo:
        alerts.append({
            'tone': 'warning',
            'title': 'Estoque crítico',
            'body': f"{len(estoque_baixo)} item(ns) estão no limite mínimo ou abaixo dele.",
        })
    if pendentes:
        alerts.append({
            'tone': 'warning',
            'title': 'Checklist pendente',
            'body': f"{pendentes} tarefa(s) operacionais ainda exigem atenção.",
        })
    if variacao <= -10:
        alerts.append({
            'tone': 'warning',
            'title': 'Queda de faturamento',
            'body': f"O comparativo recente caiu {variacao:.1f}% frente ao período anterior.",
        })
    if analise_importada.get('recomendacoes'):
        alerts.append({
            'tone': 'info',
            'title': 'IA operacional',
            'body': analise_importada['recomendacoes'][0],
        })
    if not alerts:
        alerts.append({
            'tone': 'success',
            'title': 'Operação estável',
            'body': 'Sem alertas críticos no momento. O ambiente está pronto para otimização fina.',
        })
    return alerts[:4]


def render_insight_cards(cards: list[dict]):
    if not cards:
        return
    html = ['<div class="insight-grid">']
    for card in cards:
        tone = card.get('tone', 'info')
        html.append(
            f'<div class="insight-card tone-{tone}"><strong>{card.get("title","")}</strong><p>{card.get("body","")}</p></div>'
        )
    html.append('</div>')
    st.markdown(''.join(html), unsafe_allow_html=True)


def render_kpi_cards(cards: list[dict]):
    if not cards:
        return
    html = ['<div class="kpi-grid">']
    for card in cards:
        html.append(
            "<div class=\"kpi-card\">"
            f"<span>{card.get('label', '')}</span>"
            f"<strong>{card.get('value', '')}</strong>"
            f"<small>{card.get('caption', '')}</small>"
            "</div>"
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def render_section_header(title: str, subtitle: str = ""):
    st.markdown(
        "<div class=\"section-title\">"
        f"<div><h3>{title}</h3><p>{subtitle}</p></div>"
        "</div>",
        unsafe_allow_html=True,
    )


def run_app():
    st.set_page_config(
        page_title='Mestre IA | DOJO',
        page_icon='assets/dojo.png',
        layout='wide',
        initial_sidebar_state='expanded',
    )
    init_db()
    insert_default_data()
    render_global_style()

    empresas = sorted(set((obter_empresas() or []) + ['Japatê', 'Rellicário']))
    empresa_selecionada = st.sidebar.selectbox('Selecionar Empresa', empresas)
    brand = get_brand_config(empresa_selecionada)
    if DOJO_LOGO.exists():
        st.sidebar.image(str(DOJO_LOGO), width=120)
    st.sidebar.title('Mestre IA')
    st.sidebar.caption('Sistema operacional inteligente da DOJO para gestão multiempresa.')
    if Path(brand['logo']).exists():
        st.sidebar.image(str(brand['logo']), width=140)
    st.sidebar.markdown(f"**{brand['display_name']}**")
    st.sidebar.caption(brand['subtitle'])
    st.sidebar.divider()
    pagina_padrao = 'inicio'
    pagina_atual = st.session_state.get('pagina_mestre_ia', pagina_padrao)
    if pagina_atual not in PAGINAS:
        st.session_state['pagina_mestre_ia'] = pagina_padrao
        pagina_atual = pagina_padrao
    pagina = st.sidebar.radio(
        'Navegação',
        list(PAGINAS.keys()),
        key='pagina_mestre_ia',
        format_func=lambda item: PAGINAS[item],
    )
    st.sidebar.divider()
    st.sidebar.write(f'Unidade ativa: {empresa_selecionada}')
    st.sidebar.caption('Dados, IA e operação trabalham no mesmo fluxo com leitura centralizada do ChefWeb.')

    if pagina == 'inicio':
        render_home(empresa_selecionada)
    elif pagina == 'painel_operacional':
        render_dashboard(empresa_selecionada)
    elif pagina == 'importar_dados':
        render_importar_dados(empresa_selecionada)
    elif pagina == 'inteligencia':
        render_ia(empresa_selecionada)
    elif pagina == 'estoque':
        render_estoque(empresa_selecionada)
    elif pagina == 'configuracoes':
        render_configuracoes(empresa_selecionada)


def render_home(empresa):
    render_page_header(
        empresa,
        f"Início | {get_brand_config(empresa)['display_name']}",
        'Tenha uma visão geral da operação, dos alertas e da saúde do negócio em um único lugar.',
    )

    indicadores = indicadores_empresa(empresa)
    checklist = listar_checklist(empresa)
    analise_importada = analisar_operacao_importada(empresa)
    uploads = [dict(row) for row in listar_uploads_historico(empresa, limite=6)]
    historico_ia = [dict(row) for row in listar_insights_ia_historico(empresa, limite=6)]
    todas_empresas = sorted(set((obter_empresas() or []) + ['Japatê', 'Rellicário']))

    cards = collect_operational_alerts(empresa, indicadores, analise_importada, checklist)

    with st.container():
        render_section_header('Visão geral', 'Principais indicadores da unidade selecionada.')
        render_kpi_cards([
            {'label': 'Faturamento', 'value': f"R$ {indicadores['faturamento_total']:.2f}", 'caption': 'Receita acumulada da operação'},
            {'label': 'Pedidos', 'value': int(indicadores.get('pedidos_periodo') or 0), 'caption': 'Movimento no período analisado'},
            {'label': 'Ticket médio', 'value': f"R$ {indicadores.get('ticket_medio', 0.0):.2f}", 'caption': 'Valor médio por pedido'},
            {'label': 'Alertas', 'value': len(cards), 'caption': 'Sinais operacionais abertos'},
        ])

    with st.container():
        render_section_header('Alertas importantes', 'O que precisa de atenção imediata na operação.')
        render_insight_cards(cards)

    with st.container():
        left, right = st.columns([1.2, 1])
        with left:
            render_section_header('Resumo das empresas', 'Comparativo rápido entre as operações da DOJO.')
            resumo = []
            for nome in todas_empresas:
                ind = indicadores_empresa(nome)
                resumo.append({
                    'Empresa': nome,
                    'Faturamento': round(ind.get('faturamento_total', 0.0), 2),
                    'Pedidos': int(ind.get('pedidos_periodo') or 0),
                    'Estoque crítico': len(ind.get('estoque_baixo') or []),
                })
            st.dataframe(pd.DataFrame(resumo), use_container_width=True)

        with right:
            render_section_header('Prioridades do dia', 'Leitura rápida para tomada de decisão.')
            priority_cards = []
            if cards:
                priority_cards.extend(cards[:2])
            if uploads:
                priority_cards.append({
                    'tone': 'info',
                    'title': 'Último upload',
                    'body': f"{uploads[0].get('nome_arquivo', 'Arquivo')} processado recentemente.",
                })
            if not priority_cards:
                priority_cards.append({
                    'tone': 'success',
                    'title': 'Tudo sob controle',
                    'body': 'Nenhuma prioridade crítica aberta neste momento.',
                })
            render_insight_cards(priority_cards[:3])

    render_divider()
    with st.container():
        render_section_header('Inteligência em destaque', 'Resumo do que a análise operacional identificou.')
        left, right = st.columns([1.15, 0.85])
        with left:
            destaque = []
            for insight in (analise_importada.get('insights') or [])[:3]:
                destaque.append({'tone': 'info', 'title': 'Sinal identificado', 'body': insight})
            for recomendacao in (analise_importada.get('recomendacoes') or [])[:2]:
                destaque.append({'tone': 'success', 'title': 'Recomendação', 'body': recomendacao})
            if destaque:
                render_insight_cards(destaque)
            else:
                st.info('A IA ainda não encontrou sinais suficientes para destaque automático.')
        with right:
            render_section_header('Leitura gerencial', 'Síntese para acompanhamento da operação no dia.')
            resumo_gerencial = []
            if cards:
                resumo_gerencial.append(cards[0])
            if indicadores.get('variacao_periodo', 0.0) >= 0:
                resumo_gerencial.append({
                    'tone': 'success',
                    'title': 'Desempenho do período',
                    'body': 'O resultado recente está estável ou em crescimento. Vale manter o plano operacional atual.',
                })
            else:
                resumo_gerencial.append({
                    'tone': 'warning',
                    'title': 'Desempenho do período',
                    'body': 'O resultado recente exige atenção. Revise escala, mix e ações comerciais.',
                })
            render_insight_cards(resumo_gerencial[:2])

    render_divider()
    with st.container():
        c1, c2 = st.columns(2)
        with c1:
            render_section_header('Última atividade', 'Arquivos e movimentos recentes.')
            if uploads:
                df_uploads = pd.DataFrame(uploads)
                cols = [col for col in ['criado_em', 'nome_arquivo', 'status'] if col in df_uploads.columns]
                st.dataframe(df_uploads[cols], use_container_width=True)
            else:
                st.info('Nenhum upload recente registrado.')
        with c2:
            render_section_header('Insights recentes', 'Histórico salvo pela IA operacional.')
            if historico_ia:
                df_ia = pd.DataFrame(historico_ia)
                cols = [col for col in ['criado_em', 'insight', 'prioridade'] if col in df_ia.columns]
                st.dataframe(df_ia[cols], use_container_width=True)
            else:
                st.info('Nenhum insight histórico salvo ainda.')


def render_dashboard(empresa):
    render_page_header(
        empresa,
        f"Painel Operacional | {get_brand_config(empresa)['display_name']}",
        'Acompanhe KPIs, sinais de risco e oportunidades geradas a partir do histórico real da operação.',
    )

    indicadores = indicadores_empresa(empresa)
    checklist = listar_checklist(empresa)
    pendentes = len([item for item in checklist if item['status'] == 'pendente'])
    estoque_baixo = indicadores['estoque_baixo']
    top_item = indicadores['vendas_por_item'][0]['item'] if indicadores['vendas_por_item'] else 'Sem dados'
    variacao = indicadores.get('variacao_periodo', 0.0)
    horario_pico = indicadores.get('horario_pico') or {}
    horario_label = horario_pico.get('hora_referencia', '--') if isinstance(horario_pico, dict) else '--'

    render_kpi_cards([
        {'label': 'Faturamento', 'value': f"R$ {indicadores['faturamento_total']:.2f}", 'caption': 'Receita consolidada da operação'},
        {'label': 'Pedidos', 'value': int(indicadores.get('pedidos_periodo') or 0), 'caption': 'Volume do período recente'},
        {'label': 'Ticket médio', 'value': f"R$ {indicadores.get('ticket_medio', 0.0):.2f}", 'caption': f"{variacao:+.1f}% vs. período anterior"},
        {'label': 'Horário de pico', 'value': horario_label, 'caption': 'Faixa de maior movimento'},
        {'label': 'Checklist', 'value': pendentes, 'caption': 'Tarefas pendentes'},
        {'label': 'Estoque crítico', 'value': len(estoque_baixo), 'caption': 'Itens com risco operacional'},
        {'label': 'Produto líder', 'value': top_item, 'caption': 'Maior destaque em receita'},
    ])

    if variacao <= -10:
        st.warning('Queda relevante de faturamento detectada no comparativo recente. Vale revisar mix, equipe e ações promocionais.')
    elif variacao >= 10:
        st.success('A operação está acelerando no comparativo recente. Ótimo momento para consolidar boas práticas.')
    else:
        st.info('Variação de faturamento dentro de uma faixa estável no período analisado.')

    analise_importada = analisar_operacao_importada(empresa)
    metricas = analise_importada.get('metricas', {})
    insights_hist = [dict(row) for row in listar_insights_ia_historico(empresa, limite=8)]
    uploads_hist = [dict(row) for row in listar_uploads_historico(empresa, limite=8)]
    recentes = [dict(row) for row in listar_vendas_recentes(empresa, limite=12)]
    serie = build_sales_timeseries(empresa, limit=90)
    alert_cards = collect_operational_alerts(empresa, indicadores, analise_importada, checklist)

    render_insight_cards(alert_cards)

    with st.container():
        left, right = st.columns([1.3, 1])
        with left:
            render_section_header('Decisões da IA', 'Leitura analítica com foco em ação operacional.')
            if analise_importada.get('insights') or analise_importada.get('recomendacoes'):
                st.markdown('<div class="ia-callout"><h3>Decisões da IA</h3><p>A inteligência sintetizou os principais sinais da operação e destacou os próximos movimentos recomendados.</p></div>', unsafe_allow_html=True)
                cards = []
                for insight in (analise_importada.get('insights') or [])[:3]:
                    cards.append({'tone': 'info', 'title': 'Leitura identificada', 'body': insight})
                for recomendacao in (analise_importada.get('recomendacoes') or [])[:2]:
                    cards.append({'tone': 'success', 'title': 'Ação recomendada', 'body': recomendacao})
                render_insight_cards(cards)
            else:
                st.info('Ainda não há dados suficientes para gerar leitura automática da operação.')

            if metricas:
                render_divider()
                stat1, stat2, stat3 = st.columns(3)
                hora_pico = metricas.get('hora_pico')
                stat1.metric('Pico operacional', f'{hora_pico:02d}h' if isinstance(hora_pico, int) else '--')
                stat2.metric('Dia mais fraco', metricas.get('dia_fraco', 'N/D'))
                stat3.metric('Produto líder', metricas.get('top_produto', 'N/D'))

        with right:
            render_section_header('Alertas operacionais', 'Riscos reais e sinais para monitorar.')
            render_insight_cards(alert_cards[:3])
            if AIOperacional.detectar_queda_vendas(empresa):
                warning('Queda de faturamento detectada nas últimas semanas', empresa)

    render_divider()
    with st.container():
        col_a, col_b = st.columns([1.25, 1])
        with col_a:
            render_section_header('Gráfico de vendas', 'Evolução recente do faturamento.')
            if not serie.empty:
                st.line_chart(serie.set_index('data_ref')['total'], use_container_width=True)
            else:
                st.info('Nenhum dado recente disponível para tendência.')

        with col_b:
            render_section_header('Produtos em destaque', 'Comparativo de desempenho por receita.')
            if indicadores['vendas_por_item']:
                df_comp = pd.DataFrame([dict(row) for row in indicadores['vendas_por_item'][:5]])
                st.bar_chart(df_comp.set_index('item')['total'], use_container_width=True)
            else:
                st.info('Sem base suficiente para comparação de produtos.')

    render_divider()
    with st.container():
        bottom_left, bottom_right = st.columns([1.2, 1])
        with bottom_left:
            render_section_header('Dados recentes importados', 'Últimas informações incorporadas ao sistema.')
            if analise_importada.get('recentes'):
                st.dataframe(pd.DataFrame(analise_importada['recentes']), use_container_width=True)
            elif recentes:
                st.dataframe(pd.DataFrame(recentes), use_container_width=True)
            else:
                st.info('Nenhum dado recente disponível no banco.')

        with bottom_right:
            render_section_header('Histórico de uploads', 'Rastreabilidade das importações do ChefWeb.')
            if uploads_hist:
                df_uploads = pd.DataFrame(uploads_hist)
                cols = [col for col in ['criado_em', 'nome_arquivo', 'tipo_arquivo', 'linhas_importadas', 'faturamento_importado', 'status'] if col in df_uploads.columns]
                st.dataframe(df_uploads[cols], use_container_width=True)
            else:
                st.info('Nenhum upload registrado para esta empresa.')

    render_divider()
    with st.container():
        insights_col, products_col = st.columns([1, 1.2])
        with insights_col:
            render_section_header('Histórico de insights', 'Memória recente da inteligência operacional.')
            if insights_hist:
                df_insights = pd.DataFrame(insights_hist)
                cols = [col for col in ['criado_em', 'categoria', 'insight', 'recomendacao', 'prioridade'] if col in df_insights.columns]
                st.dataframe(df_insights[cols], use_container_width=True)
            else:
                st.info('Nenhum insight histórico salvo ainda.')
        with products_col:
            render_section_header('Produtos com maior receita', 'Itens que puxam o resultado da operação.')
            vendas_item = indicadores['vendas_por_item']
            if vendas_item:
                df_vendas = pd.DataFrame([dict(row) for row in vendas_item])
                st.dataframe(
                    df_vendas[['item', 'qtd', 'total']].rename(
                        columns={'item': 'Produto', 'qtd': 'Quantidade', 'total': 'Total (R$)'}
                    ),
                    use_container_width=True,
                )
            else:
                st.info('As vendas ainda não possuem volume suficiente para ranking por item.')

    render_divider()
    st.subheader('Entrada de vendas')
    st.info('O registro de vendas desta operação é alimentado pelos arquivos e relatórios importados do ChefWeb.')
    st.caption('Para atualizar faturamento, pedidos e produtos vendidos, use a página "Importar Dados".')


def render_importar_dados(empresa):
    render_page_header(
        empresa,
        'Importar Dados',
        'Envie relatórios em CSV, Excel, PDF ou imagem para leitura automática, consolidação no banco e análise por IA.',
    )

    uploaded = st.file_uploader(
        'Carregar arquivo do ChefWeb',
        type=['csv', 'xlsx', 'xls', 'pdf', 'png', 'jpg', 'jpeg'],
        help='Arquivos são salvos automaticamente em data/uploads/.',
    )
    processar = st.button('Processar arquivo', type='primary')

    if processar and uploaded is None:
        st.error('Selecione um arquivo antes de iniciar o processamento.')

    if processar and uploaded is not None:
        with st.spinner('Processando arquivo e integrando dados ao Mestre IA...'):
            try:
                resultado = process_chefweb_upload(uploaded, empresa)
                info(f"Arquivo ChefWeb processado: {resultado['filename']}", empresa)
                st.success(f"Importação concluída com {resultado['imported_rows']} linha(s) integradas.")

                m1, m2, m3 = st.columns(3)
                m1.metric('Linhas importadas', resultado['imported_rows'])
                m2.metric('Faturamento importado', f"R$ {resultado['imported_total']:.2f}")
                m3.metric('Pedidos identificados', resultado['pedidos_total'])

                analise_upload = registrar_analise_operacional(empresa)
                if analise_upload.get('insights'):
                    st.subheader('Insights gerados após a importação')
                    for insight in analise_upload['insights']:
                        st.write(f'- {insight}')
                if analise_upload.get('recomendacoes'):
                    st.caption('Recomendações da IA')
                    for recomendacao in analise_upload['recomendacoes']:
                        st.write(f'- {recomendacao}')

                for aviso in resultado.get('warnings', []):
                    st.warning(aviso)

                if isinstance(resultado.get('preview'), pd.DataFrame) and not resultado['preview'].empty:
                    st.subheader('Prévia original do arquivo')
                    st.dataframe(resultado['preview'], use_container_width=True)

                if isinstance(resultado.get('normalized_preview'), pd.DataFrame) and not resultado['normalized_preview'].empty:
                    st.subheader('Dados normalizados para o sistema')
                    st.dataframe(resultado['normalized_preview'], use_container_width=True)

                if resultado.get('text_preview'):
                    st.subheader('Texto extraído do PDF')
                    st.text_area('Conteúdo identificado', value=resultado['text_preview'], height=220)
            except Exception as exc:
                error(f'Erro ao processar upload ChefWeb: {exc}', empresa)
                st.error(f'Erro ao processar arquivo: {exc}')

    render_divider()
    col1, col2 = st.columns(2)
    with col1:
        st.subheader('Histórico local de importação')
        historico = list_import_history(limit=10)
        if historico:
            st.dataframe(pd.DataFrame(historico), use_container_width=True)
        else:
            st.info('Ainda não há histórico local de importação.')
    with col2:
        st.subheader('Histórico operacional no banco')
        uploads_db = listar_uploads_historico(empresa, limite=10)
        if uploads_db:
            st.dataframe(pd.DataFrame([dict(row) for row in uploads_db]), use_container_width=True)
        else:
            st.info('Nenhum upload operacional registrado para esta empresa.')


def render_ia(empresa):
    render_page_header(
        empresa,
        'Inteligência',
        'Combine histórico de vendas, contexto externo e padrões da operação para decidir com mais confiança.',
    )

    col1, col2 = st.columns([1, 1.15])
    with col1:
        resultado = None
        if st.button('Executar análise da operação', type='primary'):
            resultado = AIOperacional.analisar_dados(empresa)
            info('Análise de dados executada', empresa)

        st.subheader('Decisões da IA')
        if resultado is not None:
            decisoes = []
            for insight in resultado['insights'][:2]:
                texto = insight.lower()
                if 'queda' in texto or 'baixo' in texto or 'pendente' in texto:
                    st.warning(f"{insight} Criar ação corretiva imediata.")
                elif 'maior receita' in texto or 'crescimento' in texto or 'estável' in texto:
                    st.success(f"{insight} Bom desempenho. Manter operação.")
                else:
                    st.info(f"{insight} Revisar e acompanhar de perto.")
                decisoes.append(insight)
            for recomendacao in resultado['recomendacoes'][:3]:
                texto = recomendacao.lower()
                if 'promo' in texto or 'reabaste' in texto or 'refor' in texto:
                    st.warning(recomendacao)
                elif 'continuar' in texto or 'manter' in texto:
                    st.success(recomendacao)
                else:
                    st.info(recomendacao)
            st.caption(f"Análise gerada em {resultado['timestamp']}")
        else:
            st.info('Execute a análise para receber decisões operacionais da IA.')

    with col2:
        historico = listar_insights_ia_historico(empresa, limite=12)
        st.subheader('Histórico recente da inteligência')
        if historico:
            st.dataframe(pd.DataFrame([dict(row) for row in historico]), use_container_width=True)
        else:
            st.info('A IA ainda não salvou insights históricos para esta unidade.')

    info_empresa = obter_empresa(empresa)
    if info_empresa:
        lat = info_empresa.get('latitude')
        lon = info_empresa.get('longitude')
        cidade = info_empresa.get('cidade')
        if (lat is not None and lon is not None) or cidade:
            fatores = assess_location_impact(lat, lon, cidade, days=3)
            render_divider()
            st.subheader('Fatores externos da operação')
            erros_fontes = fatores.get('errors') or []
            if cidade:
                import os
                if not os.environ.get('EVENTBRITE_TOKEN'):
                    st.info('Eventos externos estão desativados. Configure o token do Eventbrite em Administrador para habilitar a coleta real.')
            if erros_fontes:
                st.warning('Parte das fontes externas falhou. O sistema manteve fallback para não interromper a análise.')
                for mensagem in erros_fontes:
                    detalhe = (mensagem or '').lower()
                    if detalhe.startswith('weather:'):
                        st.write('- Clima: consulta indisponível no momento.')
                    elif detalhe.startswith('events:'):
                        st.write('- Eventos: fonte externa indisponível no momento.')
                    else:
                        st.write('- Fonte externa temporariamente indisponível.')
                    st.caption(f'Detalhe técnico: {mensagem}')

            c1, c2 = st.columns(2)
            with c1:
                st.metric('Impact score', f"{fatores.get('impact_score', 0):.2f}")
                for motivo in fatores.get('reasons', []):
                    st.write(f'- {motivo}')
            with c2:
                if fatores.get('events'):
                    st.write('Eventos próximos')
                    st.dataframe(pd.DataFrame(fatores['events']), use_container_width=True)
                elif cidade:
                    st.info('Nenhum evento próximo retornado para a cidade informada.')

            if fatores.get('weather'):
                st.subheader('Clima previsto')
                try:
                    st.dataframe(pd.DataFrame(fatores['weather'].get('daily', [])), use_container_width=True)
                except Exception:
                    st.json(fatores['weather'])


def render_vision(empresa, embedded: bool = False):
    if embedded:
        st.subheader('Conferência visual de estoque')
        st.caption('Cadastre referências visuais dos itens e use a IA para apoiar a identificação e a contagem por imagem.')
    else:
        render_page_header(
            empresa,
            'Visão Computacional',
            'Cadastre referências visuais dos itens de estoque e use a IA para apoiar a identificação e a contagem por imagem.',
        )
    estoque_atual = [dict(row) for row in listar_estoque(empresa)]
    itens_estoque = [row['item'] for row in estoque_atual] or ['Sem itens cadastrados']
    referencias = listar_referencias_visuais(empresa, limite=50)
    historico = historico_contagens_estoque(empresa, limite=15)

    aba1, aba2, aba3 = st.tabs(['Referências visuais', 'Contagem por imagem', 'Histórico'])

    with aba1:
        st.subheader('Cadastrar referência visual do item')
        st.caption('Use fotos limpas e bem iluminadas para cada item. Quanto mais referências, melhor a identificação.')
        if not estoque_atual:
            st.warning('Cadastre itens no estoque antes de criar referências visuais.')
        else:
            item_referencia = st.selectbox('Item do estoque', itens_estoque, key='vision_ref_item')
            nome_modelo = st.text_input('Nome da referência', value='Frente da embalagem', key='vision_ref_name')
            arquivo_ref = st.file_uploader(
                'Imagem de referência',
                type=['png', 'jpg', 'jpeg'],
                key='vision_reference_upload',
            )
            if st.button('Salvar referência visual', type='primary', key='save_visual_reference'):
                if arquivo_ref is None:
                    st.error('Envie uma imagem de referência antes de salvar.')
                else:
                    try:
                        resultado_ref = salvar_modelo_visual_estoque(
                            arquivo_ref,
                            empresa=empresa,
                            item=item_referencia,
                            nome_modelo=nome_modelo,
                        )
                        info(f"Referência visual cadastrada para {item_referencia}", empresa)
                        st.success(f"Referência salva para {resultado_ref['item']}.")
                        st.rerun()
                    except Exception as exc:
                        error(f'Erro ao salvar referência visual: {exc}', empresa)
                        st.error(f'Erro ao salvar referência: {exc}')

        render_divider()
        st.subheader('Referências cadastradas')
        if referencias:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            'Item': ref['item'],
                            'Modelo': ref['model_name'],
                            'Arquivo': ref['reference_path'],
                            'Criado em': ref['created_at'],
                        }
                        for ref in referencias
                    ]
                ),
                use_container_width=True,
            )
        else:
            st.info('Ainda não há referências visuais cadastradas para esta empresa.')

    with aba2:
        st.subheader('Contagem de estoque por imagem')
        st.caption('A IA compara a imagem com as referências já cadastradas e registra a conferência no histórico.')
        item_foco = st.selectbox('Item esperado na imagem', ['Auto detectar'] + itens_estoque, key='vision_focus_item')
        uploaded = st.file_uploader('Escolha uma imagem', type=['png', 'jpg', 'jpeg'], key='vision_upload')
        use_yolo = st.checkbox('Usar YOLO se estiver disponível', value=False)
        min_area = st.slider('Área mínima para considerar objeto (px)', min_value=10, max_value=500, value=50)
        if uploaded is not None:
            image_bytes = uploaded.read()
            st.image(image_bytes, caption='Imagem enviada', use_container_width=True)
            if st.button('Analisar contagem com IA', type='primary', key='vision_count_run'):
                with st.spinner('Analisando imagem de estoque...'):
                    try:
                        resultado = analisar_contagem_estoque(
                            uploaded,
                            empresa=empresa,
                            item_foco=item_foco,
                            use_yolo=use_yolo,
                            min_area=min_area,
                        )
                        deteccao = resultado['detection']
                        classificacao = resultado['classification']

                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric('Quantidade detectada', int(deteccao.get('total_count', 0)))
                        col2.metric('Item identificado', resultado.get('identified_item') or 'Não identificado')
                        col3.metric('Confiança', f"{float(classificacao.get('confidence') or 0.0) * 100:.1f}%")
                        col4.metric(
                            'Diferença vs estoque',
                            '--' if resultado.get('difference') is None else int(resultado['difference']),
                        )

                        st.info(resultado['recommendation'])
                        for observacao in resultado.get('observations', []):
                            st.warning(observacao)

                        if resultado.get('current_stock') is not None:
                            st.write(f"Estoque cadastrado atual: {resultado['current_stock']}")

                        ranking = classificacao.get('ranking') or []
                        if ranking:
                            st.subheader('Ranking de similaridade')
                            st.dataframe(pd.DataFrame(ranking), use_container_width=True)

                        bboxes = deteccao.get('bboxes', [])
                        if bboxes:
                            st.subheader('Objetos detectados')
                            st.dataframe(pd.DataFrame(bboxes), use_container_width=True)

                        annotated_b64 = deteccao.get('annotated_image')
                        if annotated_b64:
                            annotated_bytes = base64.b64decode(annotated_b64)
                            st.image(annotated_bytes, caption='Imagem anotada', use_container_width=True)

                        checklist_result = analyze_checklist_from_image(image_bytes)
                        st.subheader('Estrutura complementar de checklist visual')
                        st.json(checklist_result)
                        info('Contagem de estoque por imagem executada', empresa)
                        st.success('Conferência visual registrada com sucesso.')
                    except Exception as exc:
                        error(f'Erro ao processar imagem de estoque: {exc}', empresa)
                        st.error(f'Erro ao processar imagem: {exc}')

    with aba3:
        st.subheader('Últimas conferências por IA')
        if historico:
            st.dataframe(pd.DataFrame(historico), use_container_width=True)
        else:
            st.info('Nenhuma conferência visual foi registrada ainda.')


def render_estoque(empresa):
    render_page_header(
        empresa,
        'Estoque',
        'Monitore itens críticos, atualize quantidades e use a visão computacional para apoiar a conferência física do estoque.',
    )
    aba1, aba2 = st.tabs(['Controle de estoque', 'Conferência visual com IA'])

    with aba1:
        dados = listar_estoque(empresa)
        st.subheader('Itens em estoque')
        st.dataframe(dados, use_container_width=True)

        st.subheader('Atualizar item de estoque')
        if dados:
            item_id = st.selectbox('Item', [f"{r['id']} - {r['item']}" for r in dados], key='estoque_item_select')
            selecionado = int(item_id.split(' - ')[0])
            atual = [r for r in dados if r['id'] == selecionado][0]
            quantidade = st.number_input('Quantidade', min_value=0, value=int(atual['quantidade']))
            minimo = st.number_input('Mínimo', min_value=0, value=int(atual['minimo']))
            if st.button('Salvar estoque'):
                atualizar_item_estoque(selecionado, quantidade, minimo)
                info(f'Estoque do item {selecionado} atualizado para {quantidade}', empresa)
                st.success('Estoque atualizado com sucesso.')
                st.rerun()

        estoque_baixo = itens_estoque_baixo(empresa)
        render_divider()
        if estoque_baixo:
            st.warning(f'{len(estoque_baixo)} item(ns) com estoque baixo.')
            st.table([{'Item': item['item'], 'Quantidade': item['quantidade'], 'Mínimo': item['minimo']} for item in estoque_baixo])
        else:
            st.success('Estoques dentro dos níveis mínimos definidos.')

    with aba2:
        render_vision(empresa, embedded=True)


def render_configuracoes(empresa):
    render_page_header(
        empresa,
        'Configurações',
        'Centralize ajustes estruturais, integrações e registros administrativos em um único espaço.',
    )
    aba1, aba2, aba3 = st.tabs(['Empresas', 'Administrador', 'Registros'])
    with aba1:
        render_empresas(empresa)
    with aba2:
        render_admin(empresa)
    with aba3:
        render_logs(empresa)


def render_empresas(empresa):
    st.subheader('Empresas')
    st.caption('Gerencie unidades, contatos e localização das operações conectadas à central DOJO.')

    st.subheader('Empresas cadastradas')
    empresas_list = obter_empresas_completas()
    if empresas_list:
        st.caption(f'Total cadastradas: {len(empresas_list)}')
        st.dataframe(pd.DataFrame(empresas_list))
    else:
        st.info('Nenhuma empresa cadastrada ainda.')

    st.subheader('Adicionar nova empresa')
    with st.form('form_empresa'):
        nome = st.text_input('Nome da empresa', help='Nome único da unidade ou empresa.')
        contato = st.text_input('Contato (WhatsApp/telefone)', help='Opcional. Ex.: +5511999999999')
        tipo = st.selectbox('Tipo', ['restaurante', 'delivery', 'multiunidade'])
        ativa = st.checkbox('Ativa', value=True)
        enviar = st.form_submit_button('Cadastrar empresa')
        if enviar:
            nome_limpo = (nome or '').strip()
            if not nome_limpo:
                st.error('Informe um nome válido para a empresa.')
            else:
                existentes = [e.get('nome', '').strip().lower() for e in (empresas_list or [])]
                if nome_limpo.lower() in existentes:
                    st.error('Já existe uma empresa com esse nome.')
                else:
                    criar_empresa(nome_limpo, tipo, ativa)
                    if contato and contato.strip():
                        try:
                            atualizar_contato_empresa(nome=nome_limpo, contato=contato.strip())
                        except Exception:
                            pass
                    info(f'Empresa cadastrada: {nome_limpo}', empresa)
                    st.success('Empresa cadastrada com sucesso.')
                    st.rerun()

    render_divider()
    st.subheader('Atualizar localização da empresa')
    if not empresas_list:
        st.info('Cadastre uma empresa para editar localização e contato.')
        return

    nomes = [e['nome'] for e in empresas_list]
    selecionada = st.selectbox('Selecione empresa', nomes, key='loc_sel')
    emp = next((e for e in empresas_list if e['nome'] == selecionada), None)
    if not emp:
        st.warning('Empresa não encontrada na lista atual.')
        return

    if st.session_state.get('loc_sel_prev') != selecionada:
        st.session_state['loc_lat'] = '' if emp.get('latitude') is None else str(emp.get('latitude'))
        st.session_state['loc_lon'] = '' if emp.get('longitude') is None else str(emp.get('longitude'))
        st.session_state['loc_cidade'] = '' if emp.get('cidade') is None else emp.get('cidade')
        st.session_state['loc_endereco'] = '' if emp.get('endereco') is None else emp.get('endereco')
        st.session_state['loc_contato'] = '' if emp.get('contato') is None else emp.get('contato')
        st.session_state['loc_auto'] = bool(emp.get('auto_send_plan'))
        st.session_state['loc_sel_prev'] = selecionada

    st.caption('Dica: preencha o endereço e use a busca para completar latitude e longitude automaticamente.')
    lat_in = st.text_input('Latitude', key='loc_lat')
    lon_in = st.text_input('Longitude', key='loc_lon')
    cidade_in = st.text_input('Cidade', key='loc_cidade')
    endereco_in = st.text_input('Endereço', key='loc_endereco')
    contato_in = st.text_input('Contato', key='loc_contato')
    auto_send_in = st.checkbox('Enviar plano automaticamente (WhatsApp)', key='loc_auto')

    if st.button('Buscar coordenadas pelo endereço', key='geo_loc'):
        if endereco_in.strip():
            geo = geocode_address(endereco_in)
            if geo:
                st.session_state['loc_lat'] = str(geo['latitude'])
                st.session_state['loc_lon'] = str(geo['longitude'])
                st.success(f"Encontrado: {geo.get('display_name')}")
            else:
                st.error('Não foi possível encontrar coordenadas para o endereço informado.')
        else:
            st.error('Informe um endereço para buscar coordenadas.')

    if st.button('Salvar localização', key='save_loc'):
        try:
            lat_v = float(lat_in) if lat_in.strip() else None
            lon_v = float(lon_in) if lon_in.strip() else None
            if lat_v is not None and not (-90 <= lat_v <= 90):
                raise ValueError('Latitude fora do intervalo -90 a 90.')
            if lon_v is not None and not (-180 <= lon_v <= 180):
                raise ValueError('Longitude fora do intervalo -180 a 180.')
        except Exception:
            st.error('Latitude ou longitude inválida.')
            lat_v = None
            lon_v = None

        atualizar_local_empresa(
            nome=selecionada,
            latitude=lat_v,
            longitude=lon_v,
            cidade=cidade_in or None,
            endereco=endereco_in or None,
        )
        try:
            atualizar_contato_empresa(nome=selecionada, contato=contato_in or None)
        except Exception:
            pass
        try:
            from services.empresa_service import atualizar_auto_send_empresa
            atualizar_auto_send_empresa(selecionada, bool(auto_send_in))
        except Exception:
            pass
        info(f'Localização atualizada para {selecionada}', empresa)
        st.success('Localização salva com sucesso.')
        st.rerun()


def render_admin(empresa):
    st.subheader('Administrador')
    st.caption('Configure integrações externas e mantenha o ambiente pronto para automações mais avançadas.')
    import os
    from services.config_service import set_env_var

    current = os.environ.get('EVENTBRITE_TOKEN', '')
    st.subheader('Integração Eventbrite')
    st.write('Informe o token para habilitar a coleta real de eventos externos por cidade.')
    token = st.text_input('Eventbrite Token', value=current, type='password')
    if st.button('Salvar token Eventbrite'):
        if not token or not token.strip():
            st.error('Token inválido.')
        else:
            try:
                set_env_var('EVENTBRITE_TOKEN', token.strip())
                st.success('Token salvo com sucesso. Se necessário, reinicie a aplicação.')
            except Exception as exc:
                st.error(f'Erro ao salvar token: {exc}')


def render_logs(empresa):
    st.subheader('Registros e Auditoria')
    st.caption('Acompanhe eventos operacionais, uploads recentes e o histórico que sustenta a inteligência do sistema.')
    col1, col2 = st.columns([1.2, 1])
    with col1:
        st.subheader('Logs do sistema')
        logs = obter_logs(200)
        st.dataframe(logs, use_container_width=True)
    with col2:
        st.subheader('Últimas vendas registradas')
        recentes = listar_vendas_recentes(empresa, limite=20)
        if recentes:
            st.dataframe(pd.DataFrame([dict(row) for row in recentes]), use_container_width=True)
        else:
            st.info('Ainda não há vendas recentes para exibir.')

    render_divider()
    uploads = listar_uploads_historico(empresa, limite=10)
    if uploads:
        st.subheader('Uploads recentes desta empresa')
        st.dataframe(pd.DataFrame([dict(row) for row in uploads]), use_container_width=True)


if __name__ == '__main__':
    run_app()
