from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Postgres is used ONLY for user accounts (register/login).
    # Chat messages and files are never written here.
    #
    # Default here matches the Render-hosted "chatapp" Postgres instance
    # (External Database URL, since this typically runs outside Render's
    # private network). .env's DATABASE_URL takes precedence over this
    # default when present — keep the real value there, not committed here.
    database_url: str = (
        "postgresql://chatapp_8wkz_user:qrpCXnxOOrfzwoIyZhj8IuWv7XOoMa76"
        "@dpg-da19k2gu01pc739pbk9g-a.ohio-postgres.render.com:5432/chatapp_8wkz"
    )

    secret_key: str = "change-this-to-a-long-random-secret"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Files are held transiently on disk just long enough to be delivered,
    # then deleted. No chat content ever touches the database.
    file_transfer_dir: str = "./tmp_transfer"
    file_ttl_seconds: int = 3600

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Some hosts (Vercel, etc.) let an env var exist but be set to an empty
    # string rather than truly unset — pydantic treats that as "value = ''"
    # and fails int parsing instead of falling back to the default. Treat
    # blank as "not provided" for these two so a stray empty env var in the
    # dashboard doesn't crash the whole app on boot. Returning the concrete
    # default here (not None) since these fields are plain `int`, not
    # `Optional[int]`.
    @field_validator("access_token_expire_minutes", mode="before")
    @classmethod
    def _blank_expire_minutes(cls, value):
        if isinstance(value, str) and value.strip() == "":
            return 60
        return value

    @field_validator("file_ttl_seconds", mode="before")
    @classmethod
    def _blank_ttl_seconds(cls, value):
        if isinstance(value, str) and value.strip() == "":
            return 3600
        return value


settings = Settings()