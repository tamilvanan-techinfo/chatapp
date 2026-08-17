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


settings = Settings()