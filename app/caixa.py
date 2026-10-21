"""Caixa de entrada: fotos de conteudo/eventos-realizados que ainda não pertencem a um evento.

A pasta nunca é alterada (no Docker ela é só leitura); o que já foi tratado fica na tabela caixa_entrada.
"""

from pathlib import Path

from app import midia
from app.conteudo import Conteudo

PASTA = "eventos-realizados"


def assinatura(arquivo: Path) -> str:
    info = arquivo.stat()
    return f"{arquivo.name}:{info.st_size}:{info.st_mtime_ns}"


def pendentes(conteudo: Conteudo, tratadas: set[str], foto_capa: str | None) -> list[dict]:
    lista = []
    for arquivo in conteudo.arquivos(PASTA):
        tipo = midia.tipo_por_extensao(arquivo.name)
        if tipo is None or arquivo.name == foto_capa:
            continue
        marca = assinatura(arquivo)
        if marca in tratadas:
            continue
        versao = conteudo.versao_web(arquivo) if tipo == "imagem" else None
        lista.append({
            "nome": arquivo.name,
            "assinatura": marca,
            "tipo": tipo,
            "caminho": arquivo,
            "miniatura_url": versao.url_miniatura if versao else None,
        })
    return lista


def resolver(lista_pendentes: list[dict], nomes: list[str]) -> list[dict]:
    """Só aceita nomes que estão exatamente na lista de pendentes; qualquer outro nome é recusado."""
    por_nome = {p["nome"]: p for p in lista_pendentes}
    desconhecidos = [n for n in nomes if n not in por_nome]
    if desconhecidos or not nomes:
        raise ValueError("Arquivo fora da caixa de entrada: " + ", ".join(desconhecidos or ["nenhum selecionado"]))
    return [por_nome[n] for n in dict.fromkeys(nomes)]
