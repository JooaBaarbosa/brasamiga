from datetime import date
from pathlib import Path

from fastapi.templating import Jinja2Templates

APP_DIR = Path(__file__).resolve().parent
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

templates = Jinja2Templates(directory=APP_DIR / "templates")


def _data(valor: str | None) -> date | None:
    try:
        return date.fromisoformat(valor) if valor else None
    except ValueError:
        return None


def data_br(valor: str | None) -> str:
    d = _data(valor)
    return d.strftime("%d/%m/%Y") if d else ""


def dia(valor: str | None) -> str:
    d = _data(valor)
    return f"{d.day:02d}" if d else ""


def mes(valor: str | None) -> str:
    d = _data(valor)
    return f"{MESES[d.month - 1]} {d.year}" if d else ""


templates.env.filters.update(data_br=data_br, dia=dia, mes=mes)
