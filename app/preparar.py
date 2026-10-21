"""Gera as versões web das fotos e vídeos de conteudo/eventos-realizados.

Uso: uv run python -m app.preparar   (no build da Vercel, antes do deploy)
"""

from app.config import Settings
from app.conteudo import Conteudo


def main() -> None:
    settings = Settings.from_env()
    resultado = Conteudo(settings.content_dir, settings.cache_dir).preparar()
    print(f"Fotos prontas: {resultado['imagens']} · Vídeos prontos: {resultado['videos']}")


if __name__ == "__main__":
    main()
