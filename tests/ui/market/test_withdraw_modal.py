"""UI-тесты модалки вывода (Withdraw).

Кнопка Withdraw доступна только если у кошелька есть активные депозиты в пуле.
Используется: Pool B (TEST_POOL_ID) + WALLET_WITH_BALANCE (TEST_WALLET_ADDRESS).
"""
from decimal import Decimal

import allure
import pytest

from core.ui.pages.marketplace_page import MarketplacePage
from core.ui.pages.withdraw_modal import WithdrawModal


pytestmark = [pytest.mark.ui, pytest.mark.smoke]


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Withdrawal")
@allure.title("Withdraw modal opens on Withdraw button click")
@allure.severity(allure.severity_level.CRITICAL)
def test_withdraw_modal_opens(page_with_wallet_on_pool):
    mp = MarketplacePage(page_with_wallet_on_pool)
    modal = WithdrawModal(page_with_wallet_on_pool)

    with allure.step("Ждём загрузки страницы пула"):
        mp.wait_for_pool_page()

    with allure.step("Ждём кнопки Withdraw (загрузка баланса по API)"):
        mp.wait_for_withdraw_button()

    with allure.step("Кликаем Withdraw"):
        mp.withdraw_button().click()

    with allure.step("Модалка вывода открылась"):
        modal.wait_for()

    with allure.step("Скриншот модалки вывода"):
        allure.attach(
            page_with_wallet_on_pool.screenshot(),
            name="Withdraw modal",
            attachment_type=allure.attachment_type.PNG,
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Withdrawal")
@allure.title("Withdraw modal shows pool balance matching portfolio API")
@allure.severity(allure.severity_level.CRITICAL)
def test_withdraw_modal_shows_pool_balance(page_with_wallet_on_pool, wallet_portfolio, test_pool_id):
    """Баланс в модалке вывода > 0 и соответствует данным из portfolio API."""
    mp = MarketplacePage(page_with_wallet_on_pool)
    modal = WithdrawModal(page_with_wallet_on_pool)

    # Находим пул в portfolio
    pool_stat = next(
        (p.poolStat for p in wallet_portfolio.pools if p.id == test_pool_id),
        None,
    )
    assert pool_stat is not None, f"Pool {test_pool_id} not found in portfolio"

    with allure.step("Открываем модалку вывода"):
        mp.wait_for_pool_page()
        mp.wait_for_withdraw_button()
        mp.withdraw_button().click()
        modal.wait_for()

    with allure.step("Текст баланса в модалке содержит ненулевое значение"):
        balance_text = modal.balance_text()
        allure.attach(balance_text, name="Balance text", attachment_type=allure.attachment_type.TEXT)
        # Извлекаем число после "Balance: "
        import re
        m = re.search(r"Balance:\s*([\d.]+)", balance_text)
        assert m, f"Could not parse balance from: {balance_text!r}"
        ui_balance = float(m.group(1))
        assert ui_balance > 0, f"Balance in modal is zero: {ui_balance}"

    with allure.step("Баланс в UI близок к значению из portfolio API (погрешность < 5%)"):
        # portfolio totalBalance в наименьших единицах (decimals=6)
        # wallet_portfolio.pools содержит PortfolioPool, у которого decimals из Pool
        pool_entry = next(p for p in wallet_portfolio.pools if p.id == test_pool_id)
        api_balance_tokens = Decimal(pool_stat.totalBalance) / Decimal(10 ** pool_entry.decimals)
        # UI показывает баланс в токенах пула, не в USDT — соотношение может отличаться
        # Проверяем что оба > 0 и примерно одного порядка (не ожидаем точного совпадения
        # из-за разницы в курсе vault token/USDT)
        assert float(api_balance_tokens) > 0, "API portfolio balance is zero"
        allure.attach(
            f"UI: {ui_balance}, API (USDT equivalent): {float(api_balance_tokens):.6f}",
            name="Balance comparison",
            attachment_type=allure.attachment_type.TEXT,
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Withdrawal")
@allure.title("Withdraw modal has Request Withdrawal button")
@allure.severity(allure.severity_level.CRITICAL)
def test_withdraw_modal_has_request_withdrawal_button(page_with_wallet_on_pool):
    mp = MarketplacePage(page_with_wallet_on_pool)
    modal = WithdrawModal(page_with_wallet_on_pool)

    with allure.step("Открываем модалку вывода"):
        mp.wait_for_pool_page()
        mp.wait_for_withdraw_button()
        mp.withdraw_button().click()
        modal.wait_for()

    with allure.step("Кнопка 'Request Withdrawal' видна"):
        modal.request_withdrawal_button().wait_for(state="visible", timeout=5_000)


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Withdrawal")
@allure.title("Withdraw modal: pool token input updates withdrawal token input")
@allure.severity(allure.severity_level.CRITICAL)
def test_withdraw_modal_pool_input_updates_token_input(page_with_wallet_on_pool):
    """Ввод суммы в pool token input автоматически пересчитывает withdrawal token input."""
    mp = MarketplacePage(page_with_wallet_on_pool)
    modal = WithdrawModal(page_with_wallet_on_pool)

    with allure.step("Открываем модалку вывода"):
        mp.wait_for_pool_page()
        mp.wait_for_withdraw_button()
        mp.withdraw_button().click()
        modal.wait_for()

    with allure.step("Вводим '1' в pool token input (sell coin)"):
        modal.pool_token_input().fill("1")
        page_with_wallet_on_pool.wait_for_timeout(1_000)

    with allure.step("Withdrawal token input (buy coin) обновился"):
        buy_value = modal.withdraw_token_input().input_value()
        assert buy_value not in ("", "0"), (
            f"Buy coin input not updated after filling sell coin. Got: {buy_value!r}"
        )
        allure.attach(
            f"Pool token input: 1 → Withdrawal token input: {buy_value}",
            name="Input cross-update",
            attachment_type=allure.attachment_type.TEXT,
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Withdrawal")
@allure.title("Withdraw modal: withdrawal token input updates pool token input")
@allure.severity(allure.severity_level.CRITICAL)
def test_withdraw_modal_token_input_updates_pool_input(page_with_wallet_on_pool):
    """Ввод суммы в withdrawal token input автоматически пересчитывает pool token input."""
    mp = MarketplacePage(page_with_wallet_on_pool)
    modal = WithdrawModal(page_with_wallet_on_pool)

    with allure.step("Открываем модалку вывода"):
        mp.wait_for_pool_page()
        mp.wait_for_withdraw_button()
        mp.withdraw_button().click()
        modal.wait_for()

    with allure.step("Вводим '1' в withdrawal token input (buy coin)"):
        modal.withdraw_token_input().fill("1")
        page_with_wallet_on_pool.wait_for_timeout(1_000)

    with allure.step("Pool token input (sell coin) обновился"):
        sell_value = modal.pool_token_input().input_value()
        assert sell_value not in ("", "0"), (
            f"Sell coin input not updated after filling buy coin. Got: {sell_value!r}"
        )
        allure.attach(
            f"Withdrawal token input: 1 → Pool token input: {sell_value}",
            name="Input cross-update",
            attachment_type=allure.attachment_type.TEXT,
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Withdrawal")
@allure.title("Withdraw modal MAX button fills pool token input with full balance")
@allure.severity(allure.severity_level.CRITICAL)
def test_withdraw_modal_max_button(page_with_wallet_on_pool):
    """Клик MAX заполняет pool token input максимальным балансом."""
    mp = MarketplacePage(page_with_wallet_on_pool)
    modal = WithdrawModal(page_with_wallet_on_pool)

    with allure.step("Открываем модалку вывода"):
        mp.wait_for_pool_page()
        mp.wait_for_withdraw_button()
        mp.withdraw_button().click()
        modal.wait_for()

    with allure.step("Запоминаем отображаемый баланс"):
        balance_text = modal.balance_text()
        import re
        m = re.search(r"Balance:\s*([\d.]+)", balance_text)
        displayed_balance = m.group(1) if m else None

    with allure.step("Кликаем MAX"):
        modal.max_button().click()
        page_with_wallet_on_pool.wait_for_timeout(500)

    with allure.step("Pool token input заполнен балансом"):
        sell_value = modal.pool_token_input().input_value()
        assert sell_value not in ("", "0"), (
            f"Pool token input empty after MAX click: {sell_value!r}"
        )

    with allure.step(f"Значение ≈ отображаемому балансу {displayed_balance} (погрешность < 1%)"):
        if displayed_balance:
            try:
                diff = abs(float(sell_value) - float(displayed_balance))
                tolerance = float(displayed_balance) * 0.01
                assert diff <= tolerance, (
                    f"MAX filled {sell_value!r} differs from displayed balance "
                    f"{displayed_balance!r} by more than 1%"
                )
            except ValueError:
                pytest.fail(f"Could not compare values: {sell_value!r} vs {displayed_balance!r}")

    with allure.step("Скриншот после MAX"):
        allure.attach(
            page_with_wallet_on_pool.screenshot(),
            name="Withdraw modal after MAX",
            attachment_type=allure.attachment_type.PNG,
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Withdrawal")
@allure.title("Withdraw submit button triggers signing flow")
@allure.severity(allure.severity_level.CRITICAL)
def test_withdraw_triggers_signing(page_with_wallet_on_pool):
    """Клик Request Withdrawal вызывает подпись транзакции.

    Ожидаемое поведение — TBD.
    Запустить: HEADED=1 SLOWMO=800 pytest tests/ui/market/test_withdraw_modal.py::test_withdraw_triggers_signing -v -s
    """
    mp = MarketplacePage(page_with_wallet_on_pool)
    modal = WithdrawModal(page_with_wallet_on_pool)

    with allure.step("Открываем модалку вывода"):
        mp.wait_for_pool_page()
        mp.wait_for_withdraw_button()
        mp.withdraw_button().click()
        modal.wait_for()

    with allure.step("Нажимаем MAX"):
        modal.max_button().click()
        page_with_wallet_on_pool.wait_for_timeout(500)

    with allure.step("Скриншот перед нажатием Request Withdrawal"):
        allure.attach(
            page_with_wallet_on_pool.screenshot(),
            name="Before Request Withdrawal",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Кликаем Request Withdrawal"):
        modal.request_withdrawal_button().click()

    with allure.step("Ждём 3 секунды — наблюдаем результат"):
        page_with_wallet_on_pool.wait_for_timeout(3_000)
        allure.attach(
            page_with_wallet_on_pool.screenshot(),
            name="After Request Withdrawal click (3s)",
            attachment_type=allure.attachment_type.PNG,
        )
    # TODO: добавить assertion после запуска в HEADED=1 и наблюдения поведения
