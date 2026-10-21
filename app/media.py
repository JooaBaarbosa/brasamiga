from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

IMAGENS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
VIDEOS = {".mp4", ".webm", ".mov"}
CHUNK = 1024 * 1024


class UploadInvalido(ValueError):
    pass


def tipo_por_extensao(nome: str) -> str | None:
    ext = Path(nome).suffix.lower()
    if ext in IMAGENS:
        return "imagem"
    if ext in VIDEOS:
        return "video"
    return None


async def salvar_upload(upload: UploadFile, destino: Path, limite_mb: int) -> tuple[str, str]:
    """Grava o arquivo com nome aleatório e devolve (nome_no_disco, tipo)."""
    nome_original = upload.filename or ""
    tipo = tipo_por_extensao(nome_original)
    if tipo is None:
        raise UploadInvalido(
            f"“{nome_original}” não foi enviado: use JPG, PNG, WEBP, GIF, AVIF, MP4, WEBM ou MOV."
        )

    destino.mkdir(parents=True, exist_ok=True)
    nome = f"{uuid4().hex}{Path(nome_original).suffix.lower()}"
    caminho = destino / nome
    limite = limite_mb * CHUNK
    total = 0
    try:
        with caminho.open("wb") as arquivo:
            while chunk := await upload.read(CHUNK):
                total += len(chunk)
                if total > limite:
                    raise UploadInvalido(
                        f"“{nome_original}” passou do limite de {limite_mb} MB. Comprima o arquivo e envie de novo."
                    )
                arquivo.write(chunk)
    except BaseException:
        caminho.unlink(missing_ok=True)
        raise
    return nome, tipo


def apagar_arquivo(pasta: Path, nome: str) -> None:
    (pasta / Path(nome).name).unlink(missing_ok=True)
