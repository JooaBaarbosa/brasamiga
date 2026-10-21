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
