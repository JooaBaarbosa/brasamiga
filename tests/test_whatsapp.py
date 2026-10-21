from datetime import date
from urllib.parse import parse_qs, urlparse

from app import whatsapp


def test_link_limpa_numero_e_codifica_texto():
    url = whatsapp.link("+55 (11) 99343-3998", "Olá! Quero orçamento & preço")
    partes = urlparse(url)
    assert f"{partes.scheme}://{partes.netloc}{partes.path}" == "https://wa.me/5511993433998"
    assert parse_qs(partes.query)["text"] == ["Olá! Quero orçamento & preço"]


def test_link_sem_mensagem():
    assert whatsapp.link("5511993433998") == "https://wa.me/5511993433998"


def test_mensagem_completa():
    texto = whatsapp.mensagem_orcamento(
        "Carla", pacote="Nelore", data_evento=date(2026, 12, 12), local="Moema", convidados=80,
        mensagem="Tem opção sem glúten?",
    )
    assert texto == (
        "Olá! Sou Carla e quero um orçamento do Brasamiga. Pacote: Nelore. Data: 12/12/2026. "
        "Local: Moema. Convidados: 80. Tem opção sem glúten?"
    )


def test_link_aceita_numero_sem_aspas_no_toml():
    assert whatsapp.link(5511993433998) == "https://wa.me/5511993433998"


def test_mensagem_so_com_nome():
    assert whatsapp.mensagem_orcamento("Carla") == "Olá! Sou Carla e quero um orçamento do Brasamiga."
