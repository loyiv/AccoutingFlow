from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, case_sensitive=False)

    database_url: str
    jwt_secret: str = "dev-secret-change-me"
    jwt_alg: str = "HS256"
    jwt_expire_minutes: int = 720

    # 说明：
    # - cors_origins：显式白名单（逗号分隔）
    # - cors_origin_regex：可选，用于开发环境允许“本机 IP:5173”（例如 http://198.10.0.1:5173）
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    cors_origin_regex: str = r"^http://(localhost|127\.0\.0\.1|\d+\.\d+\.\d+\.\d+):5173$"
    storage_dir: str = "./storage"

    seed_admin_username: str = "admin"
    seed_admin_password: str = "admin123"
    seed_accountant_username: str = "accountant"
    seed_accountant_password: str = "accountant123"
    seed_manager_username: str = "manager"
    seed_manager_password: str = "manager123"

    @property
    def cors_origin_list(self) -> list[str]:
        return [s.strip() for s in self.cors_origins.split(",") if s.strip()]

    @property
    def cors_origin_regex_str(self) -> str | None:
        s = (self.cors_origin_regex or "").strip()
        return s or None


settings = Settings()


