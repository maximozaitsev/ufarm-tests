"""Фикстуры для UI-тестов маркетплейса: данные пулов и балансы кошельков."""
from decimal import Decimal

import pytest

from core.api.models.pool import PoolDetailResponse
from core.api.models.portfolio import Portfolio

# Публичный адрес Binance hot wallet на Arbitrum — держит сотни миллионов USDT.
# Используется для тестов, требующих кошелёк с балансом >= min deposit Pool C (5000 USDT).
_WHALE_WALLET = "0xF977814e90dA44bFA03b6295A0616a897441aceC"

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


@pytest.fixture(scope="module")
def page_with_whale_wallet_on_min_deposit_pool(browser, base_url, pool_min_deposit_id):
    """Playwright Page на Pool C с Binance hot wallet (баланс >> 5000 USDT).

    Используется для тестов валидации суммы ниже min deposit в модалке депозита.
    scope=module — Pool C делает долгие polling-запросы (networkidle недостижим).

    При старте проверяет что баланс кошелька >= 5000 USDT, иначе тест скипается.
    """
    from core.ui.on_chain import get_erc20_balance, USDT_ARB
    from core.ui.wallet_injection import inject_wallet
    from core.ui.mocks import mock_auth_connect

    whale_balance = get_erc20_balance(_WHALE_WALLET, USDT_ARB)
    if whale_balance < 5000:
        pytest.skip(
            f"Whale wallet {_WHALE_WALLET} balance dropped below 5000 USDT: {whale_balance}"
        )

    context = browser.new_context()
    page = context.new_page()
    mock_auth_connect(page)
    page.goto(
        f"{base_url}/marketplace/pool/{pool_min_deposit_id}",
        wait_until="domcontentloaded",
        timeout=60_000,
    )
    page.get_by_role("heading", level=1).wait_for(timeout=10_000)
    inject_wallet(page, _WHALE_WALLET)
    try:
        page.wait_for_load_state("networkidle", timeout=10_000)
    except Exception:
        pass
    yield page
    context.close()
