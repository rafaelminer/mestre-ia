from typing import List, Dict
from datetime import datetime, timedelta
import pandas as pd
from services.vendas_service import total_vendas, vendas_por_item, listar_vendas_recentes
from services.estoque_service import itens_estoque_baixo
from services.checklist_service import listar_checklist
from services.empresa_service import obter_empresa
from services.external_service import assess_location_impact


class AIOperacional:
    """Analisa dados e gera recomendações operacionais inteligentes."""

    @staticmethod
    def analisar_dados(empresa: str = None) -> Dict[str, List[str]]:
        insights = []
        recomendacoes = []

        faturamento = total_vendas(empresa)
        insights.append(f"Faturamento total atual para {empresa or 'todas as empresas'}: R$ {faturamento:.2f}")

        vendas_item = vendas_por_item(empresa)
        if vendas_item:
            top_item = vendas_item[0]
            insights.append(f"Item com maior receita: {top_item['item']} (R$ {top_item['total']:.2f})")
        else:
            insights.append("Sem vendas registradas ainda para análise de itens.")

        checklist_pendente = listar_checklist(empresa, None)
        pendentes = [c for c in checklist_pendente if c['status'] == 'pendente']
        if len(pendentes) > 0:
            insights.append(f"Existem {len(pendentes)} tarefas pendentes no checklist.")
            recomendacoes.append("Ativar processo de acompanhamento diário para checklist e distribuir responsabilidade.")

        baixos = itens_estoque_baixo(empresa)
        if baixos:
            insights.append(f"{len(baixos)} itens com estoque baixo detectados.")
            recomendacoes.append("Reabastecer itens críticos e revisar previsões de consumo.")

        # operador simples de queda de faturamento semanal (simulado)
        if AIOperacional.detectar_queda_vendas(empresa):
            insights.append("Detectada queda de faturamento nos últimos 7 dias.")
            recomendacoes.append("Implementar promoções, revisar cartões de menu e otimizar custos de insumos.")

        if faturamento > 0:
            recomendacoes.append("Continuar ações que funcionam, mas buscar reduzir desperdício e aumentar ticket médio.")

        # Analisar fatores externos relacionados à localização (clima, eventos)
        if empresa:
            info_empresa = obter_empresa(empresa)
            if info_empresa:
                lat = info_empresa.get('latitude')
                lon = info_empresa.get('longitude')
                cidade = info_empresa.get('cidade')
                fatores_locais = assess_location_impact(lat, lon, cidade, days=3)
                if fatores_locais:
                    insights.append(f"Fatores externos detectados (impact_score={fatores_locais.get('impact_score')}):")
                    for r in fatores_locais.get('reasons', []):
                        insights.append(f" - {r}")
                    score = fatores_locais.get('impact_score', 0)
                    if score < -0.2:
                        recomendacoes.append('Prepare operações para condições adversas: reforçar delivery, reduzir ocupação, revisar staff e estoques sensíveis a perda.')
                    elif score > 0.2:
                        recomendacoes.append('Prevê aumento de movimento: aumentar staff e suprimentos, otimizar checkout e controle de fluxo.')

        return {
            'insights': insights,
            'recomendacoes': recomendacoes,
            'timestamp': datetime.now().isoformat()
        }

    @staticmethod
    def detectar_queda_vendas(empresa: str = None) -> bool:
        # Simula análise de série temporal usando heurísticas simples
        from database.db import get_connection
        seven_days_ago = (datetime.now() - timedelta(days=7)).date()
        fourteen_days_ago = (datetime.now() - timedelta(days=14)).date()

        with get_connection() as conn:
            cursor = conn.cursor()
            if empresa:
                cursor.execute("SELECT SUM(total) as soma FROM vendas WHERE data >= ? AND data < ? AND empresa = ?", (fourteen_days_ago.isoformat(), seven_days_ago.isoformat(), empresa))
                anterior = cursor.fetchone()['soma'] or 0
                cursor.execute("SELECT SUM(total) as soma FROM vendas WHERE data >= ? AND data <= ? AND empresa = ?", (seven_days_ago.isoformat(), datetime.now().date().isoformat(), empresa))
                atual = cursor.fetchone()['soma'] or 0
            else:
                cursor.execute("SELECT SUM(total) as soma FROM vendas WHERE data >= ? AND data < ?", (fourteen_days_ago.isoformat(), seven_days_ago.isoformat()))
                anterior = cursor.fetchone()['soma'] or 0
                cursor.execute("SELECT SUM(total) as soma FROM vendas WHERE data >= ? AND data <= ?", (seven_days_ago.isoformat(), datetime.now().date().isoformat()))
                atual = cursor.fetchone()['soma'] or 0

        if anterior > 0 and atual < anterior * 0.9:
            return True
        return False
