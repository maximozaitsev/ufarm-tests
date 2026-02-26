import pytest
from playwright.sync_api import sync_playwright
from config.settings import settings


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