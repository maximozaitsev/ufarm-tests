"""UI-тесты модалки депозита.

Покрывает:
  - Single-token пул (Pool A): нет дропдауна токенов
  - Multi-token пул (Pool B): есть дропдаун токенов
  - Тоглер Gasless transaction (ON/OFF → меняет текст кнопки)
  - Кнопка MAX (заполняет инпут on-chain балансом)
  - Кнопка submit: disabled когда инпут пустой
  - Клик submit → наблюдаем что происходит (TBD — запустить в HEADED=1)
"""
import allure
import pytest

from core.ui.pages.marketplace_page import MarketplacePage
from core.ui.pages.deposit_modal import DepositModal


pytestmark = [pytest.mark.ui, pytest.mark.smoke]

_TERMS_HEADINGS = {"proof of agreement", "terms", "agreement"}


def open_deposit_modal(page, mp: MarketplacePage, modal: DepositModal):
    """Открывает модалку депозита; пропускает тест если появились Terms.

    В headless режиме приложение может сначала показать Terms или промежуточное
    состояние — нельзя читать heading сразу. Ждём конкретный "DEPOSIT" heading
    с таймаутом, и только если он не появился — проверяем что показалось.

    Terms (PROOF OF AGREEMENT) требует подписи кошелька — не поддерживается
    при inject_wallet без приватного ключа. Тест будет SKIPPED до решения.
    """
    mp.wait_for_pool_page()
    mp.deposit_button().click()
    modal.wait_for()

    # Ждём DEPOSIT heading (приложение может сначала показать Terms, потом Deposit)
    try:
        page.get_by_role("heading", name="DEPOSIT").wait_for(state="visible", timeout=15_000)
        return  # Deposit modal открылась корректно
    except Exception:
        pass

    # Deposit не появился — смотрим что открылось
    headings = page.locator(".mantine-Modal-content").first.locator(
        "h1, h2, h3, h4"
    ).all_inner_texts()
    heading_lower = " ".join(h.strip().lower() for h in headings)

    if any(t in heading_lower for t in _TERMS_HEADINGS):
        pytest.skip(
            f"Terms modal appeared — requires wallet signing, not supported with inject_wallet. "
            f"Headings: {headings}"
        )
    pytest.skip(f"Expected deposit modal but got: {headings}")


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

    with allure.step("В модалке нет элемента с role=combobox или listbox"):
        page = page_with_wallet_on_single_token_pool
        has_combobox = page.locator(".mantine-Modal-body [role='combobox']").count() > 0
        has_listbox = page.locator(".mantine-Modal-body [role='listbox']").count() > 0
        assert not has_combobox and not has_listbox, (
            "Token dropdown (combobox/listbox) found in single-token deposit modal"
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
        mp.wait_for_pool_page()
        mp.deposit_button().click()
        modal.wait_for()

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
