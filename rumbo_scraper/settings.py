"""Application settings loaded from environment variables."""

from dataclasses import dataclass
import os
from urllib.parse import urlparse

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the scraper."""

    supabase_url: str = os.getenv("SUPABASE_URL", "").strip()
    supabase_service_role_key: str = (
        os.getenv("SUPABASE_SECRET_KEY", "")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    ).strip()

    def validate_supabase(self) -> None:
        """Raise a clear error when Supabase credentials are missing."""
        missing = []
        if not self.supabase_url:
            missing.append("SUPABASE_URL")
        if not self.supabase_service_role_key:
            missing.append("SUPABASE_SECRET_KEY o SUPABASE_SERVICE_ROLE_KEY")
        if missing:
            raise RuntimeError(
                "Missing required environment variables: " + ", ".join(missing)
            )
        parsed = urlparse(self.supabase_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RuntimeError(
                "SUPABASE_URL inválida. Debe tener el formato "
                "https://TU_PROJECT_REF.supabase.co"
            )


settings = Settings()
