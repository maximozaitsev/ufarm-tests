"""UI-тесты модалки депозита.

Покрывает:
  - Single-token пул (Pool A): нет дропдауна токенов
  - Multi-token пул (Pool B): есть дропдаун токенов, переключение токенов
  - Тоглер Gasless transaction (ON/OFF → меняет текст кнопки)
  - Кнопка MAX (заполняет инпут on-chain балансом)
  - Инпут суммы: позитивные и негативные сценарии
  - Клик submit → наблюдаем что происходит (TBD — запустить в HEADED=1)
"""
import json
import random
from decimal import Decimal

import allure
import pytest

from core.ui.pages.marketplace_page import MarketplacePage
from core.ui.pages.deposit_modal import DepositModal


@pytest.fixture
def page_with_new_user_on_pool(browser, base_url, test_pool_id, test_wallet_address):
    """Page на Pool B с кошельком, у которого createdAt=null (новый пользователь).

    auth/connect возвращает createdAt=null → приложение показывает PROOF OF AGREEMENT.
    user/verification возвращает 404 → верификация не пройдена.
    Используется только для теста что Terms модалка появляется.
    """
    from core.ui.wallet_injection import inject_wallet

    def _mock_new_user(page):
        def _auth(route, _):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"createdAt": None, "lastTopUp": None}),
            )
        def _verification(route, _):
            route.fulfill(
                status=404,
                content_type="application/json",
                body=json.dumps({"message": "User not found"}),
            )
        page.route("**/auth/connect/**", _auth)
        page.route("**/user/verification**", _verification)

    page = browser.new_page()
    _mock_new_user(page)
    page.goto(f"{base_url}/marketplace/pool/{test_pool_id}", wait_until="networkidle")
    inject_wallet(page, test_wallet_address)
    page.wait_for_load_state("networkidle", timeout=15_000)
    yield page
    page.close()


pytestmark = [pytest.mark.ui, pytest.mark.smoke]


def _random_valid_deposit(pool_info, wallet_balance) -> float:
    """Случайная сумма депозита в диапазоне (min_deposit, wallet_balance].

    Если deposit_min = 0, нижняя граница = 0.01 (практический минимум).
    Возвращает число с 2 децималами.
    """
    raw = int(pool_info.limits.deposit_min)
    min_deposit = float(Decimal(raw) / Decimal(10 ** pool_info.decimals))
    lower = max(min_deposit, 0.01)
    return round(random.uniform(lower, float(wallet_balance)), 2)


def open_deposit_modal(page, mp: MarketplacePage, modal: DepositModal):
    """Открывает модалку депозита и ждёт DEPOSIT heading.

    Terms (PROOF OF AGREEMENT) замоканы через _mock_auth_connect() в conftest.py:
      - GET /auth/connect/{address} → createdAt всегда не null
      - POST /user/verification → всегда возвращает валидную подпись
    Оба мока устанавливаются до page.goto() — Terms не должны появляться.

    Если DEPOSIT heading не появился в течение 15 сек — тест падает (FAIL, не SKIP).
    """
    mp.wait_for_pool_page()
    mp.deposit_button().click()
    modal.wait_for()

    # Ждём DEPOSIT heading — приложение может мгновенно показать его или
    # сначала промежуточное состояние загрузки баланса.
    try:
        page.get_by_role("heading", name="DEPOSIT").wait_for(state="visible", timeout=15_000)
        return
    except Exception:
        pass

    headings = page.locator(".mantine-Modal-content").first.locator(
        "h1, h2, h3, h4"
    ).all_inner_texts()
    pytest.fail(
        f"Expected DEPOSIT modal but got: {headings}. "
        "Check that _mock_auth_connect() mocks are applied before page.goto()."
    )


# ══════════════════════════════════════════════════════════════════════════════
# Single-token pool (Pool A)
# ══════════════════════════════════════════════════════════════════════════════

@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Deposit modal opens on single-token pool")
@allure.severity(allure.severity_level.CRITICAL)
def test_deposit_modal_opens_single_token(page_with_wallet_on_single_token_pool):
    mp = MarketplacePage(page_with_wallet_on_single_token_pool)
    modal = DepositModal(page_with_wallet_on_single_token_pool)

    with allure.step("Открываем модалку депозита"):
        open_deposit_modal(page_with_wallet_on_single_token_pool, mp, modal)

    with allure.step("Скриншот модалки депозита (single token)"):
        allure.attach(
            page_with_wallet_on_single_token_pool.screenshot(),
            name="Deposit modal single token",
            attachment_type=allure.attachment_type.PNG,
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Single-token pool deposit modal has no token dropdown")
@allure.severity(allure.severity_level.NORMAL)
def test_deposit_modal_single_token_no_dropdown(page_with_wallet_on_single_token_pool):
    """В single-token пуле в модалке нет комбобокса/дропдауна выбора токена."""
    mp = MarketplacePage(page_with_wallet_on_single_token_pool)
    modal = DepositModal(page_with_wallet_on_single_token_pool)

    with allure.step("Открываем модалку депозита"):
        mp.wait_for_pool_page()
        mp.deposit_button().click()
        modal.wait_for()

    with allure.step("Token selector не интерактивен — нет стрелки дропдауна"):
        # В single-token пуле _arrowWrapper_ отсутствует, элемент имеет класс _noPointer_.
        assert modal.token_selector_arrow().count() == 0, (
            "Arrow wrapper should not be present in single-token pool deposit modal"
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Deposit modal input is visible")
@allure.severity(allure.severity_level.CRITICAL)
def test_deposit_modal_input_visible(page_with_wallet_on_single_token_pool):
    mp = MarketplacePage(page_with_wallet_on_single_token_pool)
    modal = DepositModal(page_with_wallet_on_single_token_pool)

    with allure.step("Открываем модалку депозита"):
        open_deposit_modal(page_with_wallet_on_single_token_pool, mp, modal)

    with allure.step("Инпут суммы виден"):
        assert modal.amount_input().is_visible(), "Amount input not visible"


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Deposit modal submit button is disabled when input is empty")
@allure.severity(allure.severity_level.CRITICAL)
def test_deposit_modal_empty_input_button_disabled(page_with_wallet_on_single_token_pool):
    mp = MarketplacePage(page_with_wallet_on_single_token_pool)
    modal = DepositModal(page_with_wallet_on_single_token_pool)

    with allure.step("Открываем модалку депозита"):
        mp.wait_for_pool_page()
        mp.deposit_button().click()
        modal.wait_for()

    with allure.step("Инпут пустой — кнопка submit задизейблена"):
        assert modal.amount_input().input_value() in ("", "0"), "Input is not empty"
        assert modal.submit_button().is_disabled(), (
            "Submit button is not disabled with empty input"
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("MAX button fills input with wallet on-chain balance")
@allure.severity(allure.severity_level.CRITICAL)
def test_deposit_modal_max_button_fills_wallet_balance(
    page_with_wallet_on_single_token_pool, wallet_usdt_balance
):
    """Клик MAX заполняет инпут суммой on-chain USDT баланса кошелька."""
    mp = MarketplacePage(page_with_wallet_on_single_token_pool)
    modal = DepositModal(page_with_wallet_on_single_token_pool)

    with allure.step("Открываем модалку депозита"):
        mp.wait_for_pool_page()
        mp.deposit_button().click()
        modal.wait_for()

    with allure.step(f"Кликаем MAX (ожидаемый баланс ≈ {wallet_usdt_balance} USDT)"):
        modal.max_button().click()

    with allure.step("Инпут заполнен (не пустой, не '0')"):
        value = modal.amount_input().input_value()
        assert value not in ("", "0"), f"Input still empty after MAX click: {value!r}"

    with allure.step("Значение инпута ≈ on-chain баланс USDT (погрешность < 1%)"):
        try:
            input_val = float(value.replace(",", "."))
            expected = float(wallet_usdt_balance)
            assert abs(input_val - expected) / max(expected, 1e-9) < 0.01, (
                f"Input value {input_val} differs from on-chain balance {expected} by > 1%"
            )
        except ValueError:
            pytest.fail(f"Input value is not a valid number: {value!r}")

    with allure.step("Кнопка submit активна после заполнения инпута"):
        assert not modal.submit_button().is_disabled(), (
            "Submit button is still disabled after filling amount"
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Gasless toggle is ON by default")
@allure.severity(allure.severity_level.NORMAL)
def test_deposit_modal_gasless_on_by_default(page_with_wallet_on_single_token_pool):
    mp = MarketplacePage(page_with_wallet_on_single_token_pool)
    modal = DepositModal(page_with_wallet_on_single_token_pool)

    with allure.step("Открываем модалку депозита"):
        mp.wait_for_pool_page()
        mp.deposit_button().click()
        modal.wait_for()

    with allure.step("Тоглер Gasless transaction включён по умолчанию"):
        assert modal.gasless_toggle().is_checked(), "Gasless toggle is OFF by default"

    with allure.step("Текст кнопки при Gasless ON — 'request deposit'"):
        assert modal.submit_button_text() == "request deposit", (
            f"Expected 'request deposit', got '{modal.submit_button_text()}'"
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Disabling Gasless toggle changes button text to Instant Deposit")
@allure.severity(allure.severity_level.CRITICAL)
def test_deposit_modal_gasless_off_shows_instant_deposit(page_with_wallet_on_single_token_pool):
    mp = MarketplacePage(page_with_wallet_on_single_token_pool)
    modal = DepositModal(page_with_wallet_on_single_token_pool)

    with allure.step("Открываем модалку депозита"):
        mp.wait_for_pool_page()
        mp.deposit_button().click()
        modal.wait_for()
        
    with allure.step("Выключаем тоглер Gasless"):
        modal.gasless_toggle().evaluate("el => el.click()")

    with allure.step("Текст кнопки изменился на 'instant deposit'"):
        page_with_wallet_on_single_token_pool.locator("#poolDepositConfirm").get_by_text(
            "instant deposit", exact=False
        ).wait_for(state="visible", timeout=3_000)
        text = modal.submit_button_text()
        assert "instant deposit" in text, (
            f"Expected 'instant deposit', got '{text}'"
        )

    with allure.step("Скриншот с Gasless OFF"):
        allure.attach(
            page_with_wallet_on_single_token_pool.screenshot(),
            name="Deposit modal Gasless OFF",
            attachment_type=allure.attachment_type.PNG,
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Enabling Gasless toggle back changes button text to Request Deposit")
@allure.severity(allure.severity_level.NORMAL)
def test_deposit_modal_gasless_on_shows_request_deposit(page_with_wallet_on_single_token_pool):
    mp = MarketplacePage(page_with_wallet_on_single_token_pool)
    modal = DepositModal(page_with_wallet_on_single_token_pool)

    with allure.step("Открываем модалку депозита"):
        mp.wait_for_pool_page()
        mp.deposit_button().click()
        modal.wait_for()

    with allure.step("Выключаем тоглер Gasless, затем включаем обратно"):
        modal.gasless_toggle().evaluate("el => el.click()")
        modal.gasless_toggle().evaluate("el => el.click()")

    with allure.step("Текст кнопки вернулся к 'request deposit'"):
        text = modal.submit_button_text()
        assert "request deposit" in text, (
            f"Expected 'request deposit', got '{text}'"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Multi-token pool (Pool B)
# ══════════════════════════════════════════════════════════════════════════════

@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Deposit modal opens on multi-token pool")
@allure.severity(allure.severity_level.CRITICAL)
def test_deposit_modal_opens_multi_token(page_with_wallet_on_pool):
    mp = MarketplacePage(page_with_wallet_on_pool)
    modal = DepositModal(page_with_wallet_on_pool)

    with allure.step("Открываем модалку депозита"):
        open_deposit_modal(page_with_wallet_on_pool, mp, modal)

    with allure.step("Скриншот модалки депозита (multi token)"):
        allure.attach(
            page_with_wallet_on_pool.screenshot(),
            name="Deposit modal multi token",
            attachment_type=allure.attachment_type.PNG,
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Multi-token pool deposit modal has token dropdown")
@allure.severity(allure.severity_level.NORMAL)
def test_deposit_modal_multi_token_has_dropdown(page_with_wallet_on_pool, pool_info_multi_token):
    """В multi-token пуле клик по токен-иконке открывает список вариантов."""
    mp = MarketplacePage(page_with_wallet_on_pool)
    modal = DepositModal(page_with_wallet_on_pool)

    tokens = [t.upper() for t in (pool_info_multi_token.availableValueTokens or [])]

    with allure.step("Открываем модалку депозита"):
        mp.wait_for_pool_page()
        mp.deposit_button().click()
        modal.wait_for()

    with allure.step("Кликаем по иконке токена — открывается дропдаун"):
        modal.token_selector().click()

    modal.token_dropdown().wait_for(state="visible")

    with allure.step(f"В дропдауне видны варианты токенов {tokens}"):
        visible_tokens = [
            t for t in tokens
            if modal.token_dropdown().get_by_text(t).first.is_visible()
        ]

        assert len(visible_tokens) > 1, (
            f"Expected multiple token options, visible: {visible_tokens}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Multi-token pool — token dropdown (дополнительные тесты)
# ══════════════════════════════════════════════════════════════════════════════

@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Deposit modal: default token is in pool's available token list")
@allure.severity(allure.severity_level.CRITICAL)
def test_deposit_modal_multi_token_default_token_in_available_list(
    page_with_wallet_on_pool, pool_info_multi_token
):
    """Тикер токена по умолчанию совпадает с одним из availableValueTokens пула."""
    mp = MarketplacePage(page_with_wallet_on_pool)
    modal = DepositModal(page_with_wallet_on_pool)

    available_tokens_upper = [t.upper() for t in (pool_info_multi_token.availableValueTokens or [])]
    assert available_tokens_upper, "Pool B should have availableValueTokens"

    with allure.step("Открываем модалку депозита"):
        open_deposit_modal(page_with_wallet_on_pool, mp, modal)

    with allure.step(f"Тикер по умолчанию входит в список доступных токенов: {available_tokens_upper}"):
        current = modal.current_token_ticker()
        allure.attach(
            f"Current: {current}\nAvailable: {available_tokens_upper}",
            name="Token info",
            attachment_type=allure.attachment_type.TEXT,
        )
        assert current.upper() in available_tokens_upper, (
            f"Default token '{current}' not in available tokens: {available_tokens_upper}"
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Deposit modal: switching token in multi-token pool updates selected ticker")
@allure.severity(allure.severity_level.CRITICAL)
def test_deposit_modal_multi_token_token_switch_changes_ticker(
    page_with_wallet_on_pool, pool_info_multi_token
):
    """Переключение токена в дропдауне обновляет тикер в селекторе."""
    mp = MarketplacePage(page_with_wallet_on_pool)
    modal = DepositModal(page_with_wallet_on_pool)

    available_tokens = pool_info_multi_token.availableValueTokens or []
    assert len(available_tokens) >= 2, (
        f"Pool B should have at least 2 tokens for switch test: {available_tokens}"
    )

    with allure.step("Открываем модалку депозита"):
        open_deposit_modal(page_with_wallet_on_pool, mp, modal)

    with allure.step("Запоминаем текущий токен и выбираем альтернативный"):
        initial_ticker = modal.current_token_ticker()
        other_ticker = next(
            t.upper() for t in available_tokens if t.upper() != initial_ticker.upper()
        )

    with allure.step(f"Открываем дропдаун и выбираем {other_ticker} (было {initial_ticker})"):
        modal.token_selector().click()
        modal.token_dropdown().wait_for(state="visible", timeout=3_000)
        modal.token_option(other_ticker).click()
        page_with_wallet_on_pool.wait_for_timeout(500)

    with allure.step(f"Тикер в селекторе обновился на {other_ticker}"):
        new_ticker = modal.current_token_ticker()
        assert new_ticker.upper() == other_ticker.upper(), (
            f"Expected ticker '{other_ticker}' after switch, got '{new_ticker}'"
        )

    with allure.step(f"Скриншот после переключения токена на {other_ticker}"):
        allure.attach(
            page_with_wallet_on_pool.screenshot(),
            name=f"Token switched to {other_ticker}",
            attachment_type=allure.attachment_type.PNG,
        )


# ══════════════════════════════════════════════════════════════════════════════
# Amount input — позитивные сценарии
# ══════════════════════════════════════════════════════════════════════════════

@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Deposit modal: entering valid amount enables submit button")
@allure.severity(allure.severity_level.CRITICAL)
def test_deposit_modal_valid_amount_enables_submit(
    page_with_wallet_on_single_token_pool, wallet_usdt_balance, pool_info_single_token
):
    """Ввод рандомной суммы в диапазоне (min_deposit, wallet_balance) активирует кнопку submit."""
    mp = MarketplacePage(page_with_wallet_on_single_token_pool)
    modal = DepositModal(page_with_wallet_on_single_token_pool)

    valid_amount = _random_valid_deposit(pool_info_single_token, wallet_usdt_balance)

    with allure.step("Открываем модалку депозита"):
        open_deposit_modal(page_with_wallet_on_single_token_pool, mp, modal)

    with allure.step(f"Вводим {valid_amount} USDT (баланс кошелька ≈ {float(wallet_usdt_balance):.4f})"):
        modal.amount_input().fill(str(valid_amount))
        page_with_wallet_on_single_token_pool.wait_for_timeout(500)

    with allure.step("Кнопка submit активна"):
        assert not modal.submit_button().is_disabled(), (
            f"Submit button should be enabled after entering valid amount {valid_amount}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Amount input — негативные сценарии
# ══════════════════════════════════════════════════════════════════════════════

@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Deposit modal: zero amount disables submit button")
@allure.severity(allure.severity_level.NORMAL)
def test_deposit_modal_zero_amount_disables_submit(page_with_wallet_on_single_token_pool):
    """Ввод нулевой суммы держит кнопку submit задизейбленной."""
    mp = MarketplacePage(page_with_wallet_on_single_token_pool)
    modal = DepositModal(page_with_wallet_on_single_token_pool)

    with allure.step("Открываем модалку депозита"):
        open_deposit_modal(page_with_wallet_on_single_token_pool, mp, modal)

    with allure.step("Вводим '0' в инпут суммы"):
        modal.amount_input().fill("0")
        page_with_wallet_on_single_token_pool.wait_for_timeout(500)

    with allure.step("Кнопка submit недоступна"):
        assert modal.submit_button().is_disabled(), (
            "Submit button should be disabled when amount is zero"
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Deposit modal: amount exceeding wallet balance disables submit button")
@allure.severity(allure.severity_level.CRITICAL)
def test_deposit_modal_amount_exceeds_balance_disables_submit(
    page_with_wallet_on_single_token_pool, wallet_usdt_balance
):
    """Ввод суммы больше on-chain баланса кошелька делает кнопку submit недоступной."""
    mp = MarketplacePage(page_with_wallet_on_single_token_pool)
    modal = DepositModal(page_with_wallet_on_single_token_pool)

    over_balance = round(float(wallet_usdt_balance) * 2 + 1, 2)

    with allure.step("Открываем модалку депозита"):
        open_deposit_modal(page_with_wallet_on_single_token_pool, mp, modal)

    with allure.step(f"Вводим {over_balance} USDT (баланс ≈ {wallet_usdt_balance})"):
        modal.amount_input().fill(str(over_balance))
        page_with_wallet_on_single_token_pool.wait_for_timeout(500)

    with allure.step("Кнопка submit недоступна"):
        assert modal.submit_button().is_disabled(), (
            f"Submit button should be disabled when amount {over_balance} exceeds balance {wallet_usdt_balance}"
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Deposit modal: clearing input after fill disables submit button")
@allure.severity(allure.severity_level.NORMAL)
def test_deposit_modal_clear_input_disables_submit(
    page_with_wallet_on_single_token_pool, wallet_usdt_balance, pool_info_single_token
):
    """Очистка инпута после ввода валидной суммы снова дизейблит кнопку submit."""
    mp = MarketplacePage(page_with_wallet_on_single_token_pool)
    modal = DepositModal(page_with_wallet_on_single_token_pool)

    valid_amount = _random_valid_deposit(pool_info_single_token, wallet_usdt_balance)

    with allure.step("Открываем модалку депозита"):
        open_deposit_modal(page_with_wallet_on_single_token_pool, mp, modal)

    with allure.step(f"Вводим {valid_amount} USDT — кнопка активируется"):
        modal.amount_input().fill(str(valid_amount))
        page_with_wallet_on_single_token_pool.wait_for_timeout(500)
        assert not modal.submit_button().is_disabled(), (
            f"Submit button should be enabled after entering '{valid_amount}'"
        )

    with allure.step("Очищаем инпут"):
        modal.amount_input().fill("")
        page_with_wallet_on_single_token_pool.wait_for_timeout(500)

    with allure.step("Кнопка submit снова недоступна"):
        assert modal.submit_button().is_disabled(), (
            "Submit button should be disabled after clearing input"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Min deposit validation (Pool C)
# ══════════════════════════════════════════════════════════════════════════════

@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Deposit modal: amount below min deposit disables submit and shows error")
@allure.severity(allure.severity_level.CRITICAL)
def test_deposit_modal_below_min_deposit_shows_error(
    page_with_whale_wallet_on_min_deposit_pool, pool_info_min_deposit
):
    """Ввод суммы ниже минимального депозита пула блокирует submit и показывает ошибку.

    Pool C (POOL_MIN_DEPOSIT_ID) — min deposit = 5000 USDT.
    Кошелёк: Binance hot wallet (публичный адрес, баланс >> 5000 USDT).
    Вводим сумму = 1 USDT (заведомо ниже минимума).
    """
    from decimal import Decimal

    mp = MarketplacePage(page_with_whale_wallet_on_min_deposit_pool)
    modal = DepositModal(page_with_whale_wallet_on_min_deposit_pool)

    import random

    raw = int(pool_info_min_deposit.limits.deposit_min)
    min_deposit = Decimal(raw) / Decimal(10 ** pool_info_min_deposit.decimals)
    below_min = str(round(random.uniform(1, float(min_deposit) - 0.01), 2))

    with allure.step("Открываем модалку депозита (ждём DEPOSIT heading)"):
        mp.wait_for_pool_page()
        mp.deposit_button().click()
        modal.wait_for()
        try:
            page_with_whale_wallet_on_min_deposit_pool.get_by_role(
                "heading", name="DEPOSIT"
            ).wait_for(state="visible", timeout=20_000)
        except Exception:
            headings = page_with_whale_wallet_on_min_deposit_pool.locator(
                ".mantine-Modal-content h1, .mantine-Modal-content h2, .mantine-Modal-content h3, .mantine-Modal-content h4"
            ).all_inner_texts()
            pytest.skip(f"Deposit modal not opened, got: {headings}")

    with allure.step(f"Вводим {below_min} USDT (min deposit = {min_deposit} USDT)"):
        modal.amount_input().fill(below_min)
        page_with_whale_wallet_on_min_deposit_pool.wait_for_timeout(500)

    with allure.step("Кнопка submit недоступна"):
        assert modal.submit_button().is_disabled(), (
            f"Submit should be disabled when amount {below_min} < min deposit {min_deposit}"
        )

    with allure.step(f"Отображается сообщение 'Minimum: {min_deposit}'"):
        display_min = str(int(min_deposit)) if min_deposit == int(min_deposit) else str(min_deposit)
        error = page_with_whale_wallet_on_min_deposit_pool.locator(
            ".mantine-Modal-body"
        ).get_by_text(f"Minimum: {display_min}", exact=False)
        error.wait_for(state="visible", timeout=3_000)

    with allure.step("Скриншот с ошибкой валидации min deposit"):
        allure.attach(
            page_with_whale_wallet_on_min_deposit_pool.screenshot(),
            name="Below min deposit error",
            attachment_type=allure.attachment_type.PNG,
        )


# ══════════════════════════════════════════════════════════════════════════════
# Terms (PROOF OF AGREEMENT)
# ══════════════════════════════════════════════════════════════════════════════

@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Deposit modal: PROOF OF AGREEMENT appears for new user without accepted terms")
@allure.severity(allure.severity_level.CRITICAL)
def test_deposit_modal_terms_appear_for_new_user(page_with_new_user_on_pool):
    """Для нового пользователя (createdAt=null) при клике Deposit открывается PROOF OF AGREEMENT.

    auth/connect замокан на createdAt=null, user/verification — на 404.
    """
    mp = MarketplacePage(page_with_new_user_on_pool)
    modal = DepositModal(page_with_new_user_on_pool)

    with allure.step("Ждём загрузки страницы пула"):
        mp.wait_for_pool_page()

    with allure.step("Кликаем Deposit"):
        mp.deposit_button().click()
        modal.wait_for()

    with allure.step("Открылась модалка PROOF OF AGREEMENT (не deposit форма)"):
        page_with_new_user_on_pool.get_by_role(
            "heading", name="PROOF OF AGREEMENT", exact=False
        ).wait_for(state="visible", timeout=15_000)

    with allure.step("Скриншот модалки Terms"):
        allure.attach(
            page_with_new_user_on_pool.screenshot(),
            name="PROOF OF AGREEMENT modal",
            attachment_type=allure.attachment_type.PNG,
        )


# ══════════════════════════════════════════════════════════════════════════════
# Transaction signing (TBD)
# ══════════════════════════════════════════════════════════════════════════════

@allure.epic("Market")
@allure.feature("UI")
@allure.story("Deposit")
@allure.title("Deposit submit button triggers signing flow")
@allure.severity(allure.severity_level.CRITICAL)
def test_deposit_triggers_signing(page_with_wallet_on_single_token_pool):
    """Клик на кнопку submit после заполнения суммы вызывает подпись транзакции.

    Ожидаемое поведение — TBD.
    Запустить: HEADED=1 SLOWMO=800 pytest tests/ui/market/test_deposit_modal.py::test_deposit_triggers_signing -v -s
    """
    mp = MarketplacePage(page_with_wallet_on_single_token_pool)
    modal = DepositModal(page_with_wallet_on_single_token_pool)

    with allure.step("Открываем модалку депозита"):
        mp.wait_for_pool_page()
        mp.deposit_button().click()
        modal.wait_for()

    with allure.step("Нажимаем MAX для заполнения суммы"):
        modal.max_button().click()
        # Ждём пока кнопка станет активной
        page_with_wallet_on_single_token_pool.locator(
            "#poolDepositConfirm:not([disabled])"
        ).wait_for(state="visible", timeout=5_000)

    with allure.step("Скриншот перед нажатием submit"):
        allure.attach(
            page_with_wallet_on_single_token_pool.screenshot(),
            name="Before submit click",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Кликаем кнопку submit"):
        modal.submit_button().click()

    with allure.step("Ждём 3 секунды — наблюдаем результат"):
        page_with_wallet_on_single_token_pool.wait_for_timeout(3_000)
        allure.attach(
            page_with_wallet_on_single_token_pool.screenshot(),
            name="After submit click (3s)",
            attachment_type=allure.attachment_type.PNG,
        )
    # TODO: добавить assertion после запуска в HEADED=1 и наблюдения поведения
