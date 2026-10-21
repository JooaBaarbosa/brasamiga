"""Banco de dados. SQLite hoje; Postgres (Neon) na Vercel trocando só a DATABASE_URL."""

from datetime import date
from pathlib import Path

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    delete,
    event,
    func,
    insert,
    inspect,
    not_,
    or_,
    select,
    update,
)

from app import relogio

metadata = MetaData()

eventos = Table(
    "eventos",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("titulo", String(200), nullable=False),
    Column("data", Date),
    Column("local", String(200), nullable=False, default=""),
    Column("descricao", Text, nullable=False, default=""),
    Column("tipo", String(10), nullable=False),
    Column("criado_em", DateTime, nullable=False, default=relogio.agora),
    CheckConstraint("tipo IN ('realizado', 'futuro')", name="ck_eventos_tipo"),
)

midias = Table(
    "midias",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("evento_id", Integer, ForeignKey("eventos.id", ondelete="CASCADE"), nullable=False),
    Column("chave", String(200), nullable=False),
    Column("chave_miniatura", String(200)),
    Column("tipo", String(10), nullable=False),
    Column("criado_em", DateTime, nullable=False, default=relogio.agora),
    CheckConstraint("tipo IN ('imagem', 'video')", name="ck_midias_tipo"),
)

orcamentos = Table(
    "orcamentos",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("nome", String(200), nullable=False),
    Column("telefone", String(40), nullable=False),
    Column("email", String(200), nullable=False, default=""),
    Column("data_evento", Date),
    Column("local", String(200), nullable=False, default=""),
    Column("convidados", Integer),
    Column("pacote", String(50), nullable=False, default=""),
    Column("mensagem", Text, nullable=False, default=""),
    Column("lido", Boolean, nullable=False, default=False),
    Column("criado_em", DateTime, nullable=False, default=relogio.agora),
)


class Database:
    def __init__(self, url: str) -> None:
        if url.startswith("sqlite:///"):
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(url)
        if self.engine.dialect.name == "sqlite":
            event.listen(self.engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys = ON"))
        metadata.create_all(self.engine)
        self._conferir_schema()

    def _conferir_schema(self) -> None:
        """create_all não altera tabelas existentes: um banco da v1 quebraria o site em silêncio."""
        inspetor = inspect(self.engine)
        faltando = [
            f"{tabela.name}.{coluna.name}"
            for tabela in metadata.sorted_tables
            for coluna in tabela.columns
            if coluna.name not in {c["name"] for c in inspetor.get_columns(tabela.name)}
        ]
        if faltando:
            onde = self.engine.url.render_as_string(hide_password=True)
            raise RuntimeError(
                f"O banco {onde} é de uma versão antiga do site (faltam as colunas {', '.join(faltando)}). "
                "Apague esse arquivo (ou a pasta data/) para o site criar um banco novo, "
                "ou aponte DATABASE_URL para outro banco."
            )

    def _linhas(self, stmt) -> list[dict]:
        with self.engine.connect() as conn:
            return [dict(linha._mapping) for linha in conn.execute(stmt)]

    def _executar(self, stmt):
        with self.engine.begin() as conn:
            return conn.execute(stmt)

    # Eventos

    def listar_eventos(self, tipo: str, a_partir_de: date | None = None) -> list[dict]:
        total = (
            select(func.count(midias.c.id)).where(midias.c.evento_id == eventos.c.id).scalar_subquery()
        )
        stmt = select(eventos, total.label("total_midias")).where(eventos.c.tipo == tipo)
        if a_partir_de:
            stmt = stmt.where(or_(eventos.c.data.is_(None), eventos.c.data >= a_partir_de))
        ordem = eventos.c.data.asc() if tipo == "futuro" else eventos.c.data.desc()
        return self._linhas(stmt.order_by(ordem.nulls_last(), eventos.c.id.desc()))

    def obter_evento(self, evento_id: int) -> dict | None:
        linhas = self._linhas(select(eventos).where(eventos.c.id == evento_id))
        return linhas[0] if linhas else None

    def criar_evento(self, titulo: str, data: date | None, local: str, descricao: str, tipo: str) -> int:
        valores = dict(titulo=titulo, data=data, local=local, descricao=descricao, tipo=tipo)
        return self._executar(insert(eventos).values(**valores)).inserted_primary_key[0]

    def atualizar_evento(
        self, evento_id: int, titulo: str, data: date | None, local: str, descricao: str, tipo: str
    ) -> None:
        valores = dict(titulo=titulo, data=data, local=local, descricao=descricao, tipo=tipo)
        self._executar(update(eventos).where(eventos.c.id == evento_id).values(**valores))

    def excluir_evento(self, evento_id: int) -> list[dict]:
        apagadas = self.listar_midias(evento_id)
        with self.engine.begin() as conn:
            conn.execute(delete(midias).where(midias.c.evento_id == evento_id))
            conn.execute(delete(eventos).where(eventos.c.id == evento_id))
        return apagadas

    # Mídias

    def adicionar_midia(self, evento_id: int, chave: str, tipo: str, chave_miniatura: str | None = None) -> int:
        valores = dict(evento_id=evento_id, chave=chave, tipo=tipo, chave_miniatura=chave_miniatura)
        return self._executar(insert(midias).values(**valores)).inserted_primary_key[0]

    def listar_midias(self, evento_id: int) -> list[dict]:
        return self._linhas(select(midias).where(midias.c.evento_id == evento_id).order_by(midias.c.id))

    def midias_por_evento(self, ids: list[int]) -> dict[int, list[dict]]:
        if not ids:
            return {}
        agrupado: dict[int, list[dict]] = {}
        for m in self._linhas(select(midias).where(midias.c.evento_id.in_(ids)).order_by(midias.c.id)):
            agrupado.setdefault(m["evento_id"], []).append(m)
        return agrupado

    def excluir_midia(self, midia_id: int) -> dict | None:
        linhas = self._linhas(select(midias).where(midias.c.id == midia_id))
        if not linhas:
            return None
        self._executar(delete(midias).where(midias.c.id == midia_id))
        return linhas[0]

    # Orçamentos

    def criar_orcamento(
        self,
        nome: str,
        telefone: str,
        email: str = "",
        data_evento: date | None = None,
        local: str = "",
        convidados: int | None = None,
        pacote: str = "",
        mensagem: str = "",
    ) -> int:
        valores = dict(
            nome=nome,
            telefone=telefone,
            email=email,
            data_evento=data_evento,
            local=local,
            convidados=convidados,
            pacote=pacote,
            mensagem=mensagem,
        )
        return self._executar(insert(orcamentos).values(**valores)).inserted_primary_key[0]

    def listar_orcamentos(self) -> list[dict]:
        return self._linhas(select(orcamentos).order_by(orcamentos.c.lido, orcamentos.c.id.desc()))

    def alternar_lido(self, orcamento_id: int) -> None:
        self._executar(
            update(orcamentos).where(orcamentos.c.id == orcamento_id).values(lido=not_(orcamentos.c.lido))
        )
