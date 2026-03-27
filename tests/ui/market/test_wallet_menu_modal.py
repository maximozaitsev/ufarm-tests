"""UI-тесты модалки кошелька (Wallet Menu Modal).

Модалка открывается кликом на кнопку с адресом кошелька в хедере
(когда кошелёк подключён).

Покрытие:
  - Главная страница: адрес, балансы, кнопки
  - fund wallet → buy crypto: форма, дефолтная сумма, адрес кошелька, Unlimit виджет
  - fund wallet → receive funds: QR-код, copy address
  - Send: форма, валидация кнопки
"""

from decimal import Decimal, ROUND_DOWN

import allure
import pytest
import requests

from core.ui.mocks import mock_auth_connect
from core.ui.on_chain import get_erc20_balance, USDT_ARB, USDC_ARB, ARB_MAINNET_RPC
from core.ui.pages.marketplace_page import MarketplacePage
from core.ui.pages.wallet_menu_modal import WalletMenuModal


pytestmark = [pytest.mark.ui, pytest.mark.smoke]


# ── Фикстуры ──────────────────────────────────────────────────────────────────


@pytest.fixture
def page_with_wallet_clipboard(browser, base_url, test_wallet_address):
    """Page с подключённым кошельком и разрешением на чтение буфера обмена.

    Отдельная фикстура от page_with_wallet — clipboard-read/write permissions
    нельзя добавить после создания контекста.
    """
    from core.ui.wallet_injection import inject_wallet

    context = browser.new_context(
        permissions=["clipboard-read", "clipboard-write"]
    )
    page = context.new_page()
    mock_auth_connect(page)
    page.goto(f"{base_url}/marketplace", wait_until="networkidle")
    inject_wallet(page, test_wallet_address)
    yield page
    context.close()


# ── Фикстуры балансов ─────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def wallet_usdc_balance(test_wallet_address) -> Decimal:
    """On-chain USDC баланс тестового кошелька на Arbitrum."""
    return get_erc20_balance(test_wallet_address, USDC_ARB)


@pytest.fixture(scope="session")
def wallet_eth_balance(test_wallet_address) -> Decimal:
    """Нативный ETH баланс тестового кошелька на Arbitrum через eth_getBalance."""
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_getBalance",
        "params": [test_wallet_address, "latest"],
        "id": 1,
    }
    resp = requests.post(ARB_MAINNET_RPC, json=payload, timeout=15)
    resp.raise_for_status()
    raw = int(resp.json()["result"], 16)
    return Decimal(raw) / Decimal(10 ** 18)


# ── Вспомогательные функции ───────────────────────────────────────────────────


def _parse_balance_text(row_text: str) -> Decimal:
    """Извлекает числовой баланс из текста строки баланса модалки.

    Примеры входных строк (inner_text() строки баланса):
      '5,8\\n USDT'   → Decimal('5.8')
      '2\\n USDC'     → Decimal('2')
      '0.00230363 \\n ETH' → Decimal('0.00230363')

    Обработка разделителей:
      - Запятая перед ≤ 2 цифрами в конце → десятичный разделитель ('5,8' → '5.8')
      - Запятая перед >2 цифрами → разделитель тысяч ('1,234' → '1234')
    """
    number = row_text.split("\n")[0].strip()
    if "," in number:
        parts = number.split(",")
        if len(parts[-1]) <= 2:
            number = number.replace(",", ".")   # десятичный разделитель
        else:
            number = number.replace(",", "")    # разделитель тысяч
    return Decimal(number)


def _assert_balance_matches(displayed: Decimal, on_chain: Decimal, token: str):
    """Проверяет что отображаемый баланс соответствует on-chain значению.

    Допустимое отклонение — пол-единицы последнего отображаемого знака.
    Примеры:
      '5,8' (1 знак) → tolerance = 0.05
      '2'   (0 знаков) → tolerance = 0.5
      '0.00230363' (8 знаков) → tolerance = 0.000000005
    """
    sign, digits, exponent = displayed.normalize().as_tuple()
    decimal_places = max(0, -exponent)
    tolerance = Decimal(1) / (Decimal(10) ** decimal_places) / 2
    assert abs(displayed - on_chain) <= tolerance, (
        f"{token} balance mismatch: UI shows {displayed}, on-chain {on_chain} "
        f"(tolerance ±{tolerance})"
    )


def _open_wallet_modal(page, mp: MarketplacePage) -> WalletMenuModal:
    """Открывает модалку кошелька из хедера и ждёт появления главной страницы."""
    mp.wait_for_pool_cards()
    # Ждём исчезновения Reown overlay после inject_wallet (race condition).
    page.locator(".mantine-Modal-overlay").wait_for(state="hidden", timeout=5_000)
    mp.wallet_header_button().click()
    modal = WalletMenuModal(page)
    modal.wait_opened()
    return modal


def _navigate_to_buy_crypto(page, mp: MarketplacePage) -> WalletMenuModal:
    """Открывает модалку и переходит на форму buy crypto."""
    modal = _open_wallet_modal(page, mp)
    modal.fund_wallet_button().click()
    modal.buy_crypto_option().wait_for(state="visible", timeout=5_000)
    modal.buy_crypto_option().click()
    # Ждём форму: кнопка Continue появляется вместе с инпутом
    modal.buy_continue_button().wait_for(state="visible", timeout=5_000)
    return modal


def _navigate_to_receive_funds(page, mp: MarketplacePage) -> WalletMenuModal:
    """Открывает модалку и переходит на страницу receive funds."""
    modal = _open_wallet_modal(page, mp)
    modal.fund_wallet_button().click()
    modal.receive_funds_option().wait_for(state="visible", timeout=5_000)
    modal.receive_funds_option().click()
    modal.copy_address_button().wait_for(state="visible", timeout=5_000)
    return modal


# ── Главная страница модалки ──────────────────────────────────────────────────


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Wallet Modal")
@allure.title("Wallet modal main page: address, balances and action buttons")
@allure.tag("cross-verified: on-chain")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.cross_verified
def test_wallet_modal_main_page(
    page_with_wallet,
    test_wallet_address,
    wallet_usdt_balance,
    wallet_usdc_balance,
    wallet_eth_balance,
):
    """Smoke-тест главной страницы модалки кошелька.

    Проверяет за один проход:
    - модалка открывается
    - отображается сокращённый адрес кошелька
    - балансы USDT / USDC / ETH видны и совпадают с on-chain значениями
    - кнопки fund wallet, Send, Disconnect присутствуют
    """
    mp = MarketplacePage(page_with_wallet)

    with allure.step("Открываем модалку кошелька"):
        modal = _open_wallet_modal(page_with_wallet, mp)

    with allure.step("Скриншот открытой модалки"):
        allure.attach(
            page_with_wallet.screenshot(),
            name="Wallet modal main page",
            attachment_type=allure.attachment_type.PNG,
        )

    # ── Адрес ──────────────────────────────────────────────────────────────

    addr_start = test_wallet_address[:6].lower()

    with allure.step(f"Отображается сокращённый адрес кошелька ({addr_start}...)"):
        display = modal.address_display()
        display.wait_for(state="visible", timeout=5_000)
        address_text = display.inner_text().lower()
        assert addr_start in address_text, (
            f"Expected address start '{addr_start}' in: {address_text!r}"
        )
        assert "..." in address_text, (
            f"Expected truncated address (with ...) in: {address_text!r}"
        )

    # ── Балансы ─────────────────────────────────────────────────────────────

    with allure.step("Ждём загрузки балансов (исчезновения спиннеров)"):
        modal.wait_for_balances(timeout=15_000)

    with allure.step(f"USDT баланс виден и совпадает с on-chain ({wallet_usdt_balance} USDT)"):
        assert modal.usdt_balance_label().is_visible(), "USDT balance label not visible"
        usdt_displayed = _parse_balance_text(modal.get_balance_value("USDT"))
        _assert_balance_matches(usdt_displayed, wallet_usdt_balance, "USDT")

    with allure.step(f"USDC баланс виден и совпадает с on-chain ({wallet_usdc_balance} USDC)"):
        assert modal.usdc_balance_label().is_visible(), "USDC balance label not visible"
        usdc_displayed = _parse_balance_text(modal.get_balance_value("USDC"))
        _assert_balance_matches(usdc_displayed, wallet_usdc_balance, "USDC")

    with allure.step(f"ETH баланс виден и совпадает с on-chain ({wallet_eth_balance:.8f} ETH)"):
        assert modal.eth_balance_label().is_visible(), "ETH balance label not visible"
        eth_displayed = _parse_balance_text(modal.get_balance_value("ETH"))
        _assert_balance_matches(eth_displayed, wallet_eth_balance, "ETH")

    # ── Кнопки действий ─────────────────────────────────────────────────────

    with allure.step("Кнопки 'fund wallet', 'Send', 'Disconnect' видны"):
        assert modal.fund_wallet_button().is_visible(), "'fund wallet' button not visible"
        assert modal.send_nav_button().is_visible(), "'Send' button not visible"
        assert modal.disconnect_button().is_visible(), "'Disconnect' button not visible"


# ── Fund wallet: выбор способа пополнения ─────────────────────────────────────


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Wallet Modal")
@allure.title("Fund wallet shows buy crypto and receive funds options")
@allure.severity(allure.severity_level.CRITICAL)
def test_fund_wallet_shows_options(page_with_wallet):
    mp = MarketplacePage(page_with_wallet)

    with allure.step("Открываем модалку, кликаем 'fund wallet'"):
        modal = _open_wallet_modal(page_with_wallet, mp)
        modal.fund_wallet_button().click()

    with allure.step("Кнопки 'buy crypto' и 'receive funds' появились"):
        modal.buy_crypto_option().wait_for(state="visible", timeout=5_000)
        modal.receive_funds_option().wait_for(state="visible", timeout=5_000)
        assert modal.buy_crypto_option().is_visible()
        assert modal.receive_funds_option().is_visible()

    with allure.step("Скриншот sub-страницы fund wallet"):
        allure.attach(
            page_with_wallet.screenshot(),
            name="Fund wallet options",
            attachment_type=allure.attachment_type.PNG,
        )


# ── Buy crypto: форма покупки ─────────────────────────────────────────────────


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Wallet Modal")
@allure.title("Buy crypto form has token selector, amount input and continue button")
@allure.severity(allure.severity_level.CRITICAL)
def test_buy_crypto_form_elements(page_with_wallet):
    mp = MarketplacePage(page_with_wallet)

    with allure.step("Открываем форму buy crypto"):
        modal = _navigate_to_buy_crypto(page_with_wallet, mp)

    with allure.step("Скриншот формы покупки"):
        allure.attach(
            page_with_wallet.screenshot(),
            name="Buy crypto form",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Дропдаун токена виден"):
        assert modal.buy_token_selector().is_visible(), "Token selector not visible"

    with allure.step("Инпут суммы виден"):
        assert modal.buy_amount_input().is_visible(), "Amount input not visible"

    with allure.step("Кнопка 'continue' видна"):
        assert modal.buy_continue_button().is_visible(), "'continue' button not visible"


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Wallet Modal")
@allure.title("Buy crypto continue button is disabled until valid amount is entered")
@allure.severity(allure.severity_level.NORMAL)
def test_buy_crypto_continue_requires_amount(page_with_wallet):
    """Continue disabled когда инпут пустой, активен после ввода минимальной суммы (15)."""
    mp = MarketplacePage(page_with_wallet)

    with allure.step("Открываем форму buy crypto"):
        modal = _navigate_to_buy_crypto(page_with_wallet, mp)

    with allure.step("Кнопка Continue задизейблена при пустом инпуте"):
        btn = modal.buy_continue_button()
        is_disabled = btn.is_disabled() or btn.get_attribute("data-disabled") == "true"
        assert is_disabled, "Continue button should be disabled when amount is empty"

    with allure.step("Вводим минимальную сумму 15"):
        modal.buy_amount_input().fill("15")

    with allure.step("Кнопка Continue стала активной"):
        btn = modal.buy_continue_button()
        is_disabled = btn.is_disabled() or btn.get_attribute("data-disabled") == "true"
        allure.attach(
            page_with_wallet.screenshot(),
            name="Buy crypto amount 15 entered",
            attachment_type=allure.attachment_type.PNG,
        )
        assert not is_disabled, "Continue button should be enabled after entering amount 15"


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Wallet Modal")
@allure.title("Buy crypto form shows wallet address in fund my wallet label")
@allure.severity(allure.severity_level.NORMAL)
def test_buy_crypto_shows_wallet_address(page_with_wallet, test_wallet_address):
    mp = MarketplacePage(page_with_wallet)

    with allure.step("Открываем форму buy crypto"):
        modal = _navigate_to_buy_crypto(page_with_wallet, mp)

    with allure.step("Строка 'fund my wallet' видна"):
        label = modal.fund_my_wallet_label()
        label.wait_for(state="visible", timeout=5_000)
        assert label.is_visible(), "'fund my wallet' label not visible"

    with allure.step(f"Адрес кошелька совпадает с {test_wallet_address[:10]}..."):
        # Адрес отображается в отдельном <span> рядом с "fund my wallet: Arbitrum network"
        addr_element = modal.buy_form_wallet_address()
        addr_element.wait_for(state="visible", timeout=5_000)
        displayed = addr_element.inner_text().lower()
        assert test_wallet_address.lower() in displayed, (
            f"Expected wallet address in buy form, got: {displayed!r}"
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Wallet Modal")
@allure.title("Buy crypto continue button opens Unlimit widget with correct token and network")
@allure.severity(allure.severity_level.CRITICAL)
def test_buy_crypto_continue_opens_unlimit_widget(page_with_wallet, network_name):
    mp = MarketplacePage(page_with_wallet)

    with allure.step("Открываем форму buy crypto, вводим сумму 15 и нажимаем Continue"):
        modal = _navigate_to_buy_crypto(page_with_wallet, mp)
        modal.buy_amount_input().fill("15")
        modal.buy_continue_button().click()

    with allure.step("Контейнер Unlimit виджета (#gatefi-widget) становится видимым"):
        widget = modal.unlimit_widget_container()
        widget.wait_for(state="visible", timeout=15_000)
        # Ждём появления дочерних элементов виджета
        page_with_wallet.wait_for_function(
            "() => { const w = document.querySelector('#gatefi-widget'); "
            "return w && w.children.length > 0; }",
            timeout=15_000,
        )

    with allure.step("Скриншот виджета Unlimit"):
        allure.attach(
            page_with_wallet.screenshot(),
            name="Unlimit widget opened",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Виджет Unlimit загрузился в iframe"):
        # Виджет рендерится в cross-origin iframe внутри #gatefi-widget.
        # Playwright обходит cross-origin ограничения через CDP.
        frame = page_with_wallet.frame_locator("#gatefi-widget iframe").first
        # "You get" секция появляется после загрузки курсов
        frame.get_by_text("You get", exact=False).first.wait_for(
            state="visible", timeout=20_000
        )

    with allure.step("Виджет показывает USDT как токен получения"):
        # "USDT" отображается отдельно от "You get" label — ищем напрямую
        frame.get_by_text("USDT", exact=True).first.wait_for(
            state="visible", timeout=5_000
        )
        assert frame.get_by_text("USDT", exact=True).first.is_visible()

    with allure.step(f"Виджет показывает сеть {network_name}"):
        # Unlimit показывает "ARBITRUM ONE" для Arbitrum — проверяем без регистра
        frame.get_by_text(network_name, exact=False).first.wait_for(
            state="visible", timeout=5_000
        )
        assert frame.get_by_text(network_name, exact=False).first.is_visible()


# ── Receive funds ──────────────────────────────────────────────────────────────


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Wallet Modal")
@allure.title("Receive funds page shows QR code and copy address button")
@allure.severity(allure.severity_level.CRITICAL)
def test_receive_funds_view_elements(page_with_wallet):
    mp = MarketplacePage(page_with_wallet)

    with allure.step("Открываем fund wallet → receive funds"):
        modal = _navigate_to_receive_funds(page_with_wallet, mp)

    with allure.step("Скриншот страницы receive funds"):
        allure.attach(
            page_with_wallet.screenshot(),
            name="Receive funds page",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("QR-код присутствует"):
        assert modal.qr_code_element().is_visible(), "QR code (canvas) not visible"

    with allure.step("Кнопка 'Copy address' видна"):
        assert modal.copy_address_button().is_visible(), "'Copy address' button not visible"


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Wallet Modal")
@allure.title("Receive funds copy address puts full wallet address in clipboard")
@allure.severity(allure.severity_level.CRITICAL)
def test_receive_funds_copy_address(page_with_wallet_clipboard, test_wallet_address):
    mp = MarketplacePage(page_with_wallet_clipboard)
    modal = WalletMenuModal(page_with_wallet_clipboard)

    with allure.step("Открываем fund wallet → receive funds"):
        mp.wait_for_pool_cards()
        page_with_wallet_clipboard.locator(".mantine-Modal-overlay").wait_for(
            state="hidden", timeout=5_000
        )
        mp.wallet_header_button().click()
        modal.wait_opened()
        modal.fund_wallet_button().click()
        modal.receive_funds_option().wait_for(state="visible", timeout=5_000)
        modal.receive_funds_option().click()
        modal.copy_address_button().wait_for(state="visible", timeout=5_000)

    with allure.step("Кликаем 'Copy address'"):
        modal.copy_address_button().click()

    with allure.step(f"Буфер обмена содержит полный адрес {test_wallet_address[:10]}..."):
        clipboard_text = page_with_wallet_clipboard.evaluate(
            "navigator.clipboard.readText()"
        )
        assert clipboard_text.lower() == test_wallet_address.lower(), (
            f"Expected clipboard: {test_wallet_address!r}, got: {clipboard_text!r}"
        )


# ── Send: форма отправки ───────────────────────────────────────────────────────


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Wallet Modal")
@allure.title("Send page has token dropdown, amount input, to input and send button")
@allure.severity(allure.severity_level.CRITICAL)
def test_send_form_elements(page_with_wallet, network_name):
    mp = MarketplacePage(page_with_wallet)

    with allure.step("Открываем модалку → Send"):
        modal = _open_wallet_modal(page_with_wallet, mp)
        modal.send_nav_button().click()

    with allure.step("Форма отправки загружена"):
        modal.send_to_input().wait_for(state="visible", timeout=5_000)

    with allure.step("Скриншот формы Send"):
        allure.attach(
            page_with_wallet.screenshot(),
            name="Send form",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Дропдаун токена виден"):
        assert modal.send_token_dropdown().is_visible(), "Token dropdown not visible"

    with allure.step("Инпут суммы виден"):
        assert modal.send_amount_input().is_visible(), "Amount input not visible"

    with allure.step("Кнопка MAX видна"):
        assert modal.send_max_button().is_visible(), "MAX button not visible"

    with allure.step(f"Плейсхолдер поля 'To' содержит название сети {network_name}"):
        placeholder = modal.send_to_input().get_attribute("placeholder") or ""
        assert network_name in placeholder, (
            f"Network '{network_name}' not in To input placeholder: {placeholder!r}"
        )

    with allure.step("Кнопка SEND видна"):
        assert modal.send_submit_button().is_visible(), "SEND button not visible"


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Wallet Modal")
@allure.title("Send button is disabled when inputs are empty")
@allure.severity(allure.severity_level.NORMAL)
def test_send_button_disabled_initially(page_with_wallet):
    mp = MarketplacePage(page_with_wallet)

    with allure.step("Открываем форму Send"):
        modal = _open_wallet_modal(page_with_wallet, mp)
        modal.send_nav_button().click()
        modal.send_to_input().wait_for(state="visible", timeout=5_000)

    with allure.step("Кнопка SEND задизейблена при пустых полях"):
        btn = modal.send_submit_button()
        is_disabled = (
            btn.is_disabled()
            or btn.get_attribute("data-disabled") == "true"
        )
        assert is_disabled, "Send button should be disabled when inputs are empty"

    with allure.step("Скриншот (пустая форма Send)"):
        allure.attach(
            page_with_wallet.screenshot(),
            name="Send form empty",
            attachment_type=allure.attachment_type.PNG,
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Wallet Modal")
@allure.title("Send button becomes enabled with valid amount and address")
@allure.severity(allure.severity_level.CRITICAL)
def test_send_button_enabled_with_valid_inputs(page_with_wallet, test_wallet_address):
    mp = MarketplacePage(page_with_wallet)

    with allure.step("Открываем форму Send"):
        modal = _open_wallet_modal(page_with_wallet, mp)
        modal.send_nav_button().click()
        modal.send_to_input().wait_for(state="visible", timeout=5_000)

    with allure.step("Кликаем MAX для заполнения максимального баланса"):
        modal.send_max_button().click()

    with allure.step(f"Вводим адрес получателя: {test_wallet_address[:10]}..."):
        modal.send_to_input().fill(test_wallet_address)

    with allure.step("Кнопка SEND стала активной"):
        btn = modal.send_submit_button()
        btn.wait_for(state="visible", timeout=3_000)
        allure.attach(
            page_with_wallet.screenshot(),
            name="Send form filled",
            attachment_type=allure.attachment_type.PNG,
        )
        is_disabled = (
            btn.is_disabled()
            or btn.get_attribute("data-disabled") == "true"
        )
        assert not is_disabled, (
            "Send button should be enabled with valid amount and address"
        )
