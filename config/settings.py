from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    base_url: str
    fund_url: str
    api_url: str
    test_pool_id: str = ""
    test_wallet_address: str = ""

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()