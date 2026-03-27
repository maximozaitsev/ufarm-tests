"""Транзакционные UI-тесты: Withdraw.

Кошелёк: WALLET_TRX_ADDRESS / WALLET_TRX_PRIVATE_KEY
Пул:     TEST_POOL_ID (REF TEST, minClientTier=0, deposit_min=0, withdraw_delay=1s)

Тесты выполняют реальные on-chain операции на Arbitrum Mainnet.

Withdraw только gasless: пользователь подписывает EIP-712, relay отправляет транзакцию.
Кошелёк не тратит ETH на газ.

Зависимость от onchain_deposit:
  Фикстура onchain_deposit (scope=session, из conftest.py) гарантирует наличие
  LP-токенов перед тестом вывода. Транзакция депозита выполняется ОДИН РАЗ
  на всю сессию — переиспользуется и в test_deposit_trx.py.
"""

import allure
import pytest

from core.ui.pages.marketplace_page import MarketplacePage
from core.ui.pages.withdraw_modal import WithdrawModal

from .conftest import attach_tx_link


pytestmark = [pytest.mark.trx, pytest.mark.smoke]

# Сколько мс ждать появления модалки успеха после клика submit.
SIGNING_TIMEOUT_MS = 30_000


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Withdraw")
@allure.title("Gasless withdrawal request: relay accepts, UI shows success modal")
@allure.severity(allure.severity_level.CRITICAL)
def test_gasless_withdraw_request(page_with_trx_wallet, onchain_deposit):
    """Безгазовый запрос вывода принят relay: UI показывает модалку успеха.

    Зависит от onchain_deposit — гарантирует наличие LP-токенов для вывода.
    Вывод только gasless: пользователь подписывает EIP-712, relay отправляет транзакцию.
    После успеха — модалка «Request submitted», сообщение на странице пула не появляется.

    Шаги:
    1. Ждём кнопку Withdraw (LP-токены есть после on-chain депозита)
    2. Открываем модалку Withdraw, выбираем MAX
    3. Нажимаем «Request Withdrawal» → EIP-712 подпись через Python
    4. UI показывает модалку успеха
    """
    attach_tx_link(onchain_deposit.tx_hash)

    page = page_with_trx_wallet
    mp = MarketplacePage(page)
    modal = WithdrawModal(page)

    with allure.step("Ожидаем кнопку Withdraw (LP-токены доступны после депозита)"):
        mp.wait_for_withdraw_button()

    with allure.step("Открываем модалку Withdraw"):
        page.locator(".mantine-Modal-overlay").wait_for(state="hidden", timeout=5_000)
        mp.withdraw_button().click()
        modal.wait_for()
        allure.attach(
            page.screenshot(),
            name="Withdraw modal opened",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Выбираем MAX"):
        modal.max_button().click()

    with allure.step("Нажимаем «Request Withdrawal» (gasless — relay отправит tx)"):
        allure.attach(
            page.screenshot(),
            name="Before submit",
            attachment_type=allure.attachment_type.PNG,
        )
        modal.request_withdrawal_button().click()

    with allure.step("Ждём модалку успеха — relay принял подписи"):
        page.get_by_text("Request submitted").wait_for(timeout=SIGNING_TIMEOUT_MS)
        allure.attach(
            page.screenshot(),
            name="Success modal",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Модалка «Request submitted» видна"):
        assert page.get_by_text("Request submitted").is_visible()

    with allure.step("Закрываем модалку"):
        page.get_by_role("button", name="CLOSE").click()
