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


def test_layout_minimalista_com_capa_e_senepol_como_nota(client, settings):
    (settings.content_dir / "eventos-realizados" / "40DB4488-618F-46D8-B957-EDCF4BEAF35E.jpg").write_bytes(jpeg_bytes())
    html = client.get("/").text
    assert 'class="capa-foto"' in html and "-grande.webp" in html
    assert "Só o churrasqueiro?" in html
    assert 'id="pacote-senepol"' not in html
    assert 'id="pacote-nelore"' in html
    assert 'class="comparativo"' not in html


def test_foto_da_capa_nao_se_repete_na_galeria(client, settings):
    pasta = settings.content_dir / "eventos-realizados"
    (pasta / "40DB4488-618F-46D8-B957-EDCF4BEAF35E.jpg").write_bytes(jpeg_bytes((800, 600)))
    (pasta / "outra.jpg").write_bytes(jpeg_bytes((600, 800)))
    html = client.get("/").text
    capa_mini = html.split('class="capa-foto" src="')[1].split('"')[0].replace("-grande.webp", "-mini.webp")
    assert capa_mini not in html
    assert html.count('class="foto ') == 1


def test_healthz(client):
    assert client.get("/healthz").json() == {"ok": True}


def test_galeria_da_pasta_so_publica_versao_web(client, settings):
    (settings.content_dir / "eventos-realizados" / "IMG_0001.JPEG").write_bytes(jpeg_bytes())  # vira a capa
    (settings.content_dir / "eventos-realizados" / "IMG_0385.JPEG").write_bytes(jpeg_bytes(gps=True))
    html = client.get("/").text
    assert "/cache/galeria/" in html and "-mini.webp" in html
    arquivo = html.split('src="/cache/galeria/')[1].split('"')[0]
    assert client.get(f"/cache/galeria/{arquivo}").headers["content-type"] == "image/webp"
    assert client.get("/conteudo/eventos-realizados/IMG_0385.JPEG").status_code == 404
    assert client.get("/conteudo/site.toml").status_code == 404


def test_agenda_so_aparece_com_evento_futuro(client, settings):
    assert "Próximos eventos" not in client.get("/").text
    db = Database(settings.database_url)
    db.criar_evento("Formatura de Medicina", date(2099, 12, 12), "Campinas", "", "futuro")
    db.criar_evento("Já passou", date(2001, 1, 1), "", "", "futuro")
    html = client.get("/").text
    assert "Próximos eventos" in html and "Formatura de Medicina" in html
    assert "Já passou" not in html


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

    Database(settings.database_url).criar_evento("Festa de hoje", date(2099, 12, 12), "", "", "futuro")
    monkeypatch.setattr(relogio, "hoje", lambda: date(2099, 12, 13))
    assert "Festa de hoje" not in client.get("/").text
    monkeypatch.setattr(relogio, "hoje", lambda: date(2099, 12, 12))
    assert "Festa de hoje" in client.get("/").text


def test_site_toml_quebrado_mostra_linha(client, settings):
    (settings.content_dir / "site.toml").write_text('[marca]\nnome = "x\n', encoding="utf-8")
    resp = client.get("/")
    assert resp.status_code == 500
    assert "site.toml" in resp.text and "linha 2" in resp.text
