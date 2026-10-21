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


def test_banco_da_versao_antiga_da_erro_claro(tmp_path):
    import sqlite3

    caminho = tmp_path / "velho.db"
    conexao = sqlite3.connect(caminho)
    conexao.execute("CREATE TABLE orcamentos (id INTEGER PRIMARY KEY, nome TEXT, tipo_evento TEXT)")
    conexao.commit()
    conexao.close()
    with pytest.raises(RuntimeError, match="versão antiga"):
        Database(f"sqlite:///{caminho.as_posix()}")


def test_criado_em_usa_o_fuso_configurado(db, monkeypatch):
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    from app import relogio

    longe = ZoneInfo("Pacific/Kiritimati")  # UTC+14, diferente de qualquer fuso local
    monkeypatch.setattr(relogio, "FUSO", longe)
    db.criar_orcamento("Ana", "1199")
    criado = db.listar_orcamentos()[0]["criado_em"]
    esperado = datetime.now(longe).replace(tzinfo=None)
    assert abs(criado - esperado) < timedelta(minutes=2)


def test_migra_colunas_novas_sem_perder_dados(tmp_path):
    import sqlite3

    caminho = tmp_path / "anterior.db"
    conexao = sqlite3.connect(caminho)
    conexao.executescript(
        """
        CREATE TABLE eventos (id INTEGER PRIMARY KEY, titulo VARCHAR(200) NOT NULL, data DATE,
            local VARCHAR(200) NOT NULL, descricao TEXT NOT NULL, tipo VARCHAR(10) NOT NULL, criado_em DATETIME NOT NULL);
        CREATE TABLE midias (id INTEGER PRIMARY KEY, evento_id INTEGER NOT NULL, chave VARCHAR(200) NOT NULL,
            chave_miniatura VARCHAR(200), tipo VARCHAR(10) NOT NULL, criado_em DATETIME NOT NULL);
        CREATE TABLE orcamentos (id INTEGER PRIMARY KEY, nome VARCHAR(200) NOT NULL, telefone VARCHAR(40) NOT NULL,
            email VARCHAR(200) NOT NULL, data_evento DATE, local VARCHAR(200) NOT NULL, convidados INTEGER,
            pacote VARCHAR(50) NOT NULL, mensagem TEXT NOT NULL, lido BOOLEAN NOT NULL, criado_em DATETIME NOT NULL);
        INSERT INTO eventos VALUES (1, 'Antigo', '2026-01-10', '', '', 'realizado', '2026-01-10 10:00:00');
        """
    )
    conexao.commit()
    conexao.close()
    db = Database(f"sqlite:///{caminho.as_posix()}")
    evento = db.obter_evento(1)
    assert evento["titulo"] == "Antigo" and evento["hora_inicio"] is None and evento["titulo_publico"] is None
    assert db.listar_midias(1) == []


def test_criar_evento_com_horarios_e_dados_publicos(db):
    from datetime import time

    e = db.criar_evento(
        "Casamento da Ana", date(2026, 10, 31), "Atibaia", "", "futuro",
        hora_inicio=time(12), hora_fim=time(17), titulo_publico="Casamento no interior",
        categoria="Casamento", convidados=120, pacote="Angus",
    )
    salvo = db.obter_evento(e)
    assert (salvo["hora_inicio"], salvo["hora_fim"]) == (time(12), time(17))
    assert (salvo["titulo_publico"], salvo["categoria"], salvo["convidados"], salvo["pacote"]) == (
        "Casamento no interior", "Casamento", 120, "Angus")
    db.atualizar_evento(e, "Casamento da Ana", date(2026, 10, 31), "Atibaia", "", "futuro",
                        hora_inicio=time(13), hora_fim=time(18))
    assert db.obter_evento(e)["hora_inicio"] == time(13)


def test_horarios_entre_so_traz_data_e_horas(db):
    from datetime import time

    db.criar_evento("A", date(2026, 10, 31), "X", "", "futuro", hora_inicio=time(12), hora_fim=time(17))
    db.criar_evento("B", date(2026, 11, 2), "Y", "", "futuro", hora_inicio=time(19), hora_fim=time(23))
    db.criar_evento("C", date(2026, 10, 31), "Z", "", "realizado")
    linhas = db.horarios_entre(date(2026, 10, 1), date(2026, 10, 31))
    assert linhas == [{"data": date(2026, 10, 31), "hora_inicio": time(12), "hora_fim": time(17)}]


def test_eventos_entre_ordenado_por_data_e_hora(db):
    from datetime import time

    db.criar_evento("Noite", date(2026, 10, 31), "", "", "futuro", hora_inicio=time(19), hora_fim=time(23))
    db.criar_evento("Tarde", date(2026, 10, 31), "", "", "futuro", hora_inicio=time(12), hora_fim=time(17))
    db.criar_evento("Antes", date(2026, 10, 30), "", "", "realizado")
    titulos = [e["titulo"] for e in db.eventos_entre(date(2026, 10, 30), date(2026, 10, 31))]
    assert titulos == ["Antes", "Tarde", "Noite"]
    assert [e["titulo"] for e in db.eventos_entre(date(2026, 10, 30), date(2026, 10, 31), "futuro")] == ["Tarde", "Noite"]


def test_caixa_registra_e_excluir_evento_devolve_fotos(db):
    e = db.criar_evento("A", None, "", "", "realizado")
    db.registrar_caixa("a.jpg", "a.jpg:10:1", "importado", e)
    db.registrar_caixa("b.jpg", "b.jpg:20:2", "ignorado")
    assert db.assinaturas_tratadas() == {"a.jpg:10:1", "b.jpg:20:2"}
    db.registrar_caixa("b.jpg", "b.jpg:20:2", "importado", e)  # mesma assinatura: atualiza, não duplica
    assert db.assinaturas_tratadas() == {"a.jpg:10:1", "b.jpg:20:2"}
    db.excluir_evento(e)
    assert db.assinaturas_tratadas() == set()


def test_atualizar_alt(db):
    e = db.criar_evento("A", None, "", "", "realizado")
    m = db.adicionar_midia(e, "x.webp", "imagem")
    db.atualizar_alt(m, "Mesa de frios")
    assert db.listar_midias(e)[0]["alt"] == "Mesa de frios"
