import re
from datetime import date
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import conteudo
from app.admin import router as admin_router
from app.config import Settings
from app.db import Database
from app.web import APP_DIR, templates

MENSAGEM_WHATSAPP = "Olá! Quero um orçamento de churrasco para o meu evento."


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    db = Database(settings.db_path)
    db.iniciar()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    conteudo.garantir_pastas(settings.content_dir)

    app = FastAPI(title="Brasamiga", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.db = db

    app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
    app.mount("/uploads", StaticFiles(directory=settings.uploads_dir), name="uploads")
    # Só as subpastas de mídia ficam públicas; o site.toml não é servido.
    for pasta in conteudo.PASTAS:
        app.mount(
            f"/conteudo/{pasta}",
            StaticFiles(directory=settings.content_dir / pasta),
            name=f"conteudo-{pasta}",
        )

    app.include_router(admin_router)

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request, enviado: bool = False, erro: bool = False):
        site = conteudo.carregar_site(settings.content_dir)
        hoje = date.today().isoformat()

        realizados = [
            {**e, "midias": db.listar_midias(e["id"])} for e in db.listar_eventos("realizado")
        ]
        futuros = [
            {**e, "midias": db.listar_midias(e["id"])}
            for e in db.listar_eventos("futuro")
            if not e["data"] or e["data"] >= hoje
        ]

        whatsapp = re.sub(r"\D", "", str(site.get("contato", {}).get("whatsapp", "")))
        whatsapp_url = f"https://wa.me/{whatsapp}?text={quote(MENSAGEM_WHATSAPP)}" if whatsapp else None

        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "marca": site.get("marca", {}),
                "contato": site.get("contato", {}),
                "servicos": site.get("servicos", []),
                "categorias": site.get("cardapio", []),
                "logo": conteudo.logo(settings.content_dir),
                "cardapio": conteudo.cardapio(settings.content_dir),
                "galeria": conteudo.galeria(settings.content_dir),
                "realizados": realizados,
                "futuros": futuros,
                "whatsapp_url": whatsapp_url,
                "enviado": enviado,
                "erro": erro,
            },
        )

    @app.post("/orcamento")
    def pedir_orcamento(
        nome: str = Form(""),
        telefone: str = Form(""),
        email: str = Form(""),
        data_evento: str = Form(""),
        convidados: str = Form(""),
        tipo_evento: str = Form(""),
        mensagem: str = Form(""),
        site: str = Form(""),  # campo isca: só robôs preenchem
    ):
        if site:
            return RedirectResponse("/?enviado=1#orcamento", status_code=303)
        nome, telefone = nome.strip(), telefone.strip()
        if not nome or not telefone:
            return RedirectResponse("/?erro=1#orcamento", status_code=303)

        db.criar_orcamento(
            nome=nome[:200],
            telefone=telefone[:40],
            email=email.strip()[:200],
            data_evento=data_evento.strip()[:10],
            convidados=int(convidados) if convidados.strip().isdigit() else None,
            tipo_evento=tipo_evento.strip()[:100],
            mensagem=mensagem.strip()[:2000],
        )
        return RedirectResponse("/?enviado=1#orcamento", status_code=303)

    return app
