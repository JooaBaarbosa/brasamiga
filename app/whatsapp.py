import re
from datetime import date
from urllib.parse import quote

MENSAGEM_PADRAO = "Olá! Quero um orçamento de churrasco para o meu evento."


def so_digitos(numero: str | int) -> str:
    # str(): no site.toml o número pode vir sem aspas, como inteiro.
    return re.sub(r"\D", "", str(numero))


def link(numero: str | int, mensagem: str | None = None) -> str:
    url = f"https://wa.me/{so_digitos(numero)}"
    return f"{url}?text={quote(mensagem)}" if mensagem else url


def mensagem_orcamento(
    nome: str,
    pacote: str = "",
    data_evento: date | None = None,
    local: str = "",
    convidados: int | None = None,
    mensagem: str = "",
) -> str:
    partes = [f"Olá! Sou {nome} e quero um orçamento do Brasamiga."]
    if pacote:
        partes.append(f"Pacote: {pacote}.")
    if data_evento:
        partes.append(f"Data: {data_evento:%d/%m/%Y}.")
    if local:
        partes.append(f"Local: {local}.")
    if convidados:
        partes.append(f"Convidados: {convidados}.")
    if mensagem:
        partes.append(mensagem)
    return " ".join(partes)
