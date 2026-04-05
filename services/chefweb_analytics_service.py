from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from database.queries import adicionar_insight_ia_historico
from services.vendas_service import listar_vendas_recentes

DIAS_SEMANA_PT = {
    "Monday": "segunda-feira",
    "Tuesday": "terça-feira",
    "Wednesday": "quarta-feira",
    "Thursday": "quinta-feira",
    "Friday": "sexta-feira",
    "Saturday": "sábado",
    "Sunday": "domingo",
}


def analisar_operacao_importada(empresa: Optional[str] = None) -> Dict[str, object]:
    rows = [dict(row) for row in listar_vendas_recentes(empresa, limite=500)]
    if not rows:
        return {
            "metricas": {},
            "insights": [],
            "recomendacoes": [],
            "recentes": [],
        }

    df = pd.DataFrame(rows)
    df["data_dt"] = pd.to_datetime(df["data"], errors="coerce")
    df["quantidade"] = pd.to_numeric(df["quantidade"], errors="coerce").fillna(0)
    df["total"] = pd.to_numeric(df["total"], errors="coerce").fillna(0.0)
    df["hora"] = df["data_dt"].dt.hour
    df["dia_semana"] = df["data_dt"].dt.day_name()

    insights: List[str] = []
    recomendacoes: List[str] = []
    metricas: Dict[str, object] = {}

    hourly = df.dropna(subset=["hora"]).groupby("hora", as_index=False)["total"].sum().sort_values("total", ascending=False)
    if not hourly.empty:
        hora_pico = int(hourly.iloc[0]["hora"])
        metricas["hora_pico"] = hora_pico
        insights.append(f"Horário de pico identificado às {hora_pico:02d}h.")
        recomendacoes.append(f"Reforçar equipe e produção antes de {hora_pico:02d}h.")

    weekday = df.dropna(subset=["dia_semana"]).groupby("dia_semana", as_index=False)["total"].sum().sort_values("total")
    if not weekday.empty:
        dia_fraco = str(weekday.iloc[0]["dia_semana"])
        dia_fraco = DIAS_SEMANA_PT.get(dia_fraco, dia_fraco)
        metricas["dia_fraco"] = dia_fraco
        insights.append(f"Dia mais fraco detectado: {dia_fraco}.")
        recomendacoes.append(f"Criar promoção, combo ou ação comercial no dia {dia_fraco}.")

    itens = df.groupby("item", as_index=False).agg({"quantidade": "sum", "total": "sum"}).sort_values("quantidade", ascending=False)
    if not itens.empty:
        top_produto = itens.iloc[0]
        metricas["top_produto"] = str(top_produto["item"])
        insights.append(f"Produto mais vendido: {top_produto['item']} com {int(top_produto['quantidade'])} unidades.")
        recomendacoes.append(f"Aumentar produção e disponibilidade do item {top_produto['item']}.")
        if len(itens) > 2:
            item_fraco = itens.iloc[-1]
            insights.append(f"Produto com menor giro recente: {item_fraco['item']}.")
            recomendacoes.append(f"Produto {item_fraco['item']} está vendendo pouco; revisar oferta, preço ou exposição.")

    recentes = df.head(15).copy()
    recentes["data"] = recentes["data_dt"].fillna(pd.Timestamp(datetime.now())).dt.strftime("%Y-%m-%d %H:%M")

    return {
        "metricas": metricas,
        "insights": insights,
        "recomendacoes": recomendacoes,
        "recentes": recentes[["empresa", "data", "item", "quantidade", "total"]].to_dict("records"),
    }


def registrar_analise_operacional(empresa: Optional[str] = None) -> Dict[str, object]:
    resultado = analisar_operacao_importada(empresa)
    empresa_ref = empresa or "Japatê"
    for insight in resultado.get("insights", []):
        recomendacao = None
        for item in resultado.get("recomendacoes", []):
            if "pico" in insight.lower() and "equipe" in item.lower():
                recomendacao = item
                break
            if "fraco" in insight.lower() and "promo" in item.lower():
                recomendacao = item
                break
            if "mais vendido" in insight.lower() and "produção" in item.lower():
                recomendacao = item
                break
            if "menor giro" in insight.lower() and "vendendo pouco" in item.lower():
                recomendacao = item
                break
        prioridade = "alta" if ("pico" in insight.lower() or "fraco" in insight.lower()) else "media"
        adicionar_insight_ia_historico(empresa_ref, "operacao", insight, recomendacao, prioridade)
    return resultado
