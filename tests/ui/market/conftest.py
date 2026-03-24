"""Фикстуры для UI-тестов маркетплейса: данные пулов и балансы кошельков."""
from decimal import Decimal

import pytest

from core.api.models.pool import PoolDetailResponse
from core.api.models.portfolio import Portfolio

# ── Карта сети по имени окружения ─────────────────────────────────────────────
NETWORK_BY_ENV = {
    "demo": "Arbitrum",
    "prod_arb": "Arbitrum",
    "prod_eth": "Ethereum",
}


# ── Данные пулов из API ───────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def pool_info_single_token(api_client, pool_single_token_id):
    """Детали single-token пула (Pool A) из API."""
    resp = api_client.get(f"/pool/{pool_single_token_id}")
    assert resp.status_code == 200
    return PoolDetailResponse.model_validate(resp.json()).pool


@pytest.fixture(scope="session")
def pool_info_multi_token(api_client, test_pool_id):
    """Детали multi-token пула (Pool B) из API."""
    resp = api_client.get(f"/pool/{test_pool_id}")
    assert resp.status_code == 200
    return PoolDetailResponse.model_validate(resp.json()).pool


@pytest.fixture(scope="session")
def pool_info_min_deposit(api_client, pool_min_deposit_id):
    """Детали пула с минимальным депозитом (Pool C) из API."""
    resp = api_client.get(f"/pool/{pool_min_deposit_id}")
    assert resp.status_code == 200
    return PoolDetailResponse.model_validate(resp.json()).pool


# ── Балансы кошельков ─────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def wallet_usdt_balance(test_wallet_address) -> Decimal:
    """On-chain USDT баланс WALLET_WITH_BALANCE на Arbitrum."""
    from core.ui.on_chain import get_erc20_balance, USDT_ARB
    return get_erc20_balance(test_wallet_address, USDT_ARB)


@pytest.fixture(scope="session")
def wallet_portfolio(api_client, test_wallet_address) -> Portfolio:
    """Portfolio данные WALLET_WITH_BALANCE из API."""
    resp = api_client.get(f"/user/portfolio/{test_wallet_address}")
    assert resp.status_code == 200
    return Portfolio.model_validate(resp.json())


@pytest.fixture(scope="session")
def network_name(env_name) -> str:
    """Название сети для текущего окружения (используется в проверке текста модалок)."""
    return NETWORK_BY_ENV[env_name]
