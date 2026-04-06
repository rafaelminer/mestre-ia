import json
import re
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from database.queries import adicionar_upload_historico
from services.vendas_service import registrar_vendas_detalhadas


UPLOAD_DIR = Path(__file__).resolve().parent.parent / "data" / "uploads"
UPLOAD_INDEX = UPLOAD_DIR / "imports_index.json"


def _ensure_upload_dir() -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOAD_DIR


def _sanitize_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", filename or "upload")
    return cleaned.strip("._") or "upload"


def save_uploaded_file(uploaded_file, empresa: str) -> Path:
    upload_dir = _ensure_upload_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix_name = _sanitize_filename(uploaded_file.name)
    target = upload_dir / f"{timestamp}_{empresa}_{suffix_name}"
    target.write_bytes(uploaded_file.getbuffer())
    return target


def _read_csv(path: Path) -> pd.DataFrame:
    encodings = ["utf-8", "utf-8-sig", "latin-1"]
    last_error = None
    for encoding in encodings:
        try:
            return pd.read_csv(path, encoding=encoding)
        except Exception as exc:
            last_error = exc
    raise last_error


def _read_excel(path: Path) -> pd.DataFrame:
    errors = []
    raw = path.read_bytes()

    # ChefWeb exports HTML files with .xls extension — detect and handle
    if raw[:200].lstrip()[:1] in (b"<", b"\xef") or b"<html" in raw[:512].lower() or b"<HTML" in raw[:512]:
        for encoding in ["utf-8", "utf-8-sig", "latin-1"]:
            try:
                # header=0 usa primeira linha como cabeçalho; skiprows tenta ignorar linhas de título
                tables = pd.read_html(path, encoding=encoding, flavor="lxml", header=0)
                if tables:
                    df = tables[0]
                    # Se a primeira linha parece um cabeçalho repetido, tenta com skiprows=1
                    if df.shape[0] > 1 and str(df.iloc[0, 0]).strip().lower() == str(df.columns[0]).strip().lower():
                        tables2 = pd.read_html(path, encoding=encoding, flavor="lxml", header=0, skiprows=1)
                        if tables2:
                            df = tables2[0]
                    return df
            except ImportError:
                break
            except Exception as exc:
                errors.append(f"html({encoding}): {exc}")
        # fallback sem lxml
        for encoding in ["utf-8", "utf-8-sig", "latin-1"]:
            try:
                tables = pd.read_html(path, encoding=encoding, header=0)
                if tables:
                    return tables[0]
            except Exception as exc:
                errors.append(f"html_fallback({encoding}): {exc}")

    # Try openpyxl (real .xlsx)
    try:
        return pd.read_excel(path, engine="openpyxl")
    except Exception as exc:
        errors.append(f"openpyxl: {exc}")

    # Try xlrd (real .xls binary)
    try:
        return pd.read_excel(path, engine="xlrd")
    except Exception as exc:
        errors.append(f"xlrd: {exc}")

    raise ValueError(f"Não foi possível ler o arquivo enviado. Tentativas: {' | '.join(errors)}")


def _extract_pdf_text(path: Path) -> str:
    readers = []
    try:
        from pypdf import PdfReader  # type: ignore
        readers.append(PdfReader)
    except Exception:
        pass
    try:
        from PyPDF2 import PdfReader  # type: ignore
        readers.append(PdfReader)
    except Exception:
        pass

    if not readers:
        return "Leitor de PDF indisponivel no ambiente atual."

    for reader_cls in readers:
        try:
            reader = reader_cls(str(path))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages).strip()
        except Exception:
            continue
    return ""


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {}
    for col in df.columns:
        normalized = _strip_accents(str(col).strip().lower())
        normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
        renamed[col] = normalized.strip("_")
    return df.rename(columns=renamed)


def _find_first_column(columns: List[str], aliases: List[str]) -> Optional[str]:
    for alias in aliases:
        for col in columns:
            if col == alias or alias in col:
                return col
    return None


def _build_datetime_series(df: pd.DataFrame) -> pd.Series:
    columns = list(df.columns)
    date_col = _find_first_column(columns, ["data", "date", "dia", "movimento", "datetime"])
    hour_col = _find_first_column(columns, ["hora", "horario", "time"])
    if date_col and hour_col and date_col != hour_col:
        combined = (
            df[date_col].astype(str).str.strip() + " " + df[hour_col].astype(str).str.strip()
        )
        return pd.to_datetime(combined, errors="coerce", dayfirst=True)
    if date_col:
        return pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
    if hour_col:
        base = datetime.now().strftime("%Y-%m-%d")
        combined = base + " " + df[hour_col].astype(str).str.strip()
        return pd.to_datetime(combined, errors="coerce", dayfirst=True)
    return pd.Series([pd.NaT] * len(df))


def normalize_sales_data(df: pd.DataFrame, empresa: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["empresa", "data", "item", "categoria", "quantidade", "total", "pedidos"])

    clean_df = _normalize_columns(df.copy())
    clean_df = clean_df.dropna(how="all")
    clean_df.columns = [str(col) for col in clean_df.columns]

    item_col = _find_first_column(clean_df.columns.tolist(), ["item", "produto", "descricao", "descri", "prato", "sku", "nome", "mercadoria", "desc"])
    quantity_col = _find_first_column(clean_df.columns.tolist(), ["quantidade", "qtd", "qtde", "itens", "volume", "qt", "qnt", "quant"])
    total_col = _find_first_column(clean_df.columns.tolist(), ["total", "faturamento", "valor_total", "receita", "venda", "valor", "preco", "preco_total", "subtotal", "fat"])
    pedidos_col = _find_first_column(clean_df.columns.tolist(), ["pedidos", "pedido", "orders", "num_pedido", "n_pedido", "comanda"])
    categoria_col = _find_first_column(clean_df.columns.tolist(), ["categoria", "grupo", "familia", "setor", "tipo", "class"])

    normalized = pd.DataFrame(index=clean_df.index)
    normalized["empresa"] = [empresa] * len(clean_df)
    normalized["data"] = _build_datetime_series(clean_df)
    normalized["item"] = clean_df[item_col].astype(str).str.strip() if item_col else "ChefWeb"
    normalized["categoria"] = clean_df[categoria_col].astype(str).str.strip() if categoria_col else "Geral"
    normalized["quantidade"] = pd.to_numeric(clean_df[quantity_col], errors="coerce") if quantity_col else 1
    normalized["total"] = pd.to_numeric(clean_df[total_col], errors="coerce") if total_col else 0.0
    normalized["pedidos"] = pd.to_numeric(clean_df[pedidos_col], errors="coerce") if pedidos_col else normalized["quantidade"]

    normalized["quantidade"] = normalized["quantidade"].fillna(1).clip(lower=0)
    normalized["pedidos"] = normalized["pedidos"].fillna(normalized["quantidade"]).clip(lower=0)
    normalized["total"] = normalized["total"].fillna(0.0).clip(lower=0)
    normalized["item"] = normalized["item"].replace({"": "ChefWeb"}).fillna("ChefWeb")
    normalized["categoria"] = normalized["categoria"].replace({"": "Geral"}).fillna("Geral")
    normalized["data"] = normalized["data"].fillna(pd.Timestamp(datetime.now()))
    normalized["data"] = normalized["data"].dt.strftime("%Y-%m-%dT%H:%M:%S")

    normalized = normalized[(normalized["quantidade"] > 0) | (normalized["total"] > 0)]
    return normalized.reset_index(drop=True)


def _record_import_history(metadata: Dict) -> None:
    _ensure_upload_dir()
    history = []
    if UPLOAD_INDEX.exists():
        try:
            history = json.loads(UPLOAD_INDEX.read_text(encoding="utf-8"))
        except Exception:
            history = []
    history.insert(0, metadata)
    UPLOAD_INDEX.write_text(json.dumps(history[:50], ensure_ascii=False, indent=2), encoding="utf-8")


def list_import_history(limit: int = 20) -> List[Dict]:
    if not UPLOAD_INDEX.exists():
        return []
    try:
        history = json.loads(UPLOAD_INDEX.read_text(encoding="utf-8"))
        return history[:limit]
    except Exception:
        return []


def process_chefweb_upload(uploaded_file, empresa: str) -> Dict:
    import logging
    logging.info(f"Iniciando processamento de upload ChefWeb para empresa {empresa}, arquivo: {uploaded_file.name}")
    saved_path = save_uploaded_file(uploaded_file, empresa)
    logging.info(f"Arquivo salvo em: {saved_path}")
    suffix = saved_path.suffix.lower()
    warnings = []
    extracted_text = ""
    preview = pd.DataFrame()
    normalized = pd.DataFrame(columns=["empresa", "data", "item", "categoria", "quantidade", "total", "pedidos"])
    file_type = "unknown"

    if suffix == ".csv":
        file_type = "csv"
        preview = _read_csv(saved_path)
        normalized = normalize_sales_data(preview, empresa)
    elif suffix in [".xlsx", ".xls"]:
        file_type = "excel"
        preview = _read_excel(saved_path)
        normalized = normalize_sales_data(preview, empresa)
    elif suffix == ".pdf":
        file_type = "pdf"
        extracted_text = _extract_pdf_text(saved_path)
        warnings.append("PDF lido em modo textual. Estrutura pronta para parser avancado.")
    elif suffix in [".png", ".jpg", ".jpeg"]:
        file_type = "image"
        warnings.append("Imagem salva e preparada para leitura futura com IA visual.")
    else:
        warnings.append("Formato nao reconhecido para processamento automatico.")

    imported_rows = 0
    imported_total = 0.0
    if not normalized.empty:
        payload = [
            (
                row["empresa"],
                row["data"],
                row["item"],
                int(float(row["quantidade"])),
                float(row["total"]),
                row.get("categoria"),
                row["data"][11:16] if isinstance(row["data"], str) and len(row["data"]) >= 16 else None,
                int(float(row["pedidos"])),
                uploaded_file.name,
            )
            for _, row in normalized.iterrows()
        ]
        imported_rows = registrar_vendas_detalhadas(payload)
        imported_total = float(normalized["total"].sum())

    result = {
        "empresa": empresa,
        "filename": uploaded_file.name,
        "saved_path": str(saved_path),
        "file_type": file_type,
        "imported_rows": imported_rows,
        "imported_total": imported_total,
        "pedidos_total": int(normalized["pedidos"].sum()) if not normalized.empty else 0,
        "warnings": warnings,
        "preview": preview.head(20),
        "normalized_preview": normalized.head(20),
        "text_preview": extracted_text[:2000],
        "processed_at": datetime.now().isoformat(),
    }
    _record_import_history({
        "empresa": empresa,
        "filename": uploaded_file.name,
        "saved_path": str(saved_path),
        "file_type": file_type,
        "imported_rows": imported_rows,
        "imported_total": imported_total,
        "pedidos_total": result["pedidos_total"],
        "processed_at": result["processed_at"],
    })
    adicionar_upload_historico(
        empresa=empresa,
        nome_arquivo=uploaded_file.name,
        tipo_arquivo=file_type,
        caminho_arquivo=str(saved_path),
        linhas_importadas=imported_rows,
        faturamento_importado=imported_total,
        pedidos_importados=result["pedidos_total"],
        status="processado" if file_type != "unknown" else "parcial",
    )
    return result
