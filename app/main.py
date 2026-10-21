import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.config import Settings
from app.conteudo import PASTAS_PUBLICAS, Conteudo, ConteudoInvalido
from app.db import Database
from app.rotas_admin import router as admin_router
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
    app.include_router(admin_router)
    return app
