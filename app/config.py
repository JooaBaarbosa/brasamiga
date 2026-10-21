import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    admin_user: str
    admin_password: str
    data_dir: Path
    content_dir: Path
    database_url: str
    storage_backend: str = "local"
    blob_token: str = ""
    max_upload_mb: int = 300

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def tmp_dir(self) -> Path:
        return self.data_dir / "tmp"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(BASE_DIR / ".env")
        data_dir = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
        return cls(
            admin_user=os.getenv("ADMIN_USER", "admin"),
            admin_password=os.getenv("ADMIN_PASSWORD", ""),
            data_dir=data_dir,
            content_dir=Path(os.getenv("CONTENT_DIR", BASE_DIR / "conteudo")),
            database_url=os.getenv("DATABASE_URL") or f"sqlite:///{(data_dir / 'brasamiga.db').as_posix()}",
            storage_backend=os.getenv("STORAGE_BACKEND", "local"),
            blob_token=os.getenv("BLOB_READ_WRITE_TOKEN", ""),
            max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "300")),
        )
