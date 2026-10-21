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


def test_layout_minimalista_com_capa_e_quatro_cards(client, settings):
    (settings.content_dir / "eventos-realizados" / "40DB4488-618F-46D8-B957-EDCF4BEAF35E.jpg").write_bytes(jpeg_bytes())
    html = client.get("/").text
    assert 'class="capa-foto"' in html and "-grande.webp" in html
    for pacote in ("senepol", "devon", "nelore", "angus"):
        assert f'id="pacote-{pacote}"' in html, pacote
    assert "a partir de" in html.split('id="pacote-senepol"')[1].split("</article>")[0]
    assert "Só o churrasqueiro?" not in html
    assert "Valores por pessoa para 15 a 39 convidados" not in html  # texto de desconto removido
    assert 'class="comparativo"' not in html


def test_fotos_da_pasta_so_aparecem_como_capa(client, settings):
    pasta = settings.content_dir / "eventos-realizados"
    (pasta / "40DB4488-618F-46D8-B957-EDCF4BEAF35E.jpg").write_bytes(jpeg_bytes((800, 600)))
    (pasta / "outra.jpg").write_bytes(jpeg_bytes((600, 800)))
    html = client.get("/").text
    assert html.count("/cache/galeria/") == 1 and 'class="capa-foto"' in html
    assert 'class="foto"' not in html


def test_healthz(client):
    assert client.get("/healthz").json() == {"ok": True}


def test_capa_da_pasta_so_publica_versao_web(client, settings):
    (settings.content_dir / "eventos-realizados" / "IMG_0385.JPEG").write_bytes(jpeg_bytes(gps=True))  # vira a capa
    html = client.get("/").text
    arquivo = html.split('src="/cache/galeria/')[1].split('"')[0]
    assert client.get(f"/cache/galeria/{arquivo}").headers["content-type"] == "image/webp"
    assert client.get("/conteudo/eventos-realizados/IMG_0385.JPEG").status_code == 404
    assert client.get("/conteudo/site.toml").status_code == 404


def test_evento_futuro_nunca_mostra_nome_nem_local(client, settings):
    Database(settings.database_url).criar_evento("Formatura de Medicina", date(2099, 12, 12), "Campinas", "", "futuro")
    html = client.get("/").text
    assert "Formatura de Medicina" not in html and "Campinas" not in html
    assert 'id="agenda"' in html


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


def test_whatsapp_sem_aspas_no_toml_nao_derruba_o_site(client, settings):
    toml = settings.content_dir / "site.toml"
    toml.write_text(toml.read_text(encoding="utf-8").replace('"5511993433998"', "5511993433998"), encoding="utf-8")
    resp = client.get("/")
    assert resp.status_code == 200 and "https://wa.me/5511993433998" in resp.text


def test_pacote_sem_nome_nao_quebra_o_orcamento(client, settings):
    toml = settings.content_dir / "site.toml"
    toml.write_text(toml.read_text(encoding="utf-8").replace('nome = "Senepol"\n', "", 1), encoding="utf-8")
    resp = client.post("/orcamento", data={"nome": "Carla", "telefone": "1199"}, follow_redirects=False)
    assert resp.status_code == 303


def test_convidados_com_digito_estranho_nao_derruba(client, settings):
    resp = client.post("/orcamento", data={"nome": "Carla", "telefone": "1199", "convidados": "²"},
                       follow_redirects=False)
    assert resp.status_code == 303
    assert Database(settings.database_url).listar_orcamentos()[0]["convidados"] is None


def test_agenda_usa_o_dia_do_fuso_configurado(client, settings, monkeypatch):
    from app import relogio

    from datetime import time

    Database(settings.database_url).criar_evento("Festa de hoje", date(2099, 12, 12), "", "", "futuro",
                                                hora_inicio=time(12), hora_fim=time(17))
    monkeypatch.setattr(relogio, "hoje", lambda: date(2099, 12, 13))
    assert client.get("/api/agenda?mes=2099-12").json()["dias"] == {}
    monkeypatch.setattr(relogio, "hoje", lambda: date(2099, 12, 12))
    assert "2099-12-12" in client.get("/api/agenda?mes=2099-12").json()["dias"]


def test_site_toml_quebrado_mostra_linha(client, settings):
    (settings.content_dir / "site.toml").write_text('[marca]\nnome = "x\n', encoding="utf-8")
    resp = client.get("/")
    assert resp.status_code == 500
    assert "site.toml" in resp.text and "linha 2" in resp.text
