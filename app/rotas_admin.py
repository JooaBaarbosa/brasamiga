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
SENHA_DE_EXEMPLO = "troque-esta-senha"  # a do .env.example
security = HTTPBasic(realm="Painel Brasamiga")


def exigir_admin(request: Request, credenciais: HTTPBasicCredentials = Depends(security)) -> None:
    settings = request.app.state.settings
    if not settings.admin_password:
        raise HTTPException(503, "Painel desligado: defina ADMIN_PASSWORD no arquivo .env e reinicie o servidor.")
    if settings.admin_password == SENHA_DE_EXEMPLO:
        raise HTTPException(
            503,
            "Painel desligado: a senha ainda é a de exemplo. Troque ADMIN_PASSWORD no arquivo .env "
            "(não no .env.example) e reinicie o servidor.",
        )
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
