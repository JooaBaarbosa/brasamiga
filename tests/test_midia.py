import asyncio
import io
import subprocess

import pytest
from fastapi import UploadFile
from PIL import Image

from app import midia
from tests.fabrica import jpeg_bytes, logo_png


@pytest.mark.parametrize(
    ("nome", "tipo"),
    [
        ("foto.jpg", "imagem"),
        ("Festa Junina 2025.JPG", "imagem"),
        ("IMG_0001.HEIC", "imagem"),
        ("IMG_5038.MOV", "video"),
        ("clip.mp4", "video"),
        ("virus.exe", None),
        ("sem-extensao", None),
    ],
)
def test_tipo_por_extensao(nome, tipo):
    assert midia.tipo_por_extensao(nome) == tipo


def test_otimizar_gira_reduz_e_remove_gps():
    original = jpeg_bytes(tamanho=(3200, 1600), orientacao=6, gps=True)
    assert Image.open(io.BytesIO(original)).getexif().get_ifd(0x8825), "a foto de teste precisa ter GPS"

    saida = Image.open(io.BytesIO(midia.otimizar_imagem(io.BytesIO(original), midia.LADO_GRANDE)))
    assert saida.format == "WEBP"
    assert saida.size == (800, 1600)  # 3200x1600 girada 90° = 1600x3200, reduzida a 1600 no maior lado
    assert len(saida.getexif()) == 0


def test_otimizar_nao_aumenta_foto_pequena():
    saida = Image.open(io.BytesIO(midia.otimizar_imagem(io.BytesIO(jpeg_bytes((400, 200))), 600)))
    assert saida.size == (400, 200)


def test_otimizar_recusa_arquivo_que_nao_e_imagem():
    with pytest.raises(midia.MidiaInvalida):
        midia.otimizar_imagem(io.BytesIO(b"isto nao e uma foto"), 600)


def test_logo_vira_branco_transparente_e_recortado(tmp_path):
    logo_png(tmp_path / "logo.png")
    img = Image.open(io.BytesIO(midia.logo_para_fundo_escuro(tmp_path / "logo.png", largura=50)))
    assert img.mode == "RGBA"
    assert img.width == 50  # recortado ao desenho (101x101) e reduzido
    assert img.getpixel((25, 25))[3] == 255
    inteiro = midia.logo_para_fundo_escuro(tmp_path / "logo.png")
    assert Image.open(io.BytesIO(inteiro)).size == (101, 101)  # não amplia além do desenho


def _upload(nome: str, dados: bytes) -> UploadFile:
    return UploadFile(file=io.BytesIO(dados), filename=nome)


def test_receber_upload_respeita_limite(tmp_path):
    with pytest.raises(midia.MidiaInvalida, match="limite de 1 MB"):
        asyncio.run(midia.receber_upload(_upload("grande.mp4", b"0" * (2 * 1024 * 1024)), tmp_path, 1))
    assert list(tmp_path.iterdir()) == []


def test_receber_upload_recusa_extensao(tmp_path):
    with pytest.raises(midia.MidiaInvalida, match="virus.exe"):
        asyncio.run(midia.receber_upload(_upload("virus.exe", b"MZ"), tmp_path, 1))


def test_processar_imagem_gera_grande_e_miniatura(tmp_path):
    bruto = asyncio.run(midia.receber_upload(_upload("Festa Junina.JPG", jpeg_bytes((2000, 1000))), tmp_path, 5))
    pronto = midia.processar(bruto, "Festa Junina.JPG")
    assert (pronto.tipo, pronto.extensao, pronto.content_type) == ("imagem", ".webp", "image/webp")
    assert Image.open(pronto.principal).size == (1600, 800)
    assert Image.open(pronto.miniatura).size == (600, 300)
    assert pronto.aviso is None


def test_processar_imagem_corrompida(tmp_path):
    falsa = tmp_path / "falsa.jpg"
    falsa.write_bytes(b"nada")
    with pytest.raises(midia.MidiaInvalida, match="falsa.jpg"):
        midia.processar(falsa, "falsa.jpg")


def test_conversao_grava_em_temporario_e_renomeia(tmp_path, monkeypatch):
    destino = tmp_path / "saida.mp4"
    saidas = []

    def ffmpeg_falso(comando, **_):
        saidas.append(comando[-1])
        with open(comando[-1], "wb") as arquivo:
            arquivo.write(b"mp4")
        return subprocess.CompletedProcess(comando, 0)

    monkeypatch.setattr(midia, "ffmpeg_disponivel", lambda: True)
    monkeypatch.setattr(midia.subprocess, "run", ffmpeg_falso)
    assert midia.converter_video(tmp_path / "entrada.mov", destino)
    assert saidas[0] != str(destino)  # o ffmpeg nunca escreve direto no arquivo final
    assert destino.read_bytes() == b"mp4"
    assert [p.name for p in tmp_path.iterdir()] == ["saida.mp4"]


@pytest.mark.skipif(midia.ffmpeg_disponivel(), reason="só vale sem ffmpeg instalado")
def test_video_sem_ffmpeg_fica_original_com_aviso(tmp_path):
    video = tmp_path / "clip.mov"
    video.write_bytes(b"\x00" * 10)
    pronto = midia.processar(video, "clip.MOV")
    assert (pronto.tipo, pronto.extensao, pronto.content_type) == ("video", ".mov", "video/quicktime")
    assert "formato original" in pronto.aviso


@pytest.mark.skipif(not midia.ffmpeg_disponivel(), reason="ffmpeg não instalado")
def test_video_convertido_para_mp4(tmp_path):
    origem = tmp_path / "clip.mov"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10", "-t", "1", str(origem)],
        check=True,
    )
    pronto = midia.processar(origem, "clip.MOV")
    assert (pronto.extensao, pronto.content_type, pronto.aviso) == (".mp4", "video/mp4", None)
    assert pronto.principal.stat().st_size > 0


@pytest.mark.skipif(not midia.ffmpeg_disponivel(), reason="ffmpeg não instalado")
def test_video_corrompido_e_recusado(tmp_path):
    falso = tmp_path / "falso.mp4"
    falso.write_bytes(b"\x00" * 100)
    with pytest.raises(midia.MidiaInvalida, match="falso.mp4"):
        midia.processar(falso, "falso.mp4")
