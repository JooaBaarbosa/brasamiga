"""Agenda: quando um evento ocupa a equipe e se dois eventos cabem no mesmo dia.

Cada evento bloqueia do início menos a montagem até o fim mais a folga de deslocamento.
Blocos que só encostam não conflitam.
"""

import calendar
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


# Calendário (usado pelas APIs /api/agenda e /admin/api/agenda)

def mes_ou_atual(texto: str | None, hoje: date) -> date:
    """Primeiro dia do mês 'AAAA-MM'; qualquer coisa inválida vira o mês de hoje."""
    try:
        ano, mes = texto.split("-") if texto else ("", "")
        if len(ano) == 4 and len(mes) == 2:
            return date(int(ano), int(mes), 1)
    except ValueError:
        pass
    return hoje.replace(day=1)


def fim_do_mes(mes: date) -> date:
    return date(mes.year, mes.month, calendar.monthrange(mes.year, mes.month)[1])


def vizinhos(mes: date) -> tuple[str | None, str | None]:
    anterior = (mes - timedelta(days=1)).replace(day=1) if mes > date.min else None
    proximo = fim_do_mes(mes) + timedelta(days=1) if fim_do_mes(mes) < date.max else None
    formato = lambda d: f"{d.year:04d}-{d.month:02d}" if d else None  # noqa: E731
    return formato(anterior), formato(proximo)


def _hhmm(valor: time | None) -> str | None:
    return valor.strftime("%H:%M") if valor else None


def mapa_dias(linhas: list[dict], campos_extras: tuple[str, ...] = ()) -> dict[str, list[dict]]:
    dias: dict[str, list[dict]] = {}
    ordenadas = sorted(linhas, key=lambda l: (l["data"], l["hora_inicio"] is not None, l["hora_inicio"] or time()))
    for linha in ordenadas:
        item = {"inicio": _hhmm(linha["hora_inicio"]), "fim": _hhmm(linha["hora_fim"])}
        item.update({campo: linha[campo] for campo in campos_extras})
        dias.setdefault(linha["data"].isoformat(), []).append(item)
    return dias


def resposta(mes: date, hoje: date, dias: dict) -> dict:
    anterior, proximo = vizinhos(mes)
    return {"mes": f"{mes.year:04d}-{mes.month:02d}", "anterior": anterior, "proximo": proximo,
            "hoje": hoje.isoformat(), "dias": dias}


def _horas(valor) -> timedelta:
    if isinstance(valor, bool) or not isinstance(valor, int | float) or valor < 0:
        valor = PADRAO_HORAS
    return timedelta(hours=valor)


def parametros(site: dict) -> tuple[timedelta, timedelta]:
    """(montagem, folga) a partir de [agenda] no site.toml; ausente ou inválido → 1h."""
    config = site.get("agenda", {}) if isinstance(site.get("agenda"), dict) else {}
    return _horas(config.get("montagem_horas", PADRAO_HORAS)), _horas(config.get("folga_horas", PADRAO_HORAS))
