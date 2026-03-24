import json
import os
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from config.settings import settings
from core.api.client import APIClient


def _mock_auth_connect(page) -> None:
    """Мокает GET /auth/connect/{address} — возвращает createdAt мгновенно.

    Без мока реальный HTTP-запрос приходит с задержкой, и React не успевает
    обработать userData.createdAt до клика на Deposit. Это приводит к тому,
    что приложение показывает «PROOF OF AGREEMENT» вместо модалки депозита.

    Устанавливать ДО page.goto().
    """
    def _handler(route, _request):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"createdAt": "2024-01-01T00:00:00.000Z", "lastTopUp": None}),
        )

    page.route("**/auth/connect/**", _handler)


ENV_CONFIG = {
    "demo": {
        "base_url": "https://app.demo.ufarm.digital",
        "fund_url": "https://fund.demo.ufarm.digital/fund",
        "api_url": "https://api.demo.ufarm.digital/api/v1",
    },
    "prod_arb": {
        "base_url": "https://app.ufarm.digital",
        "fund_url": "https://fund.ufarm.digital/fund",
        "api_url": "https://api.ufarm.digital/api/v1",
    },
    "prod_eth": {
        "base_url": "https://black.ufarm.digital",
        "fund_url": "https://efund.ufarm.digital/fund",
        "api_url": "https://api.ufarm.digital/api/v2",
    },
}


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Сохраняет результат каждой фазы теста в item.rep_<when>.
    Нужно для фикстур, которые проверяют упал ли тест (например screenshot_on_failure).
    """
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


def pytest_addoption(parser):
    parser.addoption(
        "--env",
        action="store",
        default="demo",
        help="Target environment: demo | prod_arb | prod_eth",
    )
    parser.addoption(
        "--api-url",
        action="store",
        default=None,
        help="Override API base URL for tests (e.g. https://api.demo.ufarm.digital/api/v1)",
    )
    parser.addoption(
        "--test-pool-id",
        action="store",
        default=None,
        help="Override test pool ID (UUID)",
    )
    parser.addoption(
        "--test-wallet-address",
        action="store",
        default=None,
        help="Override test wallet address (0x...)",
    )
    parser.addoption(
        "--pool-single-token-id",
        action="store",
        default=None,
        help="Override single-token pool ID (UUID)",
    )
    parser.addoption(
        "--pool-min-deposit-id",
        action="store",
        default=None,
        help="Override min-deposit pool ID (UUID)",
    )
    parser.addoption(
        "--wallet-zero-balance",
        action="store",
        default=None,
        help="Override zero-balance wallet address (0x...)",
    )


@pytest.fixture(scope="session")
def env_name(request):
    env = request.config.getoption("--env")
    if env not in ENV_CONFIG:
        raise ValueError(f"Unknown env '{env}'. Use one of: {', '.join(ENV_CONFIG.keys())}")
    return env


@pytest.fixture(scope="session")
def env_config(env_name):
    return ENV_CONFIG[env_name]


@pytest.fixture(scope="session")
def api_url(request, env_config):
    override = request.config.getoption("--api-url")
    return override or env_config["api_url"]


@pytest.fixture(scope="session")
def base_url(env_config):
    return env_config["base_url"]


@pytest.fixture(scope="session")
def api_client(api_url):
    return APIClient(api_url)


@pytest.fixture(scope="session")
def test_pool_id(request):
    override = request.config.getoption("--test-pool-id")
    value = override or settings.test_pool_id
    if not value:
        raise ValueError("TEST_POOL_ID is not set. Add it to .env or pass --test-pool-id")
    return value


@pytest.fixture(scope="session")
def test_wallet_address(request):
    override = request.config.getoption("--test-wallet-address")
    value = override or settings.test_wallet_address
    if not value:
        raise ValueError("TEST_WALLET_ADDRESS is not set. Add it to .env or pass --test-wallet-address")
    return value


@pytest.fixture(scope="session")
def pool_single_token_id(request):
    override = request.config.getoption("--pool-single-token-id")
    value = override or settings.pool_single_token_id
    if not value:
        raise ValueError("POOL_SINGLE_TOKEN_ID is not set. Add it to .env or pass --pool-single-token-id")
    return value


@pytest.fixture(scope="session")
def pool_min_deposit_id(request):
    override = request.config.getoption("--pool-min-deposit-id")
    value = override or settings.pool_min_deposit_id
    if not value:
        raise ValueError("POOL_MIN_DEPOSIT_ID is not set. Add it to .env or pass --pool-min-deposit-id")
    return value


@pytest.fixture(scope="session")
def wallet_zero_balance(request):
    override = request.config.getoption("--wallet-zero-balance")
    value = override or settings.wallet_zero_balance
    if not value:
        raise ValueError("WALLET_ZERO_BALANCE is not set. Add it to .env or pass --wallet-zero-balance")
    return value


@pytest.fixture(scope="session", autouse=True)
def allure_environment(env_name, api_url, base_url):
    """Записывает environment.properties для Allure-отчёта."""
    yield
    results_dir = Path("allure-results")
    if results_dir.exists():
        props = (
            f"Environment={env_name.upper()}\n"
            f"API_URL={api_url}\n"
            f"Base_URL={base_url}\n"
            f"Python={os.popen('python --version').read().strip()}\n"
        )
        (results_dir / "environment.properties").write_text(props)


PROD_ETH_API_URL = "https://api.ufarm.digital/api/v2"


@pytest.fixture(scope="session")
def leaderboard_api_client():
    """APIClient для лидерборда и портфолио — всегда PROD ETH (v2), независимо от --env."""
    return APIClient(PROD_ETH_API_URL)


@pytest.fixture(scope="session")
def browser():
    # HEADED=1  — запустить в видимом браузере (для отладки)
    # SLOWMO=500 — замедлить каждое действие на N мс (вместе с HEADED)
    headed = os.environ.get("HEADED", "0") == "1"
    slow_mo = int(os.environ.get("SLOWMO", "0"))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed, slow_mo=slow_mo)
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    page = browser.new_page()
    yield page
    page.close()


@pytest.fixture
def page_with_wallet_on_pool(browser, base_url, test_pool_id, test_wallet_address):
    """Playwright Page на странице тестового пула с программно подключённым кошельком.

    Открывает /marketplace/pool/{test_pool_id}, инжектирует кошелёк.
    Используется для тестов Deposit/Withdrawal кнопок и модалок.
    """
    from core.ui.wallet_injection import inject_wallet

    page = browser.new_page()
    _mock_auth_connect(page)
    page.goto(f"{base_url}/marketplace/pool/{test_pool_id}", wait_until="networkidle")
    inject_wallet(page, test_wallet_address)
    # После inject_wallet приложение делает запросы за балансом пользователя —
    # ждём их завершения, чтобы Withdrawal кнопка появилась.
    page.wait_for_load_state("networkidle", timeout=15_000)
    yield page
    page.close()


@pytest.fixture
def page_with_wallet_on_single_token_pool(browser, base_url, pool_single_token_id, test_wallet_address):
    """Playwright Page на странице single-token пула с подключённым кошельком.

    Используется для тестов депозит-модалки без дропдауна токенов.
    """
    from core.ui.wallet_injection import inject_wallet

    page = browser.new_page()
    _mock_auth_connect(page)
    page.goto(f"{base_url}/marketplace/pool/{pool_single_token_id}", wait_until="networkidle")
    inject_wallet(page, test_wallet_address)
    page.wait_for_load_state("networkidle", timeout=15_000)
    yield page
    page.close()


@pytest.fixture(scope="module")
def page_with_zero_wallet_on_min_deposit_pool(browser, base_url, pool_min_deposit_id, wallet_zero_balance):
    """Playwright Page на странице пула с min deposit, кошелёк с нулевым балансом.

    module-scope: страница загружается один раз для всего модуля.
    Первый клик Deposit занимает ~15 сек (on-chain баланс-чек), последующие — быстро (кеш).

    Используется для теста модалки Fund wallet.
    """
    from core.ui.wallet_injection import inject_wallet

    page = browser.new_page()
    _mock_auth_connect(page)
    # "networkidle" недостижим для Pool C — пул делает долгие polling-запросы.
    page.goto(f"{base_url}/marketplace/pool/{pool_min_deposit_id}", wait_until="domcontentloaded", timeout=60_000)
    page.get_by_role("heading", level=1).wait_for(timeout=30_000)
    inject_wallet(page, wallet_zero_balance)
    try:
        page.wait_for_load_state("networkidle", timeout=10_000)
    except Exception:
        pass
    yield page
    page.close()


@pytest.fixture
def page_with_wallet(browser, base_url, test_wallet_address):
    """Playwright Page с программно подключённым тестовым кошельком.

    Открывает /marketplace, дожидается загрузки и инжектирует кошелёк
    напрямую в wagmi store через React Fiber — без модалки и подписей.
    После инжекции хедер показывает адрес кошелька вместо "Connect Wallet".

    Использование::

        def test_something(page_with_wallet, base_url, test_wallet_address):
            page = page_with_wallet
            # кошелёк уже подключён, можно работать с UI
    """
    from core.ui.wallet_injection import inject_wallet

    page = browser.new_page()
    page.goto(f"{base_url}/marketplace", wait_until="networkidle")
    inject_wallet(page, test_wallet_address)
    yield page
    page.close()
