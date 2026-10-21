import unicodedata
from datetime import date, datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates

APP_DIR = Path(__file__).resolve().parent
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

templates = Jinja2Templates(directory=APP_DIR / "templates")


def _data(valor: date | str | None) -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str) and valor:
        try:
            return date.fromisoformat(valor)
        except ValueError:
            return None
    return None


def data_br(valor: date | str | None) -> str:
    d = _data(valor)
    return d.strftime("%d/%m/%Y") if d else ""


def dia(valor: date | str | None) -> str:
    d = _data(valor)
    return f"{d.day:02d}" if d else ""


def mes(valor: date | str | None) -> str:
    d = _data(valor)
    return f"{MESES[d.month - 1]} {d.year}" if d else ""


MESES_LONGOS = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto",
                "Setembro", "Outubro", "Novembro", "Dezembro"]


def mes_ano(valor: date | str | None) -> str:
    d = _data(valor)
    return f"{MESES_LONGOS[d.month - 1]} {d.year}" if d else ""


def normalizar(texto: str | None) -> str:
    """Minúsculas, sem acento e com espaços simples: o formato que a busca da galeria compara."""
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", texto or "") if not unicodedata.combining(c))
    return " ".join(sem_acento.lower().split())


templates.env.filters.update(data_br=data_br, dia=dia, mes=mes, mes_ano=mes_ano, normalizar=normalizar)
