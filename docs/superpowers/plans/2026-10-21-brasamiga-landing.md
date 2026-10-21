# Brasamiga Landing + Admin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Brasamiga landing page with the visual identity and content of the commercial proposal PDF, keep an `/admin` panel for events with photos/videos and quote requests, and package it with Docker while keeping storage and database swappable for a future Vercel deploy.

**Architecture:** FastAPI app rendered server-side with Jinja2. Small single-purpose modules: `config` (env), `db` (SQLAlchemy Core, SQLite now / Postgres later via `DATABASE_URL`), `storage` (`LocalStorage` now, `BlobStorage` stub for Vercel), `midia` (Pillow image optimisation + ffmpeg video conversion), `conteudo` (reads `conteudo/site.toml` and folders, caches web versions of photos), `whatsapp` (wa.me links), and two routers (site, admin).

**Tech Stack:** Python 3.14, FastAPI, Jinja2, SQLAlchemy 2 (Core), Pillow + pillow-heif, ffmpeg (in Docker), uvicorn, pytest + httpx, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-10-21-brasamiga-landing-design.md`

## Global Constraints

- `pyproject.toml`: `requires-python = ">=3.14,<3.15"`; `.python-version`: `3.14.8` (project rule from `claude-projetos/CLAUDE.md`).
- All user-facing copy in pt-BR; content comes from the PDF, no invented numbers, testimonials or promises.
- WhatsApp: `5511993433998`, shown as `(11) 99343-3998`; Instagram `@brasamiga`.
- Colours: `--madeira #1C1512`, `--papel #F3EBDF`, `--papel-escuro #EADFCE`, `--brasa #A93226`, `--cobre #B8966A`, `--tinta #1E1A17`.
- Fonts (Google Fonts): Anton (titles), Oswald (labels), Lato (body).
- Env vars: `ADMIN_USER`, `ADMIN_PASSWORD`, `DATABASE_URL`, `STORAGE_BACKEND` (`local`|`blob`), `BLOB_READ_WRITE_TOKEN`, `DATA_DIR`, `CONTENT_DIR`, `MAX_UPLOAD_MB` (default 300).
- No `ADMIN_PASSWORD` → `/admin` answers 503. Admin POSTs with a foreign `Origin` → 403.
- Images are stored/served as WEBP 1600 px (q≈80) + 600 px thumbnail, EXIF rotation applied, all metadata (incl. GPS) stripped.
- Videos converted with `ffmpeg -c:v libx264 -crf 26 -preset veryfast -c:a aac -movflags +faststart`, max 1080p, metadata stripped; on failure keep original + admin warning.
- Original files in `conteudo/eventos-realizados/` are never served directly (they carry GPS metadata).
- Run all commands from the repository root (the worktree). Tests: `uv run pytest -q`.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. `site.toml` saved by Windows Notepad with a UTF-8 BOM and accents → site still loads (no 500).
2. Someone guesses `/conteudo/eventos-realizados/IMG_0385.JPEG` → 404; only stripped WEBP copies under `/cache/` are public.
3. Quote form with odd input (`convidados="80 pessoas"`, `data_evento="31/02"`, unknown pacote) → request accepted, bad optional fields dropped, never a 422 JSON page.
4. Upload named `Festa Junina 2025.JPG` (spaces, accents, upper-case extension) → accepted and processed.
5. Mixed upload (one valid photo + one `.exe`) → valid photo saved, error lists only the `.exe`.

Each line above has a pinned test in the owning task (Tasks 3, 5, 6, 8).

## File Structure

```
app/
  __init__.py
  config.py        Settings from env                                  (Task 1)
  storage.py       Armazenamento protocol, LocalStorage, BlobStorage  (Task 1)
  db.py            SQLAlchemy Core tables + Database                  (Task 2)
  midia.py         validation, images, logo, video                    (Task 3)
  whatsapp.py      wa.me link + quote message                         (Task 4)
  conteudo.py      site.toml, folders, gallery cache                  (Task 5)
  web.py           Jinja2 templates + date filters                    (Task 6)
  rotas_site.py    GET /, GET /healthz, POST /orcamento               (Task 6)
  main.py          create_app()                                       (Task 6)
  rotas_admin.py   /admin/*                                           (Task 8)
  preparar.py      CLI: pre-build gallery cache                       (Task 9)
  templates/base.html, index.html, erro_conteudo.html                 (Task 6)
  templates/admin/base.html, index.html, evento.html, _campos_evento.html (Task 8)
  static/css/site.css, static/js/site.js                              (Task 7)
  static/css/admin.css                                                (Task 8)
conteudo/site.toml, conteudo/LEIA-ME.md                               (Tasks 5, 9)
tests/fabrica.py, conftest.py, test_*.py
Dockerfile, docker-compose.yml, .dockerignore, .env.example, README.md (Task 9)
```

Removed in Task 1: `app/admin.py`, `app/media.py`, `app/conteudo.py`, `app/db.py`, `app/main.py`, `app/web.py`, `app/templates/**`, `app/static/**`, `tests/test_app.py` (old version, fully replaced).

---

### Task 1: Clean slate, dependencies, config and storage

**Files:**
- Delete: old `app/*.py` (except `__init__.py`), `app/templates/`, `app/static/`, `tests/test_app.py`
- Modify: `pyproject.toml`, `.gitignore` (add `.claude/`)
- Create: `app/config.py`, `app/storage.py`, `tests/fabrica.py`, `tests/conftest.py`, `tests/test_storage.py`

**Interfaces:**
- Produces: `Settings(admin_user, admin_password, data_dir, content_dir, database_url, storage_backend="local", blob_token="", max_upload_mb=300)` with properties `uploads_dir`, `cache_dir`, `tmp_dir` and `Settings.from_env()`.
- Produces: `Armazenamento` protocol (`salvar(chave, dados: BinaryIO, content_type) -> None`, `apagar(chave) -> None`, `url(chave) -> str`), `LocalStorage(pasta: Path, prefixo_url="/uploads")`, `BlobStorage(token)`, `criar_armazenamento(settings) -> Armazenamento`.
- Produces: `tests/fabrica.py` with `AUTH`, `jpeg_bytes(tamanho=(400, 200), orientacao=None, gps=False) -> bytes`, `logo_png(caminho)`; `tests/conftest.py` fixtures `settings`, `client`.

- [ ] **Step 1: Remove the old implementation and ignore worktrees**

```bash
git rm -q app/admin.py app/media.py app/conteudo.py app/db.py app/main.py app/web.py tests/test_app.py
git rm -q -r app/templates app/static
printf ".claude/\n" >> .gitignore
```

- [ ] **Step 2: Add dependencies**

```bash
uv add "sqlalchemy>=2.0" "pillow>=11" "pillow-heif>=1.0"
```

Expected: `pyproject.toml` dependencies now include fastapi, jinja2, python-dotenv, python-multipart, uvicorn[standard], sqlalchemy, pillow, pillow-heif. If `pillow-heif` has no wheel for Python 3.14 on this platform, drop it (`uv remove pillow-heif`), remove `.heic`/`.heif` from `EXT_IMAGEM` in Task 3 and the `register_heif_opener` lines, and note it in the final report.

- [ ] **Step 3: Write test helpers and fixtures**

`tests/fabrica.py`:

```python
import io
from pathlib import Path

from PIL import Image, ImageDraw

AUTH = ("admin", "segredo")


def jpeg_bytes(tamanho=(400, 200), orientacao: int | None = None, gps: bool = False) -> bytes:
    """JPEG gerado na hora, com orientação EXIF e GPS opcionais (como foto de iPhone)."""
    img = Image.new("RGB", tamanho, (169, 50, 38))
    exif = Image.Exif()
    if orientacao:
        exif[0x0112] = orientacao
    if gps:
        exif[0x8825] = {1: "S", 2: (23.0, 33.0, 0.0)}
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif.tobytes())
    return buf.getvalue()


def logo_png(caminho: Path) -> None:
    """Logo falso no estilo do LOGO-03: desenho branco sobre fundo preto."""
    img = Image.new("RGBA", (300, 200), (0, 0, 0, 255))
    ImageDraw.Draw(img).rectangle((100, 50, 200, 150), fill=(255, 255, 255, 255))
    img.save(caminho)
```

`tests/conftest.py`:

```python
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import BASE_DIR, Settings
from tests.fabrica import logo_png


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    conteudo = tmp_path / "conteudo"
    for pasta in ("logo", "cardapio", "eventos-realizados"):
        (conteudo / pasta).mkdir(parents=True)
    shutil.copy(BASE_DIR / "conteudo" / "site.toml", conteudo / "site.toml")
    logo_png(conteudo / "logo" / "LOGO-03.png")
    data = tmp_path / "data"
    return Settings(
        admin_user="admin",
        admin_password="segredo",
        data_dir=data,
        content_dir=conteudo,
        database_url=f"sqlite:///{(data / 'teste.db').as_posix()}",
        max_upload_mb=1,
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    from app.main import create_app

    return TestClient(create_app(settings))
```

(`client` imports lazily so Tasks 1–5 run before `app.main` exists.)

- [ ] **Step 4: Write the failing tests**

`tests/test_storage.py`:

```python
import io

import pytest

from app.config import Settings
from app.storage import BlobStorage, LocalStorage, criar_armazenamento


def test_local_salva_serve_e_apaga(tmp_path):
    storage = LocalStorage(tmp_path / "uploads")
    storage.salvar("abc.webp", io.BytesIO(b"conteudo"), "image/webp")
    assert (tmp_path / "uploads" / "abc.webp").read_bytes() == b"conteudo"
    assert storage.url("abc.webp") == "/uploads/abc.webp"
    storage.apagar("abc.webp")
    assert not (tmp_path / "uploads" / "abc.webp").exists()
    storage.apagar("abc.webp")  # apagar duas vezes não quebra


@pytest.mark.parametrize("chave", ["../fora.txt", "sub/arq.webp", "", ".oculto"])
def test_local_recusa_chave_perigosa(tmp_path, chave):
    with pytest.raises(ValueError):
        LocalStorage(tmp_path).salvar(chave, io.BytesIO(b"x"), "text/plain")


def test_fabrica_escolhe_backend(settings):
    assert isinstance(criar_armazenamento(settings), LocalStorage)
    blob = Settings(**{**settings.__dict__, "storage_backend": "blob", "blob_token": "t"})
    assert isinstance(criar_armazenamento(blob), BlobStorage)
    with pytest.raises(ValueError, match="STORAGE_BACKEND"):
        criar_armazenamento(Settings(**{**settings.__dict__, "storage_backend": "s3"}))


def test_blob_ainda_nao_implementado():
    with pytest.raises(NotImplementedError):
        BlobStorage("t").salvar("a.webp", io.BytesIO(b""), "image/webp")


def test_settings_do_ambiente(monkeypatch, tmp_path):
    monkeypatch.setenv("ADMIN_PASSWORD", "x")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("MAX_UPLOAD_MB", "50")
    s = Settings.from_env()
    assert s.admin_password == "x"
    assert s.database_url == f"sqlite:///{(tmp_path / 'brasamiga.db').as_posix()}"
    assert s.max_upload_mb == 50
    assert s.uploads_dir == tmp_path / "uploads"
    assert s.cache_dir == tmp_path / "cache"
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `uv run pytest tests/test_storage.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.config'`

- [ ] **Step 6: Implement `app/config.py`**

```python
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    admin_user: str
    admin_password: str
    data_dir: Path
    content_dir: Path
    database_url: str
    storage_backend: str = "local"
    blob_token: str = ""
    max_upload_mb: int = 300

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def tmp_dir(self) -> Path:
        return self.data_dir / "tmp"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(BASE_DIR / ".env")
        data_dir = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
        return cls(
            admin_user=os.getenv("ADMIN_USER", "admin"),
            admin_password=os.getenv("ADMIN_PASSWORD", ""),
            data_dir=data_dir,
            content_dir=Path(os.getenv("CONTENT_DIR", BASE_DIR / "conteudo")),
            database_url=os.getenv("DATABASE_URL") or f"sqlite:///{(data_dir / 'brasamiga.db').as_posix()}",
            storage_backend=os.getenv("STORAGE_BACKEND", "local"),
            blob_token=os.getenv("BLOB_READ_WRITE_TOKEN", ""),
            max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "300")),
        )
```

- [ ] **Step 7: Implement `app/storage.py`**

```python
"""Onde ficam as fotos e vídeos enviados pelo painel.

Hoje: disco local (volume do Docker). Na Vercel: Vercel Blob, trocando STORAGE_BACKEND.
"""

import shutil
from pathlib import Path
from typing import BinaryIO, Protocol

from app.config import Settings


class Armazenamento(Protocol):
    def salvar(self, chave: str, dados: BinaryIO, content_type: str) -> None: ...
    def apagar(self, chave: str) -> None: ...
    def url(self, chave: str) -> str: ...


def _validar(chave: str) -> str:
    if not chave or chave.startswith(".") or "/" in chave or "\\" in chave:
        raise ValueError(f"Chave de arquivo inválida: {chave!r}")
    return chave


class LocalStorage:
    def __init__(self, pasta: Path, prefixo_url: str = "/uploads") -> None:
        self.pasta = pasta
        self.prefixo_url = prefixo_url.rstrip("/")
        pasta.mkdir(parents=True, exist_ok=True)

    def salvar(self, chave: str, dados: BinaryIO, content_type: str) -> None:
        with (self.pasta / _validar(chave)).open("wb") as destino:
            shutil.copyfileobj(dados, destino)

    def apagar(self, chave: str) -> None:
        (self.pasta / _validar(chave)).unlink(missing_ok=True)

    def url(self, chave: str) -> str:
        return f"{self.prefixo_url}/{_validar(chave)}"


class BlobStorage:
    """Vercel Blob. Implementar na migração para a Vercel.

    API: PUT https://blob.vercel-storage.com/<chave> com o header
    `Authorization: Bearer <BLOB_READ_WRITE_TOKEN>`; a resposta traz a `url` pública.
    Uploads maiores que 4,5 MB precisam ir direto do navegador para o Blob (client upload).
    """

    def __init__(self, token: str) -> None:
        self.token = token

    def salvar(self, chave: str, dados: BinaryIO, content_type: str) -> None:
        raise NotImplementedError("BlobStorage ainda não foi implementado: use STORAGE_BACKEND=local.")

    def apagar(self, chave: str) -> None:
        raise NotImplementedError("BlobStorage ainda não foi implementado: use STORAGE_BACKEND=local.")

    def url(self, chave: str) -> str:
        raise NotImplementedError("BlobStorage ainda não foi implementado: use STORAGE_BACKEND=local.")


def criar_armazenamento(settings: Settings) -> Armazenamento:
    if settings.storage_backend == "local":
        return LocalStorage(settings.uploads_dir)
    if settings.storage_backend == "blob":
        return BlobStorage(settings.blob_token)
    raise ValueError(f"STORAGE_BACKEND desconhecido: {settings.storage_backend!r}. Use 'local' ou 'blob'.")
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/test_storage.py -q`
Expected: `8 passed`

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "Recomeça a base com config e armazenamento trocável

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Database (SQLAlchemy Core)

**Files:**
- Create: `app/db.py`, `tests/test_db.py`

**Interfaces:**
- Consumes: the `settings` fixture (`settings.database_url`).
- Produces: `Database(url: str)` with:
  - `listar_eventos(tipo: str, a_partir_de: date | None = None) -> list[dict]` (each dict has event columns + `total_midias`)
  - `obter_evento(evento_id: int) -> dict | None`
  - `criar_evento(titulo: str, data: date | None, local: str, descricao: str, tipo: str) -> int`
  - `atualizar_evento(evento_id: int, titulo: str, data: date | None, local: str, descricao: str, tipo: str) -> None`
  - `excluir_evento(evento_id: int) -> list[dict]` (returns the deleted media rows)
  - `adicionar_midia(evento_id: int, chave: str, tipo: str, chave_miniatura: str | None = None) -> int`
  - `listar_midias(evento_id: int) -> list[dict]`
  - `midias_por_evento(ids: list[int]) -> dict[int, list[dict]]`
  - `excluir_midia(midia_id: int) -> dict | None`
  - `criar_orcamento(nome, telefone, email="", data_evento=None, local="", convidados=None, pacote="", mensagem="") -> int`
  - `listar_orcamentos() -> list[dict]` (not-yet-answered first, newest first)
  - `alternar_lido(orcamento_id: int) -> None`

- [ ] **Step 1: Write the failing tests**

`tests/test_db.py`:

```python
from datetime import date

import pytest

from app.db import Database


@pytest.fixture
def db(settings):
    return Database(settings.database_url)


def test_eventos_realizados_mais_recentes_primeiro(db):
    db.criar_evento("Antigo", date(2025, 1, 10), "", "", "realizado")
    db.criar_evento("Recente", date(2026, 5, 10), "Atibaia", "", "realizado")
    db.criar_evento("Sem data", None, "", "", "realizado")
    titulos = [e["titulo"] for e in db.listar_eventos("realizado")]
    assert titulos == ["Recente", "Antigo", "Sem data"]


def test_futuros_filtra_passados_e_ordena(db):
    db.criar_evento("Longe", date(2099, 12, 1), "", "", "futuro")
    db.criar_evento("Perto", date(2099, 1, 1), "", "", "futuro")
    db.criar_evento("Passou", date(2001, 1, 1), "", "", "futuro")
    db.criar_evento("A confirmar", None, "", "", "futuro")
    titulos = [e["titulo"] for e in db.listar_eventos("futuro", a_partir_de=date(2026, 10, 21))]
    assert titulos == ["Perto", "Longe", "A confirmar"]


def test_tipo_invalido_e_recusado(db):
    with pytest.raises(Exception):
        db.criar_evento("X", None, "", "", "talvez")


def test_midias_contagem_agrupamento_e_cascata(db):
    a = db.criar_evento("A", None, "", "", "realizado")
    b = db.criar_evento("B", None, "", "", "realizado")
    db.adicionar_midia(a, "1.webp", "imagem", "1-mini.webp")
    db.adicionar_midia(a, "2.mp4", "video")
    db.adicionar_midia(b, "3.webp", "imagem", "3-mini.webp")
    contagem = {e["titulo"]: e["total_midias"] for e in db.listar_eventos("realizado")}
    assert contagem == {"A": 2, "B": 1}
    agrupado = db.midias_por_evento([a, b])
    assert [m["chave"] for m in agrupado[a]] == ["1.webp", "2.mp4"]
    assert db.midias_por_evento([]) == {}

    apagadas = db.excluir_evento(a)
    assert {m["chave"] for m in apagadas} == {"1.webp", "2.mp4"}
    assert db.listar_midias(a) == []
    assert db.obter_evento(a) is None


def test_atualizar_e_excluir_midia(db):
    e = db.criar_evento("A", None, "", "", "futuro")
    db.atualizar_evento(e, "A2", date(2027, 1, 1), "Moema", "Desc", "realizado")
    evento = db.obter_evento(e)
    assert (evento["titulo"], evento["data"], evento["tipo"]) == ("A2", date(2027, 1, 1), "realizado")
    m = db.adicionar_midia(e, "x.webp", "imagem")
    assert db.excluir_midia(m)["chave"] == "x.webp"
    assert db.excluir_midia(m) is None


def test_orcamentos_novos_primeiro_e_alternar_lido(db):
    primeiro = db.criar_orcamento("Ana", "1199", pacote="Nelore", convidados=80, data_evento=date(2026, 12, 12))
    segundo = db.criar_orcamento("Bia", "1188")
    db.alternar_lido(segundo)
    nomes = [o["nome"] for o in db.listar_orcamentos()]
    assert nomes == ["Ana", "Bia"]
    db.alternar_lido(segundo)
    assert [o["nome"] for o in db.listar_orcamentos()] == ["Bia", "Ana"]
    assert db.listar_orcamentos()[1]["convidados"] == 80
    assert primeiro != segundo
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_db.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.db'`

- [ ] **Step 3: Implement `app/db.py`**

```python
"""Banco de dados. SQLite hoje; Postgres (Neon) na Vercel trocando só a DATABASE_URL."""

from datetime import date, datetime
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
    not_,
    or_,
    select,
    update,
)

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
    Column("criado_em", DateTime, nullable=False, default=datetime.now),
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
    Column("criado_em", DateTime, nullable=False, default=datetime.now),
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
    Column("criado_em", DateTime, nullable=False, default=datetime.now),
)


class Database:
    def __init__(self, url: str) -> None:
        if url.startswith("sqlite:///"):
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(url)
        if self.engine.dialect.name == "sqlite":
            event.listen(self.engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys = ON"))
        metadata.create_all(self.engine)

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_db.py -q`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add app/db.py tests/test_db.py
git commit -m "Adiciona banco com SQLAlchemy Core pronto para Postgres

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Media processing (images, logo, video)

**Files:**
- Create: `app/midia.py`, `tests/test_midia.py`

**Interfaces:**
- Consumes: `tests/fabrica.jpeg_bytes`, `tests/fabrica.logo_png`.
- Produces (module `app.midia`):
  - `EXT_IMAGEM: set[str]`, `EXT_VIDEO: set[str]`, `LADO_GRANDE = 1600`, `LADO_MINIATURA = 600`
  - `class MidiaInvalida(ValueError)`
  - `tipo_por_extensao(nome: str) -> str | None` → `"imagem"`, `"video"` or `None`
  - `otimizar_imagem(origem: Path | BinaryIO, lado: int) -> bytes` (WEBP)
  - `logo_para_fundo_escuro(origem: Path, largura: int = 1200) -> bytes` (PNG, white on transparent, cropped)
  - `ffmpeg_disponivel() -> bool`, `video_legivel(caminho: Path) -> bool`, `converter_video(origem: Path, destino: Path) -> bool`
  - `@dataclass Processado(tipo: str, principal: Path, extensao: str, content_type: str, miniatura: Path | None, aviso: str | None)`
  - `async receber_upload(upload: UploadFile, pasta: Path, limite_mb: int) -> Path`
  - `processar(origem: Path, nome_original: str) -> Processado`

- [ ] **Step 1: Write the failing tests**

`tests/test_midia.py`:

```python
import asyncio
import io
import subprocess

import pytest
from fastapi import UploadFile
from PIL import Image

from app import midia
from tests.fabrica import jpeg_bytes, logo_png


@pytest.mark.parametrize(
    ("nome", "tipo"),
    [
        ("foto.jpg", "imagem"),
        ("Festa Junina 2025.JPG", "imagem"),
        ("IMG_0001.HEIC", "imagem"),
        ("IMG_5038.MOV", "video"),
        ("clip.mp4", "video"),
        ("virus.exe", None),
        ("sem-extensao", None),
    ],
)
def test_tipo_por_extensao(nome, tipo):
    assert midia.tipo_por_extensao(nome) == tipo


def test_otimizar_gira_reduz_e_remove_gps():
    original = jpeg_bytes(tamanho=(3200, 1600), orientacao=6, gps=True)
    assert Image.open(io.BytesIO(original)).getexif().get_ifd(0x8825), "a foto de teste precisa ter GPS"

    saida = Image.open(io.BytesIO(midia.otimizar_imagem(io.BytesIO(original), midia.LADO_GRANDE)))
    assert saida.format == "WEBP"
    assert saida.size == (800, 1600)  # 3200x1600 girada 90° = 1600x3200, reduzida a 1600 no maior lado
    assert len(saida.getexif()) == 0


def test_otimizar_nao_aumenta_foto_pequena():
    saida = Image.open(io.BytesIO(midia.otimizar_imagem(io.BytesIO(jpeg_bytes((400, 200))), 600)))
    assert saida.size == (400, 200)


def test_otimizar_recusa_arquivo_que_nao_e_imagem():
    with pytest.raises(midia.MidiaInvalida):
        midia.otimizar_imagem(io.BytesIO(b"isto nao e uma foto"), 600)


def test_logo_vira_branco_transparente_e_recortado(tmp_path):
    logo_png(tmp_path / "logo.png")
    img = Image.open(io.BytesIO(midia.logo_para_fundo_escuro(tmp_path / "logo.png", largura=50)))
    assert img.mode == "RGBA"
    assert img.width == 50  # recortado ao desenho (101x101) e reduzido
    assert img.getpixel((25, 25))[3] == 255
    inteiro = midia.logo_para_fundo_escuro(tmp_path / "logo.png")
    assert Image.open(io.BytesIO(inteiro)).size == (101, 101)  # não amplia além do desenho


def _upload(nome: str, dados: bytes) -> UploadFile:
    return UploadFile(file=io.BytesIO(dados), filename=nome)


def test_receber_upload_respeita_limite(tmp_path):
    with pytest.raises(midia.MidiaInvalida, match="limite de 1 MB"):
        asyncio.run(midia.receber_upload(_upload("grande.mp4", b"0" * (2 * 1024 * 1024)), tmp_path, 1))
    assert list(tmp_path.iterdir()) == []


def test_receber_upload_recusa_extensao(tmp_path):
    with pytest.raises(midia.MidiaInvalida, match="virus.exe"):
        asyncio.run(midia.receber_upload(_upload("virus.exe", b"MZ"), tmp_path, 1))


def test_processar_imagem_gera_grande_e_miniatura(tmp_path):
    bruto = asyncio.run(midia.receber_upload(_upload("Festa Junina.JPG", jpeg_bytes((2000, 1000))), tmp_path, 5))
    pronto = midia.processar(bruto, "Festa Junina.JPG")
    assert (pronto.tipo, pronto.extensao, pronto.content_type) == ("imagem", ".webp", "image/webp")
    assert Image.open(pronto.principal).size == (1600, 800)
    assert Image.open(pronto.miniatura).size == (600, 300)
    assert pronto.aviso is None


def test_processar_imagem_corrompida(tmp_path):
    falsa = tmp_path / "falsa.jpg"
    falsa.write_bytes(b"nada")
    with pytest.raises(midia.MidiaInvalida, match="falsa.jpg"):
        midia.processar(falsa, "falsa.jpg")


@pytest.mark.skipif(midia.ffmpeg_disponivel(), reason="só vale sem ffmpeg instalado")
def test_video_sem_ffmpeg_fica_original_com_aviso(tmp_path):
    video = tmp_path / "clip.mov"
    video.write_bytes(b"\x00" * 10)
    pronto = midia.processar(video, "clip.MOV")
    assert (pronto.tipo, pronto.extensao, pronto.content_type) == ("video", ".mov", "video/quicktime")
    assert "formato original" in pronto.aviso


@pytest.mark.skipif(not midia.ffmpeg_disponivel(), reason="ffmpeg não instalado")
def test_video_convertido_para_mp4(tmp_path):
    origem = tmp_path / "clip.mov"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10", "-t", "1", str(origem)],
        check=True,
    )
    pronto = midia.processar(origem, "clip.MOV")
    assert (pronto.extensao, pronto.content_type, pronto.aviso) == (".mp4", "video/mp4", None)
    assert pronto.principal.stat().st_size > 0


@pytest.mark.skipif(not midia.ffmpeg_disponivel(), reason="ffmpeg não instalado")
def test_video_corrompido_e_recusado(tmp_path):
    falso = tmp_path / "falso.mp4"
    falso.write_bytes(b"\x00" * 100)
    with pytest.raises(midia.MidiaInvalida, match="falso.mp4"):
        midia.processar(falso, "falso.mp4")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_midia.py -q`
Expected: FAIL with `ImportError: cannot import name 'midia' from 'app'`

- [ ] **Step 3: Implement `app/midia.py`**

```python
"""Validação e preparo de fotos e vídeos para a web."""

import io
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

register_heif_opener()

EXT_IMAGEM = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
EXT_VIDEO = {".mp4", ".mov", ".m4v", ".webm"}
LADO_GRANDE = 1600
LADO_MINIATURA = 600
CHUNK = 1024 * 1024
CONTENT_TYPES = {
    ".webp": "image/webp",
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
}
FORMATOS_ACEITOS = "JPG, PNG, WEBP, HEIC, MP4, MOV ou WEBM"


class MidiaInvalida(ValueError):
    pass


@dataclass
class Processado:
    tipo: str
    principal: Path
    extensao: str
    content_type: str
    miniatura: Path | None
    aviso: str | None


def tipo_por_extensao(nome: str) -> str | None:
    ext = Path(nome).suffix.lower()
    if ext in EXT_IMAGEM:
        return "imagem"
    if ext in EXT_VIDEO:
        return "video"
    return None


def otimizar_imagem(origem: Path | BinaryIO, lado: int) -> bytes:
    """WEBP com no máximo `lado` px no maior lado, já girada e sem metadados (GPS incluso)."""
    try:
        with Image.open(origem) as aberta:
            img = ImageOps.exif_transpose(aberta)
            img.thumbnail((lado, lado))
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
            img.info = {}
            buf = io.BytesIO()
            img.save(buf, "WEBP", quality=80, method=4, exif=b"")
            return buf.getvalue()
    except (UnidentifiedImageError, OSError, ValueError) as erro:
        raise MidiaInvalida("não é uma imagem válida") from erro


def logo_para_fundo_escuro(origem: Path, largura: int = 1200) -> bytes:
    """Transforma um logo branco sobre preto em branco sobre transparente, recortado ao desenho."""
    try:
        with Image.open(origem) as aberta:
            fundo = Image.new("RGBA", aberta.size, (0, 0, 0, 255))
            fundo.alpha_composite(aberta.convert("RGBA"))
    except (UnidentifiedImageError, OSError) as erro:
        raise MidiaInvalida("o logo não é uma imagem válida") from erro
    luz = fundo.convert("L")
    branco = Image.new("RGBA", fundo.size, (255, 255, 255, 255))
    branco.putalpha(luz)
    caixa = luz.point(lambda v: 255 if v > 40 else 0).getbbox()
    if caixa:
        branco = branco.crop(caixa)
    if branco.width > largura:
        branco = branco.resize((largura, round(branco.height * largura / branco.width)), Image.LANCZOS)
    buf = io.BytesIO()
    branco.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def ffmpeg_disponivel() -> bool:
    return shutil.which("ffmpeg") is not None


def video_legivel(caminho: Path) -> bool:
    """Confere com o ffprobe se há uma faixa de vídeo. Sem ffprobe, confia na extensão."""
    if shutil.which("ffprobe") is None:
        return True
    resultado = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_type",
         "-of", "csv=p=0", str(caminho)],
        capture_output=True, text=True, timeout=60,
    )
    return resultado.returncode == 0 and "video" in resultado.stdout


def converter_video(origem: Path, destino: Path) -> bool:
    """MP4 H.264 até 1080p, sem metadados. Devolve False se o ffmpeg faltar ou falhar."""
    if not ffmpeg_disponivel():
        return False
    comando = [
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(origem),
        "-map_metadata", "-1",
        "-vf", "scale='min(1920,iw)':'min(1080,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        str(destino),
    ]
    try:
        ok = subprocess.run(comando, capture_output=True, timeout=900).returncode == 0
    except subprocess.TimeoutExpired:
        ok = False
    if not ok:
        destino.unlink(missing_ok=True)
    return ok


async def receber_upload(upload: UploadFile, pasta: Path, limite_mb: int) -> Path:
    """Grava o upload num arquivo temporário, recusando extensão estranha ou tamanho acima do limite."""
    nome = upload.filename or ""
    if tipo_por_extensao(nome) is None:
        raise MidiaInvalida(f"“{nome}” não foi enviado: use {FORMATOS_ACEITOS}.")
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{uuid4().hex}{Path(nome).suffix.lower()}"
    limite = limite_mb * CHUNK
    total = 0
    try:
        with destino.open("wb") as arquivo:
            while chunk := await upload.read(CHUNK):
                total += len(chunk)
                if total > limite:
                    raise MidiaInvalida(
                        f"“{nome}” passou do limite de {limite_mb} MB. Comprima o arquivo e envie de novo."
                    )
                arquivo.write(chunk)
    except BaseException:
        destino.unlink(missing_ok=True)
        raise
    return destino


def processar(origem: Path, nome_original: str) -> Processado:
    tipo = tipo_por_extensao(nome_original)
    if tipo == "imagem":
        try:
            grande = otimizar_imagem(origem, LADO_GRANDE)
            mini = otimizar_imagem(origem, LADO_MINIATURA)
        except MidiaInvalida:
            raise MidiaInvalida(f"“{nome_original}” não é uma imagem válida.") from None
        caminho_grande = origem.parent / f"{origem.stem}-grande.webp"
        caminho_mini = origem.parent / f"{origem.stem}-mini.webp"
        caminho_grande.write_bytes(grande)
        caminho_mini.write_bytes(mini)
        return Processado("imagem", caminho_grande, ".webp", "image/webp", caminho_mini, None)

    if tipo != "video":
        raise MidiaInvalida(f"“{nome_original}” não foi enviado: use {FORMATOS_ACEITOS}.")
    if not video_legivel(origem):
        raise MidiaInvalida(f"“{nome_original}” não é um vídeo válido.")
    convertido = origem.parent / f"{origem.stem}-web.mp4"
    if converter_video(origem, convertido):
        return Processado("video", convertido, ".mp4", "video/mp4", None, None)
    ext = origem.suffix.lower()
    aviso = f"“{nome_original}” foi salvo no formato original e pode não tocar em todos os navegadores."
    return Processado("video", origem, ext, CONTENT_TYPES[ext], None, aviso)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_midia.py -q`
Expected (Windows, no ffmpeg): `16 passed, 2 skipped`. Inside Docker the two ffmpeg tests run and the no-ffmpeg test is skipped.

If `test_otimizar_gira_reduz_e_remove_gps` fails on the GPS precondition assertion, Pillow could not write the nested GPS IFD: replace the `gps` branch in `tests/fabrica.py` with `exif.get_ifd(0x8825).update({1: "S", 2: (23.0, 33.0, 0.0)})` and rerun.

- [ ] **Step 5: Commit**

```bash
git add app/midia.py tests/test_midia.py
git commit -m "Adiciona preparo de fotos, logo e vídeos para a web

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: WhatsApp links

**Files:**
- Create: `app/whatsapp.py`, `tests/test_whatsapp.py`

**Interfaces:**
- Produces: `MENSAGEM_PADRAO: str`, `so_digitos(numero: str) -> str`, `link(numero: str, mensagem: str | None = None) -> str`, `mensagem_orcamento(nome: str, pacote: str = "", data_evento: date | None = None, local: str = "", convidados: int | None = None, mensagem: str = "") -> str`.

- [ ] **Step 1: Write the failing tests**

`tests/test_whatsapp.py`:

```python
from datetime import date
from urllib.parse import parse_qs, urlparse

from app import whatsapp


def test_link_limpa_numero_e_codifica_texto():
    url = whatsapp.link("+55 (11) 99343-3998", "Olá! Quero orçamento & preço")
    partes = urlparse(url)
    assert f"{partes.scheme}://{partes.netloc}{partes.path}" == "https://wa.me/5511993433998"
    assert parse_qs(partes.query)["text"] == ["Olá! Quero orçamento & preço"]


def test_link_sem_mensagem():
    assert whatsapp.link("5511993433998") == "https://wa.me/5511993433998"


def test_mensagem_completa():
    texto = whatsapp.mensagem_orcamento(
        "Carla", pacote="Nelore", data_evento=date(2026, 12, 12), local="Moema", convidados=80,
        mensagem="Tem opção sem glúten?",
    )
    assert texto == (
        "Olá! Sou Carla e quero um orçamento do Brasamiga. Pacote: Nelore. Data: 12/12/2026. "
        "Local: Moema. Convidados: 80. Tem opção sem glúten?"
    )


def test_mensagem_so_com_nome():
    assert whatsapp.mensagem_orcamento("Carla") == "Olá! Sou Carla e quero um orçamento do Brasamiga."
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_whatsapp.py -q`
Expected: FAIL with `ImportError: cannot import name 'whatsapp'`

- [ ] **Step 3: Implement `app/whatsapp.py`**

```python
import re
from datetime import date
from urllib.parse import quote

MENSAGEM_PADRAO = "Olá! Quero um orçamento de churrasco para o meu evento."


def so_digitos(numero: str) -> str:
    return re.sub(r"\D", "", numero)


def link(numero: str, mensagem: str | None = None) -> str:
    url = f"https://wa.me/{so_digitos(numero)}"
    return f"{url}?text={quote(mensagem)}" if mensagem else url


def mensagem_orcamento(
    nome: str,
    pacote: str = "",
    data_evento: date | None = None,
    local: str = "",
    convidados: int | None = None,
    mensagem: str = "",
) -> str:
    partes = [f"Olá! Sou {nome} e quero um orçamento do Brasamiga."]
    if pacote:
        partes.append(f"Pacote: {pacote}.")
    if data_evento:
        partes.append(f"Data: {data_evento:%d/%m/%Y}.")
    if local:
        partes.append(f"Local: {local}.")
    if convidados:
        partes.append(f"Convidados: {convidados}.")
    if mensagem:
        partes.append(mensagem)
    return " ".join(partes)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_whatsapp.py -q`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add app/whatsapp.py tests/test_whatsapp.py
git commit -m "Adiciona montagem do link de orçamento pelo WhatsApp

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Site content (`site.toml`) and gallery cache

**Files:**
- Rewrite: `conteudo/site.toml`
- Create: `app/conteudo.py`, `tests/test_conteudo.py`

**Interfaces:**
- Consumes: `app.midia.otimizar_imagem`, `LADO_GRANDE`, `LADO_MINIATURA`, `MidiaInvalida`, `tipo_por_extensao`, `converter_video`, `logo_para_fundo_escuro`.
- Produces (module `app.conteudo`):
  - `PASTAS_PUBLICAS = ("logo", "cardapio")`
  - `class ConteudoInvalido(RuntimeError)` with attributes `arquivo: Path`, `linha: int | None`, `detalhe: str`
  - `carregar_site(content_dir: Path) -> dict`
  - `@dataclass(frozen=True) ItemGaleria(tipo: str, url: str, url_miniatura: str)`
  - `Conteudo(content_dir: Path, cache_dir: Path)` with `site() -> dict`, `galeria() -> list[ItemGaleria]`, `logo_escuro(nome: str | None) -> str | None`, `pdfs() -> list[dict]` (keys `url`, `nome`), `preparar() -> dict` (keys `imagens`, `videos`).
  - Public URLs: `/cache/galeria/<chave>-grande.webp`, `/cache/galeria/<chave>-mini.webp`, `/cache/galeria/<chave>.mp4`, `/cache/logo/<chave>.png`, `/conteudo/cardapio/<arquivo>`.
- Produces the `site.toml` schema consumed by the templates in Tasks 6–7 (see Step 3).

- [ ] **Step 1: Write the failing tests**

`tests/test_conteudo.py`:

```python
import pytest

from app.config import BASE_DIR
from app.conteudo import Conteudo, ConteudoInvalido, carregar_site
from tests.fabrica import jpeg_bytes


def test_site_real_tem_os_quatro_pacotes_do_pdf():
    site = carregar_site(BASE_DIR / "conteudo")
    pacotes = {p["nome"]: p for p in site["pacotes"]}
    assert list(pacotes) == ["Senepol", "Devon", "Nelore", "Angus"]
    assert [p["preco"] for p in site["pacotes"]] == ["R$ 300", "R$ 100", "R$ 120", "R$ 150"]
    assert pacotes["Nelore"]["destaque"] is True
    assert sum(p["destaque"] for p in site["pacotes"]) == 1
    assert all(len(linha["valores"]) == 4 for linha in site["comparativo"])
    assert site["contato"]["whatsapp"] == "5511993433998"
    assert any(f["pergunta"] == "Qual região vocês atendem?" for f in site["faq"])


def test_toml_com_bom_e_acentos_carrega(tmp_path):
    (tmp_path / "site.toml").write_bytes('﻿[marca]\nnome = "Brasamiga Ação"\n'.encode("utf-8"))
    assert carregar_site(tmp_path)["marca"]["nome"] == "Brasamiga Ação"


def test_toml_com_erro_informa_a_linha(tmp_path):
    (tmp_path / "site.toml").write_text('[marca]\nnome = "Brasamiga\n', encoding="utf-8")
    with pytest.raises(ConteudoInvalido) as erro:
        carregar_site(tmp_path)
    assert erro.value.linha == 2


def test_toml_ausente(tmp_path):
    with pytest.raises(ConteudoInvalido, match="não encontrado"):
        carregar_site(tmp_path)


def test_galeria_gera_webp_em_cache_e_reaproveita(settings):
    pasta = settings.content_dir / "eventos-realizados"
    (pasta / "b.jpg").write_bytes(jpeg_bytes((2000, 1000), gps=True))
    (pasta / "a.JPEG").write_bytes(jpeg_bytes((800, 600)))
    (pasta / "leia.txt").write_text("ignorar")
    (pasta / "quebrada.jpg").write_bytes(b"nada")
    conteudo = Conteudo(settings.content_dir, settings.cache_dir)

    itens = conteudo.galeria()
    assert [i.tipo for i in itens] == ["imagem", "imagem"]
    assert all(i.url.startswith("/cache/galeria/") and i.url.endswith("-grande.webp") for i in itens)
    arquivo = settings.cache_dir / "galeria" / itens[1].url.rsplit("/", 1)[1]
    modificado = arquivo.stat().st_mtime_ns

    assert conteudo.galeria() == itens
    assert arquivo.stat().st_mtime_ns == modificado  # não refaz o que já está em cache


def test_video_sem_versao_web_nao_aparece(settings):
    (settings.content_dir / "eventos-realizados" / "IMG_5038.MOV").write_bytes(b"\x00")
    assert Conteudo(settings.content_dir, settings.cache_dir).galeria() == []


def test_logo_e_pdfs(settings):
    (settings.content_dir / "cardapio" / "Brasamiga_Proposta_Comercial.pdf").write_bytes(b"%PDF-1.4")
    conteudo = Conteudo(settings.content_dir, settings.cache_dir)
    url = conteudo.logo_escuro("LOGO-03.png")
    assert url.startswith("/cache/logo/") and url.endswith(".png")
    assert conteudo.logo_escuro("nao-existe.png") is None
    assert conteudo.logo_escuro(None) is None
    assert conteudo.pdfs() == [
        {"url": "/conteudo/cardapio/Brasamiga_Proposta_Comercial.pdf", "nome": "Brasamiga Proposta Comercial"}
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_conteudo.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.conteudo'`

- [ ] **Step 3: Rewrite `conteudo/site.toml` with the PDF content**

```toml
# Conteúdo da landing page do Brasamiga (tirado da Proposta Comercial 2026).
# Edite e recarregue a página: não precisa reiniciar o site.
# Dica: mantenha as aspas e os colchetes. Se algo quebrar, o site mostra a linha do erro.

[marca]
nome = "Brasamiga"
chamada = "Churrasco para eventos"
subtitulo = "De reuniões em família a grandes eventos corporativos"
logo_escuro = "LOGO-03.png"   # logo branco sobre preto, usado nas faixas escuras
regiao = "Capital e Grande São Paulo"

[contato]
whatsapp = "5511993433998"          # só números: 55 + DDD + número
whatsapp_exibicao = "(11) 99343-3998"
instagram = "brasamiga"             # sem o @

[sobre]
titulo_destaque = "Paixão por churrasco,"
titulo = "servida com capricho."
paragrafos = [
  "A Brasamiga nasceu da vontade de levar um churrasco bem feito para qualquer ocasião. Cuidamos de tudo — carnes, acompanhamentos, carvão, utensílios e serviço — para que você só se preocupe em receber bem os seus convidados.",
  "Trabalhamos com cortes selecionados e técnica de brasa para entregar carne suculenta e no ponto certo. O cardápio é flexível: escolha um dos nossos pacotes ou monte um menu personalizado para o seu evento.",
  "Atendemos desde pequenas reuniões familiares até eventos corporativos com dezenas de convidados, sempre com o mesmo padrão de qualidade e organização.",
]

[[numeros]]
valor = "2022"
legenda = "no mercado desde"

[[numeros]]
valor = "SP"
legenda = "capital e Grande SP"

[[numeros]]
valor = "15–200"
legenda = "convidados por evento"

[[diferenciais]]
titulo = "Tudo incluso"
texto = "Carvão, descartáveis, rechaud, pegadores e demais utensílios já fazem parte do pacote."

[[diferenciais]]
titulo = "Menu flexível"
texto = "Troque, adicione ou remova itens; ajustamos o cardápio e o valor à sua necessidade."

[[diferenciais]]
titulo = "Serviço completo"
texto = "Chegamos 1h antes para montar tudo e servimos durante 4h de evento."

[[diferenciais]]
titulo = "Transparência"
texto = "Preço por pessoa fechado, sem surpresa. Sinal de 50% para reservar a data, restante no fim do evento."

[pacotes_info]
introducao = "Quatro pacotes, do mais simples ao mais completo. As opções 2, 3 e 4 incluem churrasqueiro, carvão, descartáveis e utensílios; a opção 1 é só o serviço. Bebidas não estão inclusas em nenhum pacote."
legenda = "Valores por pessoa para 15 a 39 convidados; de 40 a 59, 5% de desconto; 60 ou mais, 10%. Grupos menores que 15: sob consulta. Válido para capital e Grande São Paulo; consulte taxa de deslocamento."
observacoes = [
  "Vegetarianos: espetinho de legumes, queijo coalho e abobrinha grelhada sob consulta.",
  "Crianças até 7 anos: 50% do valor.",
  "Porção: ~450 g de carne por adulto.",
  "Serviço de 5h (1h de montagem + 4h de evento). Sinal de 50% na reserva e 50% ao final do evento, via Pix.",
]
bebidas = "Quer bebidas inclusas? Os pacotes não contemplam bebidas, mas podemos incluir refrigerantes, água, cerveja ou drinks. Fale conosco pelo WhatsApp e ajustamos o valor por pessoa conforme a sua escolha."

# Cada [[pacotes]] é um pacote. Os [[pacotes.itens]] logo abaixo pertencem a ele.
[[pacotes]]
id = "senepol"
opcao = 1
nome = "Senepol"
resumo = "Só o serviço de churrasqueiro — você fornece as carnes."
prefixo_preco = "a partir de"
preco = "R$ 300"
unidade = "só o serviço"
rotulo_preco = "Valor"
detalhe_preco = ""
destaque = false
incluso = "Churrasqueiro e utensílios de manuseio (pegadores, facas, tábuas). Carvão e descartáveis podem ser incluídos mediante ajuste do valor."

[[pacotes.itens]]
rotulo = "O que fazemos"
texto = "Preparo, tempero, assar e servir as carnes fornecidas por você, com toda a técnica Brasamiga."

[[pacotes.itens]]
rotulo = "O que você fornece"
texto = "Carnes, acompanhamentos e estrutura do local (churrasqueira). Carvão e descartáveis ficam por sua conta, salvo se combinados conosco."

[[pacotes.itens]]
rotulo = "Ideal para"
texto = "Quem já tem tudo em casa e quer só a mão de obra especializada, ou eventos com cardápio próprio."

[[pacotes.itens]]
rotulo = "Como orçar"
texto = "Envie a data, o número de convidados e o cardápio pretendido pelo WhatsApp e retornamos o valor."

[[pacotes]]
id = "devon"
opcao = 2
nome = "Devon"
resumo = "O essencial bem feito, para grupos a partir de 15 pessoas."
prefixo_preco = ""
preco = "R$ 100"
unidade = "por pessoa · mín. 15"
rotulo_preco = "Por pessoa"
detalhe_preco = "mín. 15 pessoas"
destaque = false
incluso = "Churrasqueiro, carvão, descartáveis (pratos, talheres e guardanapos) e utensílios (rechaud, pegadores etc.). Alteração ou exclusão de itens: informe para ajuste do cardápio e do preço."

[[pacotes.itens]]
rotulo = "Entradas"
texto = "Pão de alho e queijo coalho com mel."

[[pacotes.itens]]
rotulo = "Carnes"
texto = "Chorizo e fraldinha na manteiga de ervas."

[[pacotes.itens]]
rotulo = "Carnes brancas"
texto = "Barriga, tulipa de frango e linguiça toscana."

[[pacotes.itens]]
rotulo = "Acompanhamentos"
texto = "Arroz branco e farofa com bacon."

[[pacotes.itens]]
rotulo = "Saladas"
texto = "Salada de folhas verdes e salada de maionese."

[[pacotes.itens]]
rotulo = "Molhos da casa"
texto = "Vinagrete, molho de alho e pimenta artesanal."

[[pacotes.itens]]
rotulo = "Sobremesa"
texto = "Abacaxi na brasa com açúcar e canela."

[[pacotes]]
id = "nelore"
opcao = 3
nome = "Nelore"
resumo = "Cortes nobres e mesa completa — o mais pedido."
prefixo_preco = ""
preco = "R$ 120"
unidade = "por pessoa · mín. 15"
rotulo_preco = "Por pessoa"
detalhe_preco = "mín. 15 pessoas · abaixo disso sob consulta"
destaque = true
incluso = "Churrasqueiro, carvão, descartáveis (pratos, talheres e guardanapos) e utensílios (rechaud, pegadores etc.). Alteração ou exclusão de itens: informe para ajuste do cardápio e do preço."

[[pacotes.itens]]
rotulo = "Entradas"
texto = "Choripan, pão de alho e queijo coalho com mel."

[[pacotes.itens]]
rotulo = "Carnes"
texto = "Ancho com crosta de alho e parmesão, fraldinha e picanha."

[[pacotes.itens]]
rotulo = "Carnes brancas"
texto = "Barriga com geleia de pimenta, tulipa de frango e linguiça cuiabana."

[[pacotes.itens]]
rotulo = "Acompanhamentos"
texto = "Farofa de bacon, feijão tropeiro e arroz branco."

[[pacotes.itens]]
rotulo = "Saladas"
texto = "Batata em conserva, salada verde e salada de maionese."

[[pacotes.itens]]
rotulo = "Molhos da casa"
texto = "Vinagrete, molho de alho, chimichurri e pimenta artesanal."

[[pacotes.itens]]
rotulo = "Sobremesa"
texto = "Abacaxi na brasa com açúcar e canela."

[[pacotes]]
id = "angus"
opcao = 4
nome = "Angus"
resumo = "A experiência completa, com wagyu, cordeiro e mesa farta."
prefixo_preco = ""
preco = "R$ 150"
unidade = "por pessoa · mín. 15"
rotulo_preco = "Por pessoa"
detalhe_preco = "mín. 15 pessoas · abaixo disso sob consulta"
destaque = false
incluso = "Churrasqueiro, carvão, descartáveis (pratos, talheres e guardanapos) e utensílios (rechaud, pegadores etc.)."

[[pacotes.itens]]
rotulo = "Entradas"
texto = "Choripan com queijo, queijo coalho com mel, pão de alho e provolone defumado."

[[pacotes.itens]]
rotulo = "Carnes"
texto = "Fraldinha, picanha no alho, flat iron wagyu e carré de cordeiro com molho de hortelã."

[[pacotes.itens]]
rotulo = "Carnes brancas"
texto = "Barriga com geleia, linguiça cuiabana ou de costela, linguiça toscana, coração marinado e tulipa de frango."

[[pacotes.itens]]
rotulo = "Acompanhamentos"
texto = "Arroz biro-biro, arroz branco, farofa de ovo com banana da terra e feijão tropeiro."

[[pacotes.itens]]
rotulo = "Saladas"
texto = "Salada verde, caponata, salada Caesar e salada de verão."

[[pacotes.itens]]
rotulo = "Molhos da casa"
texto = "Vinagrete, molho de alho, chimichurri e pimenta artesanal."

[[pacotes.itens]]
rotulo = "Sobremesa"
texto = "Abacaxi na brasa com açúcar e canela, banana na churrasqueira com doce de leite caseiro e sorvete."

# Tabela comparativa: um valor por pacote, na ordem Senepol, Devon, Nelore, Angus.
# "sim" vira o quadradinho vermelho de incluso; "—" significa não incluso.
[[comparativo]]
item = "Serviço de churrasqueiro"
valores = ["sim", "sim", "sim", "sim"]

[[comparativo]]
item = "Carnes vermelhas (~450 g/pessoa)"
valores = ["do cliente", "2 cortes", "3 cortes", "4 cortes"]

[[comparativo]]
item = "Carnes brancas e embutidos"
valores = ["do cliente", "3", "3", "5"]

[[comparativo]]
item = "Entradas"
valores = ["—", "2", "3", "4"]

[[comparativo]]
item = "Acompanhamentos"
valores = ["—", "2", "3", "4"]

[[comparativo]]
item = "Saladas"
valores = ["—", "2", "3", "4"]

[[comparativo]]
item = "Molhos da casa"
valores = ["—", "sim", "sim", "sim"]

[[comparativo]]
item = "Sobremesa"
valores = ["—", "1", "1", "2"]

[[comparativo]]
item = "Opção vegetariana / infantil"
valores = ["—", "sim", "sim", "sim"]

[[comparativo]]
item = "Carvão + descartáveis + utensílios"
valores = ["—", "sim", "sim", "sim"]

[[condicoes]]
titulo = "Serviço e horário"

[[condicoes.itens]]
rotulo = "Duração"
texto = "5 horas no total — chegamos 1h antes para montar e preparar, e servimos durante as 4h seguintes."

[[condicoes.itens]]
rotulo = "Hora extra"
texto = "após as 5h, caso precise estender, cobramos um acréscimo a combinar."

[[condicoes.itens]]
rotulo = "Bebidas"
texto = "não estão inclusas nos pacotes, mas podem ser adicionadas (refrigerante, água, cerveja, drinks) com ajuste do valor por pessoa."

[[condicoes]]
titulo = "Pagamento e reserva"

[[condicoes.itens]]
rotulo = "Reserva"
texto = "a data só é garantida com o pagamento do sinal (usado para reservar e realizar as compras)."

[[condicoes.itens]]
rotulo = "Forma"
texto = "50% de sinal na reserva + 50% ao final do evento, via Pix."

[[condicoes.itens]]
rotulo = "Ajustes"
texto = "alteração ou exclusão de itens do cardápio e confirmação do número final de convidados até 5 dias antes do evento; ajustamos menu e preço."

[[condicoes.itens]]
rotulo = "Faixas"
texto = "preço de tabela para 15 a 39 convidados; 40 a 59: 5% de desconto; 60 ou mais: 10%. Abaixo de 15: valor sob consulta."

[[faq]]
pergunta = "Qual região vocês atendem?"
resposta = "Capital e Grande São Paulo. Para outras cidades, consulte a taxa de deslocamento."

[[faq]]
pergunta = "Qual a quantidade de carne por pessoa?"
resposta = "Cerca de 450 g de carne crua por adulto, além de entradas, acompanhamentos e sobremesa."

[[faq]]
pergunta = "Têm opção para crianças ou vegetarianos?"
resposta = "Sim. Crianças até 7 anos pagam 50%; opções vegetarianas (espetinho de legumes, queijo coalho, abobrinha) sob consulta."

[[faq]]
pergunta = "E se meu evento tiver menos de 15 convidados?"
resposta = "Atendemos, com valor sob consulta — os custos fixos do evento pesam mais em grupos pequenos. Acima de 40 convidados o desconto é automático (5% de 40 a 59, 10% a partir de 60)."

[[faq]]
pergunta = "Posso cancelar ou remarcar?"
resposta = "Sim. Cancelando com mais de 15 dias, devolvemos 75% do sinal; de 8 a 15 dias, 50%; com 7 dias ou menos, 25% (as compras já foram feitas) — ou você converte 100% do sinal em crédito para remarcar em até 90 dias. Remarcação com 7+ dias de antecedência é gratuita, uma vez."

[orcamento]
titulo = "Vamos planejar o seu evento?"
texto = "Envie data, local e número de convidados e receba seu orçamento no mesmo dia."
```

- [ ] **Step 4: Implement `app/conteudo.py`**

```python
"""Lê o que o dono coloca em `conteudo/` e prepara versões leves das fotos."""

import hashlib
import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from app import midia

log = logging.getLogger(__name__)

PASTAS_PUBLICAS = ("logo", "cardapio")  # eventos-realizados nunca é servida direto (fotos têm GPS)


class ConteudoInvalido(RuntimeError):
    def __init__(self, arquivo: Path, linha: int | None, detalhe: str) -> None:
        self.arquivo, self.linha, self.detalhe = arquivo, linha, detalhe
        onde = f", linha {linha}" if linha else ""
        super().__init__(f"Problema em {arquivo.name}{onde}: {detalhe}")


def carregar_site(content_dir: Path) -> dict:
    caminho = content_dir / "site.toml"
    try:
        texto = caminho.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise ConteudoInvalido(caminho, None, "arquivo não encontrado") from None
    except UnicodeDecodeError:
        raise ConteudoInvalido(caminho, None, "salve o arquivo com a codificação UTF-8") from None
    try:
        return tomllib.loads(texto)
    except tomllib.TOMLDecodeError as erro:
        raise ConteudoInvalido(caminho, erro.lineno, erro.msg) from erro


@dataclass(frozen=True)
class ItemGaleria:
    tipo: str
    url: str
    url_miniatura: str


class Conteudo:
    def __init__(self, content_dir: Path, cache_dir: Path) -> None:
        self.content_dir = content_dir
        self.cache_dir = cache_dir

    def site(self) -> dict:
        return carregar_site(self.content_dir)

    def _arquivos(self, pasta: str) -> list[Path]:
        base = self.content_dir / pasta
        if not base.is_dir():
            return []
        visiveis = (p for p in base.iterdir() if p.is_file() and not p.name.startswith("."))
        return sorted(visiveis, key=lambda p: p.name.lower())

    @staticmethod
    def _chave(arquivo: Path) -> str:
        info = arquivo.stat()
        return hashlib.sha1(f"{arquivo.name}:{info.st_size}:{info.st_mtime_ns}".encode()).hexdigest()[:16]

    def _imagem(self, arquivo: Path) -> ItemGaleria | None:
        chave = self._chave(arquivo)
        pasta = self.cache_dir / "galeria"
        grande, mini = pasta / f"{chave}-grande.webp", pasta / f"{chave}-mini.webp"
        if not (grande.exists() and mini.exists()):
            try:
                pasta.mkdir(parents=True, exist_ok=True)
                grande.write_bytes(midia.otimizar_imagem(arquivo, midia.LADO_GRANDE))
                mini.write_bytes(midia.otimizar_imagem(arquivo, midia.LADO_MINIATURA))
            except (OSError, midia.MidiaInvalida) as erro:
                log.warning("Foto %s ignorada: %s", arquivo.name, erro)
                return None
        return ItemGaleria("imagem", f"/cache/galeria/{grande.name}", f"/cache/galeria/{mini.name}")

    def _video_web(self, arquivo: Path) -> Path:
        return self.cache_dir / "galeria" / f"{self._chave(arquivo)}.mp4"

    def galeria(self) -> list[ItemGaleria]:
        itens = []
        for arquivo in self._arquivos("eventos-realizados"):
            tipo = midia.tipo_por_extensao(arquivo.name)
            if tipo == "imagem":
                if item := self._imagem(arquivo):
                    itens.append(item)
            elif tipo == "video" and (web := self._video_web(arquivo)).exists():
                url = f"/cache/galeria/{web.name}"
                itens.append(ItemGaleria("video", url, url))
        return itens

    def preparar(self) -> dict:
        """Gera todas as versões web (fotos e vídeos). Roda no início do servidor e no build."""
        imagens = len([i for i in self.galeria() if i.tipo == "imagem"])
        videos = 0
        for arquivo in self._arquivos("eventos-realizados"):
            if midia.tipo_por_extensao(arquivo.name) != "video":
                continue
            destino = self._video_web(arquivo)
            if not destino.exists():
                destino.parent.mkdir(parents=True, exist_ok=True)
                if not midia.converter_video(arquivo, destino):
                    log.warning("Vídeo %s não convertido (ffmpeg ausente ou falhou)", arquivo.name)
                    continue
            videos += 1
        return {"imagens": imagens, "videos": videos}

    def logo_escuro(self, nome: str | None) -> str | None:
        if not nome:
            return None
        origem = self.content_dir / "logo" / Path(nome).name
        if not origem.is_file():
            return None
        destino = self.cache_dir / "logo" / f"{self._chave(origem)}.png"
        if not destino.exists():
            try:
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_bytes(midia.logo_para_fundo_escuro(origem))
            except (OSError, midia.MidiaInvalida) as erro:
                log.warning("Logo %s não preparado: %s", origem.name, erro)
                return None
        return f"/cache/logo/{destino.name}"

    def pdfs(self) -> list[dict]:
        return [
            {"url": f"/conteudo/cardapio/{quote(p.name)}", "nome": p.stem.replace("_", " ").replace("-", " ")}
            for p in self._arquivos("cardapio")
            if p.suffix.lower() == ".pdf"
        ]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_conteudo.py -q`
Expected: `7 passed`

- [ ] **Step 6: Commit**

```bash
git add app/conteudo.py tests/test_conteudo.py conteudo/site.toml
git commit -m "Passa o conteúdo da proposta comercial para o site.toml

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Public site routes, app factory and page template

**Files:**
- Create: `app/web.py`, `app/rotas_site.py`, `app/main.py`, `app/templates/base.html`, `app/templates/index.html`, `app/templates/erro_conteudo.html`, `tests/test_site.py`
- Create (empty placeholders so `/static` mounts; filled in Task 7): `app/static/css/site.css`, `app/static/js/site.js`

**Interfaces:**
- Consumes: `Settings`, `Database`, `criar_armazenamento`, `LocalStorage`, `Conteudo`, `ConteudoInvalido`, `PASTAS_PUBLICAS`, `whatsapp.link`, `whatsapp.mensagem_orcamento`, `whatsapp.MENSAGEM_PADRAO`.
- Produces:
  - `app.web.templates` (Jinja2Templates) with filters `data_br`, `dia`, `mes` (accept `date | str | None`), and `app.web.APP_DIR`.
  - `app.main.create_app(settings: Settings | None = None) -> FastAPI`; `app.state` has `settings`, `db`, `storage`, `conteudo`.
  - Routes `GET /`, `GET /healthz`, `POST /orcamento`; static mounts `/static`, `/cache`, `/uploads` (local storage only), `/conteudo/logo`, `/conteudo/cardapio`.
  - Until Task 8, `create_app` registers `app.rotas_admin.router` only if the module exists (temporary `try/except`).
  - CSS class names used by `index.html` (Task 7 styles them).

- [ ] **Step 1: Write the failing tests**

`tests/test_site.py`:

```python
from datetime import date
from urllib.parse import parse_qs, urlparse

from app.db import Database
from tests.fabrica import jpeg_bytes


def test_home_mostra_marca_pacotes_e_faq(client):
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    for texto in ("Churrasco para eventos", "Senepol", "Devon", "Nelore", "Angus",
                  "R$ 120", "Mais pedido", "Qual região vocês atendem?", "Pagamento e reserva"):
        assert texto in html, texto
    assert "https://wa.me/5511993433998" in html
    assert "/cache/logo/" in html


def test_healthz(client):
    assert client.get("/healthz").json() == {"ok": True}


def test_galeria_da_pasta_so_publica_versao_web(client, settings):
    (settings.content_dir / "eventos-realizados" / "IMG_0385.JPEG").write_bytes(jpeg_bytes(gps=True))
    html = client.get("/").text
    assert "/cache/galeria/" in html and "-mini.webp" in html
    arquivo = html.split('src="/cache/galeria/')[1].split('"')[0]
    assert client.get(f"/cache/galeria/{arquivo}").headers["content-type"] == "image/webp"
    assert client.get("/conteudo/eventos-realizados/IMG_0385.JPEG").status_code == 404
    assert client.get("/conteudo/site.toml").status_code == 404


def test_agenda_so_aparece_com_evento_futuro(client, settings):
    assert "Próximos eventos" not in client.get("/").text
    db = Database(settings.database_url)
    db.criar_evento("Formatura de Medicina", date(2099, 12, 12), "Campinas", "", "futuro")
    db.criar_evento("Já passou", date(2001, 1, 1), "", "", "futuro")
    html = client.get("/").text
    assert "Próximos eventos" in html and "Formatura de Medicina" in html
    assert "Já passou" not in html


def test_orcamento_salva_e_abre_whatsapp(client, settings):
    resp = client.post(
        "/orcamento",
        data={"nome": "Carla", "telefone": "11988887777", "data_evento": "2026-12-12",
              "local": "Moema", "convidados": "80", "pacote": "Nelore", "mensagem": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    destino = urlparse(resp.headers["location"])
    assert destino.netloc == "wa.me" and destino.path == "/5511993433998"
    texto = parse_qs(destino.query)["text"][0]
    assert "Sou Carla" in texto and "Pacote: Nelore." in texto and "Data: 12/12/2026." in texto
    salvo = Database(settings.database_url).listar_orcamentos()[0]
    assert (salvo["nome"], salvo["convidados"], salvo["pacote"]) == ("Carla", 80, "Nelore")


def test_orcamento_com_campos_estranhos_e_aceito(client, settings):
    resp = client.post(
        "/orcamento",
        data={"nome": "Carla", "telefone": "11988887777", "data_evento": "31/02",
              "convidados": "80 pessoas", "pacote": "Wagyu Supremo"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    salvo = Database(settings.database_url).listar_orcamentos()[0]
    assert (salvo["data_evento"], salvo["convidados"], salvo["pacote"]) == (None, None, "")


def test_orcamento_sem_telefone_volta_preenchido(client, settings):
    resp = client.post("/orcamento", data={"nome": "Carla", "local": "Moema"})
    assert resp.status_code == 400
    assert "Preencha seu nome e um WhatsApp" in resp.text
    assert 'value="Carla"' in resp.text and 'value="Moema"' in resp.text
    assert Database(settings.database_url).listar_orcamentos() == []


def test_orcamento_de_robo_e_descartado(client, settings):
    resp = client.post(
        "/orcamento", data={"nome": "Bot", "telefone": "1", "website": "http://spam"}, follow_redirects=False
    )
    assert resp.status_code == 303
    assert Database(settings.database_url).listar_orcamentos() == []


def test_site_toml_quebrado_mostra_linha(client, settings):
    (settings.content_dir / "site.toml").write_text('[marca]\nnome = "x\n', encoding="utf-8")
    resp = client.get("/")
    assert resp.status_code == 500
    assert "site.toml" in resp.text and "linha 2" in resp.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_site.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: Implement `app/web.py`**

```python
from datetime import date, datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates

APP_DIR = Path(__file__).resolve().parent
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

templates = Jinja2Templates(directory=APP_DIR / "templates")


def _data(valor: date | str | None) -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str) and valor:
        try:
            return date.fromisoformat(valor)
        except ValueError:
            return None
    return None


def data_br(valor: date | str | None) -> str:
    d = _data(valor)
    return d.strftime("%d/%m/%Y") if d else ""


def dia(valor: date | str | None) -> str:
    d = _data(valor)
    return f"{d.day:02d}" if d else ""


def mes(valor: date | str | None) -> str:
    d = _data(valor)
    return f"{MESES[d.month - 1]} {d.year}" if d else ""


templates.env.filters.update(data_br=data_br, dia=dia, mes=mes)
```

- [ ] **Step 4: Implement `app/rotas_site.py`**

```python
from datetime import date

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import whatsapp
from app.web import templates

router = APIRouter()

ERRO_CAMPOS = "Preencha seu nome e um WhatsApp para a gente conseguir responder."


def _data_ou_none(texto: str) -> date | None:
    try:
        return date.fromisoformat(texto) if texto else None
    except ValueError:
        return None


def _contexto(request: Request, form: dict | None = None, erro: str | None = None, enviado: bool = False) -> dict:
    estado = request.app.state
    site = estado.conteudo.site()
    realizados = estado.db.listar_eventos("realizado")
    futuros = estado.db.listar_eventos("futuro", a_partir_de=date.today())
    agrupadas = estado.db.midias_por_evento([e["id"] for e in realizados + futuros])
    for evento in realizados + futuros:
        evento["midias"] = [
            {
                **m,
                "url": estado.storage.url(m["chave"]),
                "url_miniatura": estado.storage.url(m["chave_miniatura"] or m["chave"]),
            }
            for m in agrupadas.get(evento["id"], [])
        ]
    numero = site.get("contato", {}).get("whatsapp", "")
    return {
        "site": site,
        "logo": estado.conteudo.logo_escuro(site.get("marca", {}).get("logo_escuro")),
        "galeria": estado.conteudo.galeria(),
        "pdfs": estado.conteudo.pdfs(),
        "realizados": realizados,
        "futuros": futuros,
        "whatsapp_url": whatsapp.link(numero, whatsapp.MENSAGEM_PADRAO) if numero else None,
        "form": form or {},
        "erro": erro,
        "enviado": enviado,
    }


@router.get("/", response_class=HTMLResponse)
def home(request: Request, enviado: bool = False):
    return templates.TemplateResponse(request, "index.html", _contexto(request, enviado=enviado))


@router.get("/healthz")
def healthz():
    return {"ok": True}


@router.post("/orcamento")
def pedir_orcamento(
    request: Request,
    nome: str = Form(""),
    telefone: str = Form(""),
    email: str = Form(""),
    data_evento: str = Form(""),
    local: str = Form(""),
    convidados: str = Form(""),
    pacote: str = Form(""),
    mensagem: str = Form(""),
    website: str = Form(""),  # campo-isca: só robôs preenchem
):
    if website:
        return RedirectResponse("/#orcamento", status_code=303)

    form = {
        "nome": nome.strip()[:200],
        "telefone": telefone.strip()[:40],
        "email": email.strip()[:200],
        "data_evento": data_evento.strip()[:10],
        "local": local.strip()[:200],
        "convidados": convidados.strip()[:6],
        "pacote": pacote.strip()[:50],
        "mensagem": mensagem.strip()[:2000],
    }
    if not form["nome"] or not form["telefone"]:
        contexto = _contexto(request, form=form, erro=ERRO_CAMPOS)
        return templates.TemplateResponse(request, "index.html", contexto, status_code=400)

    site = request.app.state.conteudo.site()
    nomes_pacotes = {p["nome"] for p in site.get("pacotes", [])}
    convidados_ok = form["convidados"].isdigit() and int(form["convidados"]) > 0
    dados = {
        "nome": form["nome"],
        "telefone": form["telefone"],
        "email": form["email"],
        "data_evento": _data_ou_none(form["data_evento"]),
        "local": form["local"],
        "convidados": int(form["convidados"]) if convidados_ok else None,
        "pacote": form["pacote"] if form["pacote"] in nomes_pacotes else "",
        "mensagem": form["mensagem"],
    }
    request.app.state.db.criar_orcamento(**dados)

    numero = site.get("contato", {}).get("whatsapp", "")
    if not numero:
        return RedirectResponse("/?enviado=1#orcamento", status_code=303)
    texto = whatsapp.mensagem_orcamento(
        dados["nome"], dados["pacote"], dados["data_evento"], dados["local"], dados["convidados"], dados["mensagem"]
    )
    return RedirectResponse(whatsapp.link(numero, texto), status_code=303)
```

- [ ] **Step 5: Implement `app/main.py`**

```python
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.config import Settings
from app.conteudo import PASTAS_PUBLICAS, Conteudo, ConteudoInvalido
from app.db import Database
from app.rotas_site import router as site_router
from app.storage import LocalStorage, criar_armazenamento
from app.web import APP_DIR, templates

log = logging.getLogger(__name__)


def _preparar_em_segundo_plano(conteudo: Conteudo) -> None:
    try:
        log.info("Galeria preparada: %s", conteudo.preparar())
    except Exception:
        log.exception("Falha ao preparar a galeria")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    db = Database(settings.database_url)
    storage = criar_armazenamento(settings)
    conteudo = Conteudo(settings.content_dir, settings.cache_dir)
    settings.cache_dir.mkdir(parents=True, exist_ok=True)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        threading.Thread(target=_preparar_em_segundo_plano, args=(conteudo,), daemon=True).start()
        yield

    app = FastAPI(title="Brasamiga", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.settings = settings
    app.state.db = db
    app.state.storage = storage
    app.state.conteudo = conteudo

    app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
    app.mount("/cache", StaticFiles(directory=settings.cache_dir), name="cache")
    if isinstance(storage, LocalStorage):
        app.mount("/uploads", StaticFiles(directory=storage.pasta), name="uploads")
    for pasta in PASTAS_PUBLICAS:
        caminho = settings.content_dir / pasta
        if caminho.is_dir():
            app.mount(f"/conteudo/{pasta}", StaticFiles(directory=caminho), name=f"conteudo-{pasta}")

    @app.exception_handler(ConteudoInvalido)
    async def conteudo_invalido(request: Request, erro: ConteudoInvalido):
        return templates.TemplateResponse(request, "erro_conteudo.html", {"erro": erro}, status_code=500)

    app.include_router(site_router)
    try:
        from app.rotas_admin import router as admin_router
    except ModuleNotFoundError:  # remover este try quando a Task 8 criar rotas_admin
        admin_router = None
    if admin_router:
        app.include_router(admin_router)
    return app
```

Note: the gallery is also prepared lazily on the first `GET /`, so tests (which don't run the lifespan) still get images.

- [ ] **Step 6: Create templates and empty static files**

`app/templates/base.html`:

```html
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block titulo %}Brasamiga · churrasco para eventos em São Paulo{% endblock %}</title>
  <meta name="description" content="{{ (site.marca.subtitulo if site and site.marca) or 'Churrasco para eventos' }}">
  <meta name="theme-color" content="#1C1512">
  {% if logo %}<link rel="icon" href="{{ logo }}">{% endif %}
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Anton&family=Lato:ital,wght@0,400;0,700;1,400&family=Oswald:wght@400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/static/css/site.css">
</head>
<body>
  {% block conteudo %}{% endblock %}
  {% block scripts %}{% endblock %}
</body>
</html>
```

`app/templates/erro_conteudo.html`:

```html
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Erro no conteúdo · Brasamiga</title>
  <style>
    body { margin: 0; padding: 2rem 1rem; background: #F3EBDF; color: #1E1A17; font: 1.05rem/1.6 system-ui, sans-serif; }
    main { max-width: 40rem; margin: 0 auto; border-left: 4px solid #A93226; padding-left: 1.25rem; }
    code { background: #EADFCE; padding: 0.1rem 0.35rem; border-radius: 0.25rem; }
  </style>
</head>
<body>
  <main>
    <h1>O site não carregou por causa do arquivo {{ erro.arquivo.name }}</h1>
    <p><strong>{% if erro.linha %}Na linha {{ erro.linha }}: {% endif %}{{ erro.detalhe }}.</strong></p>
    <p>Abra <code>{{ erro.arquivo }}</code>, corrija {% if erro.linha %}a linha {{ erro.linha }}{% else %}o arquivo{% endif %} e recarregue esta página. Os erros mais comuns são aspas sem fechar e colchetes faltando.</p>
  </main>
</body>
</html>
```

`app/templates/index.html`:

```html
{% extends "base.html" %}

{% macro midia(item, legenda) %}
  <button class="foto" type="button" data-src="{{ item.url }}" data-tipo="{{ item.tipo }}" aria-label="Ampliar: {{ legenda }}">
    {% if item.tipo == "video" %}
      <video src="{{ item.url }}#t=0.5" muted playsinline preload="metadata"></video>
      <span class="foto-play" aria-hidden="true"></span>
    {% else %}
      <img src="{{ item.url_miniatura }}" alt="{{ legenda }}" loading="lazy">
    {% endif %}
  </button>
{% endmacro %}

{% macro titulo_secao(texto, claro=false) %}
  <h2 class="titulo-secao{{ ' titulo-secao-claro' if claro }}">{{ texto }}</h2>
{% endmacro %}

{% block conteudo %}
{% set marca = site.marca or {} %}
{% set contato = site.contato or {} %}
{% set sobre = site.sobre or {} %}
{% set info = site.pacotes_info or {} %}
{% set pacotes = site.pacotes or [] %}
{% set tem_eventos = realizados or galeria %}

<header class="topo madeira">
  <a class="topo-marca" href="/">
    {% if logo %}<img src="{{ logo }}" alt="{{ marca.nome or 'Brasamiga' }}" width="120">{% else %}{{ marca.nome or "Brasamiga" }}{% endif %}
  </a>
  <nav aria-label="Seções">
    <ul class="topo-links">
      <li><a href="#pacotes">Pacotes</a></li>
      {% if tem_eventos %}<li><a href="#eventos">Eventos</a></li>{% endif %}
      <li><a href="#faq">Dúvidas</a></li>
      {% if whatsapp_url %}<li><a class="botao botao-brasa botao-pequeno" href="{{ whatsapp_url }}" target="_blank" rel="noopener">WhatsApp</a></li>{% endif %}
    </ul>
  </nav>
</header>

<section class="hero madeira" aria-labelledby="hero-titulo">
  <h1 id="hero-titulo" class="hero-logo">
    {% if logo %}<img src="{{ logo }}" alt="{{ marca.nome or 'Brasamiga' }}" width="560">{% else %}{{ marca.nome or "Brasamiga" }}{% endif %}
  </h1>
  <p class="hero-chamada">{{ marca.chamada }}</p>
  <span class="filete filete-centro" aria-hidden="true"></span>
  <p class="hero-subtitulo">{{ marca.subtitulo }}</p>
  <div class="hero-acoes">
    <a class="botao botao-brasa" href="#orcamento">Pedir orçamento</a>
    {% if whatsapp_url %}<a class="botao botao-contorno" href="{{ whatsapp_url }}" target="_blank" rel="noopener">Chamar no WhatsApp</a>{% endif %}
  </div>
</section>

<main>
  <section id="sobre" class="secao papel">
    <div class="limite sobre">
      <div class="sobre-texto">
        <h2 class="titulo-grande"><span class="vermelho">{{ sobre.titulo_destaque }}</span> {{ sobre.titulo }}</h2>
        {% for p in sobre.paragrafos or [] %}<p>{{ p }}</p>{% endfor %}
      </div>
      {% if site.numeros %}
      <dl class="caixa-escura numeros">
        {% for n in site.numeros %}
          <div><dt>{{ n.valor }}</dt><dd>{{ n.legenda }}</dd></div>
        {% endfor %}
      </dl>
      {% endif %}
    </div>

    {% if site.diferenciais %}
    <div class="limite diferenciais">
      {{ titulo_secao("Por que escolher a " ~ (marca.nome or "Brasamiga")) }}
      <ul class="lista-diferenciais">
        {% for d in site.diferenciais %}
          <li><h3 class="rotulo-oswald">{{ d.titulo }}</h3><p>{{ d.texto }}</p></li>
        {% endfor %}
      </ul>
    </div>
    {% endif %}
  </section>

  {% if pacotes %}
  <section id="pacotes" class="secao papel pacotes"{% if logo %} style="--logo: url('{{ logo }}')"{% endif %}>
    <div class="limite">
      {{ titulo_secao("Nossos pacotes") }}
      {% if info.introducao %}<p class="introducao">{{ info.introducao }}</p>{% endif %}

      {% if site.comparativo %}
      <div class="comparativo-rolagem">
        <table class="comparativo">
          <caption class="sr-only">Comparativo dos pacotes</caption>
          <thead>
            <tr>
              <td></td>
              {% for p in pacotes %}
                <th scope="col">
                  <span class="comp-nome">{{ p.nome }}</span>
                  <span class="comp-preco{{ ' comp-preco-cobre' if p.prefixo_preco }}">{% if p.prefixo_preco %}{{ p.prefixo_preco }} {% endif %}{{ p.preco }}</span>
                  <span class="comp-unidade">{{ p.unidade }}</span>
                </th>
              {% endfor %}
            </tr>
          </thead>
          <tbody>
            {% for linha in site.comparativo %}
              <tr>
                <th scope="row">{{ linha.item }}</th>
                {% for valor in linha.valores %}
                  <td>
                    {% if valor == "sim" %}<span class="incluso" role="img" aria-label="Incluso"></span>
                    {% elif valor == "—" %}<span class="nao-incluso" aria-label="Não incluso">—</span>
                    {% else %}{{ valor }}{% endif %}
                  </td>
                {% endfor %}
              </tr>
            {% endfor %}
          </tbody>
          <tfoot>
            <tr>
              <td></td>
              {% for p in pacotes %}<td>{% if p.destaque %}<span class="selo">Mais pedido</span>{% endif %}</td>{% endfor %}
            </tr>
          </tfoot>
        </table>
      </div>
      {% endif %}
      {% if info.legenda %}<p class="legenda">{{ info.legenda }}</p>{% endif %}

      <div class="lista-pacotes">
        {% for p in pacotes %}
          <article class="pacote{{ ' pacote-destaque' if p.destaque }}" id="pacote-{{ p.id }}">
            <header class="pacote-cabeca">
              <div>
                <p class="pacote-opcao">Opção {{ p.opcao }}</p>
                <h3 class="pacote-nome">{{ p.nome }}</h3>
                <p class="pacote-resumo">{{ p.resumo }}</p>
              </div>
              <div class="caixa-escura pacote-preco">
                <span class="pacote-preco-rotulo">{{ p.rotulo_preco }}</span>
                <strong>{% if p.prefixo_preco %}{{ p.prefixo_preco }} {% endif %}{{ p.preco }}</strong>
                {% if p.detalhe_preco %}<span class="pacote-preco-detalhe">{{ p.detalhe_preco }}</span>{% endif %}
              </div>
            </header>
            {% if p.destaque %}<span class="selo">Mais pedido</span>{% endif %}
            <details class="pacote-detalhes"{% if p.destaque %} open{% endif %}>
              <summary>Ver o que está incluso</summary>
              <dl class="pacote-itens">
                {% for i in p.itens or [] %}
                  <div><dt>{{ i.rotulo }}</dt><dd>{{ i.texto }}</dd></div>
                {% endfor %}
              </dl>
              {% if p.incluso %}
                <div class="caixa-incluso">
                  <p class="rotulo-oswald">Incluso no pacote</p>
                  <p>{{ p.incluso }}</p>
                </div>
              {% endif %}
            </details>
            <a class="botao botao-brasa" href="#orcamento" data-pacote="{{ p.nome }}">Pedir orçamento do {{ p.nome }}</a>
          </article>
        {% endfor %}
      </div>

      {% if info.observacoes %}
        <ul class="lista-quadrada observacoes">
          {% for o in info.observacoes %}<li>{{ o }}</li>{% endfor %}
        </ul>
      {% endif %}
      {% if info.bebidas %}
        <blockquote class="caixa-escura citacao"><p>{{ info.bebidas }}</p></blockquote>
      {% endif %}
      {% if pdfs %}
        <p class="pdfs">
          {% for pdf in pdfs %}<a class="botao botao-escuro" href="{{ pdf.url }}" target="_blank" rel="noopener">Baixar a proposta completa (PDF)</a>{% endfor %}
        </p>
      {% endif %}
    </div>
  </section>
  {% endif %}

  {% if tem_eventos %}
  <section id="eventos" class="secao madeira">
    <div class="limite">
      {{ titulo_secao("Eventos realizados", claro=true) }}
      <p class="introducao introducao-clara">Fotos e vídeos de festas servidas pela nossa equipe.</p>

      {% for e in realizados %}
        <article class="evento">
          <h3 class="evento-titulo">{{ e.titulo }}</h3>
          <p class="evento-meta">
            {% if e.data %}<time datetime="{{ e.data }}">{{ e.data | data_br }}</time>{% endif %}{% if e.data and e.local %}, {% endif %}{{ e.local }}
          </p>
          {% if e.descricao %}<p class="evento-descricao">{{ e.descricao }}</p>{% endif %}
          {% if e.midias %}
            <div class="galeria">{% for m in e.midias %}{{ midia(m, e.titulo) }}{% endfor %}</div>
          {% endif %}
        </article>
      {% endfor %}

      {% if galeria %}
        <div class="galeria">{% for m in galeria %}{{ midia(m, "Evento servido pela " ~ (marca.nome or "Brasamiga")) }}{% endfor %}</div>
      {% endif %}
    </div>
  </section>
  {% endif %}

  {% if futuros %}
  <section id="agenda" class="secao papel">
    <div class="limite">
      {{ titulo_secao("Próximos eventos") }}
      <ul class="agenda">
        {% for e in futuros %}
          <li class="agenda-item">
            <div class="caixa-escura agenda-data">
              {% if e.data %}
                <time datetime="{{ e.data }}"><span class="agenda-dia">{{ e.data | dia }}</span><span class="agenda-mes">{{ e.data | mes }}</span></time>
              {% else %}
                <span class="agenda-mes">Data a confirmar</span>
              {% endif %}
            </div>
            <div>
              <h3 class="evento-titulo evento-titulo-escuro">{{ e.titulo }}</h3>
              {% if e.local %}<p class="agenda-local">{{ e.local }}</p>{% endif %}
              {% if e.descricao %}<p>{{ e.descricao }}</p>{% endif %}
              {% if e.midias %}<div class="galeria galeria-compacta">{% for m in e.midias %}{{ midia(m, e.titulo) }}{% endfor %}</div>{% endif %}
            </div>
          </li>
        {% endfor %}
      </ul>
    </div>
  </section>
  {% endif %}

  <section id="faq" class="secao papel">
    <div class="limite condicoes">
      {% for c in site.condicoes or [] %}
        <div class="condicao">
          {{ titulo_secao(c.titulo) }}
          <ul class="lista-quadrada">
            {% for i in c.itens or [] %}<li><strong>{{ i.rotulo }}:</strong> {{ i.texto }}</li>{% endfor %}
          </ul>
        </div>
      {% endfor %}
    </div>
    {% if site.faq %}
    <div class="limite">
      {{ titulo_secao("Perguntas frequentes") }}
      <div class="faq">
        {% for f in site.faq %}
          <details class="faq-item">
            <summary>{{ f.pergunta }}</summary>
            <p>{{ f.resposta }}</p>
          </details>
        {% endfor %}
      </div>
    </div>
    {% endif %}
  </section>

  <section id="orcamento" class="secao madeira orcamento">
    <div class="limite orcamento-grade">
      <div class="orcamento-texto">
        <h2 class="titulo-grande titulo-claro">{{ (site.orcamento or {}).titulo or "Vamos planejar o seu evento?" }}</h2>
        <p class="orcamento-sub">{{ (site.orcamento or {}).texto }}</p>
        <p class="orcamento-contato">
          {% if whatsapp_url %}<a href="{{ whatsapp_url }}" target="_blank" rel="noopener">WhatsApp {{ contato.whatsapp_exibicao }}</a>{% endif %}
          {% if contato.instagram %}<a class="cobre" href="https://instagram.com/{{ contato.instagram }}" target="_blank" rel="noopener">Instagram @{{ contato.instagram }}</a>{% endif %}
        </p>
      </div>

      <form class="formulario" method="post" action="/orcamento#orcamento" novalidate>
        {% if enviado %}
          <p class="aviso aviso-ok" role="status">Recebemos seu pedido de orçamento. Vamos responder pelo WhatsApp informado.</p>
        {% elif erro %}
          <p class="aviso aviso-erro" role="alert">{{ erro }}</p>
        {% endif %}
        <div class="campo">
          <label for="nome">Seu nome</label>
          <input id="nome" name="nome" autocomplete="name" required maxlength="200" value="{{ form.nome }}">
        </div>
        <div class="campo">
          <label for="telefone">WhatsApp</label>
          <input id="telefone" name="telefone" type="tel" autocomplete="tel" required maxlength="40" value="{{ form.telefone }}" placeholder="(11) 90000-0000">
        </div>
        <div class="campo-duplo">
          <div class="campo">
            <label for="data_evento">Data do evento</label>
            <input id="data_evento" name="data_evento" type="date" value="{{ form.data_evento }}">
          </div>
          <div class="campo">
            <label for="convidados">Convidados</label>
            <input id="convidados" name="convidados" type="number" min="1" inputmode="numeric" value="{{ form.convidados }}">
          </div>
        </div>
        <div class="campo">
          <label for="local">Local ou bairro</label>
          <input id="local" name="local" maxlength="200" value="{{ form.local }}" placeholder="Ex.: Moema, São Paulo">
        </div>
        <div class="campo">
          <label for="pacote">Pacote</label>
          <select id="pacote" name="pacote">
            <option value="">Ainda não sei</option>
            {% for p in pacotes %}<option value="{{ p.nome }}"{% if form.pacote == p.nome %} selected{% endif %}>{{ p.nome }} · {% if p.prefixo_preco %}{{ p.prefixo_preco }} {% endif %}{{ p.preco }}</option>{% endfor %}
          </select>
        </div>
        <div class="campo">
          <label for="email">E-mail <span class="opcional">(opcional)</span></label>
          <input id="email" name="email" type="email" autocomplete="email" maxlength="200" value="{{ form.email }}">
        </div>
        <div class="campo">
          <label for="mensagem">Algo mais que a gente deva saber? <span class="opcional">(opcional)</span></label>
          <textarea id="mensagem" name="mensagem" rows="3" maxlength="2000">{{ form.mensagem }}</textarea>
        </div>
        <div class="isca" aria-hidden="true">
          <label for="website">Não preencha</label>
          <input id="website" name="website" tabindex="-1" autocomplete="off">
        </div>
        <button class="botao botao-brasa" type="submit">Pedir orçamento pelo WhatsApp</button>
        <p class="nota">Seu pedido fica registrado com a gente e o WhatsApp abre com a mensagem pronta para enviar.</p>
      </form>
    </div>
  </section>
</main>

<footer class="rodape">
  {% if contato.instagram %}<a href="https://instagram.com/{{ contato.instagram }}" target="_blank" rel="noopener">Instagram @{{ contato.instagram }}</a>{% endif %}
  <span class="rodape-marca">{{ marca.nome or "Brasamiga" }}</span>
  {% if whatsapp_url %}<a href="{{ whatsapp_url }}" target="_blank" rel="noopener">WhatsApp {{ contato.whatsapp_exibicao }}</a>{% endif %}
</footer>

{% if whatsapp_url %}
  <a class="whatsapp-flutuante" href="{{ whatsapp_url }}" target="_blank" rel="noopener">WhatsApp</a>
{% endif %}

<dialog class="visor" id="visor" aria-label="Foto ampliada">
  <button class="visor-fechar" type="button" aria-label="Fechar">×</button>
  <div class="visor-conteudo"></div>
</dialog>
{% endblock %}

{% block scripts %}<script src="/static/js/site.js" defer></script>{% endblock %}
```

Empty static files (filled in Task 7):

```bash
mkdir -p app/static/css app/static/js && : > app/static/css/site.css && : > app/static/js/site.js
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest -q`
Expected: all tests pass (`tests/test_site.py`: `9 passed`).

- [ ] **Step 8: Commit**

```bash
git add app/web.py app/rotas_site.py app/main.py app/templates app/static tests/test_site.py
git commit -m "Monta a landing com pacotes, galeria, FAQ e orçamento pelo WhatsApp

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Visual identity (CSS + JS) and visual review

**Files:**
- Fill: `app/static/css/site.css`, `app/static/js/site.js`

**Interfaces:**
- Consumes: class names from `app/templates/index.html` (Task 6).
- Produces: no Python interfaces.

- [ ] **Step 1: Write `app/static/css/site.css`**

```css
/* Brasamiga: identidade da Proposta Comercial 2026 (madeira escura, papel, vermelho-brasa, cobre). */
:root {
  --madeira: #1C1512;
  --madeira-clara: #2A201B;
  --papel: #F3EBDF;
  --papel-escuro: #EADFCE;
  --brasa: #A93226;
  --brasa-hover: #C03A2C;
  --cobre: #B8966A;
  --tinta: #1E1A17;
  --tinta-suave: #5C524B;
  --linha: #D9CBB8;

  --titulo: "Anton", Impact, "Arial Narrow", sans-serif;
  --rotulo: "Oswald", "Arial Narrow", sans-serif;
  --texto: "Lato", system-ui, sans-serif;

  --limite: 70rem;
  --gutter: clamp(1rem, 4vw, 2.5rem);
  --raio: 0.75rem;
}

*, *::before, *::after { box-sizing: border-box; }
html { scroll-behavior: smooth; scroll-padding-top: 5rem; }
@media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }

body {
  margin: 0;
  background: var(--papel);
  color: var(--tinta);
  font: 400 1.0625rem/1.6 var(--texto);
  -webkit-font-smoothing: antialiased;
}
img, video { display: block; max-width: 100%; }
h1, h2, h3, p { margin: 0; }
a { color: inherit; }
:focus-visible { outline: 3px solid var(--cobre); outline-offset: 3px; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }

.limite { width: 100%; max-width: var(--limite); margin: 0 auto; padding: 0 var(--gutter); }
.secao { padding: clamp(3.5rem, 8vw, 6rem) 0; }
.papel { background: var(--papel); }

/* Madeira escura com fumaça vermelha, como as capas do PDF */
.madeira {
  background-color: var(--madeira);
  background-image:
    radial-gradient(55% 45% at 12% 18%, rgb(150 24 24 / 0.22), transparent 70%),
    radial-gradient(45% 40% at 88% 80%, rgb(150 24 24 / 0.18), transparent 70%),
    repeating-linear-gradient(90deg, transparent 0 118px, rgb(0 0 0 / 0.28) 118px 120px),
    repeating-linear-gradient(90deg, rgb(255 255 255 / 0.015) 0 3px, transparent 3px 11px);
  color: var(--papel);
}

/* Tipografia de marca */
.titulo-secao {
  font: 400 clamp(1.75rem, 3.6vw, 2.5rem)/1.1 var(--titulo);
  text-transform: uppercase;
  letter-spacing: 0.01em;
  color: var(--tinta);
}
.titulo-secao::after {
  content: "";
  display: block;
  width: 3.5rem;
  height: 4px;
  margin: 0.6rem 0 1.5rem;
  background: var(--brasa);
}
.titulo-secao-claro { color: var(--papel); }
.titulo-grande { font: 400 clamp(2.25rem, 5.5vw, 3.75rem)/1.05 var(--titulo); color: var(--tinta); }
.titulo-claro { color: var(--papel); text-transform: uppercase; }
.vermelho { color: var(--brasa); }
.cobre { color: var(--cobre); }
.rotulo-oswald { font: 500 1.15rem/1.2 var(--rotulo); text-transform: uppercase; letter-spacing: 0.01em; }
.introducao { max-width: 46rem; margin-bottom: 2rem; }
.introducao-clara { color: var(--cobre); }
.filete { display: block; width: 7rem; height: 4px; background: var(--brasa); }
.filete-centro { margin: 1.25rem auto; }

/* Botões */
.botao {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 3rem;
  padding: 0.7rem 1.5rem;
  border: 2px solid transparent;
  border-radius: 999px;
  font: 500 1rem/1 var(--rotulo);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  text-decoration: none;
  cursor: pointer;
  transition: background-color 0.15s, border-color 0.15s;
}
.botao-brasa { background: var(--brasa); color: #fff; }
.botao-brasa:hover { background: var(--brasa-hover); }
.botao-contorno { border-color: rgb(243 235 223 / 0.6); color: var(--papel); }
.botao-contorno:hover { border-color: var(--papel); }
.botao-escuro { background: var(--madeira); color: var(--papel); }
.botao-pequeno { min-height: 2.4rem; padding: 0.5rem 1rem; font-size: 0.9rem; }

/* Topo */
.topo {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.6rem var(--gutter);
  border-bottom: 6px solid var(--brasa);
}
.topo-marca img { width: auto; height: 3.25rem; }
.topo-marca { font: 400 1.5rem/1 var(--titulo); text-decoration: none; }
.topo-links { display: flex; align-items: center; gap: 0.25rem 1.5rem; margin: 0; padding: 0; list-style: none; }
.topo-links a:not(.botao) { font: 400 1rem/1 var(--rotulo); text-transform: uppercase; letter-spacing: 0.06em; text-decoration: none; color: var(--papel); }
.topo-links a:not(.botao):hover { color: var(--cobre); }

/* Hero */
.hero { padding: clamp(3rem, 9vw, 6.5rem) var(--gutter) clamp(3.5rem, 9vw, 6rem); text-align: center; }
.hero-logo img { width: min(36rem, 88vw); height: auto; margin: 0 auto; }
.hero-logo { font: 400 clamp(3rem, 12vw, 7rem)/1 var(--titulo); }
.hero-chamada { margin-top: 2rem; font: 400 clamp(1.1rem, 2.6vw, 1.6rem)/1.2 var(--rotulo); text-transform: uppercase; letter-spacing: 0.3em; }
.hero-subtitulo { color: var(--cobre); font-size: clamp(1rem, 1.8vw, 1.15rem); }
.hero-acoes { display: flex; flex-wrap: wrap; justify-content: center; gap: 0.75rem; margin-top: 2.25rem; }
@media (prefers-reduced-motion: no-preference) {
  .hero-logo, .hero-chamada, .hero .filete, .hero-subtitulo, .hero-acoes { animation: surgir 0.8s ease-out both; }
  .hero-chamada { animation-delay: 0.15s; }
  .hero .filete, .hero-subtitulo { animation-delay: 0.3s; }
  .hero-acoes { animation-delay: 0.45s; }
}
@keyframes surgir { from { opacity: 0; transform: translateY(0.75rem); } }

/* Quem somos */
.sobre { display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(14rem, 1fr); gap: clamp(2rem, 5vw, 4rem); align-items: start; }
.sobre-texto p { margin-top: 1rem; max-width: 40rem; }
.sobre-texto h2 { margin-bottom: 1.5rem; }
.caixa-escura { background: var(--madeira); color: var(--papel); border-top: 6px solid var(--brasa); border-radius: 0 0 var(--raio) var(--raio); }
.numeros { display: grid; gap: 1.5rem; margin: 0; padding: 1.75rem 1.5rem; text-align: center; }
.numeros dt { font: 400 2.75rem/1 var(--titulo); }
.numeros dd { margin: 0.35rem 0 0; color: var(--cobre); font-size: 0.95rem; }

.diferenciais { margin-top: clamp(3rem, 6vw, 4.5rem); padding-top: clamp(2rem, 4vw, 3rem); border-top: 1px solid var(--linha); }
.lista-diferenciais { display: grid; grid-template-columns: repeat(auto-fit, minmax(17rem, 1fr)); gap: 2rem 3rem; margin: 0; padding: 0; list-style: none; }
.lista-diferenciais li { padding-left: 1rem; border-left: 4px solid var(--brasa); }
.lista-diferenciais p { margin-top: 0.35rem; }

/* Pacotes */
.pacotes { position: relative; overflow: hidden; }
.pacotes::after {
  content: "";
  position: absolute;
  right: -4rem;
  bottom: -2rem;
  width: 28rem;
  height: 20rem;
  background: var(--logo) no-repeat center / contain;
  filter: invert(1);
  opacity: 0.05;
  pointer-events: none;
}
.pacotes .limite { position: relative; z-index: 1; }

.comparativo-rolagem { overflow-x: auto; }
.comparativo { width: 100%; min-width: 44rem; border-collapse: separate; border-spacing: 0; font-size: 1rem; }
.comparativo thead th, .comparativo thead td { background: var(--madeira); color: var(--papel); padding: 1rem 0.75rem; }
.comparativo thead td { border-radius: var(--raio) 0 0 0; }
.comparativo thead th:last-child { border-radius: 0 var(--raio) 0 0; }
.comparativo thead th { text-align: center; vertical-align: top; }
.comp-nome { display: block; font: 400 1.6rem/1.1 var(--titulo); text-transform: uppercase; }
.comp-preco { display: block; margin-top: 0.3rem; font: 400 1.2rem/1.2 var(--rotulo); color: #D9564A; }
.comp-preco-cobre { color: var(--cobre); font-size: 1rem; }
.comp-unidade { display: block; margin-top: 0.2rem; color: var(--cobre); font-size: 0.8rem; }
.comparativo tbody tr:nth-child(odd) { background: var(--papel-escuro); }
.comparativo tbody th { padding: 0.8rem 1rem; text-align: left; font-weight: 700; }
.comparativo tbody td { padding: 0.8rem 0.75rem; text-align: center; }
.comparativo tfoot td { padding-top: 0.75rem; text-align: center; }
.incluso { display: inline-block; width: 0.85rem; height: 0.85rem; background: var(--brasa); }
.nao-incluso { color: var(--tinta-suave); }
.selo { display: inline-block; padding: 0.3rem 1rem; border-radius: 999px; background: var(--brasa); color: #fff; font: 500 0.8rem/1.2 var(--rotulo); text-transform: uppercase; letter-spacing: 0.04em; }
.legenda { margin-top: 1.25rem; max-width: 52rem; color: var(--tinta-suave); font-size: 0.92rem; font-style: italic; }

.lista-pacotes { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 30rem), 1fr)); gap: 1.5rem; margin-top: clamp(2.5rem, 5vw, 3.5rem); }
.pacote { display: flex; flex-direction: column; gap: 1rem; padding: clamp(1.25rem, 3vw, 2rem); background: #fff8ef; border: 1px solid var(--linha); border-radius: var(--raio); }
.pacote-destaque { border: 2px solid var(--brasa); }
.pacote-cabeca { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 1rem; }
.pacote-opcao { color: var(--brasa); font: 400 1.05rem/1 var(--rotulo); text-transform: uppercase; }
.pacote-nome { margin-top: 0.2rem; font: 400 clamp(2.5rem, 5vw, 3.25rem)/1 var(--titulo); text-transform: uppercase; }
.pacote-resumo { margin-top: 0.4rem; color: var(--tinta-suave); font-style: italic; max-width: 24rem; }
.pacote-preco { display: flex; flex-direction: column; align-items: center; justify-content: center; min-width: 11rem; padding: 0.9rem 1.25rem; text-align: center; align-self: start; }
.pacote-preco-rotulo { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; }
.pacote-preco strong { font: 400 1.9rem/1.1 var(--titulo); text-transform: uppercase; }
.pacote-preco-detalhe { color: var(--cobre); font-size: 0.78rem; }
.pacote .selo { align-self: flex-start; }
.pacote .botao { align-self: flex-start; margin-top: auto; }

.pacote-detalhes summary { cursor: pointer; font: 500 1rem/1.4 var(--rotulo); text-transform: uppercase; color: var(--brasa); letter-spacing: 0.03em; }
.pacote-detalhes summary:hover { text-decoration: underline; }
.pacote-itens { margin: 1rem 0 0; }
.pacote-itens div { display: grid; grid-template-columns: 10.5rem 1fr; gap: 1rem; padding: 0.6rem 0; border-bottom: 1px solid var(--linha); }
.pacote-itens dt { color: var(--brasa); font: 400 1rem/1.4 var(--rotulo); text-transform: uppercase; }
.pacote-itens dd { margin: 0; }
.caixa-incluso { margin-top: 1rem; padding: 0.9rem 1.1rem; background: var(--papel-escuro); border-left: 4px solid var(--brasa); border-radius: 0 var(--raio) var(--raio) 0; }
.caixa-incluso p + p { margin-top: 0.3rem; }

.lista-quadrada { margin: 0; padding: 0; list-style: none; }
.lista-quadrada li { position: relative; padding-left: 1.4rem; margin-top: 0.6rem; }
.lista-quadrada li::before { content: ""; position: absolute; left: 0; top: 0.55em; width: 0.55rem; height: 0.55rem; background: var(--brasa); }
.observacoes { margin-top: 2.5rem; max-width: 52rem; }
.citacao { position: relative; margin: 2rem 0 0; padding: 1.25rem 1.5rem 1.25rem 4rem; border-top: 0; border-radius: var(--raio); max-width: 52rem; }
.citacao::before { content: "“"; position: absolute; left: 1.25rem; top: 0.4rem; font: 400 3.5rem/1 var(--titulo); color: var(--brasa); }
.pdfs { margin-top: 2rem; }

/* Eventos */
.evento + .evento, .evento + .galeria { margin-top: 3rem; }
.evento-titulo { font: 400 1.6rem/1.15 var(--titulo); text-transform: uppercase; color: var(--papel); }
.evento-titulo-escuro { color: var(--tinta); }
.evento-meta { color: var(--cobre); margin-top: 0.25rem; }
.evento-descricao { max-width: 46rem; margin-top: 0.5rem; }
.galeria { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 14rem), 1fr)); gap: 0.6rem; margin-top: 1.25rem; }
.galeria-compacta { grid-template-columns: repeat(auto-fill, minmax(8rem, 1fr)); }
.foto { position: relative; display: block; aspect-ratio: 4 / 5; padding: 0; border: 0; border-radius: 0.5rem; overflow: hidden; background: var(--madeira-clara); cursor: zoom-in; }
.foto img, .foto video { width: 100%; height: 100%; object-fit: cover; }
.foto:hover img { filter: brightness(1.08); }
.foto-play { position: absolute; inset: 50% auto auto 50%; width: 3.5rem; height: 3.5rem; translate: -50% -50%; border-radius: 50%; background: rgb(169 50 38 / 0.9); }
.foto-play::after { content: ""; position: absolute; inset: 50% auto auto 55%; translate: -50% -50%; border-style: solid; border-width: 0.6rem 0 0.6rem 1rem; border-color: transparent transparent transparent #fff; }

/* Agenda */
.agenda { margin: 0; padding: 0; list-style: none; }
.agenda-item { display: grid; grid-template-columns: 8rem 1fr; gap: 1.5rem; padding: 1.5rem 0; border-bottom: 1px solid var(--linha); }
.agenda-data { padding: 0.9rem 0.5rem; text-align: center; align-self: start; }
.agenda-data time { display: flex; flex-direction: column; }
.agenda-dia { font: 400 2.75rem/1 var(--titulo); }
.agenda-mes { color: var(--cobre); font: 400 0.95rem/1.3 var(--rotulo); text-transform: uppercase; }
.agenda-local { color: var(--brasa); font-weight: 700; margin-top: 0.2rem; }
.agenda-item p + p { margin-top: 0.4rem; }

/* Condições e FAQ */
.condicoes { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 26rem), 1fr)); gap: 1rem 3rem; margin-bottom: clamp(2.5rem, 5vw, 3.5rem); }
.faq { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 26rem), 1fr)); gap: 0 3rem; }
.faq-item { border-bottom: 1px solid var(--linha); padding: 0.9rem 0; }
.faq-item summary { cursor: pointer; font: 500 1.1rem/1.35 var(--rotulo); }
.faq-item summary:hover { color: var(--brasa); }
.faq-item p { margin-top: 0.5rem; color: var(--tinta-suave); }

/* Orçamento */
.orcamento-grade { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.05fr); gap: clamp(2rem, 6vw, 4.5rem); align-items: start; }
.orcamento-sub { margin-top: 1rem; color: var(--cobre); max-width: 30rem; }
.orcamento-contato { display: flex; flex-direction: column; gap: 0.4rem; margin-top: 2rem; font: 400 1.25rem/1.3 var(--rotulo); text-transform: uppercase; }
.orcamento-contato a { text-decoration: none; }
.orcamento-contato a:hover { text-decoration: underline; }

.formulario { display: grid; gap: 1rem; padding: clamp(1.25rem, 3vw, 2rem); background: var(--papel); color: var(--tinta); border-radius: var(--raio); }
.campo { display: grid; gap: 0.3rem; }
.campo-duplo { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.campo label { font: 500 0.95rem/1.3 var(--rotulo); text-transform: uppercase; letter-spacing: 0.02em; }
.opcional { font: 400 0.85rem var(--texto); text-transform: none; color: var(--tinta-suave); }
.campo input, .campo select, .campo textarea {
  width: 100%;
  padding: 0.7rem 0.85rem;
  border: 1.5px solid #C4B39C;
  border-radius: 0.5rem;
  background: #fff;
  color: var(--tinta);
  font: inherit;
}
.campo input:focus, .campo select:focus, .campo textarea:focus { border-color: var(--brasa); outline: 2px solid rgb(169 50 38 / 0.25); outline-offset: 0; }
.formulario .botao { justify-self: stretch; }
.nota { color: var(--tinta-suave); font-size: 0.85rem; }
.isca { position: absolute; left: -9999px; width: 1px; height: 1px; overflow: hidden; }
.aviso { padding: 0.8rem 1rem; border-radius: 0.5rem; font-weight: 700; }
.aviso-ok { background: #E4EBDB; color: #2F4220; border-left: 4px solid #56703D; }
.aviso-erro { background: #F6DCD6; color: #6B1D14; border-left: 4px solid var(--brasa); }

/* Rodapé */
.rodape {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem 2rem;
  padding: 1.25rem var(--gutter);
  background: var(--madeira);
  color: var(--papel);
  border-top: 6px solid var(--brasa);
  font: 400 1rem/1.3 var(--rotulo);
}
.rodape a { text-decoration: none; }
.rodape a:hover { text-decoration: underline; }
.rodape-marca { font-family: var(--titulo); font-size: 1.15rem; letter-spacing: 0.04em; text-transform: uppercase; }

.whatsapp-flutuante { display: none; }

/* Visor */
.visor { max-width: min(94vw, 72rem); max-height: 92vh; padding: 0; border: 0; border-radius: var(--raio); background: #000; overflow: visible; }
.visor::backdrop { background: rgb(28 21 18 / 0.92); }
.visor-conteudo img, .visor-conteudo video { max-width: min(94vw, 72rem); max-height: 92vh; width: auto; height: auto; border-radius: var(--raio); }
.visor-fechar { position: absolute; top: -0.9rem; right: -0.9rem; z-index: 1; width: 2.75rem; height: 2.75rem; border: 0; border-radius: 50%; background: var(--brasa); color: #fff; font-size: 1.6rem; line-height: 1; cursor: pointer; }

/* Celular */
@media (max-width: 56rem) {
  .sobre, .orcamento-grade { grid-template-columns: 1fr; }
  .comparativo-rolagem { display: none; }
  .legenda { margin-top: 0; }
}
@media (max-width: 40rem) {
  .topo-links li:not(:last-child) { display: none; }
  .topo-marca img { height: 2.6rem; }
  .campo-duplo { grid-template-columns: 1fr; }
  .pacote-itens div { grid-template-columns: 1fr; gap: 0.15rem; }
  .agenda-item { grid-template-columns: 1fr; gap: 0.75rem; }
  .agenda-data { justify-self: start; min-width: 7rem; }
  .rodape { justify-content: center; text-align: center; padding-bottom: 5rem; }
  .whatsapp-flutuante {
    position: fixed;
    right: 1rem;
    bottom: 1rem;
    z-index: 20;
    display: inline-flex;
    align-items: center;
    min-height: 3rem;
    padding: 0.7rem 1.25rem;
    border-radius: 999px;
    background: var(--brasa);
    color: #fff;
    font: 500 1rem/1 var(--rotulo);
    text-transform: uppercase;
    text-decoration: none;
    box-shadow: 0 6px 18px rgb(0 0 0 / 0.35);
  }
  .visor-fechar { top: 0.5rem; right: 0.5rem; }
}
```

- [ ] **Step 2: Write `app/static/js/site.js`**

```javascript
// Visor de fotos e vídeos.
const visor = document.getElementById("visor");
const palco = visor.querySelector(".visor-conteudo");

visor.addEventListener("close", () => palco.replaceChildren());
visor.querySelector(".visor-fechar").addEventListener("click", () => visor.close());
visor.addEventListener("click", (evento) => {
  if (evento.target === visor) visor.close();
});

document.querySelectorAll(".foto").forEach((botao) => {
  botao.addEventListener("click", () => {
    const { src, tipo } = botao.dataset;
    let midia;
    if (tipo === "video") {
      midia = document.createElement("video");
      midia.controls = true;
      midia.autoplay = true;
      midia.playsInline = true;
    } else {
      midia = document.createElement("img");
      midia.alt = botao.getAttribute("aria-label").replace(/^Ampliar: /, "");
    }
    midia.src = src;
    palco.replaceChildren(midia);
    visor.showModal();
  });
});

// "Pedir orçamento do Nelore" já escolhe o pacote no formulário.
const seletor = document.getElementById("pacote");
document.querySelectorAll("[data-pacote]").forEach((link) => {
  link.addEventListener("click", () => {
    if (seletor) seletor.value = link.dataset.pacote;
  });
});
```

- [ ] **Step 3: Run the server with the real content**

Run in the background: `DATA_DIR="$CLAUDE_JOB_DIR/tmp/data-v2" ADMIN_PASSWORD=demo uv run uvicorn app.main:create_app --factory --port 8765`
Then: `curl -s http://127.0.0.1:8765/healthz` → `{"ok":true}`; `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8765/` → `200` (first request may take ~20 s while the 21 photos are converted).

- [ ] **Step 4: Screenshot desktop and phone and review against the PDF**

```bash
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
"$EDGE" --headless=new --disable-gpu --hide-scrollbars --window-size=1366,9000 --virtual-time-budget=6000 --screenshot="$CLAUDE_JOB_DIR/tmp/v2-desktop.png" http://127.0.0.1:8765/
cat > "$CLAUDE_JOB_DIR/tmp/v2-frame.html" <<'EOF'
<!doctype html><body style="margin:0;background:#888"><iframe src="http://127.0.0.1:8765/" style="width:390px;height:9000px;border:0"></iframe></body>
EOF
"$EDGE" --headless=new --disable-gpu --hide-scrollbars --window-size=420,9000 --virtual-time-budget=6000 --screenshot="$CLAUDE_JOB_DIR/tmp/v2-mobile.png" "file:///$CLAUDE_JOB_DIR/tmp/v2-frame.html"
```

(Headless Edge on Windows enforces a ~500 px minimum window width, so the phone view is rendered inside a 390 px iframe.)

Open both PNGs with the Read tool. Fix CSS and re-screenshot until all hold:
- Header and hero look like the PDF cover: dark wood + red smoke, white bull logo with forks, "CHURRASCO PARA EVENTOS" spaced, red rule, copper subtitle.
- "Paixão por churrasco," red + "servida com capricho." dark; numbers box dark with red top border.
- Comparison table: dark rounded header row, alternating beige rows, red squares, "MAIS PEDIDO" pill under Nelore.
- Package cards: red "OPÇÃO N", huge Anton name, dark price box; Nelore expanded with red border.
- Gallery: even grid of photos (no video tiles without ffmpeg — expected outside Docker).
- Phone (390 px): no horizontal scroll, table hidden, cards stacked, floating WhatsApp button visible, form full width.

- [ ] **Step 5: Stop the server and commit**

Stop the background server, then:

```bash
git add app/static
git commit -m "Aplica a identidade visual da proposta comercial na landing

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Admin panel

**Files:**
- Create: `app/rotas_admin.py`, `app/templates/admin/base.html`, `app/templates/admin/_campos_evento.html`, `app/templates/admin/index.html`, `app/templates/admin/evento.html`, `app/static/css/admin.css`, `tests/test_admin.py`
- Modify: `app/main.py` (replace the temporary `try/except` import with a plain import)

**Interfaces:**
- Consumes: `app.state.db` (Task 2 methods), `app.state.storage` (`salvar`, `apagar`, `url`), `app.state.settings` (`admin_user`, `admin_password`, `max_upload_mb`, `tmp_dir`), `midia.receber_upload`, `midia.processar`, `midia.MidiaInvalida`, `templates`.
- Produces: `router = APIRouter(prefix="/admin")` with `GET /admin`, `POST /admin/eventos`, `GET|POST /admin/eventos/{id}`, `POST /admin/eventos/{id}/midias`, `POST /admin/eventos/{id}/excluir`, `POST /admin/midias/{id}/excluir`, `POST /admin/orcamentos/{id}/lido`.

- [ ] **Step 1: Write the failing tests**

`tests/test_admin.py`:

```python
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Database
from tests.fabrica import AUTH, jpeg_bytes


def _criar(client, arquivos=None, **campos):
    dados = {"titulo": "Casamento da Ana", "tipo": "realizado", "data": "2026-05-10", "local": "Atibaia"}
    dados.update(campos)
    arquivos = arquivos if arquivos is not None else [("arquivos", ("festa.jpg", jpeg_bytes(), "image/jpeg"))]
    return client.post("/admin/eventos", data=dados, files=arquivos, auth=AUTH, follow_redirects=False)


def _id(resp) -> int:
    return int(resp.headers["location"].split("/")[3].split("?")[0])


def test_admin_exige_senha(client):
    assert client.get("/admin").status_code == 401
    assert client.get("/admin", auth=("admin", "errada")).status_code == 401
    assert client.get("/admin", auth=AUTH).status_code == 200


def test_admin_desligado_sem_senha(settings):
    from app.main import create_app

    sem_senha = Settings(**{**settings.__dict__, "admin_password": ""})
    assert TestClient(create_app(sem_senha)).get("/admin", auth=("admin", "")).status_code == 503


def test_post_vindo_de_outro_site_e_bloqueado(client):
    resp = client.post("/admin/eventos", data={"titulo": "x", "tipo": "realizado"}, auth=AUTH,
                       headers={"origin": "https://golpe.example"})
    assert resp.status_code == 403


def test_cria_evento_com_foto_otimizada_e_aparece_no_site(client, settings):
    foto = ("Festa Junina 2025.JPG", jpeg_bytes((2400, 1200), gps=True), "image/jpeg")
    resp = _criar(client, arquivos=[("arquivos", foto)])
    assert resp.status_code == 303
    nomes = sorted(p.name for p in settings.uploads_dir.iterdir())
    assert len(nomes) == 2 and all(n.endswith(".webp") for n in nomes)
    assert any(n.endswith("-mini.webp") for n in nomes)
    html = client.get("/").text
    assert "Casamento da Ana" in html
    assert all(f"/uploads/{n}" in html for n in nomes)


def test_upload_misto_salva_o_valido_e_lista_o_invalido(client, settings):
    resp = _criar(client, arquivos=[
        ("arquivos", ("boa.jpg", jpeg_bytes(), "image/jpeg")),
        ("arquivos", ("virus.exe", b"MZ", "application/octet-stream")),
    ])
    assert resp.status_code == 400
    assert "virus.exe" in resp.text and "boa.jpg" not in resp.text
    assert len(list(settings.uploads_dir.iterdir())) == 2


def test_upload_falso_e_acima_do_limite(client, settings):
    evento = _id(_criar(client))
    falso = client.post(f"/admin/eventos/{evento}/midias", auth=AUTH,
                        files=[("arquivos", ("falsa.jpg", b"nao sou foto", "image/jpeg"))])
    assert falso.status_code == 400 and "não é uma imagem válida" in falso.text
    grande = client.post(f"/admin/eventos/{evento}/midias", auth=AUTH,
                         files=[("arquivos", ("grande.mp4", b"0" * (2 * 1024 * 1024), "video/mp4"))])
    assert grande.status_code == 400 and "limite de 1 MB" in grande.text
    assert len(list(settings.uploads_dir.iterdir())) == 2


def test_editar_evento_e_data_invalida(client, settings):
    evento = _id(_criar(client))
    client.post(f"/admin/eventos/{evento}", auth=AUTH,
                data={"titulo": "Casamento editado", "tipo": "futuro", "data": "data-ruim", "local": "", "descricao": ""})
    salvo = Database(settings.database_url).obter_evento(evento)
    assert (salvo["titulo"], salvo["tipo"], salvo["data"]) == ("Casamento editado", "futuro", None)


def test_titulo_obrigatorio(client):
    assert _criar(client, titulo="  ").status_code == 400


def test_excluir_midia_e_evento_apagam_arquivos(client, settings):
    evento = _id(_criar(client))
    midia = Database(settings.database_url).listar_midias(evento)[0]
    client.post(f"/admin/midias/{midia['id']}/excluir", auth=AUTH)
    assert list(settings.uploads_dir.iterdir()) == []

    outro = _id(_criar(client))
    client.post(f"/admin/eventos/{outro}/excluir", auth=AUTH)
    assert list(settings.uploads_dir.iterdir()) == []
    assert "Casamento da Ana" not in client.get("/").text


def test_orcamentos_no_painel_e_marcar_respondido(client, settings):
    client.post("/orcamento", data={"nome": "Carla", "telefone": "11988887777", "convidados": "80", "pacote": "Nelore"},
                follow_redirects=False)
    painel = client.get("/admin", auth=AUTH).text
    assert "Carla" in painel and "80 pessoas" in painel and "Nelore" in painel
    orcamento = Database(settings.database_url).listar_orcamentos()[0]
    client.post(f"/admin/orcamentos/{orcamento['id']}/lido", auth=AUTH)
    assert Database(settings.database_url).listar_orcamentos()[0]["lido"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_admin.py -q`
Expected: FAIL — `/admin` returns 404 (router not registered yet).

- [ ] **Step 3: Implement `app/rotas_admin.py`**

```python
import tempfile
from datetime import date
from pathlib import Path
from secrets import compare_digest
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app import midia
from app.web import templates

TIPOS = {"realizado", "futuro"}
security = HTTPBasic(realm="Painel Brasamiga")


def exigir_admin(request: Request, credenciais: HTTPBasicCredentials = Depends(security)) -> None:
    settings = request.app.state.settings
    if not settings.admin_password:
        raise HTTPException(503, "Painel desligado: defina ADMIN_PASSWORD no arquivo .env e reinicie o servidor.")
    usuario_ok = compare_digest(credenciais.username.encode(), settings.admin_user.encode())
    senha_ok = compare_digest(credenciais.password.encode(), settings.admin_password.encode())
    if not (usuario_ok and senha_ok):
        raise HTTPException(401, "Usuário ou senha incorretos.", headers={"WWW-Authenticate": "Basic"})
    # O navegador reenvia a senha sozinho; bloqueia formulários vindos de outros sites.
    if request.method == "POST":
        origem = request.headers.get("origin")
        if origem and urlparse(origem).netloc != request.url.netloc:
            raise HTTPException(403, "Envio bloqueado: o formulário não veio deste site.")


router = APIRouter(prefix="/admin", dependencies=[Depends(exigir_admin)])


def _campos_evento(titulo: str, data: str, local: str, descricao: str, tipo: str) -> dict:
    titulo = titulo.strip()
    if not titulo:
        raise HTTPException(400, "Dê um nome ao evento.")
    if tipo not in TIPOS:
        raise HTTPException(400, "Escolha se o evento já foi realizado ou ainda vai acontecer.")
    try:
        quando = date.fromisoformat(data.strip()) if data.strip() else None
    except ValueError:
        quando = None
    return {
        "titulo": titulo[:200],
        "data": quando,
        "local": local.strip()[:200],
        "descricao": descricao.strip()[:3000],
        "tipo": tipo,
    }


async def _salvar_midias(request: Request, evento_id: int, arquivos: list[UploadFile]) -> tuple[list[str], list[str]]:
    estado = request.app.state
    estado.settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    erros, avisos = [], []
    with tempfile.TemporaryDirectory(dir=estado.settings.tmp_dir) as pasta:
        for upload in arquivos:
            if not upload.filename:
                continue
            try:
                bruto = await midia.receber_upload(upload, Path(pasta), estado.settings.max_upload_mb)
                pronto = await run_in_threadpool(midia.processar, bruto, upload.filename)
            except midia.MidiaInvalida as erro:
                erros.append(str(erro))
                continue
            base = uuid4().hex
            chave = f"{base}{pronto.extensao}"
            with pronto.principal.open("rb") as arquivo:
                estado.storage.salvar(chave, arquivo, pronto.content_type)
            chave_mini = None
            if pronto.miniatura:
                chave_mini = f"{base}-mini.webp"
                with pronto.miniatura.open("rb") as arquivo:
                    estado.storage.salvar(chave_mini, arquivo, "image/webp")
            estado.db.adicionar_midia(evento_id, chave, pronto.tipo, chave_mini)
            if pronto.aviso:
                avisos.append(pronto.aviso)
    return erros, avisos


def _apagar_arquivos(request: Request, linha: dict) -> None:
    storage = request.app.state.storage
    storage.apagar(linha["chave"])
    if linha["chave_miniatura"]:
        storage.apagar(linha["chave_miniatura"])


def _pagina_evento(request: Request, evento_id: int, erros=None, avisos=None, salvo=False):
    estado = request.app.state
    evento = estado.db.obter_evento(evento_id)
    if not evento:
        raise HTTPException(404, "Evento não encontrado.")
    midias = [
        {**m, "url": estado.storage.url(m["chave_miniatura"] or m["chave"]), "url_original": estado.storage.url(m["chave"])}
        for m in estado.db.listar_midias(evento_id)
    ]
    return templates.TemplateResponse(
        request,
        "admin/evento.html",
        {"evento": evento, "midias": midias, "erros": erros or [], "avisos": avisos or [], "salvo": salvo},
        status_code=400 if erros else 200,
    )


@router.get("", response_class=HTMLResponse)
def painel(request: Request):
    db = request.app.state.db
    return templates.TemplateResponse(
        request,
        "admin/index.html",
        {
            "futuros": db.listar_eventos("futuro"),
            "realizados": db.listar_eventos("realizado"),
            "orcamentos": db.listar_orcamentos(),
        },
    )


@router.post("/eventos")
async def criar_evento(
    request: Request,
    titulo: str = Form(""),
    data: str = Form(""),
    local: str = Form(""),
    descricao: str = Form(""),
    tipo: str = Form("realizado"),
    arquivos: list[UploadFile] = File(default=[]),
):
    evento_id = request.app.state.db.criar_evento(**_campos_evento(titulo, data, local, descricao, tipo))
    erros, avisos = await _salvar_midias(request, evento_id, arquivos)
    if erros or avisos:
        return _pagina_evento(request, evento_id, erros, avisos)
    return RedirectResponse(f"/admin/eventos/{evento_id}?salvo=1", status_code=303)


@router.get("/eventos/{evento_id}", response_class=HTMLResponse)
def ver_evento(request: Request, evento_id: int, salvo: bool = False):
    return _pagina_evento(request, evento_id, salvo=salvo)


@router.post("/eventos/{evento_id}")
def atualizar_evento(
    request: Request,
    evento_id: int,
    titulo: str = Form(""),
    data: str = Form(""),
    local: str = Form(""),
    descricao: str = Form(""),
    tipo: str = Form("realizado"),
):
    db = request.app.state.db
    if not db.obter_evento(evento_id):
        raise HTTPException(404, "Evento não encontrado.")
    db.atualizar_evento(evento_id, **_campos_evento(titulo, data, local, descricao, tipo))
    return RedirectResponse(f"/admin/eventos/{evento_id}?salvo=1", status_code=303)


@router.post("/eventos/{evento_id}/midias")
async def enviar_midias(request: Request, evento_id: int, arquivos: list[UploadFile] = File(default=[])):
    if not request.app.state.db.obter_evento(evento_id):
        raise HTTPException(404, "Evento não encontrado.")
    erros, avisos = await _salvar_midias(request, evento_id, arquivos)
    if erros or avisos:
        return _pagina_evento(request, evento_id, erros, avisos)
    return RedirectResponse(f"/admin/eventos/{evento_id}?salvo=1", status_code=303)


@router.post("/eventos/{evento_id}/excluir")
def excluir_evento(request: Request, evento_id: int):
    for linha in request.app.state.db.excluir_evento(evento_id):
        _apagar_arquivos(request, linha)
    return RedirectResponse("/admin", status_code=303)


@router.post("/midias/{midia_id}/excluir")
def excluir_midia(request: Request, midia_id: int):
    linha = request.app.state.db.excluir_midia(midia_id)
    if not linha:
        raise HTTPException(404, "Arquivo não encontrado.")
    _apagar_arquivos(request, linha)
    return RedirectResponse(f"/admin/eventos/{linha['evento_id']}", status_code=303)


@router.post("/orcamentos/{orcamento_id}/lido")
def marcar_orcamento(request: Request, orcamento_id: int):
    request.app.state.db.alternar_lido(orcamento_id)
    return RedirectResponse("/admin#orcamentos", status_code=303)
```

- [ ] **Step 4: Replace the temporary import in `app/main.py`**

Replace:

```python
    app.include_router(site_router)
    try:
        from app.rotas_admin import router as admin_router
    except ModuleNotFoundError:  # remover este try quando a Task 8 criar rotas_admin
        admin_router = None
    if admin_router:
        app.include_router(admin_router)
    return app
```

with:

```python
    app.include_router(site_router)
    app.include_router(admin_router)
    return app
```

and add `from app.rotas_admin import router as admin_router` to the imports at the top, next to `from app.rotas_site import router as site_router`.

- [ ] **Step 5: Create the admin templates and stylesheet**

`app/templates/admin/base.html`:

```html
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex">
  <title>{% block titulo %}Painel{% endblock %} · Brasamiga</title>
  <link rel="stylesheet" href="/static/css/admin.css">
</head>
<body>
  <header class="barra">
    <a href="/admin" class="barra-marca">Brasamiga · painel</a>
    <a href="/" target="_blank" rel="noopener">Ver o site</a>
  </header>
  <main class="pagina">
    {% block conteudo %}{% endblock %}
  </main>
  <script>
    // Avisa que o envio pode demorar (vídeos são convertidos no servidor).
    document.querySelectorAll("form[enctype='multipart/form-data']").forEach((form) => {
      form.addEventListener("submit", () => {
        const botao = form.querySelector("button[type=submit]");
        if (botao) { botao.disabled = true; botao.textContent = "Enviando e convertendo…"; }
      });
    });
  </script>
</body>
</html>
```

`app/templates/admin/_campos_evento.html`:

```html
<label>Nome do evento
  <input name="titulo" required maxlength="200" value="{{ evento.titulo if evento else '' }}" placeholder="Ex.: Casamento da Ana e do Pedro">
</label>
<fieldset class="opcoes">
  <legend>Situação</legend>
  <label><input type="radio" name="tipo" value="realizado" {% if not evento or evento.tipo == "realizado" %}checked{% endif %}> Já realizado (aparece na galeria)</label>
  <label><input type="radio" name="tipo" value="futuro" {% if evento and evento.tipo == "futuro" %}checked{% endif %}> Vai acontecer (aparece na agenda)</label>
</fieldset>
<div class="linha">
  <label>Data
    <input type="date" name="data" value="{{ evento.data.isoformat() if evento and evento.data else '' }}">
  </label>
  <label>Local
    <input name="local" maxlength="200" value="{{ evento.local if evento else '' }}" placeholder="Ex.: Espaço Villa, Campinas">
  </label>
</div>
<label>Descrição <span class="dica">(opcional)</span>
  <textarea name="descricao" rows="3" maxlength="3000">{{ evento.descricao if evento else '' }}</textarea>
</label>
```

`app/templates/admin/index.html`:

```html
{% extends "admin/base.html" %}

{% macro lista_eventos(eventos, vazio) %}
  {% if eventos %}
    <ul class="lista">
      {% for e in eventos %}
        <li>
          <a href="/admin/eventos/{{ e.id }}"><strong>{{ e.titulo }}</strong></a>
          <span class="dica">
            {{ e.data | data_br or "sem data" }}{% if e.local %} · {{ e.local }}{% endif %}
            · {{ e.total_midias }} {{ "arquivo" if e.total_midias == 1 else "arquivos" }}
          </span>
        </li>
      {% endfor %}
    </ul>
  {% else %}
    <p class="vazio">{{ vazio }}</p>
  {% endif %}
{% endmacro %}

{% block conteudo %}
<section class="bloco">
  <h1>Cadastrar evento</h1>
  <p class="dica">Eventos realizados aparecem na galeria do site. Eventos futuros aparecem na agenda até a data passar.</p>
  <form method="post" action="/admin/eventos" enctype="multipart/form-data" class="form">
    {% include "admin/_campos_evento.html" %}
    <label>Fotos e vídeos
      <input type="file" name="arquivos" multiple accept="image/*,.heic,.heif,video/mp4,video/quicktime,video/webm">
      <span class="dica">JPG, PNG, WEBP, HEIC, MP4, MOV ou WEBM. Dá para selecionar vários de uma vez; vídeos levam alguns segundos para converter.</span>
    </label>
    <button type="submit">Cadastrar evento</button>
  </form>
</section>

<div class="colunas">
  <section class="bloco">
    <h2>Próximos eventos</h2>
    {{ lista_eventos(futuros, "Nenhum evento futuro cadastrado. Use o formulário acima e marque “Vai acontecer”.") }}
  </section>
  <section class="bloco">
    <h2>Eventos realizados</h2>
    {{ lista_eventos(realizados, "Nenhum evento realizado cadastrado. Cadastre o primeiro com as fotos da festa.") }}
  </section>
</div>

<section class="bloco" id="orcamentos">
  <h2>Pedidos de orçamento</h2>
  {% if orcamentos %}
    <div class="tabela-rolagem">
      <table>
        <thead>
          <tr><th>Recebido</th><th>Nome</th><th>Contato</th><th>Evento</th><th>Mensagem</th><th></th></tr>
        </thead>
        <tbody>
          {% for o in orcamentos %}
            <tr class="{{ 'lido' if o.lido else 'novo' }}">
              <td>{{ o.criado_em.strftime("%d/%m/%Y %H:%M") }}</td>
              <td>{{ o.nome }}</td>
              <td>{{ o.telefone }}{% if o.email %}<br><a href="mailto:{{ o.email }}">{{ o.email }}</a>{% endif %}</td>
              <td>
                {{ o.pacote or "Pacote a definir" }}<br>
                <span class="dica">{{ o.data_evento | data_br or "sem data" }}{% if o.convidados %} · {{ o.convidados }} pessoas{% endif %}{% if o.local %} · {{ o.local }}{% endif %}</span>
              </td>
              <td class="mensagem">{{ o.mensagem }}</td>
              <td>
                <form method="post" action="/admin/orcamentos/{{ o.id }}/lido">
                  <button type="submit" class="secundario">{{ "Marcar como novo" if o.lido else "Marcar como respondido" }}</button>
                </form>
              </td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  {% else %}
    <p class="vazio">Nenhum pedido ainda. Os pedidos feitos no formulário do site aparecem aqui.</p>
  {% endif %}
</section>
{% endblock %}
```

`app/templates/admin/evento.html`:

```html
{% extends "admin/base.html" %}
{% block titulo %}{{ evento.titulo }}{% endblock %}

{% block conteudo %}
<p><a href="/admin">Voltar ao painel</a></p>

{% if erros %}
  <div class="aviso erro" role="alert">
    <p>Estes arquivos não foram enviados:</p>
    <ul>{% for e in erros %}<li>{{ e }}</li>{% endfor %}</ul>
  </div>
{% endif %}
{% if avisos %}
  <div class="aviso atencao" role="status">
    <ul>{% for a in avisos %}<li>{{ a }}</li>{% endfor %}</ul>
  </div>
{% endif %}
{% if salvo and not erros %}
  <p class="aviso ok" role="status">Evento salvo.</p>
{% endif %}

<section class="bloco">
  <h1>{{ evento.titulo }}</h1>
  <form method="post" action="/admin/eventos/{{ evento.id }}" class="form">
    {% include "admin/_campos_evento.html" %}
    <button type="submit">Salvar alterações</button>
  </form>
</section>

<section class="bloco">
  <h2>Fotos e vídeos ({{ midias | length }})</h2>
  <form method="post" action="/admin/eventos/{{ evento.id }}/midias" enctype="multipart/form-data" class="form form-linha">
    <input type="file" name="arquivos" multiple required accept="image/*,.heic,.heif,video/mp4,video/quicktime,video/webm">
    <button type="submit">Enviar arquivos</button>
  </form>

  {% if midias %}
    <ul class="midias">
      {% for m in midias %}
        <li>
          {% if m.tipo == "video" %}
            <video src="{{ m.url_original }}" controls preload="metadata"></video>
          {% else %}
            <a href="{{ m.url_original }}" target="_blank" rel="noopener"><img src="{{ m.url }}" alt="" loading="lazy"></a>
          {% endif %}
          <form method="post" action="/admin/midias/{{ m.id }}/excluir">
            <button type="submit" class="perigo">Excluir {{ "vídeo" if m.tipo == "video" else "foto" }}</button>
          </form>
        </li>
      {% endfor %}
    </ul>
  {% else %}
    <p class="vazio">Este evento ainda não tem fotos nem vídeos. Envie pelo campo acima.</p>
  {% endif %}
</section>

<section class="bloco">
  <h2>Excluir evento</h2>
  <p class="dica">Apaga o evento e todos os arquivos dele. Não dá para desfazer.</p>
  <form method="post" action="/admin/eventos/{{ evento.id }}/excluir">
    <label class="confirmar"><input type="checkbox" required> Quero excluir este evento</label>
    <button type="submit" class="perigo">Excluir evento</button>
  </form>
</section>
{% endblock %}
```

`app/static/css/admin.css`:

```css
:root {
  --madeira: #1C1512;
  --brasa: #A93226;
  --cobre: #B8966A;
  --fundo: #F3EBDF;
  --linha: #D9CBB8;
  --texto: #1E1A17;
  --suave: #5C524B;
  --ok: #56703D;
}

* { box-sizing: border-box; }
body { margin: 0; background: var(--fundo); color: var(--texto); font: 1rem/1.5 system-ui, sans-serif; }
a { color: var(--brasa); }
:focus-visible { outline: 3px solid var(--cobre); outline-offset: 2px; }
h1, h2 { margin: 0 0 0.75rem; line-height: 1.2; }
h1 { font-size: 1.5rem; }
h2 { font-size: 1.2rem; }

.barra { display: flex; justify-content: space-between; align-items: center; gap: 1rem; padding: 0.9rem 1rem; background: var(--madeira); color: #fff; border-bottom: 4px solid var(--brasa); }
.barra a { color: #fff; }
.barra-marca { font-weight: 700; text-decoration: none; }

.pagina { max-width: 64rem; margin: 0 auto; padding: 1.5rem 1rem 4rem; }
.bloco { margin-top: 1.25rem; padding: 1.25rem; background: #fff; border: 1px solid var(--linha); border-radius: 0.75rem; }
.colunas { display: grid; grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr)); gap: 0 1.25rem; }

.form { display: grid; gap: 0.9rem; margin-top: 1rem; }
.form label { display: grid; gap: 0.3rem; font-weight: 600; }
.form-linha { display: flex; flex-wrap: wrap; align-items: center; gap: 0.75rem; }
.linha { display: grid; grid-template-columns: 12rem 1fr; gap: 0.9rem; }
input:not([type=radio], [type=checkbox], [type=file]), textarea { width: 100%; padding: 0.55rem 0.7rem; border: 1px solid #B9AE9F; border-radius: 0.4rem; font: inherit; }
.opcoes { display: grid; gap: 0.35rem; margin: 0; padding: 0; border: 0; }
.opcoes legend { font-weight: 600; margin-bottom: 0.3rem; }
.opcoes label, .confirmar { display: flex; gap: 0.5rem; align-items: center; font-weight: 400; }
.confirmar { margin: 0.5rem 0 0.75rem; }

button { justify-self: start; padding: 0.6rem 1.1rem; border: 0; border-radius: 0.4rem; background: var(--brasa); color: #fff; font: 600 0.95rem/1.2 system-ui, sans-serif; cursor: pointer; }
button:disabled { opacity: 0.7; cursor: progress; }
button.secundario { background: #ECE3D6; color: var(--texto); }
button.perigo { background: #7A1E14; }

.dica { color: var(--suave); font-weight: 400; font-size: 0.9rem; }
.vazio { color: var(--suave); }
.aviso { margin: 1rem 0 0; padding: 0.8rem 1rem; border-radius: 0.5rem; }
.aviso p, .aviso ul { margin: 0; }
.aviso p + ul { margin-top: 0.4rem; }
.aviso.ok { background: #E4EBDB; border-left: 4px solid var(--ok); }
.aviso.erro { background: #F6DCD6; border-left: 4px solid var(--brasa); }
.aviso.atencao { background: #F5EBD3; border-left: 4px solid var(--cobre); }

.lista { margin: 0; padding: 0; list-style: none; }
.lista li { display: grid; padding: 0.6rem 0; border-bottom: 1px solid var(--linha); }

.midias { display: grid; grid-template-columns: repeat(auto-fill, minmax(12rem, 1fr)); gap: 1rem; margin: 1.25rem 0 0; padding: 0; list-style: none; }
.midias li { display: grid; gap: 0.5rem; }
.midias img, .midias video { width: 100%; aspect-ratio: 4 / 3; object-fit: cover; border-radius: 0.4rem; background: #000; }

.tabela-rolagem { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 0.92rem; }
th, td { padding: 0.6rem 0.5rem; border-bottom: 1px solid var(--linha); text-align: left; vertical-align: top; }
tr.novo td:first-child { box-shadow: inset 3px 0 0 var(--brasa); }
tr.lido { color: var(--suave); }
.mensagem { max-width: 22rem; white-space: pre-line; }

@media (max-width: 36rem) {
  .linha { grid-template-columns: 1fr; }
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest -q`
Expected: all pass (`tests/test_admin.py`: `10 passed`).

- [ ] **Step 7: Commit**

```bash
git add app/rotas_admin.py app/main.py app/templates/admin app/static/css/admin.css tests/test_admin.py
git commit -m "Adiciona painel admin com fotos otimizadas e vídeos convertidos

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Build helper, Docker, docs and end-to-end check

**Files:**
- Create: `app/preparar.py`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `tests/test_preparar.py`
- Rewrite: `.env.example`, `README.md`, `conteudo/LEIA-ME.md`

**Interfaces:**
- Consumes: `Settings.from_env`, `Conteudo.preparar`.
- Produces: `python -m app.preparar` CLI (prints `Fotos prontas: N · Vídeos prontos: M`).

- [ ] **Step 1: Write the failing test**

`tests/test_preparar.py`:

```python
from app import preparar
from tests.fabrica import jpeg_bytes


def test_preparar_gera_cache(monkeypatch, settings, capsys):
    (settings.content_dir / "eventos-realizados" / "a.jpg").write_bytes(jpeg_bytes())
    monkeypatch.setattr(preparar.Settings, "from_env", classmethod(lambda cls: settings))
    preparar.main()
    assert "Fotos prontas: 1" in capsys.readouterr().out
    assert any(settings.cache_dir.joinpath("galeria").glob("*-mini.webp"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_preparar.py -q`
Expected: FAIL with `ImportError: cannot import name 'preparar'`

- [ ] **Step 3: Implement `app/preparar.py`**

```python
"""Gera as versões web das fotos e vídeos de conteudo/eventos-realizados.

Uso: uv run python -m app.preparar   (no build da Vercel, antes do deploy)
"""

from app.config import Settings
from app.conteudo import Conteudo


def main() -> None:
    settings = Settings.from_env()
    resultado = Conteudo(settings.content_dir, settings.cache_dir).preparar()
    print(f"Fotos prontas: {resultado['imagens']} · Vídeos prontos: {resultado['videos']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Docker files**

`Dockerfile`:

```dockerfile
FROM python:3.14-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PYTHON=/usr/local/bin/python3

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY conteudo ./conteudo

RUN useradd --create-home --uid 1000 brasamiga \
 && mkdir -p /app/data \
 && chown brasamiga:brasamiga /app/data
USER brasamiga

ENV PATH="/app/.venv/bin:$PATH" DATA_DIR=/app/data CONTENT_DIR=/app/conteudo
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
```

`docker-compose.yml`:

```yaml
services:
  web:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - path: .env
        required: false
    volumes:
      - brasamiga-data:/app/data
      - ./conteudo:/app/conteudo:ro
    restart: unless-stopped

volumes:
  brasamiga-data:
```

`.dockerignore`:

```
.venv/
.git/
.claude/
data/
docs/
tests/
**/__pycache__/
.pytest_cache/
.env
conteudo/logo/*.ai
```

- [ ] **Step 6: Rewrite `.env.example`**

```bash
# Copie para .env e troque a senha.
ADMIN_USER=admin
ADMIN_PASSWORD=troque-esta-senha

# Limite por foto/vídeo enviado pelo painel, em MB.
MAX_UPLOAD_MB=300

# Banco: SQLite no volume (padrão). Na Vercel, use a URL do Postgres (Neon):
# DATABASE_URL=postgresql+psycopg://usuario:senha@host/banco

# Armazenamento das mídias do painel: local (padrão) ou blob (Vercel Blob, ainda não implementado).
# STORAGE_BACKEND=local
# BLOB_READ_WRITE_TOKEN=

# Caminhos (padrão: ./data e ./conteudo; no Docker já vêm configurados).
# DATA_DIR=./data
# CONTENT_DIR=./conteudo
```

- [ ] **Step 7: Rewrite `README.md`**

````markdown
# Brasamiga · landing page + painel admin

Site do Brasamiga, churrasco para eventos em São Paulo, com a identidade visual da Proposta Comercial 2026:
pacotes com preços, quem somos, galeria de eventos, agenda, condições, FAQ e pedido de orçamento que
fica salvo no painel e abre o WhatsApp com a mensagem pronta.

## Rodando com Docker (recomendado)

```bash
cp .env.example .env          # troque ADMIN_PASSWORD
docker compose up --build
```

- Site: http://localhost:8000
- Painel: http://localhost:8000/admin (usuário e senha do `.env`)

Banco, fotos enviadas pelo painel e versões otimizadas ficam no volume `brasamiga-data`.
A pasta `conteudo/` é lida direto do seu computador: troque fotos ou edite o `site.toml` e recarregue a página.

## Rodando sem Docker

```bash
uv sync
cp .env.example .env
uv run uvicorn app.main:create_app --factory --reload
```

Sem ffmpeg instalado, os vídeos não são convertidos: os da pasta não aparecem e os enviados pelo painel
ficam no formato original.

## Onde editar o quê

| O quê | Onde |
|---|---|
| Pacotes, preços, textos, FAQ, WhatsApp | `conteudo/site.toml` |
| Logo | `conteudo/logo/` (`logo_escuro` no `site.toml` diz qual arquivo usar) |
| PDF da proposta (botão "Baixar") | `conteudo/cardapio/` |
| Fotos e vídeos soltos da galeria | `conteudo/eventos-realizados/` |
| Eventos com nome, data, local e fotos | Painel `/admin` |
| Pedidos de orçamento | Painel `/admin` |

## Testes

```bash
uv run pytest -q
```

## Indo para a Vercel (futuro)

1. Criar um Postgres (Neon) e definir `DATABASE_URL`; adicionar o driver (`uv add "psycopg[binary]"`).
2. Implementar `BlobStorage` em `app/storage.py` e definir `STORAGE_BACKEND=blob` + `BLOB_READ_WRITE_TOKEN`.
3. Rodar `uv run python -m app.preparar` no build para gerar as fotos otimizadas.
4. Uploads acima de 4,5 MB precisam ir direto do navegador para o Blob.
````

- [ ] **Step 8: Rewrite `conteudo/LEIA-ME.md`**

```markdown
# Pasta de conteúdo do Brasamiga

Tudo aqui aparece no site ao recarregar a página.

| Pasta / arquivo | O que colocar | Onde aparece |
|---|---|---|
| `site.toml` | Pacotes e preços, quem somos, diferenciais, condições, FAQ, WhatsApp e Instagram | Página inteira |
| `logo/` | Arquivos do logo. O `site.toml` indica qual usar nas faixas escuras (`logo_escuro`, hoje `LOGO-03.png`, branco sobre preto) | Topo, abertura e ícone da aba |
| `cardapio/` | O PDF da proposta comercial | Botão "Baixar a proposta completa" |
| `eventos-realizados/` | Fotos (JPG, PNG, WEBP, HEIC) e vídeos (MP4, MOV) de festas já feitas | Galeria "Eventos realizados" |

## Dicas

- O site cria sozinho versões leves das fotos e tira a localização (GPS) que o celular grava nelas. Os arquivos originais nunca ficam públicos.
- A ordem da galeria segue o nome dos arquivos (`01-casamento.jpg`, `02-aniversario.jpg`...).
- Para fotos separadas por evento, com nome, data e local, use o painel `/admin`.
- Ao editar o `site.toml`, mantenha as aspas e os colchetes. Se algo quebrar, o site mostra a linha do erro.
```

- [ ] **Step 9: Docker end-to-end check**

```bash
[ -f .env ] || printf "ADMIN_USER=admin\nADMIN_PASSWORD=demo-docker\n" > .env
docker compose up --build -d
docker compose ps
```

Wait for the container to be `healthy`, then:

```bash
curl -s -o /dev/null -w "site: %{http_code}\n" http://localhost:8000/
curl -s -o /dev/null -w "admin sem senha: %{http_code}\n" http://localhost:8000/admin
docker compose exec web python -c "from app import midia; print('ffmpeg:', midia.ffmpeg_disponivel())"
docker compose logs web | grep -i "galeria preparada"
curl -s http://localhost:8000/ | grep -o '/cache/galeria/[a-f0-9]*\.mp4' | sort -u | wc -l
```

Expected: `site: 200`, `admin sem senha: 401`, `ffmpeg: True`, a log line `Galeria preparada: {'imagens': 21, 'videos': 2}` (may take ~1 min on first start; if uvicorn's default log level hides it, check that `/` lists `.mp4` items instead), and the `.mp4` count `2`. Then `docker compose down` (keeps the volume).

If `.env` was created in this step with the demo password, tell the owner to change it.

- [ ] **Step 10: Commit**

```bash
git add app/preparar.py tests/test_preparar.py Dockerfile docker-compose.yml .dockerignore .env.example README.md conteudo/LEIA-ME.md
git commit -m "Dockeriza o projeto e documenta o caminho para a Vercel

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
