"""Lê o que o dono coloca na pasta `conteudo/`: textos, logo, cardápio e fotos."""

import tomllib
from pathlib import Path
from urllib.parse import quote

from app.media import tipo_por_extensao

PASTAS = ("logo", "cardapio", "eventos-realizados")


def garantir_pastas(content_dir: Path) -> None:
    for pasta in PASTAS:
        (content_dir / pasta).mkdir(parents=True, exist_ok=True)


def carregar_site(content_dir: Path) -> dict:
    caminho = content_dir / "site.toml"
    if not caminho.exists():
        return {}
    try:
        with caminho.open("rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as erro:
        raise RuntimeError(f"Erro de formatação em {caminho}: {erro}") from erro


def _arquivos(content_dir: Path, pasta: str) -> list[tuple[Path, str]]:
    """Lista (caminho, url) dos arquivos visíveis de uma subpasta, em ordem alfabética."""
    base = content_dir / pasta
    if not base.is_dir():
        return []
    arquivos = sorted(
        (p for p in base.iterdir() if p.is_file() and not p.name.startswith(".")),
        key=lambda p: p.name.lower(),
    )
    return [(p, f"/conteudo/{pasta}/{quote(p.name)}") for p in arquivos]


def logo(content_dir: Path) -> str | None:
    for caminho, url in _arquivos(content_dir, "logo"):
        if tipo_por_extensao(caminho.name) == "imagem" or caminho.suffix.lower() == ".svg":
            return url
    return None


def cardapio(content_dir: Path) -> dict:
    pdfs, imagens = [], []
    for caminho, url in _arquivos(content_dir, "cardapio"):
        if caminho.suffix.lower() == ".pdf":
            pdfs.append({"url": url, "nome": caminho.stem.replace("-", " ").replace("_", " ")})
        elif tipo_por_extensao(caminho.name) == "imagem":
            imagens.append(url)
    return {"pdfs": pdfs, "imagens": imagens}


def galeria(content_dir: Path) -> list[dict]:
    itens = []
    for caminho, url in _arquivos(content_dir, "eventos-realizados"):
        if tipo := tipo_por_extensao(caminho.name):
            itens.append({"url": url, "tipo": tipo})
    return itens
