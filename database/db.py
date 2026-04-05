import os
import sqlite3
import tempfile
from sqlite3 import Connection
from datetime import datetime
from pathlib import Path


_RUNTIME_FALLBACK_DB_PATH = None


def _activate_runtime_fallback() -> Path:
    global _RUNTIME_FALLBACK_DB_PATH
    fallback_dir = Path(tempfile.gettempdir()) / "dojo_os_runtime"
    fallback_dir.mkdir(parents=True, exist_ok=True)
    _RUNTIME_FALLBACK_DB_PATH = fallback_dir / "dojo_os.db"
    return _RUNTIME_FALLBACK_DB_PATH


def _resolve_db_path() -> Path:
    global _RUNTIME_FALLBACK_DB_PATH
    env_path = os.environ.get("DOJO_DB_PATH")
    if env_path:
        return Path(env_path)
    if _RUNTIME_FALLBACK_DB_PATH is not None:
        return _RUNTIME_FALLBACK_DB_PATH
    # Use a temp db during pytest to avoid file locks in synced folders.
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return Path(tempfile.gettempdir()) / "dojo_os_test.db"
    return Path(__file__).resolve().parent.parent / "dojo_os.db"


def get_connection() -> Connection:
    global _RUNTIME_FALLBACK_DB_PATH
    db_path = _resolve_db_path()
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.OperationalError as exc:
        if "disk i/o error" not in str(exc).lower():
            raise
        _activate_runtime_fallback()
        conn = sqlite3.connect(_RUNTIME_FALLBACK_DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def _init_db_once():
    db_path = _resolve_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT NOT NULL,
            data TEXT NOT NULL,
            item TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            total REAL NOT NULL,
            categoria TEXT,
            hora TEXT,
            pedidos INTEGER,
            origem_upload TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS checklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT NOT NULL,
            tipo TEXT NOT NULL,
            tarefa TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('pendente','em andamento','concluido')),
            data TEXT NOT NULL,
            responsavel TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS estoque (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT NOT NULL,
            item TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            minimo INTEGER NOT NULL,
            ultimo_movimento TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT,
            nivel TEXT NOT NULL,
            mensagem TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            contexto TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS empresas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            tipo TEXT NOT NULL,
            ativa INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            cidade TEXT,
            endereco TEXT,
            contato TEXT,
            auto_send_plan INTEGER NOT NULL DEFAULT 1
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS uploads_historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT NOT NULL,
            nome_arquivo TEXT NOT NULL,
            tipo_arquivo TEXT NOT NULL,
            caminho_arquivo TEXT NOT NULL,
            linhas_importadas INTEGER NOT NULL DEFAULT 0,
            faturamento_importado REAL NOT NULL DEFAULT 0,
            pedidos_importados INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            criado_em TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS insights_ia_historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT NOT NULL,
            categoria TEXT NOT NULL,
            insight TEXT NOT NULL,
            recomendacao TEXT,
            prioridade TEXT NOT NULL DEFAULT 'media',
            criado_em TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS estoque_modelos_visuais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT NOT NULL,
            item TEXT NOT NULL,
            nome_modelo TEXT NOT NULL,
            caminho_arquivo TEXT NOT NULL,
            assinatura_json TEXT NOT NULL,
            criado_em TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contagens_estoque_ia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT NOT NULL,
            item TEXT,
            quantidade_detectada INTEGER NOT NULL,
            confianca REAL NOT NULL DEFAULT 0,
            estoque_atual INTEGER,
            diferenca INTEGER,
            caminho_arquivo TEXT NOT NULL,
            observacoes TEXT,
            criado_em TEXT NOT NULL
        )
    ''')

    conn.commit()

    # Garantir colunas de localização para versões antigas do DB
    cursor.execute("PRAGMA table_info(empresas)")
    cols = [r[1] for r in cursor.fetchall()]
    # adicionar colunas se não existirem (ALTER TABLE é seguro em SQLite)
    if 'latitude' not in cols:
        cursor.execute('ALTER TABLE empresas ADD COLUMN latitude REAL')
    if 'longitude' not in cols:
        cursor.execute('ALTER TABLE empresas ADD COLUMN longitude REAL')
    if 'cidade' not in cols:
        cursor.execute('ALTER TABLE empresas ADD COLUMN cidade TEXT')
    if 'endereco' not in cols:
        cursor.execute('ALTER TABLE empresas ADD COLUMN endereco TEXT')
    if 'contato' not in cols:
        cursor.execute('ALTER TABLE empresas ADD COLUMN contato TEXT')
    if 'auto_send_plan' not in cols:
        # adicionar coluna e ativar envio automático por padrão para empresas existentes
        cursor.execute('ALTER TABLE empresas ADD COLUMN auto_send_plan INTEGER NOT NULL DEFAULT 1')
        try:
            cursor.execute('UPDATE empresas SET auto_send_plan = 1 WHERE auto_send_plan IS NULL')
        except Exception:
            pass

    conn.commit()
    # Tabela para cache de integrações externas (clima, eventos, impactos)
    cursor.execute("PRAGMA table_info(vendas)")
    vendas_cols = [r[1] for r in cursor.fetchall()]
    if 'categoria' not in vendas_cols:
        cursor.execute('ALTER TABLE vendas ADD COLUMN categoria TEXT')
    if 'hora' not in vendas_cols:
        cursor.execute('ALTER TABLE vendas ADD COLUMN hora TEXT')
    if 'pedidos' not in vendas_cols:
        cursor.execute('ALTER TABLE vendas ADD COLUMN pedidos INTEGER')
    if 'origem_upload' not in vendas_cols:
        cursor.execute('ALTER TABLE vendas ADD COLUMN origem_upload TEXT')

    cursor.execute("UPDATE empresas SET nome = 'Japatê' WHERE nome IN ('Japão', 'Japao', 'JapatÃª')")
    cursor.execute("UPDATE vendas SET empresa = 'Japatê' WHERE empresa IN ('Japão', 'Japao', 'JapatÃª')")
    cursor.execute("UPDATE estoque SET empresa = 'Japatê' WHERE empresa IN ('Japão', 'Japao', 'JapatÃª')")
    cursor.execute("UPDATE checklist SET empresa = 'Japatê' WHERE empresa IN ('Japão', 'Japao', 'JapatÃª')")
    cursor.execute("UPDATE empresas SET nome = 'Rellicário' WHERE nome IN ('Outro', 'Rellicario')")
    cursor.execute("UPDATE vendas SET empresa = 'Rellicário' WHERE empresa IN ('Outro', 'Rellicario')")
    cursor.execute("UPDATE estoque SET empresa = 'Rellicário' WHERE empresa IN ('Outro', 'Rellicario')")
    cursor.execute("UPDATE checklist SET empresa = 'Rellicário' WHERE empresa IN ('Outro', 'Rellicario')")

    conn.commit()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS external_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa TEXT NOT NULL,
            key TEXT NOT NULL,
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(empresa, key)
        )
    ''')
    conn.commit()
    conn.close()


def init_db():
    try:
        _init_db_once()
    except sqlite3.OperationalError as exc:
        if "disk i/o error" not in str(exc).lower():
            raise
        _activate_runtime_fallback()
        _init_db_once()


def _insert_default_data_once():
    conn = get_connection()
    cursor = conn.cursor()

    # Inserir dados iniciais de exemplo, caso tabela esteja vazia
    cursor.execute('SELECT COUNT(*) FROM vendas')
    if cursor.fetchone()[0] == 0:
        sample_vendas = [
            ('Japatê', '2026-04-01', 'Rolinho', 10, 250.0),
            ('Japatê', '2026-04-02', 'Sushi', 8, 320.0),
            ('Japatê', '2026-04-03', 'Temaki', 5, 150.0),
            ('Rellicário', '2026-04-01', 'Cappuccino', 20, 900.0),
        ]
        cursor.executemany('INSERT INTO vendas (empresa,data,item,quantidade,total) VALUES (?,?,?,?,?)', sample_vendas)

    cursor.execute('SELECT COUNT(*) FROM estoque')
    if cursor.fetchone()[0] == 0:
        sample_estoque = [
            ('Japatê', 'Arroz', 50, 20, datetime.now().isoformat()),
            ('Japatê', 'Peixe', 15, 10, datetime.now().isoformat()),
            ('Rellicário', 'Café em grãos', 40, 10, datetime.now().isoformat()),
        ]
        cursor.executemany('INSERT INTO estoque (empresa,item,quantidade,minimo,ultimo_movimento) VALUES (?,?,?,?,?)', sample_estoque)

    cursor.execute('SELECT COUNT(*) FROM checklist')
    if cursor.fetchone()[0] == 0:
        sample_checklist = [
            ('Japatê', 'abertura', 'Limpar bancadas', 'pendente', '2026-04-03', 'Operador A'),
            ('Japatê', 'operacao', 'Verificar temperatures', 'em andamento', '2026-04-03', 'Operador B'),
            ('Japatê', 'fechamento', 'Fechar caixas', 'pendente', '2026-04-03', 'Operador C'),
        ]
        cursor.executemany('INSERT INTO checklist (empresa,tipo,tarefa,status,data,responsavel) VALUES (?,?,?,?,?,?)', sample_checklist)

    cursor.execute('SELECT COUNT(*) FROM empresas')
    if cursor.fetchone()[0] == 0:
        sample_empresas = [
            ('Japatê', 'restaurante', 1, datetime.now().isoformat()),
            ('Rellicário', 'cafeteria', 1, datetime.now().isoformat()),
        ]
        cursor.executemany('INSERT OR IGNORE INTO empresas (nome,tipo,ativa,criado_em) VALUES (?,?,?,?)', sample_empresas)

    conn.commit()
    conn.close()


def insert_default_data():
    try:
        _insert_default_data_once()
    except sqlite3.OperationalError as exc:
        if "disk i/o error" not in str(exc).lower():
            raise
        _activate_runtime_fallback()
        init_db()
        _insert_default_data_once()
