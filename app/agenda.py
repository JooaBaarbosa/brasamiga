"""Agenda: quando um evento ocupa a equipe e se dois eventos cabem no mesmo dia.

Cada evento bloqueia do início menos a montagem até o fim mais a folga de deslocamento.
Blocos que só encostam não conflitam.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

PADRAO_HORAS = 1


@dataclass(frozen=True)
class Janela:
    inicio: datetime
    fim: datetime


def janela_evento(data: date, hora_inicio: time | None, hora_fim: time | None) -> Janela:
    """Sem horas, o evento ocupa o dia inteiro; fim antes do início termina no dia seguinte."""
    if hora_inicio is None or hora_fim is None:
        inicio = datetime.combine(data, time())
        return Janela(inicio, inicio + timedelta(days=1))
    inicio = datetime.combine(data, hora_inicio)
    fim = datetime.combine(data, hora_fim)
    if fim <= inicio:
        fim += timedelta(days=1)
    return Janela(inicio, fim)


def bloqueio(janela: Janela, montagem: timedelta, folga: timedelta, dia_inteiro: bool = False) -> Janela:
    if dia_inteiro:
        return janela
    return Janela(janela.inicio - montagem, janela.fim + folga)


def conflitam(a: Janela, b: Janela) -> bool:
    return a.inicio < b.fim and b.inicio < a.fim


def _bloqueio_do(evento: dict, montagem: timedelta, folga: timedelta) -> Janela:
    sem_horas = evento.get("hora_inicio") is None or evento.get("hora_fim") is None
    janela = janela_evento(evento["data"], evento.get("hora_inicio"), evento.get("hora_fim"))
    return bloqueio(janela, montagem, folga, dia_inteiro=sem_horas)


def conflitos(novo: dict, existentes: list[dict], montagem: timedelta, folga: timedelta) -> list[dict]:
    bloco = _bloqueio_do(novo, montagem, folga)
    return [
        e for e in existentes
        if e.get("data") is not None
        and (novo.get("id") is None or e.get("id") != novo.get("id"))
        and conflitam(bloco, _bloqueio_do(e, montagem, folga))
    ]


def _horas(valor) -> timedelta:
    if isinstance(valor, bool) or not isinstance(valor, int | float) or valor < 0:
        valor = PADRAO_HORAS
    return timedelta(hours=valor)


def parametros(site: dict) -> tuple[timedelta, timedelta]:
    """(montagem, folga) a partir de [agenda] no site.toml; ausente ou inválido → 1h."""
    config = site.get("agenda", {}) if isinstance(site.get("agenda"), dict) else {}
    return _horas(config.get("montagem_horas", PADRAO_HORAS)), _horas(config.get("folga_horas", PADRAO_HORAS))
