from io import BytesIO
from pathlib import Path
import tempfile
import uuid

from PIL import Image, ImageDraw

from database.db import init_db, insert_default_data
from services.vision_inventory_service import (
    analisar_contagem_estoque,
    historico_contagens_estoque,
    listar_referencias_visuais,
    salvar_modelo_visual_estoque,
)


class FakeUpload:
    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data

    def getbuffer(self):
        return memoryview(self._data)

    def read(self):
        return self._data


def _make_inventory_image(background_color, object_count=3):
    image = Image.new("RGB", (220, 160), background_color)
    draw = ImageDraw.Draw(image)
    for index in range(object_count):
        x = 20 + index * 55
        draw.rectangle([x, 45, x + 24, 110], fill=(255, 255, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _make_local_tmp_dir(name: str) -> Path:
    return Path(tempfile.gettempdir()) / "mestre_ia_vision_tests" / f"{name}_{uuid.uuid4().hex}"


def test_salvar_e_listar_referencias_visuais(monkeypatch):
    tmp_dir = _make_local_tmp_dir("vision_refs")
    monkeypatch.setenv("DOJO_DB_PATH", str(tmp_dir / "vision_refs.db"))
    init_db()
    insert_default_data()

    upload = FakeUpload("arroz_ref.png", _make_inventory_image((30, 160, 90), object_count=2))
    resultado = salvar_modelo_visual_estoque(upload, empresa="Japatê", item="Arroz", nome_modelo="Pacote verde")

    referencias = listar_referencias_visuais("Japatê")

    assert resultado["item"] == "Arroz"
    assert referencias
    assert referencias[0]["item"] == "Arroz"
    assert referencias[0]["model_name"] == "Pacote verde"


def test_analisar_contagem_estoque_classifica_e_registra_historico(monkeypatch):
    tmp_dir = _make_local_tmp_dir("vision_count")
    monkeypatch.setenv("DOJO_DB_PATH", str(tmp_dir / "vision_count.db"))
    init_db()
    insert_default_data()

    ref_upload = FakeUpload("arroz_ref.png", _make_inventory_image((30, 160, 90), object_count=3))
    salvar_modelo_visual_estoque(ref_upload, empresa="Japatê", item="Arroz", nome_modelo="Pacote verde")

    count_upload = FakeUpload("arroz_count.png", _make_inventory_image((30, 160, 90), object_count=3))
    resultado = analisar_contagem_estoque(count_upload, empresa="Japatê", item_foco="Auto detectar", min_area=80)

    historico = historico_contagens_estoque("Japatê")

    assert resultado["identified_item"] == "Arroz"
    assert resultado["detection"]["total_count"] == 3
    assert historico
    assert historico[0]["item"] == "Arroz"
