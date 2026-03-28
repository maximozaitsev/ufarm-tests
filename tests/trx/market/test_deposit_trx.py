"""Транзакционные UI-тесты: Deposit.

Кошелёк: WALLET_TRX_ADDRESS / WALLET_TRX_PRIVATE_KEY
Пул:     TEST_POOL_ID (REF TEST, minClientTier=0, deposit_min=0, withdraw_delay=1s)

Тесты выполняют реальные on-chain операции на Arbitrum Mainnet.

Режимы:
  - Gasless (безгазовый): пользователь подписывает два EIP-712 сообщения
    (USDT Permit + UFarm deposit), relay отправляет транзакцию.
    Кошелёк не тратит ETH на газ. Депозит требует одобрения управляющего фонда.
  - On-chain (прямой): browser вызывает eth_sendTransaction, Python подписывает
    и отправляет raw tx напрямую на Arbitrum. Требует ETH для газа.
    LP-баланс растёт сразу после подтверждения транзакции.

Паттерн "setup once, assert many":
  Каждая session-фикстура выполняет ONE операцию и собирает состояние.
  Каждый тест проверяет один аспект результата независимо:
  если один тест упадёт — остальные продолжают выполняться.
  Если упадёт сама фикстура (операция не прошла) — зависимые тесты → ERROR.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import allure
import pytest

from core.api.models.cashflow import CashflowResponse

from .conftest import (
    DEPOSIT_AMOUNT_ONCHAIN,
    GASLESS_DEPOSIT_AMOUNT,
    GaslessDepositResult,
    OnchainDepositResult,
    attach_tx_link,
)


pytestmark = [pytest.mark.trx, pytest.mark.smoke]


# ── Gasless deposit: setup once, assert many ──────────────────────────────────
# Фикстура gasless_deposit (scope=session) выполняет ONE gasless депозит.
# Каждый тест ниже проверяет один аспект независимо.


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Deposit")
@allure.title("Gasless deposit: relay accepts request, UI shows «Request submitted» modal")
@allure.severity(allure.severity_level.CRITICAL)
def test_gasless_deposit_request_submitted(gasless_deposit: GaslessDepositResult):
    """Relay принял gasless deposit: UI показал модалку «Request submitted»."""
    with allure.step("Модалка «Request submitted» появилась"):
        allure.attach(
            gasless_deposit.screenshot_modal,
            name="Request submitted modal",
            attachment_type=allure.attachment_type.PNG,
        )
        assert gasless_deposit.request_submitted_appeared, (
            "Модалка «Request submitted» не появилась — relay не принял запрос"
        )


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Deposit")
@allure.title("Gasless deposit: pool page shows «pending approval» after modal closed")
@allure.severity(allure.severity_level.CRITICAL)
def test_gasless_deposit_pending_approval(gasless_deposit: GaslessDepositResult):
    """После закрытия модалки страница пула показывает «pending approval»."""
    with allure.step("Страница пула показывает «Your deposit request is pending approval»"):
        allure.attach(
            gasless_deposit.screenshot_pending,
            name="Pending approval on pool page",
            attachment_type=allure.attachment_type.PNG,
        )
        assert gasless_deposit.pending_approval_appeared, (
            "Текст «pending approval» не появился на странице пула"
        )


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Deposit")
@allure.title("Gasless deposit: MY REQUESTS shows entry with type «Deposit»")
@allure.severity(allure.severity_level.NORMAL)
def test_gasless_deposit_my_requests_type(gasless_deposit: GaslessDepositResult):
    """MY REQUESTS содержит запись с типом «Deposit»."""
    row = gasless_deposit.requests_row
    with allure.step(f"Тип первой записи: ожидается «Deposit», получено «{row.get('type')}»"):
        allure.attach(
            gasless_deposit.screenshot_requests_tab,
            name="MY REQUESTS tab",
            attachment_type=allure.attachment_type.PNG,
        )
        assert row.get("type") == "Deposit", (
            f"Ожидается type=Deposit, got {row.get('type')!r}"
        )


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Deposit")
@allure.title("Gasless deposit: MY REQUESTS entry has today's date")
@allure.severity(allure.severity_level.NORMAL)
def test_gasless_deposit_my_requests_date(gasless_deposit: GaslessDepositResult):
    """MY REQUESTS: request_date содержит сегодняшнюю дату."""
    row = gasless_deposit.requests_row
    today = datetime.now(timezone.utc)
    expected = today.strftime("%b") + " " + str(today.day)  # e.g. "Mar 28"
    with allure.step(f"Request date содержит «{expected}»: получено «{row.get('request_date')}»"):
        assert expected in (row.get("request_date") or ""), (
            f"Request date «{row.get('request_date')}» не содержит «{expected}»"
        )


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Deposit")
@allure.title("Gasless deposit: MY REQUESTS expiration date is tomorrow")
@allure.severity(allure.severity_level.NORMAL)
def test_gasless_deposit_my_requests_expiration(gasless_deposit: GaslessDepositResult):
    """MY REQUESTS: relay выдаёт разрешение на 24 часа — expiration_date завтра."""
    row = gasless_deposit.requests_row
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    expected = tomorrow.strftime("%b") + " " + str(tomorrow.day)  # e.g. "Mar 29"
    with allure.step(f"Expiration date содержит «{expected}»: получено «{row.get('expiration_date')}»"):
        assert expected in (row.get("expiration_date") or ""), (
            f"Expiration date «{row.get('expiration_date')}» не содержит «{expected}» "
            f"(ожидается +1 день от сегодня)"
        )


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Deposit")
@allure.title("Gasless deposit: MY REQUESTS current value matches deposit amount")
@allure.severity(allure.severity_level.NORMAL)
def test_gasless_deposit_my_requests_current_value(gasless_deposit: GaslessDepositResult):
    """MY REQUESTS: «Current value, $» соответствует сумме депозита (tokenPrice ≈ 1).

    Допустимое отклонение ±0.1$: tokenPrice пула обновляется периодически,
    в обычных условиях разница < $0.01 для стабильных пулов.
    """
    row = gasless_deposit.requests_row
    raw_value = row.get("value") or ""
    with allure.step(
        f"Current value ≈ {gasless_deposit.deposit_amount}$: получено «{raw_value}»"
    ):
        value = Decimal(raw_value.replace(",", ".")) if raw_value else Decimal("0")
        expected = Decimal(gasless_deposit.deposit_amount)
        tolerance = Decimal("0.1")
        assert abs(value - expected) <= tolerance, (
            f"Current value {value} не соответствует deposit amount {expected} "
            f"(допуск ±{tolerance})"
        )


# ── On-chain deposit: setup once, assert many ─────────────────────────────────
# Фикстура onchain_deposit (scope=session) выполняет ONE on-chain tx.
# Каждый тест ниже проверяет один аспект независимо.


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Deposit")
@allure.title("On-chain deposit: UI shows «Deposit confirmed» modal")
@allure.severity(allure.severity_level.CRITICAL)
def test_onchain_deposit_confirmed_modal(onchain_deposit: OnchainDepositResult):
    """UI показал модалку «Deposit confirmed» после подтверждения tx on-chain."""
    attach_tx_link(onchain_deposit.tx_hash)
    with allure.step("Модалка «Deposit confirmed» появилась"):
        allure.attach(
            onchain_deposit.screenshot_modal,
            name="Deposit confirmed modal",
            attachment_type=allure.attachment_type.PNG,
        )
        assert onchain_deposit.deposit_confirmed_modal_appeared, (
            "Модалка «Deposit confirmed» не появилась"
        )


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Deposit")
@allure.title("On-chain deposit: tx confirmed on-chain (wallet USDT decreased)")
@allure.severity(allure.severity_level.CRITICAL)
def test_onchain_deposit_usdt_decreased(onchain_deposit: OnchainDepositResult):
    """On-chain депозит подтверждён: USDT on-chain уменьшился на сумму депозита."""
    d = onchain_deposit
    attach_tx_link(d.tx_hash)
    expected = d.usdt_before - Decimal(DEPOSIT_AMOUNT_ONCHAIN)
    tolerance = Decimal("0.01")
    with allure.step(f"USDT on-chain: {d.usdt_before} → {d.usdt_after} (ожидается ~{expected})"):
        assert abs(d.usdt_after - expected) <= tolerance, (
            f"USDT on-chain ожидается ~{expected} "
            f"({d.usdt_before} − {DEPOSIT_AMOUNT_ONCHAIN}), got {d.usdt_after}"
        )


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Deposit")
@allure.title("On-chain deposit: LP tokens in UI increased")
@allure.severity(allure.severity_level.NORMAL)
def test_onchain_deposit_lp_tokens_increased(onchain_deposit: OnchainDepositResult):
    """После on-chain депозита LP-токены в секции MY BALANCE выросли."""
    d = onchain_deposit
    attach_tx_link(d.tx_hash)
    with allure.step(f"LP tokens в UI: {d.tokens_before} → {d.tokens_after}"):
        allure.attach(
            onchain_deposit.screenshot_after,
            name="Pool page after deposit",
            attachment_type=allure.attachment_type.PNG,
        )
        assert d.tokens_after > d.tokens_before, (
            f"LP tokens не выросли: {d.tokens_before} → {d.tokens_after}"
        )


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Deposit")
@allure.title("On-chain deposit: MY WALLET USD in UI decreased")
@allure.severity(allure.severity_level.NORMAL)
def test_onchain_deposit_wallet_ui_decreased(onchain_deposit: OnchainDepositResult):
    """После on-chain депозита баланс MY WALLET (UI) уменьшился на сумму депозита."""
    d = onchain_deposit
    attach_tx_link(d.tx_hash)
    expected = d.usdt_before - Decimal(DEPOSIT_AMOUNT_ONCHAIN)
    tolerance = Decimal("0.1")
    with allure.step(
        f"MY WALLET (UI): {d.wallet_usd_after} ≈ {d.usdt_before} − {DEPOSIT_AMOUNT_ONCHAIN} = {expected}"
    ):
        allure.attach(
            onchain_deposit.screenshot_after,
            name="Pool page after deposit",
            attachment_type=allure.attachment_type.PNG,
        )
        assert abs(d.wallet_usd_after - expected) <= tolerance, (
            f"MY WALLET (UI) ожидается ~{expected} "
            f"({d.usdt_before} − {DEPOSIT_AMOUNT_ONCHAIN}), got {d.wallet_usd_after}"
        )


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Deposit")
@allure.title("On-chain deposit: entry appears in API cashflow (Completed)")
@allure.severity(allure.severity_level.CRITICAL)
def test_onchain_deposit_appears_in_api_cashflow(
    onchain_deposit: OnchainDepositResult,
    api_client,
    test_pool_id,
    trx_wallet_address,
):
    """On-chain депозит зафиксирован в API cashflow: запись со статусом Completed.

    Получаем on-chain адрес пула через GET /pool/{pool_id}, затем запрашиваем
    GET /pool/{poolAddress}/transactions/cashflows?investorAddress=...&type=Deposit.

    Примечание: для on-chain депозитов requestHash == null (транзакция уходит напрямую
    на блокчейн, минуя relay). Поэтому идентифицируем запись как самую свежую.
    """
    from datetime import timedelta

    from core.api.models.cashflow import CashflowResponse

    d = onchain_deposit
    attach_tx_link(d.tx_hash)

    with allure.step(f"Получаем on-chain адрес пула для pool_id={test_pool_id}"):
        pool_resp = api_client.get(f"/pool/{test_pool_id}")
        assert pool_resp.status_code == 200, f"GET /pool/{test_pool_id} вернул {pool_resp.status_code}"
        pool_address = pool_resp.json()["pool"]["poolAddress"]

    with allure.step("Получаем последние Deposit-записи из cashflow (page 1)"):
        cf_resp = api_client.get(
            f"/pool/{pool_address}/transactions/cashflows",
            params={
                "investorAddress": trx_wallet_address,
                "type": "Deposit",
                "limit": 5,
                "page": 1,
            },
        )
        assert cf_resp.status_code == 200, f"GET cashflows вернул {cf_resp.status_code}"
        body = cf_resp.json()
        allure.attach(
            str(body),
            name="Cashflow API response",
            attachment_type=allure.attachment_type.TEXT,
        )
        cf = CashflowResponse(**body)
        assert cf.data, "Cashflow вернул пустой список — ни одного Deposit не найдено"

    latest = cf.data[0]
    with allure.step(f"Последняя запись: type={latest.type}, status={latest.status}, date={latest.date}"):
        assert latest.type == "Deposit", f"Ожидается type=Deposit, got {latest.type}"
        assert latest.status == "Completed", f"Ожидается status=Completed, got {latest.status}"

    with allure.step(f"poolAddress совпадает: {latest.poolAddress}"):
        assert latest.poolAddress.lower() == pool_address.lower(), (
            f"Ожидается poolAddress={pool_address}, got {latest.poolAddress}"
        )

    with allure.step(f"investorAddress совпадает: {latest.investorAddress}"):
        assert latest.investorAddress.lower() == trx_wallet_address.lower(), (
            f"Ожидается investorAddress={trx_wallet_address}, got {latest.investorAddress}"
        )

    with allure.step(f"Дата записи не старше 24 часов: {latest.date}"):
        # Допускаем до 24ч: session fixture инициализируется при первом обращении,
        # а этот тест может выполниться значительно позже в той же сессии.
        entry_dt = datetime.fromisoformat(latest.date.replace("Z", "+00:00"))
        age = abs((datetime.now(timezone.utc) - entry_dt).total_seconds())
        assert age <= 86_400, (
            f"Запись слишком старая: {latest.date} (возраст {age:.0f}с, ожидается < 24ч)"
        )


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Deposit")
@allure.title("On-chain deposit: entry visible in UI «MY HISTORY» tab")
@allure.severity(allure.severity_level.NORMAL)
def test_onchain_deposit_appears_in_ui_my_history(
    onchain_deposit: OnchainDepositResult,
    page_with_trx_wallet,
    trx_wallet_address,
):
    """On-chain депозит отображается первой строкой таблицы «My history».

    Проверяем конкретную запись — дату, тип, Pool tokens, Value $ и адрес кошелька.

    Структура строки (из DOM):
      td[0] — Date:  <div._wrap_kkuze_1>Mar 28<p._grey_kkuze_7>10:33</p></div>
      td[1] — Type:  <div._deposit_ms8pn_1>Deposit</div>
      td[2] — Tokens: <p>+</p><div._wrap_1szfx_1>0,5</div>
      td[3] — Value $: <div._wrap_1szfx_1>0,5</div>
      td[4] — Address: <div._address_1z3iq_1>...0xCAc...2245C7C</div>
    """
    from core.ui.pages.marketplace_page import MarketplacePage

    d = onchain_deposit
    attach_tx_link(d.tx_hash)
    page = page_with_trx_wallet
    mp = MarketplacePage(page)

    today = datetime.now(timezone.utc)
    expected_date = today.strftime("%b") + " " + str(today.day)
    addr_start = trx_wallet_address[:5]
    addr_end = trx_wallet_address[-7:]

    with allure.step("Скроллим к табам истории и нажимаем «My history»"):
        tab = mp.my_history_tab()
        tab.wait_for(state="visible", timeout=10_000)
        tab.scroll_into_view_if_needed()
        tab.click()

    with allure.step("Читаем данные первой строки таблицы «My history»"):
        page.locator('[role="tabpanel"][aria-labelledby*="tab-history"] tbody tr').first.wait_for(
            state="visible", timeout=10_000
        )
        row = page.evaluate("""() => {
            const panel = document.querySelector('[role="tabpanel"][aria-labelledby*="tab-history"]');
            if (!panel) return null;
            const firstRow = panel.querySelector('tbody tr');
            if (!firstRow) return null;
            const cells = firstRow.querySelectorAll('td');
            const norm = el => el ? el.textContent.replace(/\\s+/g, ' ').trim() : '';
            return {
                date:    norm(cells[0]),
                type:    norm(cells[1]),
                tokens:  norm(cells[2]),
                value:   norm(cells[3]),
                address: norm(cells[4]),
            };
        }""")
        assert row is not None, "Не удалось прочитать первую строку таблицы My history"
        allure.attach(
            str(row),
            name="First row data",
            attachment_type=allure.attachment_type.TEXT,
        )
        allure.attach(
            page.screenshot(),
            name="MY HISTORY tab",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step(f"Тип транзакции: ожидается «Deposit», получено «{row['type']}»"):
        assert row["type"] == "Deposit", f"Ожидается type=Deposit, got {row['type']}"

    with allure.step(f"Pool tokens содержит «{DEPOSIT_AMOUNT_ONCHAIN}»: получено «{row['tokens']}»"):
        actual_tokens_norm = row["tokens"].replace(",", ".").replace("+", "").strip()
        assert DEPOSIT_AMOUNT_ONCHAIN in actual_tokens_norm, (
            f"Pool tokens ожидается содержит «{DEPOSIT_AMOUNT_ONCHAIN}», got «{row['tokens']}»"
        )

    with allure.step(f"Value $: ожидается «{DEPOSIT_AMOUNT_ONCHAIN}», получено «{row['value']}»"):
        assert row["value"].replace(",", ".") == DEPOSIT_AMOUNT_ONCHAIN, (
            f"Value $ ожидается «{DEPOSIT_AMOUNT_ONCHAIN}», got «{row['value']}»"
        )

    with allure.step(f"Дата содержит «{expected_date}»: получено «{row['date']}»"):
        assert expected_date in row["date"], (
            f"Дата строки «{row['date']}» не содержит «{expected_date}»"
        )

    with allure.step(f"Адрес: начало «{addr_start}» и конец «{addr_end}» кошелька TRX"):
        addr = row["address"]
        assert addr_start.lower() in addr.lower() and addr_end.lower() in addr.lower(), (
            f"Адрес строки «{addr}» не соответствует кошельку {trx_wallet_address}"
        )
