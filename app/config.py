from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SignalOps"
    database_url: str = "sqlite+aiosqlite:///./signalops.db"
    incident_z_threshold: float = 2.5
    minimum_samples: int = 5
    auth_required: bool = False
    api_key_sha256: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="SIGNALOPS_")


settings = Settings()

