import allure
import pytest

from core.ui.pages.marketplace_page import MarketplacePage


@pytest.mark.ui
@pytest.mark.smoke
@allure.epic("Market")
@allure.feature("UI")
@allure.story("Wallet Connection")
@allure.title("Connected wallet address is shown in header")
@allure.severity(allure.severity_level.CRITICAL)
def test_wallet_address_shown_in_header(page_with_wallet, base_url, test_wallet_address):
    """page_with_wallet — страница уже открыта на /marketplace с инжектированным кошельком."""
    mp = MarketplacePage(page_with_wallet)

    with allure.step("Ждём загрузки карточек пулов"):
        mp.wait_for_pool_cards()

    with allure.step("Скриншот хедера после инжекции кошелька"):
        allure.attach(
            page_with_wallet.screenshot(),
            name="Header after wallet inject",
            attachment_type=allure.attachment_type.PNG,
        )

    short_address = test_wallet_address[:6].lower()

    with allure.step(f"В хедере виден адрес кошелька (начало: {short_address}...)"):
        header_text = page_with_wallet.locator("header").inner_text().lower()
        assert short_address in header_text, (
            f"Wallet address not visible in header. "
            f"Expected to find '{short_address}' in: {header_text!r}"
        )
