"""Validação e preparo de fotos e vídeos para a web."""

import io
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

register_heif_opener()

EXT_IMAGEM = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
EXT_VIDEO = {".mp4", ".mov", ".m4v", ".webm"}
LADO_GRANDE = 1600
LADO_MINIATURA = 600
CHUNK = 1024 * 1024
CONTENT_TYPES = {
    ".webp": "image/webp",
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
}
FORMATOS_ACEITOS = "JPG, PNG, WEBP, HEIC, MP4, MOV ou WEBM"


class MidiaInvalida(ValueError):
    pass


@dataclass
class Processado:
    tipo: str
    principal: Path
    extensao: str
    content_type: str
    miniatura: Path | None
    aviso: str | None


def tipo_por_extensao(nome: str) -> str | None:
    ext = Path(nome).suffix.lower()
    if ext in EXT_IMAGEM:
        return "imagem"
    if ext in EXT_VIDEO:
        return "video"
    return None


def otimizar_imagem(origem: Path | BinaryIO, lado: int) -> bytes:
    """WEBP com no máximo `lado` px no maior lado, já girada e sem metadados (GPS incluso)."""
    try:
        with Image.open(origem) as aberta:
            img = ImageOps.exif_transpose(aberta)
            img.thumbnail((lado, lado))
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
            img.info = {}
            buf = io.BytesIO()
            img.save(buf, "WEBP", quality=80, method=4, exif=b"")
            return buf.getvalue()
    except (UnidentifiedImageError, OSError, ValueError) as erro:
        raise MidiaInvalida("não é uma imagem válida") from erro


def logo_para_fundo_escuro(origem: Path, largura: int = 1200) -> bytes:
    """Transforma um logo branco sobre preto em branco sobre transparente, recortado ao desenho."""
    try:
        with Image.open(origem) as aberta:
            fundo = Image.new("RGBA", aberta.size, (0, 0, 0, 255))
            fundo.alpha_composite(aberta.convert("RGBA"))
    except (UnidentifiedImageError, OSError) as erro:
        raise MidiaInvalida("o logo não é uma imagem válida") from erro
    luz = fundo.convert("L")
    branco = Image.new("RGBA", fundo.size, (255, 255, 255, 255))
    branco.putalpha(luz)
    caixa = luz.point(lambda v: 255 if v > 40 else 0).getbbox()
    if caixa:
        branco = branco.crop(caixa)
    if branco.width > largura:
        branco = branco.resize((largura, round(branco.height * largura / branco.width)), Image.LANCZOS)
    buf = io.BytesIO()
    branco.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def ffmpeg_disponivel() -> bool:
    return shutil.which("ffmpeg") is not None


def video_legivel(caminho: Path) -> bool:
    """Confere com o ffprobe se há uma faixa de vídeo. Sem ffprobe, confia na extensão."""
    if shutil.which("ffprobe") is None:
        return True
    resultado = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_type",
         "-of", "csv=p=0", str(caminho)],
        capture_output=True, text=True, timeout=60,
    )
    return resultado.returncode == 0 and "video" in resultado.stdout


def converter_video(origem: Path, destino: Path) -> bool:
    """MP4 H.264 até 1080p, sem metadados. Devolve False se o ffmpeg faltar ou falhar."""
    if not ffmpeg_disponivel():
        return False
    # Escreve num temporário e renomeia: um MP4 pela metade nunca fica com o nome final.
    parcial = destino.with_name(f"{destino.stem}.parcial{destino.suffix}")
    comando = [
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(origem),
        "-map_metadata", "-1",
        "-vf", "scale='min(1920,iw)':'min(1080,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        str(parcial),
    ]
    try:
        ok = subprocess.run(comando, capture_output=True, timeout=900).returncode == 0
    except subprocess.TimeoutExpired:
        ok = False
    if ok:
        parcial.replace(destino)
    else:
        parcial.unlink(missing_ok=True)
    return ok


async def receber_upload(upload: UploadFile, pasta: Path, limite_mb: int) -> Path:
    """Grava o upload num arquivo temporário, recusando extensão estranha ou tamanho acima do limite."""
    nome = upload.filename or ""
    if tipo_por_extensao(nome) is None:
        raise MidiaInvalida(f"“{nome}” não foi enviado: use {FORMATOS_ACEITOS}.")
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{uuid4().hex}{Path(nome).suffix.lower()}"
    limite = limite_mb * CHUNK
    total = 0
    try:
        with destino.open("wb") as arquivo:
            while chunk := await upload.read(CHUNK):
                total += len(chunk)
                if total > limite:
                    raise MidiaInvalida(
                        f"“{nome}” passou do limite de {limite_mb} MB. Comprima o arquivo e envie de novo."
                    )
                arquivo.write(chunk)
    except BaseException:
        destino.unlink(missing_ok=True)
        raise
    return destino


def processar(origem: Path, nome_original: str) -> Processado:
    tipo = tipo_por_extensao(nome_original)
    if tipo == "imagem":
        try:
            grande = otimizar_imagem(origem, LADO_GRANDE)
            mini = otimizar_imagem(origem, LADO_MINIATURA)
        except MidiaInvalida:
            raise MidiaInvalida(f"“{nome_original}” não é uma imagem válida.") from None
        caminho_grande = origem.parent / f"{origem.stem}-grande.webp"
        caminho_mini = origem.parent / f"{origem.stem}-mini.webp"
        caminho_grande.write_bytes(grande)
        caminho_mini.write_bytes(mini)
        return Processado("imagem", caminho_grande, ".webp", "image/webp", caminho_mini, None)

    if tipo != "video":
        raise MidiaInvalida(f"“{nome_original}” não foi enviado: use {FORMATOS_ACEITOS}.")
    if not video_legivel(origem):
        raise MidiaInvalida(f"“{nome_original}” não é um vídeo válido.")
    convertido = origem.parent / f"{origem.stem}-web.mp4"
    if converter_video(origem, convertido):
        return Processado("video", convertido, ".mp4", "video/mp4", None, None)
    ext = origem.suffix.lower()
    aviso = f"“{nome_original}” foi salvo no formato original e pode não tocar em todos os navegadores."
    return Processado("video", origem, ext, CONTENT_TYPES[ext], None, aviso)
