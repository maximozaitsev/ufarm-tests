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
        header_text = mp.nav_header().inner_text().lower()
        assert short_address in header_text, (
            f"Wallet address not visible in header. "
            f"Expected to find '{short_address}' in: {header_text!r}"
        )


@pytest.mark.ui
@pytest.mark.smoke
@allure.epic("Market")
@allure.feature("UI")
@allure.story("My Portfolio")
@allure.title("My portfolio page is accessible with connected wallet")
@allure.severity(allure.severity_level.CRITICAL)
def test_my_portfolio_accessible_with_wallet(page_with_wallet):
    """С подключённым кошельком клик на My portfolio ведёт на страницу портфолио, а не открывает Reown-модалку."""
    mp = MarketplacePage(page_with_wallet)

    with allure.step("Ждём загрузки карточек пулов"):
        mp.wait_for_pool_cards()

    with allure.step("Кликаем на таб My portfolio (SPA-навигация — wallet state сохраняется)"):
        mp.tab_my_portfolio().click()

    with allure.step("Ждём перехода на /my-portfolio"):
        page_with_wallet.wait_for_url("**/my-portfolio**", timeout=10_000)

    with allure.step("Скриншот страницы My portfolio"):
        allure.attach(
            page_with_wallet.screenshot(),
            name="My portfolio page",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Модалка Connect Wallet не появилась"):
        assert not mp.connect_wallet_modal().is_visible(), (
            "Reown modal appeared — wallet is not connected"
        )


@pytest.mark.ui
@pytest.mark.smoke
@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Deposit and Withdrawal buttons are visible on pool page with connected wallet")
@allure.severity(allure.severity_level.CRITICAL)
def test_deposit_withdrawal_buttons_visible_with_wallet(page_with_wallet_on_pool):
    """С подключённым кошельком на странице пула видны кнопки Deposit и Withdrawal,
    а не кнопка 'Connect wallet to deposit'."""
    mp = MarketplacePage(page_with_wallet_on_pool)

    with allure.step("Ждём загрузки страницы пула (h1 с названием)"):
        mp.wait_for_pool_page()

    with allure.step("Кнопка 'Deposit' видна"):
        assert mp.deposit_button().is_visible(), "Deposit button is not visible"

    with allure.step("Ждём появления кнопки 'Withdraw' (загрузка баланса по API)"):
        mp.wait_for_withdraw_button()

    with allure.step("Скриншот страницы пула с кошельком"):
        allure.attach(
            page_with_wallet_on_pool.screenshot(),
            name="Pool page with wallet",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Кнопка 'Connect wallet to deposit' не видна"):
        assert not mp.connect_to_deposit_button().is_visible(), (
            "'Connect wallet to deposit' is still visible — wallet not connected"
        )


@pytest.mark.ui
@pytest.mark.smoke
@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Deposit modal opens on Deposit button click")
@allure.severity(allure.severity_level.CRITICAL)
def test_deposit_modal_opens(page_with_wallet_on_pool):
    """Клик на кнопку Deposit открывает модалку депозита с переключателем Gasless transaction."""
    mp = MarketplacePage(page_with_wallet_on_pool)

    with allure.step("Ждём загрузки страницы пула"):
        mp.wait_for_pool_page()

    with allure.step("Кликаем на кнопку Deposit"):
        mp.deposit_button().click()

    with allure.step("Ждём появления модалки депозита"):
        # Проверяем что открылась любая mantine-модалка (deposit form или terms перед ней).
        # Детальную проверку содержимого см. в TODO test_deposit_form_content.
        page_with_wallet_on_pool.locator(".mantine-Modal-content").wait_for(
            state="visible", timeout=10_000
        )

    with allure.step("Скриншот модалки депозита"):
        allure.attach(
            page_with_wallet_on_pool.screenshot(),
            name="Deposit modal",
            attachment_type=allure.attachment_type.PNG,
        )


@pytest.mark.ui
@pytest.mark.smoke
@allure.epic("Market")
@allure.feature("UI")
@allure.story("Withdrawal")
@allure.title("Withdraw modal opens on Withdrawal button click")
@allure.severity(allure.severity_level.CRITICAL)
def test_withdraw_modal_opens(page_with_wallet_on_pool):
    """Клик на кнопку Withdrawal открывает модалку вывода с кнопкой 'Request Withdrawal'."""
    mp = MarketplacePage(page_with_wallet_on_pool)

    with allure.step("Ждём загрузки страницы пула"):
        mp.wait_for_pool_page()

    with allure.step("Ждём появления кнопки 'Withdraw' (загрузка баланса по API)"):
        mp.wait_for_withdraw_button()

    with allure.step("Кликаем на кнопку Withdraw"):
        mp.withdraw_button().click()

    with allure.step("Ждём появления кнопки 'Request Withdrawal' в модалке"):
        page_with_wallet_on_pool.get_by_text("Request Withdrawal").wait_for(
            state="visible", timeout=5_000
        )

    with allure.step("Скриншот модалки вывода"):
        allure.attach(
            page_with_wallet_on_pool.screenshot(),
            name="Withdraw modal",
            attachment_type=allure.attachment_type.PNG,
        )


@pytest.mark.ui
@pytest.mark.smoke
@allure.epic("Market")
@allure.feature("UI")
@allure.story("Withdrawal")
@allure.title("Withdraw button is not shown for wallet without deposits")
@allure.severity(allure.severity_level.CRITICAL)
def test_no_withdraw_button_for_wallet_without_deposits(page_with_zero_wallet_on_pool):
    """Кнопка Withdraw не появляется если у кошелька нет активных депозитов в пуле.

    Используется WALLET_ZERO_BALANCE на Pool B (TEST_POOL_ID).
    После загрузки баланса по API кнопка Withdraw должна отсутствовать.
    """
    mp = MarketplacePage(page_with_zero_wallet_on_pool)

    with allure.step("Ждём загрузки страницы пула"):
        mp.wait_for_pool_page()

    with allure.step("Ждём загрузки данных баланса (networkidle после inject_wallet)"):
        page_with_zero_wallet_on_pool.wait_for_timeout(5_000)

    with allure.step("Кнопка Deposit видна"):
        assert mp.deposit_button().is_visible(), "Deposit button should be visible"

    with allure.step("Скриншот страницы пула (кошелёк без депозитов)"):
        allure.attach(
            page_with_zero_wallet_on_pool.screenshot(),
            name="Pool page zero balance wallet",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Кнопка Withdraw отсутствует"):
        assert not mp.withdraw_button().is_visible(), (
            "Withdraw button should not be visible for wallet without deposits"
        )



@pytest.mark.ui
@pytest.mark.smoke
@allure.epic("Market")
@allure.feature("UI")
@allure.story("Wallet Connection")
@allure.title("SPA navigation preserves wallet connection")
@allure.severity(allure.severity_level.CRITICAL)
def test_spa_navigation_preserves_wallet(page_with_wallet_on_pool, test_wallet_address):
    """SPA-навигация pool → marketplace → pool не теряет подключённый кошелёк."""
    mp = MarketplacePage(page_with_wallet_on_pool)
    short_address = test_wallet_address[:6].lower()

    with allure.step("Стартуем на странице пула — кошелёк подключён"):
        mp.wait_for_pool_page()
        header_text = mp.nav_header().inner_text().lower()
        assert short_address in header_text, "Wallet not connected at start"

    with allure.step("Кликаем таб All products (SPA-переход на /marketplace)"):
        mp.tab_all_products().click()
        page_with_wallet_on_pool.wait_for_url("**/marketplace**", timeout=10_000)
        mp.wait_for_pool_cards()

    with allure.step("Кошелёк всё ещё подключён на странице маркета"):
        header_text = mp.nav_header().inner_text().lower()
        assert short_address in header_text, "Wallet lost after navigating to marketplace"

    with allure.step("Переходим на страницу первого пула"):
        mp.click_first_pool_card()
        mp.wait_for_pool_page()

    with allure.step("Кошелёк всё ещё подключён на странице пула"):
        header_text = mp.nav_header().inner_text().lower()
        assert short_address in header_text, "Wallet lost after navigating to pool page"

    with allure.step("Скриншот после SPA-навигации"):
        allure.attach(
            page_with_wallet_on_pool.screenshot(),
            name="Pool page after SPA navigation",
            attachment_type=allure.attachment_type.PNG,
        )
