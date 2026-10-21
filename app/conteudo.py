"""Lê o que o dono coloca em `conteudo/` e prepara versões leves das fotos."""

import hashlib
import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from app import midia

log = logging.getLogger(__name__)

PASTAS_PUBLICAS = ("logo", "cardapio")  # eventos-realizados nunca é servida direto (fotos têm GPS)


class ConteudoInvalido(RuntimeError):
    def __init__(self, arquivo: Path, linha: int | None, detalhe: str) -> None:
        self.arquivo, self.linha, self.detalhe = arquivo, linha, detalhe
        onde = f", linha {linha}" if linha else ""
        super().__init__(f"Problema em {arquivo.name}{onde}: {detalhe}")


def carregar_site(content_dir: Path) -> dict:
    caminho = content_dir / "site.toml"
    try:
        texto = caminho.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise ConteudoInvalido(caminho, None, "arquivo não encontrado") from None
    except UnicodeDecodeError:
        raise ConteudoInvalido(caminho, None, "salve o arquivo com a codificação UTF-8") from None
    try:
        return tomllib.loads(texto)
    except tomllib.TOMLDecodeError as erro:
        raise ConteudoInvalido(caminho, erro.lineno, erro.msg) from erro


@dataclass(frozen=True)
class ItemGaleria:
    tipo: str
    url: str
    url_miniatura: str


class Conteudo:
    def __init__(self, content_dir: Path, cache_dir: Path) -> None:
        self.content_dir = content_dir
        self.cache_dir = cache_dir

    def site(self) -> dict:
        return carregar_site(self.content_dir)

    def _arquivos(self, pasta: str) -> list[Path]:
        base = self.content_dir / pasta
        if not base.is_dir():
            return []
        visiveis = (p for p in base.iterdir() if p.is_file() and not p.name.startswith("."))
        return sorted(visiveis, key=lambda p: p.name.lower())

    @staticmethod
    def _chave(arquivo: Path) -> str:
        info = arquivo.stat()
        return hashlib.sha1(f"{arquivo.name}:{info.st_size}:{info.st_mtime_ns}".encode()).hexdigest()[:16]

    def _imagem(self, arquivo: Path) -> ItemGaleria | None:
        chave = self._chave(arquivo)
        pasta = self.cache_dir / "galeria"
        grande, mini = pasta / f"{chave}-grande.webp", pasta / f"{chave}-mini.webp"
        if not (grande.exists() and mini.exists()):
            try:
                pasta.mkdir(parents=True, exist_ok=True)
                grande.write_bytes(midia.otimizar_imagem(arquivo, midia.LADO_GRANDE))
                mini.write_bytes(midia.otimizar_imagem(arquivo, midia.LADO_MINIATURA))
            except (OSError, midia.MidiaInvalida) as erro:
                log.warning("Foto %s ignorada: %s", arquivo.name, erro)
                return None
        return ItemGaleria("imagem", f"/cache/galeria/{grande.name}", f"/cache/galeria/{mini.name}")

    def arquivos(self, pasta: str) -> list[Path]:
        return self._arquivos(pasta)

    def versao_web(self, arquivo: Path) -> ItemGaleria | None:
        """Versões WEBP (sem GPS) de uma foto da pasta, geradas no cache."""
        return self._imagem(arquivo)

    def _video_web(self, arquivo: Path) -> Path:
        return self.cache_dir / "galeria" / f"{self._chave(arquivo)}.mp4"

    def galeria(self) -> list[ItemGaleria]:
        itens = []
        for arquivo in self._arquivos("eventos-realizados"):
            tipo = midia.tipo_por_extensao(arquivo.name)
            if tipo == "imagem":
                if item := self._imagem(arquivo):
                    itens.append(item)
            elif tipo == "video" and (web := self._video_web(arquivo)).exists():
                url = f"/cache/galeria/{web.name}"
                itens.append(ItemGaleria("video", url, url))
        return itens

    def capa(self, nome: str | None) -> ItemGaleria | None:
        """Foto de abertura: a indicada no site.toml ou, sem ela, a primeira da galeria."""
        if nome:
            arquivo = self.content_dir / "eventos-realizados" / Path(nome).name
            if arquivo.is_file() and midia.tipo_por_extensao(arquivo.name) == "imagem":
                if item := self._imagem(arquivo):
                    return item
        return next((i for i in self.galeria() if i.tipo == "imagem"), None)

    def preparar(self) -> dict:
        """Gera todas as versões web (fotos e vídeos). Roda no início do servidor e no build."""
        imagens = len([i for i in self.galeria() if i.tipo == "imagem"])
        videos = 0
        for arquivo in self._arquivos("eventos-realizados"):
            if midia.tipo_por_extensao(arquivo.name) != "video":
                continue
            destino = self._video_web(arquivo)
            if not destino.exists():
                destino.parent.mkdir(parents=True, exist_ok=True)
                if not midia.converter_video(arquivo, destino):
                    log.warning("Vídeo %s não convertido (ffmpeg ausente ou falhou)", arquivo.name)
                    continue
            videos += 1
        return {"imagens": imagens, "videos": videos}

    def logo_escuro(self, nome: str | None) -> str | None:
        if not nome:
            return None
        origem = self.content_dir / "logo" / Path(nome).name
        if not origem.is_file():
            return None
        destino = self.cache_dir / "logo" / f"{self._chave(origem)}.png"
        if not destino.exists():
            try:
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_bytes(midia.logo_para_fundo_escuro(origem))
            except (OSError, midia.MidiaInvalida) as erro:
                log.warning("Logo %s não preparado: %s", origem.name, erro)
                return None
        return f"/cache/logo/{destino.name}"

    def pdfs(self) -> list[dict]:
        return [
            {"url": f"/conteudo/cardapio/{quote(p.name)}", "nome": p.stem.replace("_", " ").replace("-", " ")}
            for p in self._arquivos("cardapio")
            if p.suffix.lower() == ".pdf"
        ]
