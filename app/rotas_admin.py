import tempfile
from datetime import date, time, timedelta
from pathlib import Path
from secrets import compare_digest
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app import agenda, midia, relogio
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


CATEGORIAS_PADRAO = ["Aniversário", "Casamento", "Corporativo", "Outros"]
CAMPOS_FORM = (
    "titulo", "tipo", "data", "hora_inicio", "hora_fim", "local", "descricao",
    "titulo_publico", "categoria", "convidados", "pacote",
)


class ErroFormulario(Exception):
    def __init__(self, mensagens: list[str]) -> None:
        super().__init__("; ".join(mensagens))
        self.mensagens = mensagens


def categorias(site: dict) -> list[str]:
    lista = site.get("galeria", {}).get("categorias") if isinstance(site.get("galeria"), dict) else None
    validas = [c for c in lista or [] if isinstance(c, str) and c.strip()]
    return validas or CATEGORIAS_PADRAO


def nomes_pacotes(site: dict) -> list[str]:
    return [p["nome"] for p in site.get("pacotes", []) if p.get("nome")]


def _data(texto: str) -> date | None:
    try:
        return date.fromisoformat(texto) if texto else None
    except ValueError:
        return None


def _hora(texto: str) -> time | None:
    try:
        return time.fromisoformat(texto) if texto else None
    except ValueError:
        return None


def _campos_evento(form: dict[str, str], site: dict) -> dict:
    """Valida o formulário de evento; junta todos os problemas numa ErroFormulario."""
    erros = []
    titulo = form.get("titulo", "").strip()
    tipo = form.get("tipo", "")
    if not titulo:
        erros.append("Dê um nome ao evento.")
    if tipo not in TIPOS:
        erros.append("Escolha se o evento já foi realizado ou ainda vai acontecer.")
    quando = _data(form.get("data", "").strip())
    inicio, fim = _hora(form.get("hora_inicio", "").strip()), _hora(form.get("hora_fim", "").strip())
    if tipo == "futuro":
        if not quando:
            erros.append("Informe a data do evento.")
        if not inicio or not fim:
            erros.append("Informe o início e o fim do evento.")
    if inicio and fim and inicio == fim:
        erros.append("O fim do evento precisa ser diferente do início.")
    titulo_publico = form.get("titulo_publico", "").strip()[:120]
    if tipo == "realizado" and not titulo_publico:
        erros.append("Escreva o título para o site (o que o cliente vê).")
    convidados_texto = form.get("convidados", "").strip()
    convidados = None
    if convidados_texto.lstrip("-").isdecimal():
        convidados = int(convidados_texto)
        if not 1 <= convidados <= 5000:
            erros.append("Informe entre 1 e 5000 convidados.")
    if erros:
        raise ErroFormulario(erros)
    categoria = form.get("categoria", "")
    pacote = form.get("pacote", "")
    return {
        "titulo": titulo[:200],
        "data": quando,
        "local": form.get("local", "").strip()[:200],
        "descricao": form.get("descricao", "").strip()[:3000],
        "tipo": tipo,
        "hora_inicio": inicio,
        "hora_fim": fim,
        "titulo_publico": titulo_publico or None,
        "categoria": categoria if categoria in categorias(site) else "Outros",
        "convidados": convidados,
        "pacote": pacote if pacote in nomes_pacotes(site) else None,
    }


def _horas_br(duracao: timedelta) -> str:
    horas = duracao.total_seconds() / 3600
    return f"{horas:g}".replace(".", ",") + "h"


def _checar_conflito(db, campos: dict, evento_id: int | None, site: dict) -> None:
    if campos["tipo"] != "futuro":
        return
    montagem, folga = agenda.parametros(site)
    dia = campos["data"]
    existentes = db.eventos_entre(dia - timedelta(days=1), dia + timedelta(days=1), "futuro")
    novo = {"id": evento_id, "data": dia, "hora_inicio": campos["hora_inicio"], "hora_fim": campos["hora_fim"]}
    conflitantes = agenda.conflitos(novo, existentes, montagem, folga)
    if not conflitantes:
        return

    def horario(e: dict) -> str:
        if e["hora_inicio"] is None or e["hora_fim"] is None:
            return "horário a confirmar"
        return f"{e['hora_inicio']:%H:%M}–{e['hora_fim']:%H:%M}"

    raise ErroFormulario([
        f'Esse horário conflita com "{e["titulo"]}" ({e["data"]:%d/%m}, {horario(e)}). '
        f"Entre um evento e outro é preciso deixar {_horas_br(montagem)} de montagem e {_horas_br(folga)} de folga."
        for e in conflitantes
    ])


def _form_de_evento(evento: dict) -> dict[str, str]:
    """Valores de um evento salvo no formato do formulário (tudo texto)."""
    form = {campo: "" if evento.get(campo) is None else str(evento[campo]) for campo in CAMPOS_FORM}
    for campo in ("hora_inicio", "hora_fim"):
        if evento.get(campo):
            form[campo] = evento[campo].strftime("%H:%M")
    return form


def _opcoes(site: dict) -> dict:
    return {"categorias": categorias(site), "pacotes": nomes_pacotes(site)}


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


def _pagina_evento(request: Request, evento_id: int, erros=None, avisos=None, salvo=False,
                   erros_form=None, form=None):
    estado = request.app.state
    evento = estado.db.obter_evento(evento_id)
    if not evento:
        raise HTTPException(404, "Evento não encontrado.")
    midias = [
        {**m, "url": estado.storage.url(m["chave_miniatura"] or m["chave"]), "url_original": estado.storage.url(m["chave"])}
        for m in estado.db.listar_midias(evento_id)
    ]
    contexto = {
        "evento": evento, "midias": midias, "erros": erros or [], "avisos": avisos or [], "salvo": salvo,
        "erros_form": erros_form or [], "form": form or _form_de_evento(evento),
        "opcoes": _opcoes(estado.conteudo.site()),
    }
    return templates.TemplateResponse(
        request, "admin/evento.html", contexto, status_code=400 if (erros or erros_form) else 200
    )


def _pagina_painel(request: Request, erros_form=None, form=None):
    db = request.app.state.db
    contexto = {
        "futuros": db.listar_eventos("futuro"),
        "realizados": db.listar_eventos("realizado"),
        "orcamentos": db.listar_orcamentos(),
        "erros_form": erros_form or [],
        "form": form or {"tipo": "realizado"},
        "opcoes": _opcoes(request.app.state.conteudo.site()),
    }
    return templates.TemplateResponse(request, "admin/index.html", contexto, status_code=400 if erros_form else 200)


async def _form_enviado(request: Request) -> dict[str, str]:
    dados = await request.form()
    form = {campo: str(dados.get(campo, "")) for campo in CAMPOS_FORM}
    form["tipo"] = form["tipo"] or "realizado"
    return form


@router.get("/api/agenda")
def api_agenda_admin(request: Request, mes: str | None = None):
    hoje = relogio.hoje()
    inicio = agenda.mes_ou_atual(mes, hoje)
    linhas = request.app.state.db.eventos_entre(inicio, agenda.fim_do_mes(inicio))
    return agenda.resposta(inicio, hoje, agenda.mapa_dias(linhas, ("id", "titulo", "local", "tipo")))


@router.get("", response_class=HTMLResponse)
def painel(request: Request):
    return _pagina_painel(request)


@router.post("/eventos")
async def criar_evento(request: Request, arquivos: list[UploadFile] = File(default=[])):
    form = await _form_enviado(request)
    site = request.app.state.conteudo.site()
    try:
        campos = _campos_evento(form, site)
        _checar_conflito(request.app.state.db, campos, None, site)
    except ErroFormulario as erro:
        return _pagina_painel(request, erros_form=erro.mensagens, form=form)
    evento_id = request.app.state.db.criar_evento(**campos)
    erros, avisos = await _salvar_midias(request, evento_id, arquivos)
    if erros or avisos:
        return _pagina_evento(request, evento_id, erros, avisos)
    return RedirectResponse(f"/admin/eventos/{evento_id}?salvo=1", status_code=303)


@router.get("/eventos/{evento_id}", response_class=HTMLResponse)
def ver_evento(request: Request, evento_id: int, salvo: bool = False):
    return _pagina_evento(request, evento_id, salvo=salvo)


@router.post("/eventos/{evento_id}")
async def atualizar_evento(request: Request, evento_id: int):
    db = request.app.state.db
    if not db.obter_evento(evento_id):
        raise HTTPException(404, "Evento não encontrado.")
    form = await _form_enviado(request)
    site = request.app.state.conteudo.site()
    try:
        campos = _campos_evento(form, site)
        _checar_conflito(db, campos, evento_id, site)
    except ErroFormulario as erro:
        return _pagina_evento(request, evento_id, erros_form=erro.mensagens, form=form)
    db.atualizar_evento(evento_id, **campos)
    return RedirectResponse(f"/admin/eventos/{evento_id}?salvo=1", status_code=303)


@router.post("/midias/{midia_id}/alt")
def salvar_alt(request: Request, midia_id: int, alt: str = Form("")):
    db = request.app.state.db
    linha = db.obter_midia(midia_id)
    if not linha:
        raise HTTPException(404, "Arquivo não encontrado.")
    db.atualizar_alt(midia_id, alt.strip()[:200])
    return RedirectResponse(f"/admin/eventos/{linha['evento_id']}#midia-{midia_id}", status_code=303)


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
