import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    data TEXT,
    local TEXT NOT NULL DEFAULT '',
    descricao TEXT NOT NULL DEFAULT '',
    tipo TEXT NOT NULL CHECK (tipo IN ('realizado', 'futuro')),
    criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS midias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evento_id INTEGER NOT NULL REFERENCES eventos(id) ON DELETE CASCADE,
    arquivo TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('imagem', 'video')),
    criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS orcamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    telefone TEXT NOT NULL,
    email TEXT NOT NULL DEFAULT '',
    data_evento TEXT NOT NULL DEFAULT '',
    convidados INTEGER,
    tipo_evento TEXT NOT NULL DEFAULT '',
    mensagem TEXT NOT NULL DEFAULT '',
    lido INTEGER NOT NULL DEFAULT 0,
    criado_em TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def conectar(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def iniciar(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.conectar() as conn:
            conn.executescript(SCHEMA)

    # Eventos

    def listar_eventos(self, tipo: str) -> list[dict]:
        ordem = "ASC" if tipo == "futuro" else "DESC"
        with self.conectar() as conn:
            linhas = conn.execute(
                f"""SELECT e.*, COUNT(m.id) AS total_midias
                    FROM eventos e LEFT JOIN midias m ON m.evento_id = e.id
                    WHERE e.tipo = ? GROUP BY e.id
                    ORDER BY e.data IS NULL, e.data {ordem}, e.id DESC""",
                (tipo,),
            ).fetchall()
        return [dict(l) for l in linhas]

    def obter_evento(self, evento_id: int) -> dict | None:
        with self.conectar() as conn:
            linha = conn.execute("SELECT * FROM eventos WHERE id = ?", (evento_id,)).fetchone()
        return dict(linha) if linha else None

    def criar_evento(self, titulo: str, data: str | None, local: str, descricao: str, tipo: str) -> int:
        with self.conectar() as conn:
            cur = conn.execute(
                "INSERT INTO eventos (titulo, data, local, descricao, tipo) VALUES (?, ?, ?, ?, ?)",
                (titulo, data, local, descricao, tipo),
            )
        return cur.lastrowid

    def atualizar_evento(
        self, evento_id: int, titulo: str, data: str | None, local: str, descricao: str, tipo: str
    ) -> None:
        with self.conectar() as conn:
            conn.execute(
                "UPDATE eventos SET titulo = ?, data = ?, local = ?, descricao = ?, tipo = ? WHERE id = ?",
                (titulo, data, local, descricao, tipo, evento_id),
            )

    def excluir_evento(self, evento_id: int) -> list[str]:
        """Exclui o evento e devolve os arquivos das mídias para apagar do disco."""
        with self.conectar() as conn:
            arquivos = [
                l["arquivo"]
                for l in conn.execute("SELECT arquivo FROM midias WHERE evento_id = ?", (evento_id,))
            ]
            conn.execute("DELETE FROM eventos WHERE id = ?", (evento_id,))
        return arquivos

    # Mídias

    def adicionar_midia(self, evento_id: int, arquivo: str, tipo: str) -> int:
        with self.conectar() as conn:
            cur = conn.execute(
                "INSERT INTO midias (evento_id, arquivo, tipo) VALUES (?, ?, ?)",
                (evento_id, arquivo, tipo),
            )
        return cur.lastrowid

    def listar_midias(self, evento_id: int) -> list[dict]:
        with self.conectar() as conn:
            linhas = conn.execute(
                "SELECT * FROM midias WHERE evento_id = ? ORDER BY id", (evento_id,)
            ).fetchall()
        return [dict(l) for l in linhas]

    def excluir_midia(self, midia_id: int) -> dict | None:
        with self.conectar() as conn:
            linha = conn.execute("SELECT * FROM midias WHERE id = ?", (midia_id,)).fetchone()
            if linha:
                conn.execute("DELETE FROM midias WHERE id = ?", (midia_id,))
        return dict(linha) if linha else None

    # Orçamentos

    def criar_orcamento(
        self,
        nome: str,
        telefone: str,
        email: str,
        data_evento: str,
        convidados: int | None,
        tipo_evento: str,
        mensagem: str,
    ) -> int:
        with self.conectar() as conn:
            cur = conn.execute(
                """INSERT INTO orcamentos
                   (nome, telefone, email, data_evento, convidados, tipo_evento, mensagem)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (nome, telefone, email, data_evento, convidados, tipo_evento, mensagem),
            )
        return cur.lastrowid

    def listar_orcamentos(self) -> list[dict]:
        with self.conectar() as conn:
            linhas = conn.execute("SELECT * FROM orcamentos ORDER BY lido, id DESC").fetchall()
        return [dict(l) for l in linhas]

    def alternar_lido(self, orcamento_id: int) -> None:
        with self.conectar() as conn:
            conn.execute("UPDATE orcamentos SET lido = 1 - lido WHERE id = ?", (orcamento_id,))
