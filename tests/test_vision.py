import io
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient
from interface.api import app

client = TestClient(app)


def test_vision_detect():
    # Cria uma imagem de teste com 3 blobs brancos sobre fundo preto
    img = Image.new('RGB', (200, 200), 'black')
    draw = ImageDraw.Draw(img)
    draw.ellipse((20, 20, 60, 60), fill='white')
    draw.ellipse((80, 80, 120, 120), fill='white')
    draw.ellipse((140, 30, 180, 70), fill='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    files = {'file': ('test.png', buf, 'image/png')}
    response = client.post('/vision/detect', files=files)
    assert response.status_code == 200
    data = response.json()
    assert 'total_count' in data
    assert data['total_count'] >= 3
