"""UI-тесты страницы My Portfolio.

Кошелёк для тестов: PORTFOLIO_WALLET — основной тестовый кошелёк для ручного тестирования.
Имеет богатую историю депозитов/выводов на всех тестовых окружениях.

Покрытие:
  - Независимая верификация MY INVESTMENTS:
      on-chain balanceOf(poolAddress) × tokenPrice = portfolio.totalBalance (API) = UI значение
  - Структура карточек пулов и сортировка по My vault balance
  - UF-POINTS соответствуют API
"""

from decimal import Decimal

import allure
import pytest
import requests

from core.ui.helpers.mocks import mock_auth_connect
from core.ui.helpers.on_chain import get_erc20_balance, ARB_MAINNET_RPC
from core.ui.pages.marketplace_page import MarketplacePage
from core.ui.pages.portfolio_page import PortfolioPage


pytestmark = [pytest.mark.ui, pytest.mark.smoke]


# ── Фикстуры ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def page_on_portfolio(browser, base_url, wallet_active):
    """Браузерная страница My Portfolio с инжектированным wallet_active.

    module-scope: загружается один раз на все тесты файла.
    Использует SPA-навигацию (клик по табу) — page.goto после inject сбросил бы wagmi state.
    """
    from core.ui.helpers.wallet_injection import inject_wallet

    context = browser.new_context()
    page = context.new_page()
    mock_auth_connect(page)
    page.goto(f"{base_url}/marketplace", wait_until="networkidle")
    inject_wallet(page, wallet_active)

    mp = MarketplacePage(page)
    mp.wait_for_pool_cards()
    page.locator(".mantine-Modal-overlay").wait_for(state="hidden", timeout=5_000)
    mp.tab_my_portfolio().click()
    page.wait_for_url("**/my-portfolio**", timeout=10_000)
    page.wait_for_load_state("networkidle", timeout=15_000)

    portfolio = PortfolioPage(page)
    portfolio.wait_for()

    yield page
    context.close()


@pytest.fixture(scope="session")
def portfolio_api_data(api_url, wallet_active) -> dict:
    """Ответ API /user/portfolio/{wallet} для wallet_active."""
    resp = requests.get(
        f"{api_url}/user/portfolio/{wallet_active}", timeout=15
    )
    resp.raise_for_status()
    return resp.json()


@pytest.fixture(scope="session")
def portfolio_onchain_breakdown(portfolio_api_data, wallet_active) -> list[dict]:
    """On-chain расчёт MY INVESTMENTS с разбивкой по пулам.

    Для каждого пула с ненулевым балансом:
      1. on-chain: balanceOf(poolAddress, wallet) → LP-токены пользователя
      2. из API: poolMetric.tokenPrice → стоимость 1 LP-токена в $
      3. value_usd = lp_balance * tokenPrice

    Возвращает список dict с полями:
      pool_name, pool_address, lp_onchain, token_price, value_usd, poolstat_value
    """
    rows = []
    for pool in portfolio_api_data["pools"]:
        poolstat_raw = int(pool["poolStat"]["totalBalance"])
        if poolstat_raw == 0:
            continue
        pm = pool.get("poolMetric") or {}
        token_price = pm.get("tokenPrice")
        if token_price is None:
            continue
        lp_balance = get_erc20_balance(
            wallet=wallet_active,
            token_contract=pool["poolAddress"],
            rpc_url=ARB_MAINNET_RPC,
            decimals=pool.get("decimals", 6),
        )
        value_usd = lp_balance * Decimal(str(token_price))
        rows.append({
            "pool_name": pool["pool"],
            "pool_address": pool["poolAddress"],
            "lp_onchain": lp_balance,
            "token_price": Decimal(str(token_price)),
            "value_usd": value_usd,
            "poolstat_value": Decimal(poolstat_raw) / Decimal(10 ** pool.get("decimals", 6)),
        })
    return rows


@pytest.fixture(scope="session")
def portfolio_onchain_total(portfolio_onchain_breakdown) -> Decimal:
    """Суммарный MY INVESTMENTS из on-chain расчёта."""
    return sum((r["value_usd"] for r in portfolio_onchain_breakdown), Decimal("0"))


# ── API: верификация расчёта MY INVESTMENTS ───────────────────────────────────


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Portfolio")
@allure.title("MY INVESTMENTS (API) matches sum of on-chain LP balances × tokenPrice")
@allure.tag("cross-verified: on-chain")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.cross_verified
def test_my_investments_api_matches_onchain(
    portfolio_api_data, portfolio_onchain_breakdown, portfolio_onchain_total
):
    """Проверяет корректность индексера: сумма on-chain LP × tokenPrice = portfolio.totalBalance.

    Это чистый расчётный тест — браузер не нужен.
    Если тест падает — бэкенд неправильно индексирует балансы пользователя.
    """
    api_total = Decimal(portfolio_api_data["totalBalance"]) / Decimal(10**6)

    with allure.step("On-chain расчёт по пулам"):
        lines = [
            f"{'Pool':<28} {'LP on-chain':>14} {'tokenPrice':>11} {'value_usd':>10} {'poolStat':>10}",
            "-" * 77,
        ]
        for r in portfolio_onchain_breakdown:
            lines.append(
                f"{r['pool_name'][:28]:<28} "
                f"{r['lp_onchain']:>14.6f} "
                f"{r['token_price']:>11.4f} "
                f"{r['value_usd']:>10.4f} "
                f"{r['poolstat_value']:>10.4f}"
            )
        lines += [
            "-" * 77,
            f"{'Computed total (on-chain)':>55} {portfolio_onchain_total:>10.4f}",
            f"{'API portfolio.totalBalance':>55} {api_total:>10.4f}",
            f"{'Diff':>55} {abs(portfolio_onchain_total - api_total):>10.4f}",
        ]
        allure.attach(
            "\n".join(lines),
            name="On-chain breakdown vs API",
            attachment_type=allure.attachment_type.TEXT,
        )

    with allure.step(
        f"Сравниваем: on-chain={portfolio_onchain_total:.4f} vs API={api_total:.4f}"
    ):
        tolerance = Decimal("0.01")
        diff = abs(portfolio_onchain_total - api_total)
        assert diff <= tolerance, (
            f"MY INVESTMENTS mismatch: "
            f"on-chain={portfolio_onchain_total:.6f}, "
            f"api={api_total:.6f}, "
            f"diff={diff:.6f} (tolerance ±{tolerance})"
        )


# ── UI: структура Overview ─────────────────────────────────────────────────────


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Portfolio")
@allure.title("Portfolio overview section shows all three cards")
@allure.severity(allure.severity_level.NORMAL)
def test_portfolio_overview_structure(page_on_portfolio):
    """Три карточки Overview видны с правильными заголовками."""
    portfolio = PortfolioPage(page_on_portfolio)

    with allure.step("Скриншот страницы My Portfolio"):
        allure.attach(
            page_on_portfolio.screenshot(),
            name="Portfolio page",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Карточка 'My wallet' видна"):
        assert portfolio.my_wallet_heading().is_visible()

    with allure.step("Карточка 'My Investments' видна"):
        assert portfolio.my_investments_heading().is_visible()

    with allure.step("Карточка 'all-time profit' видна с realized/unrealized строками"):
        assert portfolio.all_time_profit_heading().is_visible()
        assert portfolio.realized_profit_label().first.is_visible()
        assert portfolio.unrealized_profit_label().first.is_visible()


# ── UI: верификация MY INVESTMENTS ────────────────────────────────────────────


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Portfolio")
@allure.title("MY INVESTMENTS (UI) matches on-chain LP × tokenPrice calculation")
@allure.tag("cross-verified: on-chain")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.cross_verified
def test_portfolio_investments_ui_matches_onchain(
    page_on_portfolio, portfolio_onchain_total
):
    """UI 'My Investments' совпадает с независимо вычисленной суммой on-chain.

    Цепочка верификации:
      on-chain balanceOf × tokenPrice (API) → computed_total
      computed_total ≈ UI 'My Investments' значение

    Допустимое отклонение ±0.5$: UI округляет до 1 знака, tokenPrice обновляется
    периодически (не real-time), разница в обычных условиях < $0.10.
    """
    portfolio = PortfolioPage(page_on_portfolio)

    with allure.step(f"Считываем MY INVESTMENTS из UI"):
        ui_value = portfolio.get_investments_usd()

    with allure.step(
        f"Сравниваем: UI={ui_value} vs on-chain расчёт={portfolio_onchain_total:.4f}"
    ):
        tolerance = Decimal("0.5")
        diff = abs(ui_value - portfolio_onchain_total)
        assert diff <= tolerance, (
            f"MY INVESTMENTS UI mismatch: "
            f"ui={ui_value}, "
            f"on-chain={portfolio_onchain_total:.6f}, "
            f"diff={diff:.6f} (tolerance ±{tolerance})"
        )


# ── UI: UF-POINTS ─────────────────────────────────────────────────────────────


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Portfolio")
@allure.title("UF-POINTS displayed matches API portfolio.points")
@allure.severity(allure.severity_level.NORMAL)
def test_portfolio_points_match_api(page_on_portfolio, portfolio_api_data):
    """UF-POINTS в UI совпадают с portfolio.points из API.

    Детальная верификация поинтов производится в тестах лидерборда.
    Здесь проверяем только что UI правильно отображает значение из API.
    """
    portfolio = PortfolioPage(page_on_portfolio)
    api_points = int(portfolio_api_data["points"])

    with allure.step(f"Считываем UF-POINTS из UI"):
        ui_points = portfolio.get_uf_points()

    with allure.step(f"Сравниваем: UI={ui_points} vs API={api_points}"):
        # Допуск ±1 — UI может округлять дробные поинты
        assert abs(ui_points - api_points) <= 1, (
            f"UF-POINTS mismatch: ui={ui_points}, api={api_points}"
        )


# ── UI: сортировка карточек пулов ─────────────────────────────────────────────


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Portfolio")
@allure.title("Pool cards are sorted by My vault balance descending")
@allure.severity(allure.severity_level.NORMAL)
def test_portfolio_pool_cards_sorted_by_vault_balance(page_on_portfolio):
    """Карточки пулов отсортированы по 'My vault balance' по убыванию.

    Это критично для UX: пользователь ожидает видеть крупнейшие позиции первыми.
    """
    portfolio = PortfolioPage(page_on_portfolio)

    with allure.step("Считываем список 'My vault balance' по всем карточкам"):
        balances = portfolio.get_pool_vault_balances()

    with allure.step(f"Проверяем сортировку ({len(balances)} карточек): {balances}"):
        assert len(balances) >= 1, "No pool cards found on portfolio page"
        assert balances == sorted(balances, reverse=True), (
            f"Pool cards not sorted by vault balance desc: {balances}"
        )
