import pytest
from playwright.sync_api import sync_playwright
from config.settings import settings
from core.api.client import APIClient


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
        "api_url": "https://api.ufarm.digital/api/v1",
    },
}


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
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    page = browser.new_page()
    yield page
    page.close()