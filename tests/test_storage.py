import io

import pytest

from app.config import Settings
from app.storage import BlobStorage, LocalStorage, criar_armazenamento


def test_local_salva_serve_e_apaga(tmp_path):
    storage = LocalStorage(tmp_path / "uploads")
    storage.salvar("abc.webp", io.BytesIO(b"conteudo"), "image/webp")
    assert (tmp_path / "uploads" / "abc.webp").read_bytes() == b"conteudo"
    assert storage.url("abc.webp") == "/uploads/abc.webp"
    storage.apagar("abc.webp")
    assert not (tmp_path / "uploads" / "abc.webp").exists()
    storage.apagar("abc.webp")  # apagar duas vezes não quebra


@pytest.mark.parametrize("chave", ["../fora.txt", "sub/arq.webp", "", ".oculto"])
def test_local_recusa_chave_perigosa(tmp_path, chave):
    with pytest.raises(ValueError):
        LocalStorage(tmp_path).salvar(chave, io.BytesIO(b"x"), "text/plain")


def test_fabrica_escolhe_backend(settings):
    assert isinstance(criar_armazenamento(settings), LocalStorage)
    blob = Settings(**{**settings.__dict__, "storage_backend": "blob", "blob_token": "t"})
    assert isinstance(criar_armazenamento(blob), BlobStorage)
    with pytest.raises(ValueError, match="STORAGE_BACKEND"):
        criar_armazenamento(Settings(**{**settings.__dict__, "storage_backend": "s3"}))


def test_blob_ainda_nao_implementado():
    with pytest.raises(NotImplementedError):
        BlobStorage("t").salvar("a.webp", io.BytesIO(b""), "image/webp")


def test_settings_do_ambiente(monkeypatch, tmp_path):
    monkeypatch.setenv("ADMIN_PASSWORD", "x")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("MAX_UPLOAD_MB", "50")
    s = Settings.from_env()
    assert s.admin_password == "x"
    assert s.database_url == f"sqlite:///{(tmp_path / 'brasamiga.db').as_posix()}"
    assert s.max_upload_mb == 50
    assert s.uploads_dir == tmp_path / "uploads"
    assert s.cache_dir == tmp_path / "cache"
