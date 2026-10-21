"""Hora oficial do site: São Paulo, mesmo quando o servidor roda em UTC (Docker, Vercel)."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")


def agora() -> datetime:
    return datetime.now(FUSO).replace(tzinfo=None)


def hoje() -> date:
    return datetime.now(FUSO).date()
