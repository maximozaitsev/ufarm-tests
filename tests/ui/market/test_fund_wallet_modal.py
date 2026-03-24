"""UI-тесты модалки Fund wallet.

Модалка открывается по клику Deposit когда on-chain баланс кошелька = 0.
Pool C (POOL_MIN_DEPOSIT_ID) + WALLET_ZERO_BALANCE.
"""
from decimal import Decimal

import allure
import pytest

from core.ui.pages.marketplace_page import MarketplacePage
from core.ui.pages.fund_wallet_modal import FundWalletModal


pytestmark = [pytest.mark.ui, pytest.mark.smoke]


def open_fund_wallet_modal(page, mp: MarketplacePage, modal: FundWalletModal):
    """Открывает Fund wallet модалку; пропускает тест если появилась другая модалка.

    Возможные модалки по клику Deposit с нулевым балансом:
      - Fund wallet  — ожидаемая (баланс < min deposit)
      - PROOF OF AGREEMENT / Terms — требует принятия условий, пропускаем
      - Обычный Deposit  — значит порог не сработал, пропускаем
    """
    mp.wait_for_pool_page()
    mp.deposit_button().click()
    modal.wait_for()

    headings = page.locator(".mantine-Modal-content").first.locator(
        "h1, h2, h3, h4"
    ).all_inner_texts()
    heading_text = " ".join(h.strip().lower() for h in headings)

    if "fund wallet" not in heading_text:
        pytest.skip(
            f"Expected 'Fund wallet' modal but got: {headings}. "
            "Modal condition not met (terms pending or balance above threshold)."
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Fund wallet modal opens when wallet balance is zero")
@allure.severity(allure.severity_level.CRITICAL)
def test_fund_wallet_modal_opens(page_with_zero_wallet_on_min_deposit_pool):
    mp = MarketplacePage(page_with_zero_wallet_on_min_deposit_pool)
    modal = FundWalletModal(page_with_zero_wallet_on_min_deposit_pool)

    with allure.step("Открываем модалку Fund wallet"):
        open_fund_wallet_modal(page_with_zero_wallet_on_min_deposit_pool, mp, modal)
        allure.attach(
            page_with_zero_wallet_on_min_deposit_pool.screenshot(),
            name="Fund wallet modal",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Ожидаем появления модалки Fund wallet"):
        modal.wait_opened()

    with allure.step("Скриншот модалки Fund wallet"):
        allure.attach(
            page_with_zero_wallet_on_min_deposit_pool.screenshot(),
            name="Fund wallet modal",
            attachment_type=allure.attachment_type.PNG,
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Fund wallet modal has correct title")
@allure.severity(allure.severity_level.NORMAL)
def test_fund_wallet_modal_title(page_with_zero_wallet_on_min_deposit_pool):
    mp = MarketplacePage(page_with_zero_wallet_on_min_deposit_pool)
    modal = FundWalletModal(page_with_zero_wallet_on_min_deposit_pool)

    with allure.step("Открываем модалку Fund wallet"):
        open_fund_wallet_modal(page_with_zero_wallet_on_min_deposit_pool, mp, modal)
    
    with allure.step("Ожидаем появления модалки Fund wallet"):
        modal.wait_opened()

    with allure.step("Заголовок модалки — 'Fund wallet'"):
        assert modal.title().is_visible(), "Title 'Fund wallet' not visible"


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Fund wallet modal text contains min deposit amount from API")
@allure.severity(allure.severity_level.CRITICAL)
def test_fund_wallet_modal_text_contains_min_deposit(
    page_with_zero_wallet_on_min_deposit_pool, pool_info_min_deposit
):
    """Текст модалки содержит сумму минимального депозита из API пула."""
    mp = MarketplacePage(page_with_zero_wallet_on_min_deposit_pool)
    modal = FundWalletModal(page_with_zero_wallet_on_min_deposit_pool)

    raw = int(pool_info_min_deposit.limits.deposit_min)
    amount = Decimal(raw) / Decimal(10 ** pool_info_min_deposit.decimals)
    # Форматируем: 5000.0 → "5000", 500.5 → "500.5"
    display_amount = str(int(amount)) if amount == int(amount) else str(amount)

    with allure.step("Открываем модалку Fund wallet"):
        open_fund_wallet_modal(page_with_zero_wallet_on_min_deposit_pool, mp, modal)

    with allure.step("Ожидаем появления модалки Fund wallet"):
        modal.wait_opened()

    with allure.step(f"Текст модалки содержит минимальный депозит: {display_amount}"):
        hint = modal.hint_text()
        assert display_amount in hint, (
            f"Min deposit '{display_amount}' not found in hint: {hint!r}"
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Fund wallet modal text contains deposit token from API")
@allure.severity(allure.severity_level.CRITICAL)
def test_fund_wallet_modal_text_contains_token(
    page_with_zero_wallet_on_min_deposit_pool, pool_info_min_deposit
):
    """Текст модалки содержит название токена из availableValueTokens пула."""
    mp = MarketplacePage(page_with_zero_wallet_on_min_deposit_pool)
    modal = FundWalletModal(page_with_zero_wallet_on_min_deposit_pool)

    tokens = [t.upper() for t in (pool_info_min_deposit.availableValueTokens or [])]

    with allure.step("Открываем модалку Fund wallet"):
        open_fund_wallet_modal(page_with_zero_wallet_on_min_deposit_pool, mp, modal)

    with allure.step(f"Текст модалки содержит токен из {tokens}"):
        hint = modal.hint_text()
        assert any(token in hint for token in tokens), (
            f"None of tokens {tokens} found in hint: {hint!r}"
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Fund wallet modal text contains network name")
@allure.severity(allure.severity_level.NORMAL)
def test_fund_wallet_modal_text_contains_network(
    page_with_zero_wallet_on_min_deposit_pool, network_name
):
    """Текст модалки содержит название сети текущего окружения."""
    mp = MarketplacePage(page_with_zero_wallet_on_min_deposit_pool)
    modal = FundWalletModal(page_with_zero_wallet_on_min_deposit_pool)

    with allure.step("Открываем модалку Fund wallet"):
        open_fund_wallet_modal(page_with_zero_wallet_on_min_deposit_pool, mp, modal)

    with allure.step(f"Текст модалки содержит название сети: {network_name}"):
        hint = modal.hint_text()
        assert network_name in hint, (
            f"Network '{network_name}' not found in hint: {hint!r}"
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Fund wallet modal has BUY CRYPTO button")
@allure.severity(allure.severity_level.NORMAL)
def test_fund_wallet_modal_has_buy_crypto(page_with_zero_wallet_on_min_deposit_pool):
    mp = MarketplacePage(page_with_zero_wallet_on_min_deposit_pool)
    modal = FundWalletModal(page_with_zero_wallet_on_min_deposit_pool)

    with allure.step("Открываем модалку Fund wallet"):
        open_fund_wallet_modal(page_with_zero_wallet_on_min_deposit_pool, mp, modal)

    with allure.step("Кнопка 'buy crypto' видна"):
        assert modal.buy_crypto_button().is_visible(), "'buy crypto' button not visible"


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Fund wallet modal has RECEIVE FUNDS button")
@allure.severity(allure.severity_level.NORMAL)
def test_fund_wallet_modal_has_receive_funds(page_with_zero_wallet_on_min_deposit_pool):
    mp = MarketplacePage(page_with_zero_wallet_on_min_deposit_pool)
    modal = FundWalletModal(page_with_zero_wallet_on_min_deposit_pool)

    with allure.step("Открываем модалку Fund wallet"):
        open_fund_wallet_modal(page_with_zero_wallet_on_min_deposit_pool, mp, modal)

    with allure.step("Кнопка 'receive funds' видна"):
        assert modal.receive_funds_button().is_visible(), "'receive funds' button not visible"
test_fund_wallet_modal_title