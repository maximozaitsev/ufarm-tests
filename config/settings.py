from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    base_url: str = "https://app.demo.ufarm.digital"
    fund_url: str = "https://fund.demo.ufarm.digital/fund"
    api_url: str = "https://api.demo.ufarm.digital/api/v1"
    test_pool_id: str = ""
    test_wallet_address: str = ""
    pool_single_token_id: str = ""
    pool_min_deposit_id: str = ""
    wallet_zero_balance: str = ""
    wallet_no_eth: str = ""

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()