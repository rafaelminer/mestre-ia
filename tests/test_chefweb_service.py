import pandas as pd

from services.chefweb_service import normalize_sales_data
from services.chefweb_analytics_service import analisar_operacao_importada


def test_normalize_sales_data_maps_common_columns():
    df = pd.DataFrame(
        [
            {"Data": "2026-04-04", "Produto": "Temaki", "Quantidade": 3, "Faturamento": 90.0},
            {"Data": "2026-04-04 19:30", "Produto": "Sushi", "Quantidade": 2, "Faturamento": 120.0},
        ]
    )

    normalized = normalize_sales_data(df, "Japao")

    assert list(normalized.columns) == ["empresa", "data", "item", "categoria", "quantidade", "total", "pedidos"]
    assert len(normalized) == 2
    assert normalized.iloc[0]["empresa"] == "Japao"
    assert normalized.iloc[0]["item"] == "Temaki"
    assert normalized.iloc[0]["categoria"] == "Geral"
    assert float(normalized.iloc[1]["total"]) == 120.0


def test_analisar_operacao_importada_without_data():
    resultado = analisar_operacao_importada("Empresa Inexistente")
    assert resultado["metricas"] == {}
    assert resultado["insights"] == []
