from datetime import date, time

import pytest

from app import relogio
from app.db import Database
from tests.fabrica import AUTH


@pytest.fixture
def db(settings, monkeypatch):
    monkeypatch.setattr(relogio, "hoje", lambda: date(2026, 10, 21))
    return Database(settings.database_url)


def _futuro(db, dia, inicio, fim, titulo="NOME-SECRETO"):
    return db.criar_evento(titulo, dia, "LOCAL-SECRETO", "DESC-SECRETA", "futuro", hora_inicio=inicio, hora_fim=fim)


def test_api_agenda_publica_estrutura(client, db):
    _futuro(db, date(2026, 10, 31), time(19), time(23))
    _futuro(db, date(2026, 10, 31), time(12), time(17))
    db.criar_evento("REALIZADO-SECRETO", date(2026, 10, 31), "", "", "realizado")
    resp = client.get("/api/agenda?mes=2026-10")
    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["mes"] == "2026-10" and corpo["hoje"] == "2026-10-21"
    assert (corpo["anterior"], corpo["proximo"]) == ("2026-09", "2026-11")
    assert corpo["dias"] == {
        "2026-10-31": [{"inicio": "12:00", "fim": "17:00"}, {"inicio": "19:00", "fim": "23:00"}]
    }
    assert "SECRET" not in resp.text


def test_api_agenda_ignora_dias_ja_passados(client, db):
    _futuro(db, date(2026, 10, 5), time(12), time(17))
    assert client.get("/api/agenda?mes=2026-10").json()["dias"] == {}
    assert client.get("/api/agenda?mes=2026-09").json()["dias"] == {}


def test_api_agenda_mes_invalido_usa_atual(client, db):
    assert client.get("/api/agenda?mes=banana").json()["mes"] == "2026-10"
    assert client.get("/api/agenda").json()["mes"] == "2026-10"


def test_api_agenda_bordas_do_calendario(client, db):
    resp = client.get("/api/agenda?mes=9999-12")
    assert resp.status_code == 200 and resp.json()["proximo"] is None


def test_api_agenda_evento_noturno_no_dia_de_inicio(client, db):
    _futuro(db, date(2026, 10, 31), time(20), time(2))
    assert client.get("/api/agenda?mes=2026-10").json()["dias"] == {"2026-10-31": [{"inicio": "20:00", "fim": "02:00"}]}


def test_secao_agenda_usa_api_e_esconde_nomes(client, db):
    _futuro(db, date(2026, 10, 31), time(12), time(17))
    html = client.get("/").text
    assert 'data-api="/api/agenda"' in html and 'data-modo="publico"' in html
    assert "Próximos eventos" not in html
    assert "SECRET" not in html
    assert "/static/js/agenda.js" in html


def test_admin_tem_calendario(client, db):
    html = client.get("/admin", auth=AUTH).text
    assert 'data-api="/admin/api/agenda"' in html and 'data-modo="admin"' in html


def test_api_agenda_admin_exige_senha_e_traz_nome(client, db):
    ev = _futuro(db, date(2026, 10, 31), time(12), time(17), titulo="Casamento da Ana")
    assert client.get("/admin/api/agenda?mes=2026-10").status_code == 401
    dias = client.get("/admin/api/agenda?mes=2026-10", auth=AUTH).json()["dias"]
    assert dias["2026-10-31"] == [
        {"inicio": "12:00", "fim": "17:00", "id": ev, "titulo": "Casamento da Ana", "local": "LOCAL-SECRETO", "tipo": "futuro"}
    ]
