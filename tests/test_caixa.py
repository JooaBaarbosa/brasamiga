import io

import pytest
from PIL import Image

from app.db import Database
from tests.fabrica import AUTH, jpeg_bytes

CAPA = "40DB4488-618F-46D8-B957-EDCF4BEAF35E.jpg"  # foto_capa do site.toml


@pytest.fixture
def pasta(settings):
    p = settings.content_dir / "eventos-realizados"
    (p / CAPA).write_bytes(jpeg_bytes())
    (p / "festa 1.jpg").write_bytes(jpeg_bytes((1200, 800), gps=True))
    (p / "festa 2.jpg").write_bytes(jpeg_bytes((800, 1200)))
    return p


@pytest.fixture
def evento(settings):
    return Database(settings.database_url).criar_evento(
        "Casamento da Ana", None, "", "", "realizado", titulo_publico="Casamento no interior")


def _pendentes(client):
    html = client.get("/admin", auth=AUTH).text
    return [nome for nome in ("festa 1.jpg", "festa 2.jpg", "quebrada.jpg", CAPA) if f'value="{nome}"' in html]


def test_lista_pendentes_sem_foto_capa(client, pasta):
    html = client.get("/admin", auth=AUTH).text
    assert "Fotos sem evento (2)" in html
    assert _pendentes(client) == ["festa 1.jpg", "festa 2.jpg"]
    assert 'alt="Foto sem evento: festa 1.jpg"' in html


def test_adicionar_ao_evento_importa_sem_gps(client, settings, pasta, evento):
    resp = client.post("/admin/caixa/adicionar", data={"arquivos": ["festa 1.jpg"], "evento_id": str(evento)},
                       auth=AUTH, follow_redirects=False)
    assert resp.status_code == 303
    midias = Database(settings.database_url).listar_midias(evento)
    assert len(midias) == 1
    salvo = Image.open(settings.uploads_dir / midias[0]["chave"])
    assert salvo.format == "WEBP" and len(salvo.getexif()) == 0
    assert _pendentes(client) == ["festa 2.jpg"]


def test_ignorar_tira_da_caixa(client, pasta):
    client.post("/admin/caixa/ignorar", data={"arquivos": ["festa 2.jpg"]}, auth=AUTH)
    assert _pendentes(client) == ["festa 1.jpg"]


def test_arquivo_alterado_volta_para_a_caixa(client, pasta):
    client.post("/admin/caixa/ignorar", data={"arquivos": ["festa 2.jpg"]}, auth=AUTH)
    (pasta / "festa 2.jpg").write_bytes(jpeg_bytes((640, 480)))
    assert "festa 2.jpg" in _pendentes(client)


def test_arquivo_invalido_fica_na_caixa_com_erro(client, settings, pasta, evento):
    (pasta / "quebrada.jpg").write_bytes(b"nada")
    resp = client.post("/admin/caixa/adicionar",
                       data={"arquivos": ["festa 1.jpg", "quebrada.jpg"], "evento_id": str(evento)}, auth=AUTH)
    assert resp.status_code == 400 and "quebrada.jpg" in resp.text
    assert len(Database(settings.database_url).listar_midias(evento)) == 1
    assert "quebrada.jpg" in _pendentes(client) and "festa 1.jpg" not in _pendentes(client)


@pytest.mark.parametrize("nome", ["../../.env", "nao-existe.jpg", CAPA])
def test_nome_forjado_e_recusado(client, settings, pasta, evento, nome):
    resp = client.post("/admin/caixa/adicionar", data={"arquivos": [nome], "evento_id": str(evento)}, auth=AUTH)
    assert resp.status_code == 400
    assert not settings.uploads_dir.exists() or list(settings.uploads_dir.iterdir()) == []


def test_evento_precisa_existir_e_ser_realizado(client, settings, pasta):
    futuro = Database(settings.database_url).criar_evento("F", None, "", "", "futuro")
    for evento_id in ("999", str(futuro)):
        resp = client.post("/admin/caixa/adicionar", data={"arquivos": ["festa 1.jpg"], "evento_id": evento_id},
                           auth=AUTH)
        assert resp.status_code == 400


def test_excluir_evento_devolve_fotos(client, pasta, evento):
    client.post("/admin/caixa/adicionar", data={"arquivos": ["festa 1.jpg"], "evento_id": str(evento)}, auth=AUTH)
    client.post(f"/admin/eventos/{evento}/excluir", auth=AUTH)
    assert "festa 1.jpg" in _pendentes(client)


def test_caixa_exige_senha(client, pasta):
    assert client.post("/admin/caixa/ignorar", data={"arquivos": ["festa 1.jpg"]}).status_code == 401
