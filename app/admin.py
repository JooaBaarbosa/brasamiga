from secrets import compare_digest
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.media import UploadInvalido, apagar_arquivo, salvar_upload
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
    return {
        "titulo": titulo[:200],
        "data": data.strip() or None,
        "local": local.strip()[:200],
        "descricao": descricao.strip()[:3000],
        "tipo": tipo,
    }


async def _salvar_midias(request: Request, evento_id: int, arquivos: list[UploadFile]) -> list[str]:
    settings, db = request.app.state.settings, request.app.state.db
    erros = []
    for upload in arquivos:
        if not upload.filename:
            continue
        try:
            nome, tipo = await salvar_upload(upload, settings.uploads_dir, settings.max_upload_mb)
        except UploadInvalido as erro:
            erros.append(str(erro))
            continue
        db.adicionar_midia(evento_id, nome, tipo)
    return erros


def _pagina_evento(request: Request, evento_id: int, erros: list[str] | None = None, salvo: bool = False):
    db = request.app.state.db
    evento = db.obter_evento(evento_id)
    if not evento:
        raise HTTPException(404, "Evento não encontrado.")
    return templates.TemplateResponse(
        request,
        "admin/evento.html",
        {"evento": evento, "midias": db.listar_midias(evento_id), "erros": erros or [], "salvo": salvo},
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
    erros = await _salvar_midias(request, evento_id, arquivos)
    if erros:
        return _pagina_evento(request, evento_id, erros)
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
    erros = await _salvar_midias(request, evento_id, arquivos)
    if erros:
        return _pagina_evento(request, evento_id, erros)
    return RedirectResponse(f"/admin/eventos/{evento_id}?salvo=1", status_code=303)


@router.post("/eventos/{evento_id}/excluir")
def excluir_evento(request: Request, evento_id: int):
    uploads = request.app.state.settings.uploads_dir
    for arquivo in request.app.state.db.excluir_evento(evento_id):
        apagar_arquivo(uploads, arquivo)
    return RedirectResponse("/admin", status_code=303)


@router.post("/midias/{midia_id}/excluir")
def excluir_midia(request: Request, midia_id: int):
    midia = request.app.state.db.excluir_midia(midia_id)
    if not midia:
        raise HTTPException(404, "Arquivo não encontrado.")
    apagar_arquivo(request.app.state.settings.uploads_dir, midia["arquivo"])
    return RedirectResponse(f"/admin/eventos/{midia['evento_id']}", status_code=303)


@router.post("/orcamentos/{orcamento_id}/lido")
def marcar_orcamento(request: Request, orcamento_id: int):
    request.app.state.db.alternar_lido(orcamento_id)
    return RedirectResponse("/admin#orcamentos", status_code=303)
