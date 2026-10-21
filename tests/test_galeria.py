import html as html_lib
import re
from datetime import date
from html.parser import HTMLParser

import pytest

from app.db import Database
from tests.fabrica import jpeg_bytes


@pytest.fixture
def db(settings):
    return Database(settings.database_url)


def _evento(db, settings, titulo_publico="Casamento no interior", fotos=2, **extras):
    dados = {"categoria": "Casamento", "convidados": 120, "pacote": "Angus"} | extras
    e = db.criar_evento("NOME-SECRETO", date(2026, 5, 10), "LOCAL-SECRETO", "DESC-SECRETA", "realizado",
                        titulo_publico=titulo_publico, **dados)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    for i in range(fotos):
        chave = f"{e}-{i}.webp"
        (settings.uploads_dir / chave).write_bytes(b"x")
        db.adicionar_midia(e, chave, "imagem", chave)
    return e


def test_evento_sem_midia_nao_aparece(client, db, settings):
    _evento(db, settings, "Evento sem fotos", fotos=0)
    assert "Evento sem fotos" not in client.get("/").text


def test_foto_solta_da_pasta_nao_aparece(client, settings):
    pasta = settings.content_dir / "eventos-realizados"
    (pasta / "40DB4488-618F-46D8-B957-EDCF4BEAF35E.jpg").write_bytes(jpeg_bytes())  # capa
    (pasta / "solta.jpg").write_bytes(jpeg_bytes((640, 480)))
    pagina = client.get("/").text
    assert pagina.count("/cache/galeria/") == 1  # só a capa
    assert 'class="evento-card"' not in pagina


def test_card_mostra_dados_publicos_e_esconde_os_reais(client, db, settings):
    _evento(db, settings)
    pagina = client.get("/").text
    for segredo in ("NOME-SECRETO", "LOCAL-SECRETO", "DESC-SECRETA"):
        assert segredo not in pagina
    assert "Casamento · 120 convidados" in pagina
    assert "Casamento no interior" in pagina
    assert "Maio 2026 · Pacote Angus" in pagina


def test_busca_normalizada_e_escapada(client, db, settings):
    _evento(db, settings, 'Festa da Ação & Cia "VIP"', categoria="Outros", pacote=None)
    pagina = client.get("/").text
    atributo = re.search(r'data-busca="([^"]*)"', pagina).group(1)
    assert html_lib.unescape(atributo) == 'festa da acao & cia "vip" outros'
    assert re.search(r'data-categoria="([^"]*)"', pagina).group(1) == "outros"


class _Imagens(HTMLParser):
    def __init__(self):
        super().__init__()
        self.imgs = []

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            self.imgs.append(dict(attrs))


def test_todas_as_imagens_publicas_tem_alt(client, db, settings):
    (settings.content_dir / "eventos-realizados" / "40DB4488-618F-46D8-B957-EDCF4BEAF35E.jpg").write_bytes(jpeg_bytes())
    _evento(db, settings)
    leitor = _Imagens()
    leitor.feed(client.get("/").text)
    assert leitor.imgs and all("alt" in img for img in leitor.imgs)


def test_alt_automatico_e_manual(client, db, settings):
    e = _evento(db, settings)
    pagina = client.get("/").text
    assert 'alt="Foto 1 de 2 do evento: Casamento no interior"' in pagina
    db.atualizar_alt(db.listar_midias(e)[1]["id"], "Mesa de frios")
    assert 'alt="Mesa de frios"' in client.get("/").text


def test_filtros_vem_do_site_toml(client, db, settings):
    _evento(db, settings)
    pagina = client.get("/").text
    for chip in ("Aniversário", "Casamento", "Corporativo", "Outros", "15–39", "40–59", "60+"):
        assert f">{chip}<" in pagina, chip
    assert 'aria-label="Buscar eventos"' in pagina
    assert "/static/js/galeria.js" in pagina and "/static/js/carrossel.js" in pagina
