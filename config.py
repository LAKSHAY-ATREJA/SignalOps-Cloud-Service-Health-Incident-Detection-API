from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SignalOps"
    database_url: str = "sqlite+aiosqlite:///./signalops.db"
    incident_z_threshold: float = 2.5
    minimum_samples: int = 5

    model_config = SettingsConfigDict(env_file=".env", env_prefix="SIGNALOPS_")


settings = Settings()
