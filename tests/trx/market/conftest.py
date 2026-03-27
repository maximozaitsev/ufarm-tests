"""Shared fixtures для TRX-тестов маркетплейса.

Все фикстуры scope="session" — страница и результаты транзакций создаются
один раз на всю сессию и переиспользуются в test_deposit_trx.py и test_withdraw_trx.py.
"""

from dataclasses import dataclass
from decimal import Decimal

import allure
import pytest

from core.ui.helpers.mocks import mock_auth_connect
from core.ui.helpers.on_chain import USDT_ARB, get_erc20_balance
from core.ui.helpers.trx_provider import inject_trx_provider
from core.ui.pages.deposit_modal import DepositModal
from core.ui.pages.marketplace_page import MarketplacePage


# ── Константы ─────────────────────────────────────────────────────────────────

DEPOSIT_AMOUNT_ONCHAIN = "0.5"  # 0.5 USDT on-chain (direct, with gas)

ARBISCAN_TX_URL = "https://arbiscan.io/tx/{tx_hash}"
ETHERSCAN_TX_URL = "https://etherscan.io/tx/{tx_hash}"


# ── Утилиты ───────────────────────────────────────────────────────────────────


def attach_tx_link(tx_hash: str, chain: str = "arbitrum") -> None:
    """Прикрепляет ссылку на транзакцию в блокчейн-эксплорере к Allure-отчёту.

    Вызывать в теле каждого теста с on-chain транзакцией.
    Ссылка видна в отчёте независимо от результата теста.

    Args:
        tx_hash: хэш транзакции (0x...)
        chain: "arbitrum" → Arbiscan, "ethereum" → Etherscan
    """
    if not tx_hash:
        return
    if chain == "ethereum":
        url = ETHERSCAN_TX_URL.format(tx_hash=tx_hash)
        name = f"Etherscan: {tx_hash[:10]}…"
    else:
        url = ARBISCAN_TX_URL.format(tx_hash=tx_hash)
        name = f"Arbiscan: {tx_hash[:10]}…"
    allure.dynamic.link(url, name=name)


# ── Dataclass ─────────────────────────────────────────────────────────────────


@dataclass
class OnchainDepositResult:
    """Состояние до и после on-chain депозита (собирается фикстурой onchain_deposit).

    Фикстура хранит скриншоты и данные здесь. Каждый тест сам решает
    что показать в своём body через allure.step / allure.attach.
    """
    tx_hash: str            # хэш on-chain транзакции (для ссылки на Arbiscan)
    deposit_confirmed_modal_appeared: bool  # UI показал модалку «Deposit confirmed»
    screenshot_modal: bytes     # скриншот модалки «Deposit confirmed»
    screenshot_after: bytes     # скриншот страницы пула после обновления UI
    usdt_before: Decimal    # USDT on-chain до депозита
    tokens_before: float    # LP tokens в UI до депозита
    usdt_after: Decimal     # USDT on-chain после депозита
    tokens_after: float     # LP tokens в UI после депозита
    pool_usd_after: Decimal     # MY BALANCE USD в UI после депозита
    wallet_usd_after: Decimal   # MY WALLET USD в UI после депозита


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def trx_wallet_address(request) -> str:
    """Адрес кошелька для транзакционных тестов."""
    override = request.config.getoption("--wallet-trx-address", default=None)
    value = override or pytest.importorskip("config.settings").settings.wallet_trx_address
    if not value:
        pytest.skip("WALLET_TRX_ADDRESS not set")
    return value


@pytest.fixture(scope="session")
def trx_wallet_private_key(request) -> str:
    """Приватный ключ кошелька для транзакционных тестов."""
    override = request.config.getoption("--wallet-trx-private-key", default=None)
    value = override or pytest.importorskip("config.settings").settings.wallet_trx_private_key
    if not value:
        pytest.skip("WALLET_TRX_PRIVATE_KEY not set")
    return value


@pytest.fixture(scope="session")
def page_with_trx_wallet(
    browser, base_url, test_pool_id, trx_wallet_address, trx_wallet_private_key
):
    """Страница пула с реальным Ethereum-провайдером (подписывает транзакции).

    scope="session" — страница создаётся один раз и переиспользуется
    в test_deposit_trx.py и test_withdraw_trx.py.

    Два слоя инжекции:
    1. inject_trx_provider (ДО goto) — устанавливает window.ethereum с реальным сайнером,
       чтобы wagmi подхватил провайдер при инициализации.
    2. inject_wallet (ПОСЛЕ goto) — устанавливает wagmi store state в "connected",
       чтобы UI показал адрес кошелька и кнопку Deposit.
    """
    from core.ui.helpers.wallet_injection import inject_wallet

    context = browser.new_context()
    page = context.new_page()
    mock_auth_connect(page)

    inject_trx_provider(page, private_key=trx_wallet_private_key)
    page.goto(f"{base_url}/marketplace/pool/{test_pool_id}", wait_until="networkidle")
    inject_wallet(page, trx_wallet_address)
    page.wait_for_load_state("networkidle", timeout=15_000)

    yield page
    context.close()


@pytest.fixture(scope="session")
def onchain_deposit(page_with_trx_wallet, trx_wallet_address) -> OnchainDepositResult:
    """Выполняет on-chain депозит 0.5 USDT и возвращает состояние до/после.

    scope="session" — транзакция выполняется ОДИН РАЗ на всю сессию.
    Зависимые тесты из разных файлов (deposit, withdraw) получают один объект.

    Если фикстура упадёт (tx не прошла) — все зависимые тесты → ERROR.
    """
    page = page_with_trx_wallet
    mp = MarketplacePage(page)
    modal = DepositModal(page)

    with allure.step("Фиксируем состояние до депозита"):
        usdt_before = get_erc20_balance(trx_wallet_address, USDT_ARB)
        tokens_before = mp.get_pool_balance_tokens()

    with allure.step("Открываем модалку Deposit, отключаем gasless"):
        page.locator(".mantine-Modal-overlay").wait_for(state="hidden", timeout=5_000)
        mp.deposit_button().click()
        modal.wait_for()
        modal.gasless_toggle().evaluate("el => el.click()")
        assert not modal.gasless_toggle().is_checked(), "Gasless toggle должен быть выключен"

    with allure.step(f"Вводим {DEPOSIT_AMOUNT_ONCHAIN} USDT и отправляем"):
        modal.amount_input().fill(DEPOSIT_AMOUNT_ONCHAIN)
        modal.submit_button().click()
        page.wait_for_function("() => !!window.__last_tx_hash", timeout=30_000)
        tx_hash = page.evaluate("window.__last_tx_hash") or ""

    with allure.step("Ждём модалку «Deposit confirmed» (tx подтверждена on-chain)"):
        page.get_by_text("Deposit confirmed").wait_for(timeout=60_000)
        deposit_confirmed = page.get_by_text("Deposit confirmed").is_visible()
        screenshot_modal = page.screenshot()

    with allure.step("Закрываем модалку, ждём обновления UI"):
        page.get_by_role("button", name="CLOSE").click()
        mp.wait_for_pool_tokens_above(tokens_before)

    with allure.step("Читаем состояние после депозита"):
        usdt_after = get_erc20_balance(trx_wallet_address, USDT_ARB)
        tokens_after = mp.get_pool_balance_tokens()
        pool_usd_after = mp.get_pool_balance_usd()
        wallet_usd_after = mp.get_wallet_balance_usd()
        screenshot_after = page.screenshot()

    return OnchainDepositResult(
        tx_hash=tx_hash,
        deposit_confirmed_modal_appeared=deposit_confirmed,
        screenshot_modal=screenshot_modal,
        screenshot_after=screenshot_after,
        usdt_before=usdt_before,
        tokens_before=tokens_before,
        usdt_after=usdt_after,
        tokens_after=tokens_after,
        pool_usd_after=pool_usd_after,
        wallet_usd_after=wallet_usd_after,
    )
