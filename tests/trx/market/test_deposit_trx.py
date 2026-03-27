"""Транзакционные UI-тесты: Deposit.

Кошелёк: WALLET_TRX_ADDRESS / WALLET_TRX_PRIVATE_KEY
Пул:     TEST_POOL_ID (REF TEST, minClientTier=0, deposit_min=0, withdraw_delay=1s)

Тесты выполняют реальные on-chain операции на Arbitrum Mainnet.

Режимы:
  - Gasless (безгазовый): пользователь подписывает два EIP-712 сообщения
    (USDT Permit + UFarm deposit), relay отправляет транзакцию.
    Кошелёк не тратит ETH на газ. Депозит требует одобрения управляющего фонда.
  - On-chain (прямой): browser вызывает eth_sendTransaction, Python подписывает
    и отправляет raw tx напрямую на Arbitrum. Требует ETH для газа.
    LP-баланс растёт сразу после подтверждения транзакции.

On-chain тесты: паттерн "setup once, assert many"
  Фикстура onchain_deposit (scope=module) выполняет ONE транзакцию и собирает
  состояние до/после. Каждый тест проверяет один аспект результата независимо.
  Если упадёт тест баланса UI — тест факта транзакции остаётся зелёным.
  Если упадёт сама фикстура (tx не прошла) — все зависимые тесты → ERROR.

Изоляция:
  - Wallet отдельный от всех остальных тестов — конфликтов нет.
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


pytestmark = [pytest.mark.trx, pytest.mark.smoke]

DEPOSIT_AMOUNT = "1"        # 1 USDT gasless
DEPOSIT_AMOUNT_ONCHAIN = "0.5"  # 0.5 USDT on-chain (direct, with gas)

# Сколько мс ждать появления "Request submitted" после клика submit.
# Gasless flow: submit → 2x EIP-712 signing → relay → success modal.
SIGNING_TIMEOUT_MS = 30_000


# ── Dataclass для результата on-chain депозита ─────────────────────────────────


@dataclass
class OnchainDepositResult:
    """Состояние до и после on-chain депозита (собирается фикстурой onchain_deposit).

    Фикстура хранит скриншоты и данные здесь. Каждый тест сам решает
    что показать в своём body через allure.step / allure.attach.
    """
    deposit_confirmed_modal_appeared: bool  # UI показал модалку «Deposit confirmed»
    screenshot_modal: bytes     # скриншот модалки «Deposit confirmed»
    screenshot_after: bytes     # скриншот страницы пула после обновления UI
    usdt_before: Decimal    # USDT on-chain до депозита
    tokens_before: float    # LP tokens в UI до депозита
    usdt_after: Decimal     # USDT on-chain после депозита
    tokens_after: float     # LP tokens в UI после депозита
    pool_usd_after: Decimal     # MY BALANCE USD в UI после депозита
    wallet_usd_after: Decimal   # MY WALLET USD в UI после депозита


# ── Фикстуры ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def trx_wallet_address(request) -> str:
    """Адрес кошелька для транзакционных тестов."""
    override = request.config.getoption("--wallet-trx-address", default=None)
    value = override or pytest.importorskip("config.settings").settings.wallet_trx_address
    if not value:
        pytest.skip("WALLET_TRX_ADDRESS not set")
    return value


@pytest.fixture(scope="module")
def trx_wallet_private_key(request) -> str:
    """Приватный ключ кошелька для транзакционных тестов."""
    override = request.config.getoption("--wallet-trx-private-key", default=None)
    value = override or pytest.importorskip("config.settings").settings.wallet_trx_private_key
    if not value:
        pytest.skip("WALLET_TRX_PRIVATE_KEY not set")
    return value


@pytest.fixture(scope="module")
def page_with_trx_wallet(
    browser, base_url, test_pool_id, trx_wallet_address, trx_wallet_private_key
):
    """Страница пула с реальным Ethereum-провайдером (подписывает транзакции).

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

    # Шаг 1: инжектируем провайдер ДО goto
    inject_trx_provider(page, private_key=trx_wallet_private_key)

    page.goto(f"{base_url}/marketplace/pool/{test_pool_id}", wait_until="networkidle")

    # Шаг 2: устанавливаем wagmi state (UI видит кошелёк как подключённый)
    inject_wallet(page, trx_wallet_address)
    page.wait_for_load_state("networkidle", timeout=15_000)

    yield page
    context.close()


@pytest.fixture(scope="module")
def onchain_deposit(page_with_trx_wallet, trx_wallet_address) -> OnchainDepositResult:
    """Выполняет on-chain депозит 0.5 USDT и возвращает состояние до/после.

    Запускается ОДИН РАЗ на весь модуль. Все зависимые тесты получают
    один и тот же объект OnchainDepositResult — транзакция не повторяется.

    Если фикстура упадёт (tx не прошла, модалка не появилась) — все зависимые
    тесты будут помечены как ERROR, что сигнализирует о сбое транзакции,
    а не о сбое отдельной проверки.
    """
    page = page_with_trx_wallet
    mp = MarketplacePage(page)
    modal = DepositModal(page)

    # ── До депозита ─────────────────────────────────────────────────────────
    with allure.step("Фиксируем состояние до депозита"):
        usdt_before = get_erc20_balance(trx_wallet_address, USDT_ARB)
        tokens_before = mp.get_pool_balance_tokens()

    # ── Депозит ─────────────────────────────────────────────────────────────
    with allure.step("Открываем модалку Deposit, отключаем gasless"):
        page.locator(".mantine-Modal-overlay").wait_for(state="hidden", timeout=5_000)
        mp.deposit_button().click()
        modal.wait_for()
        modal.gasless_toggle().evaluate("el => el.click()")
        assert not modal.gasless_toggle().is_checked(), "Gasless toggle должен быть выключен"

    with allure.step(f"Вводим {DEPOSIT_AMOUNT_ONCHAIN} USDT и отправляем"):
        modal.amount_input().fill(DEPOSIT_AMOUNT_ONCHAIN)
        modal.submit_button().click()

    with allure.step("Ждём модалку «Deposit confirmed» (tx подтверждена on-chain)"):
        # On-chain flow: submit → eth_sendTransaction → Python signs + broadcasts →
        # tx confirmed on Arbitrum (~0.25s block time) → UI shows success modal.
        page.get_by_text("Deposit confirmed").wait_for(timeout=60_000)
        deposit_confirmed = page.get_by_text("Deposit confirmed").is_visible()
        screenshot_modal = page.screenshot()

    with allure.step("Закрываем модалку, ждём обновления UI"):
        page.get_by_role("button", name="CLOSE").click()
        mp.wait_for_pool_tokens_above(tokens_before)

    # ── После депозита ───────────────────────────────────────────────────────
    with allure.step("Читаем состояние после депозита"):
        usdt_after = get_erc20_balance(trx_wallet_address, USDT_ARB)
        tokens_after = mp.get_pool_balance_tokens()
        pool_usd_after = mp.get_pool_balance_usd()
        wallet_usd_after = mp.get_wallet_balance_usd()
        screenshot_after = page.screenshot()

    return OnchainDepositResult(
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


# ── Тесты ─────────────────────────────────────────────────────────────────────


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Deposit")
@allure.title("Gasless deposit 1 USDT: relay accepts request, UI shows pending approval")
@allure.severity(allure.severity_level.CRITICAL)
def test_gasless_deposit_pending_approval(page_with_trx_wallet):
    """Безгазовый депозит 1 USDT принят relay: UI показывает 'Request submitted'.

    Gasless-режим: пользователь подписывает два EIP-712 сообщения
    (USDT EIP-2612 Permit + UFarm deposit), relay отправляет транзакцию.
    Кошелёк не тратит ETH на газ. LP-баланс растёт после одобрения управляющего.

    Шаги:
    1. Открываем модалку Deposit, вводим 1 USDT, нажимаем «Request Deposit»
    2. Провайдер подписывает оба EIP-712 сообщения через Python (~мгновенно)
    3. Relay получает подписи и создаёт pending deposit
    4. UI показывает модалку «Request submitted»
    5. После закрытия модалки — страница пула показывает 'pending approval'
    """
    page = page_with_trx_wallet
    mp = MarketplacePage(page)
    modal = DepositModal(page)

    with allure.step("Открываем модалку Deposit"):
        mp.wait_for_pool_cards()
        page.locator(".mantine-Modal-overlay").wait_for(state="hidden", timeout=5_000)
        mp.deposit_button().click()
        modal.wait_for()

    with allure.step(f"Вводим {DEPOSIT_AMOUNT} USDT (gasless toggle ON по умолчанию)"):
        modal.amount_input().fill(DEPOSIT_AMOUNT)

    with allure.step("Нажимаем «Request Deposit» (gasless — relay отправит tx)"):
        allure.attach(
            page.screenshot(),
            name="Before submit",
            attachment_type=allure.attachment_type.PNG,
        )
        modal.submit_button().click()

    with allure.step("Ждём модалку «Request submitted» — relay принял подписи"):
        # Gasless flow: submit → signing (2x EIP-712) → relay → success modal.
        # Signing is near-instant (Python crypto). publicnode.com RPC calls
        # are proxied via Python route handler so they also complete quickly.
        page.get_by_text("Request submitted").wait_for(timeout=SIGNING_TIMEOUT_MS)
        allure.attach(
            page.screenshot(),
            name="Request submitted modal",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Модалка «Request submitted» видна"):
        assert page.get_by_text("Request submitted").is_visible()

    with allure.step("Закрываем модалку, проверяем статус на странице пула"):
        page.get_by_role("button", name="CLOSE").click()
        pending = page.get_by_text("Your deposit request is pending approval")
        pending.wait_for(timeout=5_000)
        allure.attach(
            page.screenshot(),
            name="Pending approval on pool page",
            attachment_type=allure.attachment_type.PNG,
        )
        assert pending.is_visible()


# ── On-chain deposit: setup once, assert many ─────────────────────────────────
# Все тесты ниже зависят от фикстуры onchain_deposit (scope=module).
# Транзакция выполняется ОДИН РАЗ. Каждый тест проверяет один аспект независимо.


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Deposit")
@allure.title("On-chain deposit: UI shows «Deposit confirmed» modal")
@allure.severity(allure.severity_level.CRITICAL)
def test_onchain_deposit_confirmed_modal(onchain_deposit: OnchainDepositResult):
    """UI показал модалку «Deposit confirmed» после подтверждения tx on-chain."""
    with allure.step("Модалка «Deposit confirmed» появилась"):
        allure.attach(
            onchain_deposit.screenshot_modal,
            name="Deposit confirmed modal",
            attachment_type=allure.attachment_type.PNG,
        )
        assert onchain_deposit.deposit_confirmed_modal_appeared, (
            "Модалка «Deposit confirmed» не появилась"
        )


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Deposit")
@allure.title("On-chain deposit: tx confirmed on-chain (USDT decreased)")
@allure.severity(allure.severity_level.CRITICAL)
def test_onchain_deposit_usdt_decreased(onchain_deposit: OnchainDepositResult):
    """On-chain депозит подтверждён: USDT on-chain уменьшился на ~0.5 USDT."""
    d = onchain_deposit
    with allure.step(f"USDT on-chain: {d.usdt_before} → {d.usdt_after}"):
        assert d.usdt_after < d.usdt_before - Decimal("0.4"), (
            f"USDT on-chain должен уменьшиться примерно на {DEPOSIT_AMOUNT_ONCHAIN}: "
            f"{d.usdt_before} → {d.usdt_after}"
        )


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Deposit")
@allure.title("On-chain deposit: LP tokens in UI increased")
@allure.severity(allure.severity_level.NORMAL)
def test_onchain_deposit_lp_tokens_increased(onchain_deposit: OnchainDepositResult):
    """После on-chain депозита LP-токены в секции MY BALANCE выросли."""
    d = onchain_deposit
    with allure.step(f"LP tokens в UI: {d.tokens_before} → {d.tokens_after}"):
        allure.attach(
            onchain_deposit.screenshot_after,
            name="Pool page after deposit",
            attachment_type=allure.attachment_type.PNG,
        )
        assert d.tokens_after > d.tokens_before, (
            f"LP tokens не выросли: {d.tokens_before} → {d.tokens_after}"
        )


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Deposit")
@allure.title("On-chain deposit: MY WALLET USD in UI decreased")
@allure.severity(allure.severity_level.NORMAL)
def test_onchain_deposit_wallet_ui_decreased(onchain_deposit: OnchainDepositResult):
    """После on-chain депозита баланс в секции MY WALLET (UI) уменьшился."""
    d = onchain_deposit
    with allure.step(f"MY WALLET (UI): {d.wallet_usd_after} (было ~{d.usdt_before} on-chain)"):
        allure.attach(
            onchain_deposit.screenshot_after,
            name="Pool page after deposit",
            attachment_type=allure.attachment_type.PNG,
        )
        # Сравниваем с on-chain балансом до — reference point,
        # т.к. UI wallet balance до депозита мог не загрузиться (async).
        assert d.wallet_usd_after < d.usdt_before - Decimal("0.4"), (
            f"MY WALLET (UI) должен быть меньше on-chain до ({d.usdt_before}) на ~{DEPOSIT_AMOUNT_ONCHAIN}: "
            f"got {d.wallet_usd_after}"
        )
