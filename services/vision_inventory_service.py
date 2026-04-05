import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ai.vision import build_image_signature, detect_and_count, identify_item_by_reference
from database.queries import (
    adicionar_contagem_estoque_ia,
    adicionar_modelo_visual_estoque,
    listar_contagens_estoque_ia,
    listar_modelos_visuais_estoque,
)
from services.estoque_service import listar_estoque


VISION_DIR = Path(__file__).resolve().parent.parent / "data" / "uploads" / "vision"
REFERENCE_DIR = VISION_DIR / "references"
COUNT_DIR = VISION_DIR / "counts"


def _ensure_dirs() -> None:
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    COUNT_DIR.mkdir(parents=True, exist_ok=True)


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value or "arquivo")
    return cleaned.strip("._") or "arquivo"


def _save_upload(uploaded_file, base_dir: Path, empresa: str, prefix: str) -> Path:
    _ensure_dirs()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = _safe_name(uploaded_file.name)
    target = base_dir / f"{timestamp}_{_safe_name(empresa)}_{prefix}_{filename}"
    target.write_bytes(uploaded_file.getbuffer())
    return target


def salvar_modelo_visual_estoque(uploaded_file, empresa: str, item: str, nome_modelo: Optional[str] = None) -> Dict:
    nome_modelo = (nome_modelo or item or "Referencia").strip()
    saved_path = _save_upload(uploaded_file, REFERENCE_DIR, empresa, "ref")
    image_bytes = saved_path.read_bytes()
    signature = build_image_signature(image_bytes)
    adicionar_modelo_visual_estoque(
        empresa=empresa,
        item=item,
        nome_modelo=nome_modelo,
        caminho_arquivo=str(saved_path),
        assinatura_json=json.dumps(signature),
    )
    return {
        "empresa": empresa,
        "item": item,
        "model_name": nome_modelo,
        "saved_path": str(saved_path),
        "signature": signature,
    }


def listar_referencias_visuais(empresa: str, item: Optional[str] = None, limite: int = 50) -> List[Dict]:
    rows = listar_modelos_visuais_estoque(empresa, item=item, limite=limite)
    referencias = []
    for row in rows:
        payload = dict(row)
        try:
            signature = json.loads(payload.get("assinatura_json") or "{}")
        except Exception:
            signature = {}
        referencias.append(
            {
                "id": payload.get("id"),
                "empresa": payload.get("empresa"),
                "item": payload.get("item"),
                "model_name": payload.get("nome_modelo"),
                "reference_path": payload.get("caminho_arquivo"),
                "created_at": payload.get("criado_em"),
                "signature": signature,
            }
        )
    return referencias


def analisar_contagem_estoque(uploaded_file, empresa: str, item_foco: Optional[str] = None, use_yolo: bool = False, min_area: int = 50) -> Dict:
    saved_path = _save_upload(uploaded_file, COUNT_DIR, empresa, "count")
    image_bytes = saved_path.read_bytes()
    detection = detect_and_count(image_bytes, use_yolo=use_yolo, min_area=min_area)
    referencias = listar_referencias_visuais(empresa, item=item_foco if item_foco and item_foco != "Auto detectar" else None)
    classificacao = identify_item_by_reference(image_bytes, referencias)

    item_identificado = classificacao.get("item") if classificacao.get("matched") else item_foco
    estoque_atual = None
    diferenca = None
    recomendacao = "Revisar manualmente antes de ajustar o estoque."
    observacoes = []
    estoque = [dict(row) for row in listar_estoque(empresa)]
    if item_identificado:
        item_row = next((row for row in estoque if row.get("item") == item_identificado), None)
        if item_row:
            estoque_atual = int(item_row.get("quantidade") or 0)
            diferenca = int(detection.get("total_count", 0)) - estoque_atual
            if diferenca < 0:
                recomendacao = f"Contagem visual abaixo do saldo cadastrado. Validar perdas ou saída sem lançamento de {item_identificado}."
            elif diferenca > 0:
                recomendacao = f"Contagem visual acima do saldo cadastrado. Conferir entrada ou ajuste pendente de {item_identificado}."
            else:
                recomendacao = f"Contagem visual alinhada com o estoque cadastrado para {item_identificado}."
        else:
            observacoes.append("Item identificado não foi encontrado na tabela de estoque.")
    else:
        observacoes.append("Nenhum item foi identificado com confiança suficiente nas referências cadastradas.")

    confidence = float(classificacao.get("confidence") or 0.0)
    if confidence < 0.45:
        observacoes.append("Confiança baixa na identificação visual. Cadastre mais referências do item.")

    adicionar_contagem_estoque_ia(
        empresa=empresa,
        item=item_identificado,
        quantidade_detectada=int(detection.get("total_count", 0)),
        confianca=confidence,
        estoque_atual=estoque_atual,
        diferenca=diferenca,
        caminho_arquivo=str(saved_path),
        observacoes=" | ".join(observacoes + [recomendacao]).strip(),
    )

    return {
        "saved_path": str(saved_path),
        "detection": detection,
        "classification": classificacao,
        "identified_item": item_identificado,
        "current_stock": estoque_atual,
        "difference": diferenca,
        "recommendation": recomendacao,
        "observations": observacoes,
    }


def historico_contagens_estoque(empresa: str, limite: int = 20) -> List[Dict]:
    return [dict(row) for row in listar_contagens_estoque_ia(empresa, limite=limite)]
