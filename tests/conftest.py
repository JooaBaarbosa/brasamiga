import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import BASE_DIR, Settings
from tests.fabrica import logo_png


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    conteudo = tmp_path / "conteudo"
    for pasta in ("logo", "cardapio", "eventos-realizados"):
        (conteudo / pasta).mkdir(parents=True)
    shutil.copy(BASE_DIR / "conteudo" / "site.toml", conteudo / "site.toml")
    logo_png(conteudo / "logo" / "LOGO-03.png")
    data = tmp_path / "data"
    return Settings(
        admin_user="admin",
        admin_password="segredo",
        data_dir=data,
        content_dir=conteudo,
        database_url=f"sqlite:///{(data / 'teste.db').as_posix()}",
        max_upload_mb=1,
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    from app.main import create_app

    return TestClient(create_app(settings))
