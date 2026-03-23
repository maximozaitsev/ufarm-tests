import allure
import pytest

from core.ui.pages.marketplace_page import MarketplacePage


@pytest.mark.ui
@pytest.mark.smoke
@allure.epic("Market")
@allure.feature("UI")
@allure.story("Marketplace")
@allure.title("Marketplace page loads with correct title")
@allure.severity(allure.severity_level.CRITICAL)
def test_marketplace_page_loads(page, base_url):
    mp = MarketplacePage(page)

    with allure.step(f"Открываем {base_url}/marketplace"):
        mp.open(f"{base_url}/marketplace")

    with allure.step("Ждём появления карточек пулов"):
        mp.wait_for_pool_cards()

    with allure.step("Заголовок страницы == 'Marketplace'"):
        assert page.title() == "Marketplace", f"Unexpected title: {page.title()!r}"


@pytest.mark.ui
@pytest.mark.smoke
@allure.epic("Market")
@allure.feature("UI")
@allure.story("Marketplace")
@allure.title("Header contains logo, both tabs, and Connect Wallet button")
@allure.severity(allure.severity_level.NORMAL)
def test_header_elements_visible(page, base_url):
    mp = MarketplacePage(page)

    with allure.step(f"Открываем {base_url}/marketplace"):
        mp.open(f"{base_url}/marketplace")
        mp.wait_for_pool_cards()

    with allure.step("Логотип UFarm виден в хедере"):
        assert mp.logo().is_visible(), "Logo not visible"

    with allure.step("Таб 'All products' виден в хедере"):
        assert mp.tab_all_products().is_visible(), "Tab 'All products' not visible"

    with allure.step("Таб 'My portfolio' виден в хедере"):
        assert mp.tab_my_portfolio().is_visible(), "Tab 'My portfolio' not visible"

    with allure.step("Кнопка 'Connect Wallet' видна в хедере"):
        assert mp.connect_wallet_button().is_visible(), "Connect Wallet button not visible"


@pytest.mark.ui
@pytest.mark.smoke
@allure.epic("Market")
@allure.feature("UI")
@allure.story("Marketplace")
@allure.title("Pool cards are displayed on marketplace page")
@allure.severity(allure.severity_level.CRITICAL)
def test_pool_cards_displayed(page, base_url):
    mp = MarketplacePage(page)

    with allure.step(f"Открываем {base_url}/marketplace"):
        mp.open(f"{base_url}/marketplace")
        mp.wait_for_pool_cards()

    cards_count = mp.pool_cards().count()

    with allure.step(f"На странице отображается минимум 1 карточка пула (найдено {cards_count})"):
        assert cards_count >= 1, f"Expected at least 1 pool card, got {cards_count}"

    print(f"\n  Карточек пулов на странице: {cards_count}")


@pytest.mark.ui
@pytest.mark.smoke
@allure.epic("Market")
@allure.feature("UI")
@allure.story("Marketplace")
@allure.title("Clicking pool card navigates to pool page")
@allure.severity(allure.severity_level.CRITICAL)
def test_pool_card_navigation(page, base_url):
    mp = MarketplacePage(page)

    with allure.step(f"Открываем {base_url}/marketplace"):
        mp.open(f"{base_url}/marketplace")
        mp.wait_for_pool_cards()

    with allure.step("Кликаем на первую карточку пула"):
        mp.click_first_pool_card()
        page.wait_for_url("**/marketplace/pool/**")

    pool_url = page.url
    print(f"\n  Перешли на: {pool_url}")

    with allure.step(f"URL содержит '/marketplace/pool/' (получен: {pool_url})"):
        assert "/marketplace/pool/" in pool_url, (
            f"Expected URL with '/marketplace/pool/', got: {pool_url}"
        )


@pytest.mark.ui
@pytest.mark.smoke
@allure.epic("Market")
@allure.feature("UI")
@allure.story("Pool Page")
@allure.title("Pool page shows pool name, deposit block and Connect Wallet button")
@allure.severity(allure.severity_level.CRITICAL)
def test_pool_page_elements_visible(page, base_url):
    mp = MarketplacePage(page)

    with allure.step(f"Открываем {base_url}/marketplace и переходим на первый пул"):
        mp.open(f"{base_url}/marketplace")
        mp.wait_for_pool_cards()
        mp.click_first_pool_card()
        page.wait_for_url("**/marketplace/pool/**")
        mp.wait_for_pool_page()

    pool_name = mp.pool_name().text_content()
    print(f"\n  Пул: {pool_name!r}")

    with allure.step(f"Название пула (h1) видно: '{pool_name}'"):
        assert mp.pool_name().is_visible(), "Pool name h1 not visible"
        assert pool_name.strip(), "Pool name is empty"

    with allure.step("Кнопка 'Connect wallet to deposit' видна (кошелёк не подключён)"):
        assert mp.connect_to_deposit_button().is_visible(), (
            "Button 'Connect wallet to deposit' not visible"
        )


@pytest.mark.ui
@pytest.mark.smoke
@allure.epic("Market")
@allure.feature("UI")
@allure.story("Pool Page")
@allure.title("Pool page shows Transactions and Actions history tabs")
@allure.severity(allure.severity_level.NORMAL)
def test_pool_page_history_tabs_visible(page, base_url):
    mp = MarketplacePage(page)

    with allure.step(f"Открываем {base_url}/marketplace и переходим на первый пул"):
        mp.open(f"{base_url}/marketplace")
        mp.wait_for_pool_cards()
        mp.click_first_pool_card()
        page.wait_for_url("**/marketplace/pool/**")
        mp.wait_for_pool_page()

    tabs = mp.history_tabs()
    tabs_count = tabs.count()
    tabs_text = [tabs.nth(i).text_content().strip() for i in range(tabs_count)]
    print(f"\n  Табы истории: {tabs_text}")

    with allure.step(f"Присутствует таб 'Transactions' (найдены табы: {tabs_text})"):
        assert any("Transactions" in t for t in tabs_text), (
            f"Tab 'Transactions' not found among: {tabs_text}"
        )

    with allure.step(f"Присутствует таб 'actions' (найдены табы: {tabs_text})"):
        assert any("actions" in t.lower() for t in tabs_text), (
            f"Tab 'actions' not found among: {tabs_text}"
        )


@pytest.mark.ui
@pytest.mark.smoke
@allure.epic("Market")
@allure.feature("UI")
@allure.story("Marketplace")
@allure.title("Connect Wallet button opens Connect Wallet modal")
@allure.severity(allure.severity_level.NORMAL)
def test_connect_wallet_button_opens_modal(page, base_url):
    mp = MarketplacePage(page)

    with allure.step(f"Открываем {base_url}/marketplace"):
        mp.open(f"{base_url}/marketplace")
        mp.wait_for_pool_cards()

    with allure.step("Кликаем кнопку 'Connect Wallet' в хедере"):
        mp.connect_wallet_button().click()
        page.wait_for_timeout(500)

    with allure.step("Открылась модалка подключения кошелька (Reown)"):
        modal = mp.connect_wallet_modal()
        modal.wait_for(state="visible", timeout=5_000)
        allure.attach(
            page.screenshot(),
            name="Connect Wallet modal",
            attachment_type=allure.attachment_type.PNG,
        )
        assert modal.is_visible(), "Connect Wallet modal did not appear"


@pytest.mark.ui
@pytest.mark.smoke
@allure.epic("Market")
@allure.feature("UI")
@allure.story("My Portfolio")
@allure.title("My Portfolio tab opens Connect Wallet modal when wallet is not connected")
@allure.severity(allure.severity_level.NORMAL)
def test_my_portfolio_no_wallet(page, base_url):
    mp = MarketplacePage(page)

    with allure.step(f"Открываем {base_url}/marketplace"):
        mp.open(f"{base_url}/marketplace")
        mp.wait_for_pool_cards()

    with allure.step("Кликаем на таб 'My portfolio' в хедере"):
        mp.tab_my_portfolio().click()
        page.wait_for_timeout(500)

    with allure.step("Открылась модалка подключения кошелька (Reown)"):
        modal = mp.connect_wallet_modal()
        modal.wait_for(state="visible", timeout=5_000)
        assert modal.is_visible(), "Connect Wallet modal did not appear"
