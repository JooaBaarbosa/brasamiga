from app import preparar
from tests.fabrica import jpeg_bytes


def test_preparar_gera_cache(monkeypatch, settings, capsys):
    (settings.content_dir / "eventos-realizados" / "a.jpg").write_bytes(jpeg_bytes())
    monkeypatch.setattr(preparar.Settings, "from_env", classmethod(lambda cls: settings))
    preparar.main()
    assert "Fotos prontas: 1" in capsys.readouterr().out
    assert any(settings.cache_dir.joinpath("galeria").glob("*-mini.webp"))
