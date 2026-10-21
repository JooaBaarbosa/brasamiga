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

    outro = _id(_criar(client, titulo="Aniversário da Bia"))
    client.post(f"/admin/eventos/{outro}/excluir", auth=AUTH)
    assert list(settings.uploads_dir.iterdir()) == []
    assert "Aniversário da Bia" not in client.get("/").text


def test_orcamentos_no_painel_e_marcar_respondido(client, settings):
    client.post("/orcamento", data={"nome": "Carla", "telefone": "11988887777", "convidados": "80", "pacote": "Nelore"},
                follow_redirects=False)
    painel = client.get("/admin", auth=AUTH).text
    assert "Carla" in painel and "80 pessoas" in painel and "Nelore" in painel
    orcamento = Database(settings.database_url).listar_orcamentos()[0]
    client.post(f"/admin/orcamentos/{orcamento['id']}/lido", auth=AUTH)
    assert Database(settings.database_url).listar_orcamentos()[0]["lido"] is True
