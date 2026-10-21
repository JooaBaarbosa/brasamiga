from datetime import date

import pytest

from app.db import Database


@pytest.fixture
def db(settings):
    return Database(settings.database_url)


def test_eventos_realizados_mais_recentes_primeiro(db):
    db.criar_evento("Antigo", date(2025, 1, 10), "", "", "realizado")
    db.criar_evento("Recente", date(2026, 5, 10), "Atibaia", "", "realizado")
    db.criar_evento("Sem data", None, "", "", "realizado")
    titulos = [e["titulo"] for e in db.listar_eventos("realizado")]
    assert titulos == ["Recente", "Antigo", "Sem data"]


def test_futuros_filtra_passados_e_ordena(db):
    db.criar_evento("Longe", date(2099, 12, 1), "", "", "futuro")
    db.criar_evento("Perto", date(2099, 1, 1), "", "", "futuro")
    db.criar_evento("Passou", date(2001, 1, 1), "", "", "futuro")
    db.criar_evento("A confirmar", None, "", "", "futuro")
    titulos = [e["titulo"] for e in db.listar_eventos("futuro", a_partir_de=date(2026, 10, 21))]
    assert titulos == ["Perto", "Longe", "A confirmar"]


def test_tipo_invalido_e_recusado(db):
    with pytest.raises(Exception):
        db.criar_evento("X", None, "", "", "talvez")


def test_midias_contagem_agrupamento_e_cascata(db):
    a = db.criar_evento("A", None, "", "", "realizado")
    b = db.criar_evento("B", None, "", "", "realizado")
    db.adicionar_midia(a, "1.webp", "imagem", "1-mini.webp")
    db.adicionar_midia(a, "2.mp4", "video")
    db.adicionar_midia(b, "3.webp", "imagem", "3-mini.webp")
    contagem = {e["titulo"]: e["total_midias"] for e in db.listar_eventos("realizado")}
    assert contagem == {"A": 2, "B": 1}
    agrupado = db.midias_por_evento([a, b])
    assert [m["chave"] for m in agrupado[a]] == ["1.webp", "2.mp4"]
    assert db.midias_por_evento([]) == {}

    apagadas = db.excluir_evento(a)
    assert {m["chave"] for m in apagadas} == {"1.webp", "2.mp4"}
    assert db.listar_midias(a) == []
    assert db.obter_evento(a) is None


def test_atualizar_e_excluir_midia(db):
    e = db.criar_evento("A", None, "", "", "futuro")
    db.atualizar_evento(e, "A2", date(2027, 1, 1), "Moema", "Desc", "realizado")
    evento = db.obter_evento(e)
    assert (evento["titulo"], evento["data"], evento["tipo"]) == ("A2", date(2027, 1, 1), "realizado")
    m = db.adicionar_midia(e, "x.webp", "imagem")
    assert db.excluir_midia(m)["chave"] == "x.webp"
    assert db.excluir_midia(m) is None


def test_orcamentos_novos_primeiro_e_alternar_lido(db):
    primeiro = db.criar_orcamento("Ana", "1199", pacote="Nelore", convidados=80, data_evento=date(2026, 12, 12))
    segundo = db.criar_orcamento("Bia", "1188")
    db.alternar_lido(segundo)
    nomes = [o["nome"] for o in db.listar_orcamentos()]
    assert nomes == ["Ana", "Bia"]
    db.alternar_lido(segundo)
    assert [o["nome"] for o in db.listar_orcamentos()] == ["Bia", "Ana"]
    assert db.listar_orcamentos()[1]["convidados"] == 80
    assert primeiro != segundo
