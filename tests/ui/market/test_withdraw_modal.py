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
        modal.request_withdrawal_button().wait_for(state="visible", timeout=5_000)

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
def test_withdraw_modal_shows_pool_balance(
    page_with_wallet_on_pool, wallet_portfolio, test_pool_id, pool_info_multi_token
):
    """Баланс в модалке вывода > 0 и соответствует данным из portfolio API с учётом tokenPrice.

    portfolio.totalBalance — стоимость инвестиции в USDT (наименьшие единицы, 6 decimals).
    Модалка показывает баланс в токенах пула (pool tokens).
    Связь: ui_balance ≈ totalBalance / 10^6 / tokenPrice (погрешность < 5%).
    """
    import re

    mp = MarketplacePage(page_with_wallet_on_pool)
    modal = WithdrawModal(page_with_wallet_on_pool)

    pool_stat = next(
        (p.poolStat for p in wallet_portfolio.pools if p.id == test_pool_id),
        None,
    )
    assert pool_stat is not None, f"Pool {test_pool_id} not found in portfolio"
    assert pool_info_multi_token.poolMetric is not None, "poolMetric not available for pool"

    token_price = Decimal(str(pool_info_multi_token.poolMetric.tokenPrice))
    # totalBalance хранится в USDT (6 decimals на Arbitrum)
    USDT_DECIMALS = 6
    api_balance_usdt = Decimal(pool_stat.totalBalance) / Decimal(10 ** USDT_DECIMALS)
    api_balance_tokens = api_balance_usdt / token_price

    with allure.step("Открываем модалку вывода"):
        mp.wait_for_pool_page()
        mp.wait_for_withdraw_button()
        mp.withdraw_button().click()
        modal.wait_for()

    with allure.step("Текст баланса в модалке содержит ненулевое значение"):
        balance_text = modal.balance_text()
        allure.attach(balance_text, name="Balance text", attachment_type=allure.attachment_type.TEXT)
        m = re.search(r"Balance:\s*([\d.]+)", balance_text)
        assert m, f"Could not parse balance from: {balance_text!r}"
        ui_balance = float(m.group(1))
        assert ui_balance > 0, f"Balance in modal is zero: {ui_balance}"

    with allure.step(f"Баланс в UI ≈ portfolio / tokenPrice (погрешность < 5%)"):
        expected = float(api_balance_tokens)
        diff = abs(ui_balance - expected) / max(expected, 1e-9)
        allure.attach(
            f"UI: {ui_balance}, API (totalBalance/tokenPrice): {expected:.6f}, diff: {diff:.2%}",
            name="Balance comparison",
            attachment_type=allure.attachment_type.TEXT,
        )
        assert diff < 0.05, (
            f"UI balance {ui_balance} differs from API-derived {expected:.6f} by {diff:.2%} (> 5%)"
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

    with allure.step("Кнопка 'Request Withdrawal' неактивна при пустом инпуте"):
        assert modal.request_withdrawal_button().is_disabled(), (
            "Request Withdrawal button should be disabled when input is empty"
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Withdrawal")
@allure.title("Withdraw modal: pool token input updates withdrawal token input")
@allure.severity(allure.severity_level.CRITICAL)
def test_withdraw_modal_pool_input_updates_token_input(
    page_with_wallet_on_pool, wallet_portfolio, test_pool_id, pool_info_multi_token
):
    """Ввод случайной суммы в pool token input пересчитывает withdrawal token input.

    Случайное число с 1 децималом в диапазоне (0, баланс_токенов_пула].
    buy_coin ≈ sell_amount × tokenPrice (погрешность < 2%).
    """
    import random

    mp = MarketplacePage(page_with_wallet_on_pool)
    modal = WithdrawModal(page_with_wallet_on_pool)

    pool_stat = next(
        (p.poolStat for p in wallet_portfolio.pools if p.id == test_pool_id), None
    )
    assert pool_stat is not None, f"Pool {test_pool_id} not found in portfolio"
    assert pool_info_multi_token.poolMetric is not None, "poolMetric not available for pool"

    token_price = Decimal(str(pool_info_multi_token.poolMetric.tokenPrice))
    USDT_DECIMALS = 6
    api_balance_usdt = Decimal(pool_stat.totalBalance) / Decimal(10 ** USDT_DECIMALS)
    api_balance_tokens = float(api_balance_usdt / token_price)

    # Случайное число с 1 децималом в диапазоне (0, баланс_токенов]
    sell_amount = round(random.uniform(0.1, api_balance_tokens), 1)

    with allure.step("Открываем модалку вывода"):
        mp.wait_for_pool_page()
        mp.wait_for_withdraw_button()
        mp.withdraw_button().click()
        modal.wait_for()

    with allure.step(f"Вводим {sell_amount} в pool token input (диапазон 0..{api_balance_tokens:.1f})"):
        modal.pool_token_input().fill(str(sell_amount))
        page_with_wallet_on_pool.wait_for_timeout(1_000)

    with allure.step(f"Withdrawal token input (buy coin) ≈ {sell_amount} × tokenPrice ({float(token_price):.4f})"):
        buy_value = modal.withdraw_token_input().input_value()
        assert buy_value not in ("", "0"), (
            f"Buy coin input not updated after filling sell coin. Got: {buy_value!r}"
        )
        expected_usdt = sell_amount * float(token_price)
        actual_usdt = float(buy_value.replace(",", "."))
        diff = abs(actual_usdt - expected_usdt) / max(expected_usdt, 1e-9)
        allure.attach(
            f"sell: {sell_amount} pool tokens × {float(token_price):.4f} = {expected_usdt:.4f} USDT\n"
            f"buy input: {actual_usdt:.4f} USDT, diff: {diff:.2%}",
            name="Input cross-update",
            attachment_type=allure.attachment_type.TEXT,
        )
        assert diff < 0.02, (
            f"Buy coin {actual_usdt:.4f} differs from expected {expected_usdt:.4f} by {diff:.2%} (> 2%)"
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Withdrawal")
@allure.title("Withdraw modal: withdrawal token input updates pool token input")
@allure.severity(allure.severity_level.CRITICAL)
def test_withdraw_modal_token_input_updates_pool_input(
    page_with_wallet_on_pool, wallet_portfolio, test_pool_id, pool_info_multi_token
):
    """Ввод случайной суммы USDT в withdrawal token input пересчитывает pool token input.

    Случайное число с 1 децималом в диапазоне (0, баланс_в_USDT].
    sell_coin ≈ buy_amount / tokenPrice (погрешность < 2%).
    """
    import random

    mp = MarketplacePage(page_with_wallet_on_pool)
    modal = WithdrawModal(page_with_wallet_on_pool)

    pool_stat = next(
        (p.poolStat for p in wallet_portfolio.pools if p.id == test_pool_id), None
    )
    assert pool_stat is not None, f"Pool {test_pool_id} not found in portfolio"
    assert pool_info_multi_token.poolMetric is not None, "poolMetric not available for pool"

    token_price = Decimal(str(pool_info_multi_token.poolMetric.tokenPrice))
    USDT_DECIMALS = 6
    api_balance_usdt = float(Decimal(pool_stat.totalBalance) / Decimal(10 ** USDT_DECIMALS))

    # Случайная сумма USDT с 1 децималом в диапазоне (0, баланс_в_USDT]
    buy_amount = round(random.uniform(0.1, api_balance_usdt), 1)

    with allure.step("Открываем модалку вывода"):
        mp.wait_for_pool_page()
        mp.wait_for_withdraw_button()
        mp.withdraw_button().click()
        modal.wait_for()

    with allure.step(f"Вводим {buy_amount} USDT в withdrawal token input (диапазон 0..{api_balance_usdt:.1f})"):
        modal.withdraw_token_input().fill(str(buy_amount))
        page_with_wallet_on_pool.wait_for_timeout(1_000)

    with allure.step(f"Pool token input (sell coin) ≈ {buy_amount} / tokenPrice ({float(token_price):.4f})"):
        sell_value = modal.pool_token_input().input_value()
        assert sell_value not in ("", "0"), (
            f"Sell coin input not updated after filling buy coin. Got: {sell_value!r}"
        )
        expected_tokens = buy_amount / float(token_price)
        actual_tokens = float(sell_value.replace(",", "."))
        diff = abs(actual_tokens - expected_tokens) / max(expected_tokens, 1e-9)
        allure.attach(
            f"buy: {buy_amount} USDT / {float(token_price):.4f} = {expected_tokens:.4f} pool tokens\n"
            f"sell input: {actual_tokens:.4f} pool tokens, diff: {diff:.2%}",
            name="Input cross-update",
            attachment_type=allure.attachment_type.TEXT,
        )
        assert diff < 0.02, (
            f"Sell coin {actual_tokens:.4f} differs from expected {expected_tokens:.4f} by {diff:.2%} (> 2%)"
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
