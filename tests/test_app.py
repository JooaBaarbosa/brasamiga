import base64
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import BASE_DIR, Settings
from app.main import create_app

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
AUTH = ("admin", "segredo")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    conteudo = tmp_path / "conteudo"
    conteudo.mkdir()
    shutil.copy(BASE_DIR / "conteudo" / "site.toml", conteudo / "site.toml")
    return Settings(
        admin_user="admin",
        admin_password="segredo",
        data_dir=tmp_path / "data",
        content_dir=conteudo,
        max_upload_mb=1,
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


def criar_evento(client: TestClient, **campos) -> str:
    dados = {"titulo": "Casamento da Ana", "tipo": "realizado", "data": "2026-05-10", "local": "Atibaia"}
    dados.update(campos)
    resp = client.post(
        "/admin/eventos",
        data=dados,
        files=[("arquivos", ("festa.png", PNG, "image/png"))],
        auth=AUTH,
        follow_redirects=False,
    )
    assert resp.status_code == 303
    return resp.headers["location"]


def test_home_mostra_marca_cardapio_e_cta(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Brasamiga" in resp.text
    assert "Picanha" in resp.text
    assert "Pedir orçamento" in resp.text
    assert "https://wa.me/5511999999999" in resp.text


def test_admin_exige_senha(client):
    assert client.get("/admin").status_code == 401
    assert client.get("/admin", auth=("admin", "errada")).status_code == 401
    assert client.get("/admin", auth=AUTH).status_code == 200


def test_admin_desligado_sem_senha_configurada(settings):
    sem_senha = Settings(**{**settings.__dict__, "admin_password": ""})
    resp = TestClient(create_app(sem_senha)).get("/admin", auth=("admin", ""))
    assert resp.status_code == 503


def test_post_de_outro_site_e_bloqueado(client):
    resp = client.post(
        "/admin/eventos", data={"titulo": "x", "tipo": "realizado"}, auth=AUTH, headers={"origin": "https://malicioso.com"}
    )
    assert resp.status_code == 403


def test_evento_realizado_aparece_na_galeria(client, settings):
    criar_evento(client)
    arquivos = list(settings.uploads_dir.iterdir())
    assert len(arquivos) == 1 and arquivos[0].suffix == ".png"

    home = client.get("/").text
    assert "Casamento da Ana" in home
    assert f"/uploads/{arquivos[0].name}" in home
    assert client.get(f"/uploads/{arquivos[0].name}").content == PNG


def test_evento_futuro_aparece_na_agenda_e_passado_some(client):
    criar_evento(client, titulo="Formatura 2099", tipo="futuro", data="2099-12-01")
    criar_evento(client, titulo="Festa antiga", tipo="futuro", data="2001-01-01")
    home = client.get("/").text
    assert "Próximos eventos" in home
    assert "Formatura 2099" in home
    assert "Festa antiga" not in home


def test_upload_com_formato_invalido_e_recusado(client, settings):
    local = criar_evento(client)
    evento_id = local.split("/")[3].split("?")[0]
    resp = client.post(
        f"/admin/eventos/{evento_id}/midias",
        files=[("arquivos", ("virus.exe", b"MZ", "application/octet-stream"))],
        auth=AUTH,
    )
    assert resp.status_code == 400
    assert "virus.exe" in resp.text
    assert len(list(settings.uploads_dir.iterdir())) == 1


def test_upload_acima_do_limite_e_recusado(client, settings):
    local = criar_evento(client)
    evento_id = local.split("/")[3].split("?")[0]
    grande = b"0" * (2 * 1024 * 1024)
    resp = client.post(
        f"/admin/eventos/{evento_id}/midias", files=[("arquivos", ("grande.mp4", grande, "video/mp4"))], auth=AUTH
    )
    assert resp.status_code == 400
    assert len(list(settings.uploads_dir.iterdir())) == 1


def test_excluir_evento_apaga_arquivos(client, settings):
    local = criar_evento(client)
    evento_id = local.split("/")[3].split("?")[0]
    client.post(f"/admin/eventos/{evento_id}/excluir", auth=AUTH)
    assert list(settings.uploads_dir.iterdir()) == []
    assert "Casamento da Ana" not in client.get("/").text


def test_pedido_de_orcamento_chega_no_painel(client):
    resp = client.post(
        "/orcamento",
        data={"nome": "Carla", "telefone": "11988887777", "convidados": "80", "tipo_evento": "Casamentos"},
        follow_redirects=False,
    )
    assert resp.status_code == 303 and "enviado=1" in resp.headers["location"]
    painel = client.get("/admin", auth=AUTH).text
    assert "Carla" in painel and "80 pessoas" in painel


def test_orcamento_sem_telefone_volta_com_erro(client):
    resp = client.post("/orcamento", data={"nome": "Carla"}, follow_redirects=False)
    assert "erro=1" in resp.headers["location"]
    assert "Preencha seu nome" in client.get("/?erro=1").text


def test_fotos_da_pasta_conteudo_entram_no_site(client, settings):
    (settings.content_dir / "logo" / "logo.png").write_bytes(PNG)
    (settings.content_dir / "eventos-realizados" / "festa junina.png").write_bytes(PNG)
    (settings.content_dir / "cardapio" / "cardapio-completo.pdf").write_bytes(b"%PDF-1.4")

    home = client.get("/").text
    assert "/conteudo/logo/logo.png" in home
    assert "/conteudo/eventos-realizados/festa%20junina.png" in home
    assert "/conteudo/cardapio/cardapio-completo.pdf" in home
    assert client.get("/conteudo/eventos-realizados/festa%20junina.png").status_code == 200
    assert client.get("/conteudo/site.toml").status_code == 404
