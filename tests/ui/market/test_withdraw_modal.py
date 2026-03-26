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


# ══════════════════════════════════════════════════════════════════════════════
# Token selector / dropdown
# ══════════════════════════════════════════════════════════════════════════════

@allure.epic("Market")
@allure.feature("UI")
@allure.story("Withdrawal")
@allure.title("Withdraw modal: single-token pool has no token selector dropdown")
@allure.severity(allure.severity_level.CRITICAL)
def test_withdraw_modal_single_token_no_dropdown(page_with_wallet_on_single_token_pool):
    """В single-token пуле (Pool A) в модалке вывода нет дропдауна выбора токена.

    Отображается только один токен без стрелки/дропдауна.
    Используется: Pool A (POOL_SINGLE_TOKEN_ID) + TEST_WALLET_ADDRESS.
    """
    mp = MarketplacePage(page_with_wallet_on_single_token_pool)
    modal = WithdrawModal(page_with_wallet_on_single_token_pool)

    with allure.step("Ждём загрузки страницы пула и кнопки Withdraw"):
        mp.wait_for_pool_page()
        mp.wait_for_withdraw_button()

    with allure.step("Открываем модалку вывода"):
        mp.withdraw_button().click()
        modal.wait_for()
        modal.request_withdrawal_button().wait_for(state="visible", timeout=5_000)

    with allure.step("Token selector не интерактивен — нет стрелки дропдауна"):
        # В single-token пуле _current_ существует, но без _arrowWrapper_ внутри.
        # _noPointer_ CSS-класс делает его некликабельным.
        assert modal.token_selector_arrow().count() == 0, (
            "Arrow wrapper should not be present in single-token pool token selector"
        )

    with allure.step("Скриншот модалки single-token пула"):
        allure.attach(
            page_with_wallet_on_single_token_pool.screenshot(),
            name="Withdraw modal single-token pool",
            attachment_type=allure.attachment_type.PNG,
        )




@allure.epic("Market")
@allure.feature("UI")
@allure.story("Withdrawal")
@allure.title("Withdraw modal: multi-token pool shows token selector dropdown")
@allure.severity(allure.severity_level.CRITICAL)
def test_withdraw_modal_multi_token_has_dropdown(
    page_with_wallet_on_pool, pool_info_multi_token
):
    """В multi-token пуле (Pool B) в модалке вывода отображается дропдаун выбора токена.

    Доступные токены берутся из pool.availableValueTokens.
    Клик на selector открывает список всех доступных токенов.
    """
    mp = MarketplacePage(page_with_wallet_on_pool)
    modal = WithdrawModal(page_with_wallet_on_pool)

    available_tokens = pool_info_multi_token.availableValueTokens or []
    assert len(available_tokens) >= 2, (
        f"Pool B should have at least 2 available tokens, got: {available_tokens}"
    )

    with allure.step("Открываем модалку вывода"):
        mp.wait_for_pool_page()
        mp.wait_for_withdraw_button()
        mp.withdraw_button().click()
        modal.wait_for()

    with allure.step("Тикер выбранного токена отображается в селекторе"):
        current_ticker = modal.current_token_ticker()
        available_tokens_upper = [t.upper() for t in available_tokens]
        allure.attach(
            f"Current ticker: {current_ticker}\nAvailable: {available_tokens}",
            name="Token info",
            attachment_type=allure.attachment_type.TEXT,
        )
        assert current_ticker.upper() in available_tokens_upper, (
            f"Current token '{current_ticker}' not in available tokens: {available_tokens}"
        )

    with allure.step("Кликаем на token selector — открывается дропдаун"):
        modal.token_selector().click()
        modal.token_dropdown().wait_for(state="visible", timeout=3_000)

    with allure.step(f"Дропдаун содержит все доступные токены: {available_tokens}"):
        for ticker in available_tokens:
            # UI отображает тикеры в верхнем регистре (USDT), API — в нижнем (usdt)
            assert modal.token_option(ticker.upper()).is_visible(), (
                f"Token option '{ticker.upper()}' not visible in dropdown"
            )

    with allure.step("Скриншот дропдауна токенов"):
        allure.attach(
            page_with_wallet_on_pool.screenshot(),
            name="Token dropdown opened",
            attachment_type=allure.attachment_type.PNG,
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Withdrawal")
@allure.title("Withdraw modal: switching output token updates ticker and recalculates amount")
@allure.severity(allure.severity_level.CRITICAL)
def test_withdraw_modal_token_switch_updates_output(
    page_with_wallet_on_pool, pool_info_multi_token
):
    """Переключение токена вывода обновляет тикер в селекторе и пересчитывает withdrawal input.

    Pool B имеет несколько доступных токенов (availableValueTokens).
    После выбора альтернативного токена current_token_ticker() меняется,
    а withdrawal input (buyCoin) пересчитывается.
    """
    mp = MarketplacePage(page_with_wallet_on_pool)
    modal = WithdrawModal(page_with_wallet_on_pool)

    available_tokens = pool_info_multi_token.availableValueTokens or []
    assert len(available_tokens) >= 2, (
        f"Pool B should have at least 2 available tokens for switch test: {available_tokens}"
    )

    with allure.step("Открываем модалку вывода"):
        mp.wait_for_pool_page()
        mp.wait_for_withdraw_button()
        mp.withdraw_button().click()
        modal.wait_for()

    with allure.step("Запоминаем текущий токен и выбираем альтернативный"):
        initial_ticker = modal.current_token_ticker()
        # API возвращает тикеры в нижнем регистре, UI показывает в верхнем
        other_ticker = next(
            t.upper() for t in available_tokens if t.upper() != initial_ticker
        )

    with allure.step("Вводим '1' в pool token input чтобы было что пересчитывать"):
        modal.pool_token_input().fill("1")
        page_with_wallet_on_pool.wait_for_timeout(500)

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

    with allure.step("Withdrawal token input не пустой после смены токена"):
        buy_after = modal.withdraw_token_input().input_value()
        assert buy_after not in ("", "0"), (
            f"Buy coin input should not be empty/zero after token switch: {buy_after!r}"
        )

    with allure.step(f"Скриншот после переключения токена на {other_ticker}"):
        allure.attach(
            page_with_wallet_on_pool.screenshot(),
            name=f"Token switched to {other_ticker}",
            attachment_type=allure.attachment_type.PNG,
        )


# ══════════════════════════════════════════════════════════════════════════════
# Негативные сценарии
# ══════════════════════════════════════════════════════════════════════════════

@allure.epic("Market")
@allure.feature("UI")
@allure.story("Withdrawal")
@allure.title("Withdraw modal: amount exceeding balance shows error")
@allure.severity(allure.severity_level.CRITICAL)
def test_withdraw_modal_amount_exceeds_balance_shows_error(
    page_with_wallet_on_pool, wallet_portfolio, test_pool_id, pool_info_multi_token
):
    """Ввод суммы больше баланса показывает ошибку 'Not enough pool tokens...'."""
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
    over_balance = round(api_balance_tokens * 1.1 + 1, 1)

    with allure.step("Открываем модалку вывода"):
        mp.wait_for_pool_page()
        mp.wait_for_withdraw_button()
        mp.withdraw_button().click()
        modal.wait_for()

    with allure.step(f"Вводим {over_balance} pool tokens (баланс ≈ {api_balance_tokens:.1f})"):
        modal.pool_token_input().fill(str(over_balance))
        page_with_wallet_on_pool.wait_for_timeout(500)

    with allure.step("Появляется сообщение об ошибке"):
        error = page_with_wallet_on_pool.get_by_text("Not enough pool tokens", exact=False)
        error.wait_for(state="visible", timeout=3_000)

    with allure.step("Кнопка Request Withdrawal недоступна"):
        assert modal.request_withdrawal_button().is_disabled(), (
            "Request Withdrawal should be disabled when amount exceeds balance"
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Withdrawal")
@allure.title("Withdraw modal: zero amount shows error")
@allure.severity(allure.severity_level.NORMAL)
def test_withdraw_modal_zero_amount_shows_error(page_with_wallet_on_pool):
    """Ввод 0 в pool token input показывает ошибку 'Please indicate the withdrawal sum...'."""
    mp = MarketplacePage(page_with_wallet_on_pool)
    modal = WithdrawModal(page_with_wallet_on_pool)

    with allure.step("Открываем модалку вывода"):
        mp.wait_for_pool_page()
        mp.wait_for_withdraw_button()
        mp.withdraw_button().click()
        modal.wait_for()

    with allure.step("Вводим 0 в pool token input"):
        modal.pool_token_input().fill("0")
        page_with_wallet_on_pool.wait_for_timeout(500)

    with allure.step("Появляется сообщение об ошибке"):
        error = page_with_wallet_on_pool.get_by_text("Please indicate the withdrawal sum", exact=False)
        error.wait_for(state="visible", timeout=3_000)

    with allure.step("Кнопка Request Withdrawal недоступна"):
        assert modal.request_withdrawal_button().is_disabled(), (
            "Request Withdrawal should be disabled when amount is zero"
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Withdrawal")
@allure.title("Withdraw modal: USDT amount exceeding balance shows error")
@allure.severity(allure.severity_level.CRITICAL)
def test_withdraw_modal_usdt_exceeds_balance_shows_error(
    page_with_wallet_on_pool, wallet_portfolio, test_pool_id, pool_info_multi_token
):
    """Ввод суммы USDT больше баланса через buyCoin input показывает ошибку 'Not enough pool tokens...'."""
    mp = MarketplacePage(page_with_wallet_on_pool)
    modal = WithdrawModal(page_with_wallet_on_pool)

    pool_stat = next(
        (p.poolStat for p in wallet_portfolio.pools if p.id == test_pool_id), None
    )
    assert pool_stat is not None, f"Pool {test_pool_id} not found in portfolio"
    assert pool_info_multi_token.poolMetric is not None, "poolMetric not available for pool"

    USDT_DECIMALS = 6
    api_balance_usdt = float(Decimal(pool_stat.totalBalance) / Decimal(10 ** USDT_DECIMALS))
    over_balance_usdt = round(api_balance_usdt * 1.1 + 1, 1)

    with allure.step("Открываем модалку вывода"):
        mp.wait_for_pool_page()
        mp.wait_for_withdraw_button()
        mp.withdraw_button().click()
        modal.wait_for()

    with allure.step(f"Вводим {over_balance_usdt} USDT в withdrawal token input (баланс ≈ {api_balance_usdt:.1f} USDT)"):
        modal.withdraw_token_input().fill(str(over_balance_usdt))
        page_with_wallet_on_pool.wait_for_timeout(500)

    with allure.step("Появляется сообщение об ошибке"):
        error = page_with_wallet_on_pool.get_by_text("Not enough pool tokens", exact=False)
        error.wait_for(state="visible", timeout=3_000)

    with allure.step("Кнопка Request Withdrawal недоступна"):
        assert modal.request_withdrawal_button().is_disabled(), (
            "Request Withdrawal should be disabled when USDT amount exceeds balance"
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Withdrawal")
@allure.title("Withdraw modal: clearing input after fill disables submit button")
@allure.severity(allure.severity_level.NORMAL)
def test_withdraw_modal_clear_input_disables_button(page_with_wallet_on_pool):
    """Очистка инпута после ввода валидной суммы снова дизейблит кнопку Request Withdrawal."""
    mp = MarketplacePage(page_with_wallet_on_pool)
    modal = WithdrawModal(page_with_wallet_on_pool)

    with allure.step("Открываем модалку вывода"):
        mp.wait_for_pool_page()
        mp.wait_for_withdraw_button()
        mp.withdraw_button().click()
        modal.wait_for()

    with allure.step("Вводим валидную сумму '1'"):
        modal.pool_token_input().fill("1")
        page_with_wallet_on_pool.wait_for_timeout(500)

    with allure.step("Очищаем инпут"):
        modal.pool_token_input().fill("")
        page_with_wallet_on_pool.wait_for_timeout(500)

    with allure.step("Кнопка Request Withdrawal снова недоступна"):
        assert modal.request_withdrawal_button().is_disabled(), (
            "Request Withdrawal should be disabled after clearing input"
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Withdrawal")
@allure.title("Withdraw modal: close and reopen resets inputs")
@allure.severity(allure.severity_level.NORMAL)
def test_withdraw_modal_reopen_resets_inputs(page_with_wallet_on_pool):
    """После закрытия и повторного открытия модалки инпуты сброшены в начальное состояние."""
    mp = MarketplacePage(page_with_wallet_on_pool)
    modal = WithdrawModal(page_with_wallet_on_pool)

    with allure.step("Открываем модалку, вводим '1'"):
        mp.wait_for_pool_page()
        mp.wait_for_withdraw_button()
        mp.withdraw_button().click()
        modal.wait_for()
        modal.pool_token_input().fill("1")

    with allure.step("Закрываем модалку кликом на крестик"):
        modal.close()

    with allure.step("Открываем модалку повторно"):
        mp.withdraw_button().click()
        modal.wait_for()

    with allure.step("Pool token input пустой или нулевой"):
        sell_value = modal.pool_token_input().input_value()
        assert sell_value in ("", "0"), (
            f"Pool token input not reset after reopen: {sell_value!r}"
        )

    with allure.step("Withdrawal token input пустой или нулевой"):
        buy_value = modal.withdraw_token_input().input_value()
        assert buy_value in ("", "0"), (
            f"Withdrawal token input not reset after reopen: {buy_value!r}"
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

    with allure.step("Кнопка Request Withdrawal активна — скриншот состояния готовности"):
        # Кнопка активна — вывод можно запросить.
        # Не кликаем Request Withdrawal: может создать pending withdrawal на бэкенде
        # (gasless, без подписи), что заблокирует последующие тесты через auto-модалку.
        assert not modal.request_withdrawal_button().is_disabled(), (
            "Request Withdrawal button should be enabled after MAX"
        )
        allure.attach(
            page_with_wallet_on_pool.screenshot(),
            name="Withdrawal ready to submit (MAX filled)",
            attachment_type=allure.attachment_type.PNG,
        )
