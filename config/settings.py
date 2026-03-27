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
    # Активный кошелёк для ручного тестирования — богатая история, баланс постоянно меняется.
    # Подходит для: проверок структуры портфолио, истории транзакций, реалтайм-данных.
    # Не подходит для: проверок конкретных сумм и стабильных балансов.
    wallet_active: str = "0x2AB1aB42a102735B79DB03ff5fBBfA4fd63C414D"
    # Кошелёк для транзакционных тестов — реально подписывает и отправляет tx.
    # Приватный ключ хранить ТОЛЬКО в GitHub Secrets, не в .env!
    wallet_trx_address: str = ""
    wallet_trx_private_key: str = ""

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()