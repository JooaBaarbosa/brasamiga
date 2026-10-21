import pytest

from app.config import BASE_DIR
from app.conteudo import Conteudo, ConteudoInvalido, carregar_site
from tests.fabrica import jpeg_bytes


def test_site_real_tem_os_quatro_pacotes_do_pdf():
    site = carregar_site(BASE_DIR / "conteudo")
    pacotes = {p["nome"]: p for p in site["pacotes"]}
    assert list(pacotes) == ["Senepol", "Devon", "Nelore", "Angus"]
    assert [p["preco"] for p in site["pacotes"]] == ["R$ 300", "R$ 100", "R$ 120", "R$ 150"]
    assert pacotes["Nelore"]["destaque"] is True
    assert sum(p["destaque"] for p in site["pacotes"]) == 1
    assert all(len(linha["valores"]) == 4 for linha in site["comparativo"])
    assert site["contato"]["whatsapp"] == "5511993433998"
    assert any(f["pergunta"] == "Qual região vocês atendem?" for f in site["faq"])


def test_toml_com_bom_e_acentos_carrega(tmp_path):
    (tmp_path / "site.toml").write_bytes('﻿[marca]\nnome = "Brasamiga Ação"\n'.encode("utf-8"))
    assert carregar_site(tmp_path)["marca"]["nome"] == "Brasamiga Ação"


def test_toml_com_erro_informa_a_linha(tmp_path):
    (tmp_path / "site.toml").write_text('[marca]\nnome = "Brasamiga\n', encoding="utf-8")
    with pytest.raises(ConteudoInvalido) as erro:
        carregar_site(tmp_path)
    assert erro.value.linha == 2


def test_toml_ausente(tmp_path):
    with pytest.raises(ConteudoInvalido, match="não encontrado"):
        carregar_site(tmp_path)


def test_galeria_gera_webp_em_cache_e_reaproveita(settings):
    pasta = settings.content_dir / "eventos-realizados"
    (pasta / "b.jpg").write_bytes(jpeg_bytes((2000, 1000), gps=True))
    (pasta / "a.JPEG").write_bytes(jpeg_bytes((800, 600)))
    (pasta / "leia.txt").write_text("ignorar")
    (pasta / "quebrada.jpg").write_bytes(b"nada")
    conteudo = Conteudo(settings.content_dir, settings.cache_dir)

    itens = conteudo.galeria()
    assert [i.tipo for i in itens] == ["imagem", "imagem"]
    assert all(i.url.startswith("/cache/galeria/") and i.url.endswith("-grande.webp") for i in itens)
    arquivo = settings.cache_dir / "galeria" / itens[1].url.rsplit("/", 1)[1]
    modificado = arquivo.stat().st_mtime_ns

    assert conteudo.galeria() == itens
    assert arquivo.stat().st_mtime_ns == modificado  # não refaz o que já está em cache


def test_capa_usa_a_foto_configurada_ou_a_primeira(settings):
    pasta = settings.content_dir / "eventos-realizados"
    (pasta / "a.jpg").write_bytes(jpeg_bytes((800, 600)))
    (pasta / "b.jpg").write_bytes(jpeg_bytes((2000, 1000), gps=True))
    conteudo = Conteudo(settings.content_dir, settings.cache_dir)
    escolhida = conteudo.capa("b.jpg")
    assert escolhida.url.endswith("-grande.webp")
    assert escolhida == conteudo.galeria()[1]
    assert conteudo.capa(None) == conteudo.galeria()[0]
    assert conteudo.capa("nao-existe.jpg") == conteudo.galeria()[0]


def test_capa_sem_fotos(settings):
    assert Conteudo(settings.content_dir, settings.cache_dir).capa("x.jpg") is None


def test_video_sem_versao_web_nao_aparece(settings):
    (settings.content_dir / "eventos-realizados" / "IMG_5038.MOV").write_bytes(b"\x00")
    assert Conteudo(settings.content_dir, settings.cache_dir).galeria() == []


def test_logo_e_pdfs(settings):
    (settings.content_dir / "cardapio" / "Brasamiga_Proposta_Comercial.pdf").write_bytes(b"%PDF-1.4")
    conteudo = Conteudo(settings.content_dir, settings.cache_dir)
    url = conteudo.logo_escuro("LOGO-03.png")
    assert url.startswith("/cache/logo/") and url.endswith(".png")
    assert conteudo.logo_escuro("nao-existe.png") is None
    assert conteudo.logo_escuro(None) is None
    assert conteudo.pdfs() == [
        {"url": "/conteudo/cardapio/Brasamiga_Proposta_Comercial.pdf", "nome": "Brasamiga Proposta Comercial"}
    ]
