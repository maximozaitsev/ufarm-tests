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

Изоляция:
  - Wallet отдельный от всех остальных тестов — конфликтов нет.
"""

import allure
import pytest

from core.ui.helpers.mocks import mock_auth_connect
from core.ui.helpers.trx_provider import inject_trx_provider
from core.ui.pages.deposit_modal import DepositModal
from core.ui.pages.marketplace_page import MarketplacePage


pytestmark = [pytest.mark.trx, pytest.mark.smoke]

DEPOSIT_AMOUNT = "1"  # 1 USDT

# Сколько мс ждать появления "Request submitted" после клика submit.
# Gasless flow: submit → 2x EIP-712 signing → relay → success modal.
SIGNING_TIMEOUT_MS = 30_000


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
