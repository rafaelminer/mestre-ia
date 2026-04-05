from datetime import datetime
from typing import List, Optional
import sqlite3
from .db import get_connection


def listar_empresas() -> List[str]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT nome FROM empresas WHERE ativa = 1 ORDER BY nome')
        empresas = [row[0] for row in cursor.fetchall()]
        if empresas:
            return empresas
        cursor.execute("SELECT DISTINCT empresa FROM vendas UNION SELECT DISTINCT empresa FROM estoque UNION SELECT DISTINCT empresa FROM checklist")
        return [row[0] for row in cursor.fetchall()]


def adicionar_empresa(nome: str, tipo: str = 'restaurante', ativa: bool = True):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO empresas (nome, tipo, ativa, criado_em) VALUES (?, ?, ?, ?)',
                       (nome, tipo, int(ativa), datetime.now().isoformat()))
        conn.commit()


def listar_empresas_completas() -> List[dict]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM empresas ORDER BY nome')
        return [dict(row) for row in cursor.fetchall()]


def obter_empresa_por_nome(nome: str) -> Optional[dict]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM empresas WHERE nome = ? LIMIT 1', (nome,))
        row = cursor.fetchone()
        return dict(row) if row else None


def atualizar_local_empresa_por_id(empresa_id: int, latitude: Optional[float], longitude: Optional[float], cidade: Optional[str], endereco: Optional[str]):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE empresas SET latitude = ?, longitude = ?, cidade = ?, endereco = ? WHERE id = ?', (latitude, longitude, cidade, endereco, empresa_id))
        conn.commit()


def atualizar_local_empresa_por_nome(nome: str, latitude: Optional[float], longitude: Optional[float], cidade: Optional[str], endereco: Optional[str]):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE empresas SET latitude = ?, longitude = ?, cidade = ?, endereco = ? WHERE nome = ?', (latitude, longitude, cidade, endereco, nome))
        conn.commit()


def atualizar_contato_empresa_por_nome(nome: str, contato: Optional[str]):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE empresas SET contato = ? WHERE nome = ?', (contato, nome))
        conn.commit()


def atualizar_auto_send_empresa_por_nome(nome: str, enabled: bool):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE empresas SET auto_send_plan = ? WHERE nome = ?', (1 if enabled else 0, nome))
        conn.commit()


def obter_vendas(empresa: Optional[str] = None):
    with get_connection() as conn:
        cursor = conn.cursor()
        if empresa:
            cursor.execute("SELECT * FROM vendas WHERE empresa = ? ORDER BY data DESC", (empresa,))
        else:
            cursor.execute("SELECT * FROM vendas ORDER BY data DESC")
        return cursor.fetchall()


def adicionar_venda(empresa: str, data: str, item: str, quantidade: int, total: float):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO vendas (empresa, data, item, quantidade, total) VALUES (?,?,?,?,?)",
                       (empresa, data, item, quantidade, total))
        conn.commit()


def adicionar_vendas_em_lote(vendas: List[tuple]):
    if not vendas:
        return 0
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(
            "INSERT INTO vendas (empresa, data, item, quantidade, total) VALUES (?,?,?,?,?)",
            vendas
        )
        conn.commit()
        return cursor.rowcount


def adicionar_vendas_detalhadas_em_lote(vendas: List[tuple]):
    if not vendas:
        return 0
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(
            "INSERT INTO vendas (empresa, data, item, quantidade, total, categoria, hora, pedidos, origem_upload) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            vendas
        )
        conn.commit()
        return cursor.rowcount


def obter_checklist(empresa: Optional[str] = None, tipo: Optional[str] = None):
    with get_connection() as conn:
        cursor = conn.cursor()
        sql = "SELECT * FROM checklist"
        filtros = []
        params = []
        if empresa:
            filtros.append("empresa = ?")
            params.append(empresa)
        if tipo:
            filtros.append("tipo = ?")
            params.append(tipo)
        if filtros:
            sql += " WHERE " + " AND ".join(filtros)
        sql += " ORDER BY data DESC"
        cursor.execute(sql, tuple(params))
        return cursor.fetchall()


def atualizar_status_checklist(checklist_id: int, status: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE checklist SET status = ? WHERE id = ?", (status, checklist_id))
        conn.commit()


def adicionar_item_checklist(empresa: str, tipo: str, tarefa: str, status: str, data: str, responsavel: Optional[str] = None):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO checklist (empresa, tipo, tarefa, status, data, responsavel) VALUES (?,?,?,?,?,?)",
            (empresa, tipo, tarefa, status, data, responsavel)
        )
        conn.commit()


def obter_estoque(empresa: Optional[str] = None):
    with get_connection() as conn:
        cursor = conn.cursor()
        if empresa:
            cursor.execute("SELECT * FROM estoque WHERE empresa = ? ORDER BY item", (empresa,))
        else:
            cursor.execute("SELECT * FROM estoque ORDER BY item")
        return cursor.fetchall()


def atualizar_estoque_item(item_id: int, quantidade: int, minimo: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE estoque SET quantidade = ?, minimo = ?, ultimo_movimento = datetime('now') WHERE id = ?", (quantidade, minimo, item_id))
        conn.commit()


def verificar_estoque_baixo(empresa: Optional[str] = None):
    with get_connection() as conn:
        cursor = conn.cursor()
        if empresa:
            cursor.execute("SELECT * FROM estoque WHERE empresa = ? AND quantidade <= minimo", (empresa,))
        else:
            cursor.execute("SELECT * FROM estoque WHERE quantidade <= minimo")
        return cursor.fetchall()


def obter_total_vendas(empresa: Optional[str] = None):
    with get_connection() as conn:
        cursor = conn.cursor()
        if empresa:
            cursor.execute("SELECT SUM(total) as total FROM vendas WHERE empresa = ?", (empresa,))
        else:
            cursor.execute("SELECT SUM(total) as total FROM vendas")
        row = cursor.fetchone()
        return row[0] if row and row[0] is not None else 0.0


def obter_vendas_por_item(empresa: Optional[str] = None):
    with get_connection() as conn:
        cursor = conn.cursor()
        if empresa:
            cursor.execute("SELECT item, SUM(quantidade) as qtd, SUM(total) as total FROM vendas WHERE empresa = ? GROUP BY item ORDER BY total DESC", (empresa,))
        else:
            cursor.execute("SELECT item, SUM(quantidade) as qtd, SUM(total) as total FROM vendas GROUP BY item ORDER BY total DESC")
        return cursor.fetchall()


def obter_vendas_recentes(empresa: Optional[str] = None, limite: int = 20):
    with get_connection() as conn:
        cursor = conn.cursor()
        if empresa:
            cursor.execute(
                "SELECT * FROM vendas WHERE empresa = ? ORDER BY data DESC, id DESC LIMIT ?",
                (empresa, limite)
            )
        else:
            cursor.execute(
                "SELECT * FROM vendas ORDER BY data DESC, id DESC LIMIT ?",
                (limite,)
            )
        return cursor.fetchall()


def obter_resumo_vendas_periodo(empresa: Optional[str] = None, data_inicio: Optional[str] = None, data_fim: Optional[str] = None):
    with get_connection() as conn:
        cursor = conn.cursor()
        sql = "SELECT COUNT(*) as registros, SUM(total) as faturamento, SUM(COALESCE(pedidos, quantidade, 0)) as pedidos FROM vendas WHERE 1=1"
        params = []
        if empresa:
            sql += " AND empresa = ?"
            params.append(empresa)
        if data_inicio:
            sql += " AND data >= ?"
            params.append(data_inicio)
        if data_fim:
            sql += " AND data <= ?"
            params.append(data_fim)
        cursor.execute(sql, tuple(params))
        row = cursor.fetchone()
        return dict(row) if row else {"registros": 0, "faturamento": 0.0, "pedidos": 0}


def obter_vendas_por_hora(empresa: Optional[str] = None):
    with get_connection() as conn:
        cursor = conn.cursor()
        sql = (
            "SELECT COALESCE(hora, substr(data, 12, 5)) as hora_referencia, "
            "SUM(total) as total, SUM(COALESCE(pedidos, quantidade, 0)) as pedidos "
            "FROM vendas WHERE 1=1"
        )
        params = []
        if empresa:
            sql += " AND empresa = ?"
            params.append(empresa)
        sql += " GROUP BY hora_referencia ORDER BY total DESC"
        cursor.execute(sql, tuple(params))
        return cursor.fetchall()


def adicionar_upload_historico(
    empresa: str,
    nome_arquivo: str,
    tipo_arquivo: str,
    caminho_arquivo: str,
    linhas_importadas: int,
    faturamento_importado: float,
    pedidos_importados: int,
    status: str,
):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO uploads_historico (empresa, nome_arquivo, tipo_arquivo, caminho_arquivo, linhas_importadas, faturamento_importado, pedidos_importados, status, criado_em) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                empresa,
                nome_arquivo,
                tipo_arquivo,
                caminho_arquivo,
                linhas_importadas,
                faturamento_importado,
                pedidos_importados,
                status,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()


def listar_uploads_historico(empresa: Optional[str] = None, limite: int = 20):
    with get_connection() as conn:
        cursor = conn.cursor()
        if empresa:
            cursor.execute(
                "SELECT * FROM uploads_historico WHERE empresa = ? ORDER BY criado_em DESC LIMIT ?",
                (empresa, limite),
            )
        else:
            cursor.execute("SELECT * FROM uploads_historico ORDER BY criado_em DESC LIMIT ?", (limite,))
        return cursor.fetchall()


def adicionar_insight_ia_historico(
    empresa: str,
    categoria: str,
    insight: str,
    recomendacao: Optional[str] = None,
    prioridade: str = "media",
):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO insights_ia_historico (empresa, categoria, insight, recomendacao, prioridade, criado_em) VALUES (?,?,?,?,?,?)",
            (empresa, categoria, insight, recomendacao, prioridade, datetime.now().isoformat()),
        )
        conn.commit()


def listar_insights_ia_historico(empresa: Optional[str] = None, limite: int = 20):
    with get_connection() as conn:
        cursor = conn.cursor()
        if empresa:
            cursor.execute(
                "SELECT * FROM insights_ia_historico WHERE empresa = ? ORDER BY criado_em DESC LIMIT ?",
                (empresa, limite),
            )
        else:
            cursor.execute("SELECT * FROM insights_ia_historico ORDER BY criado_em DESC LIMIT ?", (limite,))
        return cursor.fetchall()


def adicionar_modelo_visual_estoque(
    empresa: str,
    item: str,
    nome_modelo: str,
    caminho_arquivo: str,
    assinatura_json: str,
):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO estoque_modelos_visuais (empresa, item, nome_modelo, caminho_arquivo, assinatura_json, criado_em) "
            "VALUES (?,?,?,?,?,?)",
            (empresa, item, nome_modelo, caminho_arquivo, assinatura_json, datetime.now().isoformat()),
        )
        conn.commit()
        return cursor.lastrowid


def listar_modelos_visuais_estoque(empresa: str, item: Optional[str] = None, limite: int = 50):
    with get_connection() as conn:
        cursor = conn.cursor()
        if item:
            cursor.execute(
                "SELECT * FROM estoque_modelos_visuais WHERE empresa = ? AND item = ? ORDER BY criado_em DESC LIMIT ?",
                (empresa, item, limite),
            )
        else:
            cursor.execute(
                "SELECT * FROM estoque_modelos_visuais WHERE empresa = ? ORDER BY criado_em DESC LIMIT ?",
                (empresa, limite),
            )
        return cursor.fetchall()


def adicionar_contagem_estoque_ia(
    empresa: str,
    item: Optional[str],
    quantidade_detectada: int,
    confianca: float,
    estoque_atual: Optional[int],
    diferenca: Optional[int],
    caminho_arquivo: str,
    observacoes: Optional[str] = None,
):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO contagens_estoque_ia (empresa, item, quantidade_detectada, confianca, estoque_atual, diferenca, caminho_arquivo, observacoes, criado_em) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                empresa,
                item,
                quantidade_detectada,
                confianca,
                estoque_atual,
                diferenca,
                caminho_arquivo,
                observacoes,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        return cursor.lastrowid


def listar_contagens_estoque_ia(empresa: str, limite: int = 20):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM contagens_estoque_ia WHERE empresa = ? ORDER BY criado_em DESC LIMIT ?",
            (empresa, limite),
        )
        return cursor.fetchall()


def inserir_log(empresa: Optional[str], nivel: str, mensagem: str, contexto: Optional[str] = None):
    from datetime import datetime
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO logs (empresa, nivel, mensagem, timestamp, contexto) VALUES (?,?,?,?,?)",
                (empresa, nivel, mensagem, datetime.now().isoformat(), contexto)
            )
            conn.commit()
    except sqlite3.OperationalError as exc:
        if "no such table: logs" in str(exc).lower():
            try:
                from .db import init_db
                init_db()
            except Exception:
                pass
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO logs (empresa, nivel, mensagem, timestamp, contexto) VALUES (?,?,?,?,?)",
                    (empresa, nivel, mensagem, datetime.now().isoformat(), contexto)
                )
                conn.commit()
        else:
            raise


def obter_logs(limit: int = 100):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM logs ORDER BY timestamp DESC LIMIT ?", (limit,))
        return cursor.fetchall()


def set_external_cache(empresa: str, key: str, payload: str):
    from datetime import datetime
    with get_connection() as conn:
        cursor = conn.cursor()
        updated_at = datetime.now().isoformat()
        # inserir ou atualizar com UPSERT
        cursor.execute(
            "INSERT INTO external_cache (empresa, key, payload, updated_at) VALUES (?,?,?,?) "
            "ON CONFLICT(empresa, key) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
            (empresa, key, payload, updated_at)
        )
        conn.commit()


def get_external_cache(empresa: str, key: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT empresa, key, payload, updated_at FROM external_cache WHERE empresa = ? AND key = ? LIMIT 1', (empresa, key))
        row = cursor.fetchone()
        return dict(row) if row else None
