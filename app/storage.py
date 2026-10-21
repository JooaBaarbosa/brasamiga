"""Onde ficam as fotos e vídeos enviados pelo painel.

Hoje: disco local (volume do Docker). Na Vercel: Vercel Blob, trocando STORAGE_BACKEND.
"""

import shutil
from pathlib import Path
from typing import BinaryIO, Protocol

from app.config import Settings


class Armazenamento(Protocol):
    def salvar(self, chave: str, dados: BinaryIO, content_type: str) -> None: ...
    def apagar(self, chave: str) -> None: ...
    def url(self, chave: str) -> str: ...


def _validar(chave: str) -> str:
    if not chave or chave.startswith(".") or "/" in chave or "\\" in chave:
        raise ValueError(f"Chave de arquivo inválida: {chave!r}")
    return chave


class LocalStorage:
    def __init__(self, pasta: Path, prefixo_url: str = "/uploads") -> None:
        self.pasta = pasta
        self.prefixo_url = prefixo_url.rstrip("/")
        pasta.mkdir(parents=True, exist_ok=True)

    def salvar(self, chave: str, dados: BinaryIO, content_type: str) -> None:
        with (self.pasta / _validar(chave)).open("wb") as destino:
            shutil.copyfileobj(dados, destino)

    def apagar(self, chave: str) -> None:
        (self.pasta / _validar(chave)).unlink(missing_ok=True)

    def url(self, chave: str) -> str:
        return f"{self.prefixo_url}/{_validar(chave)}"


class BlobStorage:
    """Vercel Blob. Implementar na migração para a Vercel.

    API: PUT https://blob.vercel-storage.com/<chave> com o header
    `Authorization: Bearer <BLOB_READ_WRITE_TOKEN>`; a resposta traz a `url` pública.
    Uploads maiores que 4,5 MB precisam ir direto do navegador para o Blob (client upload).
    """

    def __init__(self, token: str) -> None:
        self.token = token

    def salvar(self, chave: str, dados: BinaryIO, content_type: str) -> None:
        raise NotImplementedError("BlobStorage ainda não foi implementado: use STORAGE_BACKEND=local.")

    def apagar(self, chave: str) -> None:
        raise NotImplementedError("BlobStorage ainda não foi implementado: use STORAGE_BACKEND=local.")

    def url(self, chave: str) -> str:
        raise NotImplementedError("BlobStorage ainda não foi implementado: use STORAGE_BACKEND=local.")


def criar_armazenamento(settings: Settings) -> Armazenamento:
    if settings.storage_backend == "local":
        return LocalStorage(settings.uploads_dir)
    if settings.storage_backend == "blob":
        return BlobStorage(settings.blob_token)
    raise ValueError(f"STORAGE_BACKEND desconhecido: {settings.storage_backend!r}. Use 'local' ou 'blob'.")
