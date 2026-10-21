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
    max_upload_mb: int = 300

    @property
    def db_path(self) -> Path:
        return self.data_dir / "brasamiga.db"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(BASE_DIR / ".env")
        return cls(
            admin_user=os.getenv("ADMIN_USER", "admin"),
            admin_password=os.getenv("ADMIN_PASSWORD", ""),
            data_dir=Path(os.getenv("BRASAMIGA_DATA_DIR", BASE_DIR / "data")),
            content_dir=Path(os.getenv("BRASAMIGA_CONTENT_DIR", BASE_DIR / "conteudo")),
            max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "300")),
        )
