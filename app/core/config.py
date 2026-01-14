from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    _root_dir = Path(__file__).resolve().parents[2]
    model_config = SettingsConfigDict(env_file=str(_root_dir / ".env"), env_ignore_empty=True, extra="ignore")

    database_url: str = Field(..., validation_alias=AliasChoices("DATABASE_URL", "DB_URL_QUANT"))

    jwt_secret: str = Field(..., alias="JWT_SECRET")
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    jwt_access_token_exp_minutes: int = Field(60 * 24 * 7, alias="JWT_ACCESS_TOKEN_EXP_MINUTES")

    default_currency: str = Field("CNY", alias="DEFAULT_CURRENCY")

    admin_username: str | None = Field(default=None, alias="ADMIN_USERNAME")
    admin_password: str | None = Field(default=None, alias="ADMIN_PASSWORD")


settings = Settings()
