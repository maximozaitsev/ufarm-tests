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

On-chain тесты: паттерн "setup once, assert many"
  Фикстура onchain_deposit (scope=session) выполняет ONE транзакцию и собирает
  состояние до/после. Каждый тест проверяет один аспект результата независимо.
  Если упадёт тест баланса UI — тест факта транзакции остаётся зелёным.
  Если упадёт сама фикстура (tx не прошла) — все зависимые тесты → ERROR.

Изоляция:
  - Wallet отдельный от всех остальных тестов — конфликтов нет.
"""

from decimal import Decimal

import allure
import pytest

from core.api.models.cashflow import CashflowResponse
from core.ui.pages.deposit_modal import DepositModal
from core.ui.pages.marketplace_page import MarketplacePage

from .conftest import DEPOSIT_AMOUNT_ONCHAIN, OnchainDepositResult, attach_tx_link


pytestmark = [pytest.mark.trx, pytest.mark.smoke]

DEPOSIT_AMOUNT = "1"        # 1 USDT gasless

# Сколько мс ждать появления "Request submitted" после клика submit.
# Gasless flow: submit → 2x EIP-712 signing → relay → success modal.
SIGNING_TIMEOUT_MS = 30_000


# ── Тесты ─────────────────────────────────────────────────────────────────────


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Deposit")
@allure.title("Gasless deposit 1 USDT: relay accepts request, UI shows pending approval")
@allure.severity(allure.severity_level.CRITICAL)
def test_gasless_deposit_pending_approval(page_with_trx_wallet):
    """Безгазовый депозит 1 USDT принят relay: UI показывает 'Request submitted'.

    Gasless-режим: пользователь подписывает два EIP-712 сообщения
    (USDT EIP-2612 Permit + UFarm deposit), relay отправляет транзакцию.
    Кошелёк не тратит ETH на газ. LP-баланс растёт после одобрения управляющего.

    Шаги:
    1. Открываем модалку Deposit, вводим 1 USDT, нажимаем «Request Deposit»
    2. Провайдер подписывает оба EIP-712 сообщения через Python (~мгновенно)
    3. Relay получает подписи и создаёт pending deposit
    4. UI показывает модалку «Request submitted»
    5. После закрытия модалки — страница пула показывает 'pending approval'
    """
    page = page_with_trx_wallet
    mp = MarketplacePage(page)
    modal = DepositModal(page)

    with allure.step("Открываем модалку Deposit"):
        mp.wait_for_pool_cards()
        page.locator(".mantine-Modal-overlay").wait_for(state="hidden", timeout=5_000)
        mp.deposit_button().click()
        modal.wait_for()

    with allure.step(f"Вводим {DEPOSIT_AMOUNT} USDT (gasless toggle ON по умолчанию)"):
        modal.amount_input().fill(DEPOSIT_AMOUNT)

    with allure.step("Нажимаем «Request Deposit» (gasless — relay отправит tx)"):
        allure.attach(
            page.screenshot(),
            name="Before submit",
            attachment_type=allure.attachment_type.PNG,
        )
        modal.submit_button().click()

    with allure.step("Ждём модалку «Request submitted» — relay принял подписи"):
        # Gasless flow: submit → signing (2x EIP-712) → relay → success modal.
        # Signing is near-instant (Python crypto). publicnode.com RPC calls
        # are proxied via Python route handler so they also complete quickly.
        page.get_by_text("Request submitted").wait_for(timeout=SIGNING_TIMEOUT_MS)
        allure.attach(
            page.screenshot(),
            name="Request submitted modal",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Модалка «Request submitted» видна"):
        assert page.get_by_text("Request submitted").is_visible()

    with allure.step("Закрываем модалку, проверяем статус на странице пула"):
        page.get_by_role("button", name="CLOSE").click()
        pending = page.get_by_text("Your deposit request is pending approval")
        pending.wait_for(timeout=5_000)
        allure.attach(
            page.screenshot(),
            name="Pending approval on pool page",
            attachment_type=allure.attachment_type.PNG,
        )
        assert pending.is_visible()


# ── On-chain deposit: setup once, assert many ─────────────────────────────────
# Все тесты ниже зависят от фикстуры onchain_deposit (scope=session).
# Транзакция выполняется ОДИН РАЗ. Каждый тест проверяет один аспект независимо.


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
    # Ожидаем: usdt_after ≈ usdt_before − DEPOSIT_AMOUNT_ONCHAIN (±0.01 на комиссию пула).
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
    # Reference: on-chain USDT до депозита (UI-баланс до не читался — загружается async).
    # Ожидаем: wallet_usd_after ≈ usdt_before − DEPOSIT_AMOUNT_ONCHAIN (±0.1 на округление UI).
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


# ── On-chain deposit: API cashflow + UI history tab ───────────────────────────


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
    на блокчейн, минуя relay). Поэтому идентифицируем запись как самую свежую —
    записи отсортированы по убыванию даты, наш депозит был только что.
    """
    d = onchain_deposit
    attach_tx_link(d.tx_hash)

    with allure.step(f"Получаем on-chain адрес пула для pool_id={test_pool_id}"):
        pool_resp = api_client.get(f"/pool/{test_pool_id}")
        assert pool_resp.status_code == 200, f"GET /pool/{test_pool_id} вернул {pool_resp.status_code}"
        pool_address = pool_resp.json()["pool"]["poolAddress"]

    with allure.step("Получаем последние Deposit-записи из cashflow (page 1)"):
        # On-chain депозиты не имеют requestHash в API — запись создаётся по blockNumber.
        # Используем most-recent запись: записи отсортированы по убыванию даты,
        # наш депозит был только что — он должен быть первым в списке.
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
    with allure.step(f"Последняя Deposit-запись: type={latest.type}, status={latest.status}, date={latest.date}"):
        assert latest.type == "Deposit", f"Ожидается type=Deposit, got {latest.type}"
        assert latest.status == "Completed", f"Ожидается status=Completed, got {latest.status}"


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Deposit")
@allure.title("On-chain deposit: entry visible in UI «MY HISTORY» tab")
@allure.severity(allure.severity_level.NORMAL)
def test_onchain_deposit_appears_in_ui_my_history(
    onchain_deposit: OnchainDepositResult,
    page_with_trx_wallet,
):
    """On-chain депозит отображается в таблице «MY HISTORY» на странице пула."""
    d = onchain_deposit
    attach_tx_link(d.tx_hash)
    page = page_with_trx_wallet
    mp = MarketplacePage(page)

    with allure.step("Скроллим к табам истории и нажимаем «My history»"):
        tab = mp.my_history_tab()
        tab.wait_for(state="visible", timeout=10_000)
        tab.scroll_into_view_if_needed()
        tab.click()

    with allure.step("Ждём строку с типом «Deposit» в таблице истории"):
        mp.wait_for_history_row_with_text("Deposit")
        allure.attach(
            page.screenshot(),
            name="MY HISTORY tab with deposit row",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Строка с «Deposit» видна в таблице"):
        rows = mp.history_table_rows().filter(has_text="Deposit")
        assert rows.count() > 0, "Строка «Deposit» не найдена в таблице MY HISTORY"
