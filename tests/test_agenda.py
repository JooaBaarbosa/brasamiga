from datetime import date, datetime, time, timedelta

from app import agenda

H = timedelta(hours=1)


def _ev(id_, dia, inicio=None, fim=None):
    return {"id": id_, "data": dia, "hora_inicio": inicio, "hora_fim": fim}


def test_janela_simples():
    assert agenda.janela_evento(date(2026, 10, 31), time(12), time(17)) == agenda.Janela(
        datetime(2026, 10, 31, 12), datetime(2026, 10, 31, 17))


def test_janela_passa_da_meia_noite():
    assert agenda.janela_evento(date(2026, 10, 31), time(20), time(2)).fim == datetime(2026, 11, 1, 2)


def test_janela_sem_horas_e_o_dia_inteiro():
    assert agenda.janela_evento(date(2026, 10, 31), None, None) == agenda.Janela(
        datetime(2026, 10, 31), datetime(2026, 11, 1))


def test_blocos_que_encostam_nao_conflitam():
    existente = _ev(1, date(2026, 10, 31), time(12), time(17))
    novo = _ev(None, date(2026, 10, 31), time(19), time(23))
    assert agenda.conflitos(novo, [existente], H, H) == []


def test_um_minuto_de_sobreposicao_conflita():
    existente = _ev(1, date(2026, 10, 31), time(12), time(17))
    novo = _ev(None, date(2026, 10, 31), time(18, 59), time(23))
    assert agenda.conflitos(novo, [existente], H, H) == [existente]


def test_evento_noturno_conflita_com_manha_seguinte():
    existente = _ev(1, date(2026, 10, 31), time(20), time(2))  # bloqueia até 03:00 de 01/11
    novo = _ev(None, date(2026, 11, 1), time(3, 30), time(8))  # montagem a partir de 02:30
    assert agenda.conflitos(novo, [existente], H, H) == [existente]


def test_edicao_ignora_o_proprio_evento():
    existente = _ev(7, date(2026, 10, 31), time(12), time(17))
    assert agenda.conflitos(_ev(7, date(2026, 10, 31), time(12), time(17)), [existente], H, H) == []


def test_evento_sem_horas_bloqueia_o_dia():
    existente = _ev(1, date(2026, 10, 31))
    assert agenda.conflitos(_ev(None, date(2026, 10, 31), time(8), time(10)), [existente], H, H) == [existente]
    assert agenda.conflitos(_ev(None, date(2026, 11, 1), time(8), time(10)), [existente], H, H) == []


def test_parametros_do_site_toml():
    assert agenda.parametros({}) == (H, H)
    assert agenda.parametros({"agenda": {"montagem_horas": 2, "folga_horas": 0.5}}) == (2 * H, H / 2)
    assert agenda.parametros({"agenda": {"montagem_horas": "x", "folga_horas": -1}}) == (H, H)
