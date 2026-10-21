import io
from pathlib import Path

from PIL import Image, ImageDraw

AUTH = ("admin", "segredo")


def jpeg_bytes(tamanho=(400, 200), orientacao: int | None = None, gps: bool = False) -> bytes:
    """JPEG gerado na hora, com orientação EXIF e GPS opcionais (como foto de iPhone)."""
    img = Image.new("RGB", tamanho, (169, 50, 38))
    exif = Image.Exif()
    if orientacao:
        exif[0x0112] = orientacao
    if gps:
        exif[0x8825] = {1: "S", 2: (23.0, 33.0, 0.0)}
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif.tobytes())
    return buf.getvalue()


def logo_png(caminho: Path) -> None:
    """Logo falso no estilo do LOGO-03: desenho branco sobre fundo preto."""
    img = Image.new("RGBA", (300, 200), (0, 0, 0, 255))
    ImageDraw.Draw(img).rectangle((100, 50, 200, 150), fill=(255, 255, 255, 255))
    img.save(caminho)
