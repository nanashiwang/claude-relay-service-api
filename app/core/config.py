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

    public_base_url: str | None = Field(default=None, alias="PUBLIC_BASE_URL")
    wecom_webhook_url: str | None = Field(default=None, alias="WECOM_WEBHOOK_URL")

    admin_username: str | None = Field(default=None, alias="ADMIN_USERNAME")
    admin_password: str | None = Field(default=None, alias="ADMIN_PASSWORD")

    epay_base_url: str | None = Field(default=None, alias="EPAY_BASE_URL")
    epay_pid: str | None = Field(default=None, alias="EPAY_PID")
    epay_key: str | None = Field(default=None, alias="EPAY_KEY")
    epay_sign_type: str = Field("MD5", alias="EPAY_SIGN_TYPE")
    epay_notify_url: str | None = Field(default=None, alias="EPAY_NOTIFY_URL")
    epay_return_url: str | None = Field(default=None, alias="EPAY_RETURN_URL")


settings = Settings()
