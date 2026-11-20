from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    app_environment: str = 'development'
    database_url: str = 'postgresql+psycopg://tourismo:tourismo_dev@localhost:5432/tourismo'
    clerk_issuer: str = ''
    clerk_jwks_url: str = ''
    clerk_secret_key: str = ''
    clerk_audience: str = ''
    allowed_auth_origins: str = 'http://localhost:5173,http://localhost:8000'
    enable_phone_otp: bool = False
    enable_demo_catalog: bool = False  # Local development only; never a publishing bypass
    cors_origins: str = 'http://localhost:5173'
    web_dist_path: str = '/app/web-dist'
    vendor_document_dir: str = '/app/private_vendor_documents'
    vendor_clamav_host: str = ''
    vendor_clamav_port: int = Field(default=3310, ge=1, le=65535)
    rate_limit_requests: int = Field(default=120, ge=1, le=10000)

    @property
    def auth_ready(self) -> bool:
        return bool(self.clerk_issuer.startswith('https://') and
                    self.clerk_jwks_url.startswith('https://'))

    @property
    def accepted_origins(self) -> list[str]:
        return [value.strip().rstrip('/') for value in self.allowed_auth_origins.split(',') if value.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
