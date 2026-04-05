# DOJO OS - Gestão Operacional para Restaurantes

Sistema completo SaaS de gestão operacional para restaurantes (Japatê + multiempresa) com insights de IA.

## Estrutura

- `app.py`: ponto de entrada Streamlit.
- `interface/main.py`: UI Streamlit com Dashboard, Checklist, IA, Estoque, Logs.
- `interface/api.py`: FastAPI endpoints para operações.
- `database/db.py`: inicialização SQLite (`dojo_os.db`).
- `database/queries.py`: CRUD para vendas, checklist, estoque, logs.

## Publicação online

O projeto já está preparado para publicação com Docker e também com blueprint do Render.

### Render

Arquivos usados:

- `render.yaml`
- `Dockerfile`
- `.streamlit/config.toml`

Configuração importante:

- banco persistente em disco com `DOJO_DB_PATH=/data/dojo_os.db`

Fluxo:

1. Suba o projeto para um repositório Git.
2. No Render, escolha a opção de criar serviço a partir do `render.yaml`.
3. Aguarde o build do container.
4. A aplicação ficará disponível em uma URL pública HTTPS.

### Docker local

Também é possível publicar em um servidor próprio com Docker:

```bash
docker compose up --build -d
```
- `services/`: serviços para acesso e regras.
- `ai/analise.py`: IA operacional (analisar_dados, detectar_queda_vendas).
- `modules/dashboard.py`: indicadores e alertas.
- `logs/logger.py`: log local + persistência em DB.

## Requisitos

- Python 3.10+ (melhor) ou 3.11/3.12.
- Instalar dependências:
  ```bash
  pip install -r requirements.txt
  ```

## Executando

### Streamlit

```bash
streamlit run app.py
```

### FastAPI

```bash
uvicorn interface.api:app --reload --host 0.0.0.0 --port 8000
```

Acesse `http://localhost:8000/docs` para documentação interativa.

### Endpoints de empresas

- `GET /empresas` retorna lista de nomes de empresas ativas
- `GET /empresas/detalhes` retorna lista de empresas com metadados
- `POST /empresas` cria nova empresa

### Endpoint de WhatsApp Simulado

- `POST /whatsapp/send`
- payload: `numero`, `mensagem`, `empresa`

A API retorna um ack de envio simulado e escreve um log interno.

### Docker

```bash
docker build -t dojo-os .
docker run -p 8501:8501 -p 8000:8000 --rm dojo-os
```

ou com Docker Compose:

```bash
docker compose up --build
```

Em seguida, acesse `http://localhost:8501` para a interface Streamlit.

## Testes

Utilize pytest:

```bash
pip install pytest
pytest -q
```

## Integração WhatsApp (stub)

`services/whatsapp_service.py` está preparado para implementação Twilio.

## Observações

- Banco de dados SQLite: `dojo_os.db` gerado automaticamente.
- Multiempresa ativado: seleção por sidebar (cada endpoint recebe `empresa` param).
- IA operacional analisa vendas, estoque baixo, checklist, e queda de faturamento.
