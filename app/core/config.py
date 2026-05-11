import json
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    PROJECT_NAME: str = "Kalitron Furniture AI Gateway"
    VERSION: str = "0.1.0"
    DESCRIPTION: str = "AI brain for Kalitron Furniture Studio — LLM chat, image generation via ComfyUI, and R2 storage."
    API_PREFIX: str = "/api/v1"

    # ComfyUI
    COMFYUI_URL: str = "http://localhost:8188"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    # Cloudflare R2
    R2_ENDPOINT_URL: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "kitchen-designs"
    R2_PUBLIC_URL: str = ""

    # Local storage fallback
    OUTPUT_DIR: str = "./outputs"

    # JHipster Studio backend
    JHIPSTER_BACKEND_URL: str = "http://localhost:8080"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:8080", "http://localhost:9000"]

    @property
    def r2_configured(self) -> bool:
        return bool(self.R2_ENDPOINT_URL and self.R2_ACCESS_KEY_ID and self.R2_SECRET_ACCESS_KEY)


settings = Settings()
