from io import BytesIO
from typing import List, Dict, Tuple, Optional
import base64
import math

from PIL import Image, ImageDraw, ImageFont
import numpy as np


def _count_blobs_pil(img: Image.Image, threshold: int = 200, min_size: int = 50) -> Tuple[int, List[dict]]:
    """Conta blobs (componentes conectados) em imagem em escala de cinza usando NumPy.
    Retorna total e lista de bounding boxes.
    Método puro-Python/Pillow — funciona sem OpenCV/YOLO (fallback)."""
    gray = img.convert('L')
    arr = np.array(gray)
    mask = arr > threshold
    h, w = mask.shape
    visited = np.zeros_like(mask, dtype=bool)

    bboxes = []
    total = 0

    for y in range(h):
        for x in range(w):
            if mask[y, x] and not visited[y, x]:
                # flood fill
                stack = [(x, y)]
                visited[y, x] = True
                min_x, min_y, max_x, max_y = x, y, x, y
                area = 0
                while stack:
                    cx, cy = stack.pop()
                    area += 1
                    if cx < min_x:
                        min_x = cx
                    if cy < min_y:
                        min_y = cy
                    if cx > max_x:
                        max_x = cx
                    if cy > max_y:
                        max_y = cy
                    # neighbors 4-connectivity
                    if cx + 1 < w and mask[cy, cx + 1] and not visited[cy, cx + 1]:
                        visited[cy, cx + 1] = True
                        stack.append((cx + 1, cy))
                    if cx - 1 >= 0 and mask[cy, cx - 1] and not visited[cy, cx - 1]:
                        visited[cy, cx - 1] = True
                        stack.append((cx - 1, cy))
                    if cy + 1 < h and mask[cy + 1, cx] and not visited[cy + 1, cx]:
                        visited[cy + 1, cx] = True
                        stack.append((cx, cy + 1))
                    if cy - 1 >= 0 and mask[cy - 1, cx] and not visited[cy - 1, cx]:
                        visited[cy - 1, cx] = True
                        stack.append((cx, cy - 1))

                if area >= min_size:
                    total += 1
                    bboxes.append({
                        'x1': int(min_x), 'y1': int(min_y), 'x2': int(max_x), 'y2': int(max_y), 'area': int(area)
                    })
    return total, bboxes


def _annotate_image(img: Image.Image, bboxes: List[dict]) -> bytes:
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    for i, b in enumerate(bboxes, start=1):
        draw.rectangle([b['x1'], b['y1'], b['x2'], b['y2']], outline='red', width=2)
        text = f"#{i}"
        draw.text((b['x1'] + 3, b['y1'] + 3), text, fill='red', font=font)
    out = BytesIO()
    img.save(out, format='PNG')
    return out.getvalue()


def detect_and_count(image_bytes: bytes, use_yolo: bool = False, min_area: int = 50) -> Dict:
    """Detecta e conta objetos em uma imagem.

    Estratégia:
    - se `use_yolo=True` e `ultralytics` estiver instalado, tenta usar YOLO para detectar classes.
    - caso contrário, usa um fallback baseado em Pillow+NumPy para contar blobs.

    Retorna um dicionário com 'method', 'total_count', 'bboxes' e 'annotated_image' (base64 PNG).
    """
    img = Image.open(BytesIO(image_bytes)).convert('RGB')

    # tentar YOLO/ultralytics (opcional)
    if use_yolo:
        try:
            from ultralytics import YOLO
            model = YOLO('yolov8n.pt')  # peso genérico; recomenda-se treinar um modelo específico
            results = model.predict(source=BytesIO(image_bytes), imgsz=640, conf=0.3)
            # a API do ultralytics retorna objetos complexos; simplificamos
            bboxes = []
            total = 0
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    xyxy = box.xyxy[0].tolist()
                    area = (xyxy[2] - xyxy[0]) * (xyxy[3] - xyxy[1])
                    bboxes.append({'x1': int(xyxy[0]), 'y1': int(xyxy[1]), 'x2': int(xyxy[2]), 'y2': int(xyxy[3]), 'area': int(area)})
                    total += 1
            annotated = _annotate_image(img.copy(), bboxes)
            return {
                'method': 'yolo',
                'total_count': total,
                'bboxes': bboxes,
                'annotated_image': base64.b64encode(annotated).decode('utf-8')
            }
        except Exception:
            # falhar silenciosamente para usar fallback
            pass

    # Fallback PIL/NumPy blob counting
    total, bboxes = _count_blobs_pil(img, threshold=200, min_size=min_area)
    annotated = _annotate_image(img.copy(), bboxes)
    return {
        'method': 'pillow_fallback',
        'total_count': total,
        'bboxes': bboxes,
        'annotated_image': base64.b64encode(annotated).decode('utf-8')
    }


def build_image_signature(image_bytes: bytes) -> Dict:
    """Gera uma assinatura visual leve para comparação por similaridade."""
    img = Image.open(BytesIO(image_bytes)).convert('RGB').resize((64, 64))
    arr = np.array(img, dtype=np.float32)
    channel_means = arr.mean(axis=(0, 1)) / 255.0
    channel_std = arr.std(axis=(0, 1)) / 255.0
    gray = np.array(img.convert('L'))
    hist, _ = np.histogram(gray, bins=16, range=(0, 255), density=True)
    return {
        'channel_means': [round(float(x), 6) for x in channel_means],
        'channel_std': [round(float(x), 6) for x in channel_std],
        'gray_histogram': [round(float(x), 6) for x in hist],
    }


def compare_image_signatures(signature_a: Dict, signature_b: Dict) -> float:
    """Retorna score de similaridade entre 0 e 1."""
    if not signature_a or not signature_b:
        return 0.0

    def _distance(key: str, weight: float) -> float:
        vec_a = signature_a.get(key) or []
        vec_b = signature_b.get(key) or []
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return weight
        return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(vec_a, vec_b))) * weight

    distance = (
        _distance('channel_means', 1.8)
        + _distance('channel_std', 1.0)
        + _distance('gray_histogram', 1.4)
    )
    similarity = max(0.0, 1.0 - min(distance, 1.0))
    return round(similarity, 4)


def identify_item_by_reference(image_bytes: bytes, references: List[Dict]) -> Dict:
    """Compara a imagem atual com referências visuais e devolve o melhor match."""
    if not references:
        return {
            'matched': False,
            'item': None,
            'model_name': None,
            'confidence': 0.0,
            'ranking': [],
        }

    current_signature = build_image_signature(image_bytes)
    ranking = []
    for ref in references:
        ref_signature = ref.get('signature') or {}
        score = compare_image_signatures(current_signature, ref_signature)
        ranking.append({
            'item': ref.get('item'),
            'model_name': ref.get('model_name'),
            'confidence': score,
            'reference_path': ref.get('reference_path'),
        })

    ranking.sort(key=lambda item: item['confidence'], reverse=True)
    best = ranking[0]
    return {
        'matched': best['confidence'] >= 0.45,
        'item': best.get('item'),
        'model_name': best.get('model_name'),
        'confidence': best.get('confidence', 0.0),
        'ranking': ranking[:5],
        'signature': current_signature,
    }


def analyze_checklist_from_image(image_bytes: bytes) -> Dict:
    """Stub para extrair informações de checklist a partir da imagem.

    Observação: identificar itens de checklist por imagem requer modelos treinados por tarefa.
    Aqui deixamos um stub que retorna estrutura esperada; treinar modelos e mapeamentos é próximo passo.
    """
    # Implementação real: treinar classificadores/segmentadores por tarefa
    return {'recognized_items': [], 'recommendations': [], 'confidence': 0.0}
