"""Транзакционные UI-тесты: Withdraw.

Кошелёк: WALLET_TRX_ADDRESS / WALLET_TRX_PRIVATE_KEY
Пул:     TEST_POOL_ID (REF TEST, minClientTier=0, deposit_min=0, withdraw_delay=1s)

Тесты выполняют реальные on-chain операции на Arbitrum Mainnet.

Withdraw только gasless: пользователь подписывает EIP-712, relay отправляет транзакцию.
Кошелёк не тратит ETH на газ. USDT возвращается только после одобрения управляющего.

Паттерн "setup once, assert many":
  Фикстура gasless_withdrawal (scope=session) выполняет ONE операцию (MAX LP-токенов)
  и собирает состояние. Каждый тест проверяет один аспект независимо.
  Фикстура зависит от onchain_deposit — гарантирует наличие LP-токенов перед выводом.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import allure
import pytest

from .conftest import GaslessWithdrawalResult, OnchainDepositResult, attach_tx_link


pytestmark = [pytest.mark.trx, pytest.mark.smoke]


# ── Gasless withdrawal: setup once, assert many ───────────────────────────────
# Фикстура gasless_withdrawal (scope=session) выполняет ONE gasless вывод MAX LP-токенов.
# Каждый тест ниже проверяет один аспект независимо.


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Withdraw")
@allure.title("Gasless withdrawal: relay accepts request, UI shows «Request submitted» modal")
@allure.severity(allure.severity_level.CRITICAL)
def test_gasless_withdrawal_request_submitted(
    gasless_withdrawal: GaslessWithdrawalResult,
    onchain_deposit: OnchainDepositResult,
):
    """Relay принял gasless withdrawal: UI показал модалку «Request submitted»."""
    attach_tx_link(onchain_deposit.tx_hash)
    with allure.step("Модалка «Request submitted» появилась"):
        allure.attach(
            gasless_withdrawal.screenshot_modal,
            name="Request submitted modal",
            attachment_type=allure.attachment_type.PNG,
        )
        assert gasless_withdrawal.request_submitted_appeared, (
            "Модалка «Request submitted» не появилась — relay не принял запрос"
        )


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Withdraw")
@allure.title("Gasless withdrawal: MY REQUESTS shows entry with type «Withdrawal»")
@allure.severity(allure.severity_level.NORMAL)
def test_gasless_withdrawal_my_requests_type(gasless_withdrawal: GaslessWithdrawalResult):
    """MY REQUESTS содержит запись с типом «Withdrawal»."""
    row = gasless_withdrawal.requests_row
    with allure.step(f"Тип первой записи: ожидается «Withdrawal», получено «{row.get('type')}»"):
        allure.attach(
            gasless_withdrawal.screenshot_requests_tab,
            name="MY REQUESTS tab",
            attachment_type=allure.attachment_type.PNG,
        )
        assert row.get("type") == "Withdrawal", (
            f"Ожидается type=Withdrawal, got {row.get('type')!r}"
        )


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Withdraw")
@allure.title("Gasless withdrawal: MY REQUESTS entry has today's date")
@allure.severity(allure.severity_level.NORMAL)
def test_gasless_withdrawal_my_requests_date(gasless_withdrawal: GaslessWithdrawalResult):
    """MY REQUESTS: request_date содержит сегодняшнюю дату."""
    row = gasless_withdrawal.requests_row
    today = datetime.now(timezone.utc)
    expected = today.strftime("%b") + " " + str(today.day)
    with allure.step(f"Request date содержит «{expected}»: получено «{row.get('request_date')}»"):
        assert expected in (row.get("request_date") or ""), (
            f"Request date «{row.get('request_date')}» не содержит «{expected}»"
        )


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Withdraw")
@allure.title("Gasless withdrawal: MY REQUESTS expiration date is tomorrow")
@allure.severity(allure.severity_level.NORMAL)
def test_gasless_withdrawal_my_requests_expiration(gasless_withdrawal: GaslessWithdrawalResult):
    """MY REQUESTS: relay выдаёт разрешение на 24 часа — expiration_date завтра."""
    row = gasless_withdrawal.requests_row
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    expected = tomorrow.strftime("%b") + " " + str(tomorrow.day)
    with allure.step(f"Expiration date содержит «{expected}»: получено «{row.get('expiration_date')}»"):
        assert expected in (row.get("expiration_date") or ""), (
            f"Expiration date «{row.get('expiration_date')}» не содержит «{expected}» "
            f"(ожидается +1 день от сегодня)"
        )


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Withdraw")
@allure.title("Gasless withdrawal: MY REQUESTS pool tokens match withdrawal amount")
@allure.severity(allure.severity_level.NORMAL)
def test_gasless_withdrawal_my_requests_tokens(gasless_withdrawal: GaslessWithdrawalResult):
    """MY REQUESTS: Pool tokens соответствует запрошенному объёму вывода (MAX).

    withdrawal_amount считывается из modal pool_token_input перед submit.
    Допустимое отклонение ±0.01 LP: UI округляет до 2 знаков.
    """
    row = gasless_withdrawal.requests_row
    raw_tokens = row.get("tokens") or ""
    with allure.step(
        f"Pool tokens ≈ {gasless_withdrawal.withdrawal_amount}: получено «{raw_tokens}»"
    ):
        # Токены могут быть "0,5 UF-REF" — берём только число
        tokens_num_str = raw_tokens.replace(",", ".").split()[0] if raw_tokens else "0"
        tokens_num = Decimal(tokens_num_str)
        expected = Decimal(gasless_withdrawal.withdrawal_amount) if gasless_withdrawal.withdrawal_amount else Decimal("0")
        tolerance = Decimal("0.01")
        assert abs(tokens_num - expected) <= tolerance, (
            f"Pool tokens {tokens_num} не совпадает с withdrawal_amount {expected} "
            f"(допуск ±{tolerance})"
        )


@allure.epic("Market")
@allure.feature("Transaction")
@allure.story("Withdraw")
@allure.title("Gasless withdrawal: entry appears in API cashflow with requestHash set")
@allure.severity(allure.severity_level.CRITICAL)
def test_gasless_withdrawal_appears_in_api_cashflow(
    gasless_withdrawal: GaslessWithdrawalResult,
    api_client,
    test_pool_id,
    trx_wallet_address,
):
    """Gasless withdrawal зафиксирован в API cashflow: requestHash заполнен, адреса верны.

    Ключевое отличие gasless от on-chain:
      - requestHash ≠ null (запрос прошёл через relay)
      - on-chain депозиты имеют requestHash=null (транзакция напрямую в блокчейн)

    Статус (Pending/Completed) зависит от withdraw_delay пула:
      - TEST_POOL_ID имеет withdraw_delay=1s → вывод автоодобряется мгновенно
      - В продакшн-пулах статус будет Pending до решения управляющего

    Идентифицируем запись как самую свежую в списке (сортировка по убыванию даты).
    """
    with allure.step(f"Получаем on-chain адрес пула для pool_id={test_pool_id}"):
        pool_resp = api_client.get(f"/pool/{test_pool_id}")
        assert pool_resp.status_code == 200, f"GET /pool/{test_pool_id} вернул {pool_resp.status_code}"
        pool_address = pool_resp.json()["pool"]["poolAddress"]

    with allure.step("Получаем последние Withdrawal-записи из cashflow (page 1)"):
        from core.api.models.cashflow import CashflowResponse

        cf_resp = api_client.get(
            f"/pool/{pool_address}/transactions/cashflows",
            params={
                "investorAddress": trx_wallet_address,
                "type": "Withdrawal",
                "limit": 5,
                "page": 1,
            },
        )
        assert cf_resp.status_code == 200, f"GET cashflows вернул {cf_resp.status_code}"
        body = cf_resp.json()
        allure.attach(
            str(body),
            name="Cashflow API response (Withdrawal)",
            attachment_type=allure.attachment_type.TEXT,
        )
        cf = CashflowResponse(**body)
        assert cf.data, "Cashflow вернул пустой список — ни одного Withdrawal не найдено"

    latest = cf.data[0]
    with allure.step(f"Последняя запись: type={latest.type}, status={latest.status}, date={latest.date}"):
        assert latest.type == "Withdrawal", f"Ожидается type=Withdrawal, got {latest.type}"
        assert latest.status in ("Pending", "Completed"), (
            f"Неожиданный status: {latest.status!r} (ожидается Pending или Completed)"
        )

    with allure.step(f"requestHash заполнен (gasless проходит через relay): {latest.requestHash!r}"):
        assert latest.requestHash is not None, (
            "requestHash=null для gasless withdrawal — запрос не зарегистрирован relay"
        )

    with allure.step(f"poolAddress совпадает: {latest.poolAddress}"):
        assert latest.poolAddress.lower() == pool_address.lower(), (
            f"Ожидается poolAddress={pool_address}, got {latest.poolAddress}"
        )

    with allure.step(f"investorAddress совпадает: {latest.investorAddress}"):
        assert latest.investorAddress.lower() == trx_wallet_address.lower(), (
            f"Ожидается investorAddress={trx_wallet_address}, got {latest.investorAddress}"
        )

    with allure.step(f"Дата записи совпадает с датой из MY REQUESTS tab: {latest.date}"):
        # Сравниваем с датой из MY REQUESTS tab (зафиксирована в момент выполнения fixture).
        # Прямое сравнение с текущим временем ненадёжно: session fixture запускается
        # при первом обращении, а этот тест может выполниться через десятки минут.
        requests_date = gasless_withdrawal.requests_row.get("request_date") or ""
        entry_dt = datetime.fromisoformat(latest.date.replace("Z", "+00:00"))
        api_date_str = entry_dt.strftime("%b") + " " + str(entry_dt.day)  # e.g. "Mar 28"
        assert api_date_str in requests_date or requests_date in api_date_str, (
            f"Дата в API «{api_date_str}» не совпадает с датой в MY REQUESTS «{requests_date}»"
        )
