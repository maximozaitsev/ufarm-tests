"""Shared fixtures для TRX-тестов маркетплейса.

Все фикстуры scope="session" — страница и результаты транзакций создаются
один раз на всю сессию и переиспользуются в test_deposit_trx.py и test_withdraw_trx.py.

Порядок выполнения fixtures в сессии:
  1. gasless_deposit  — 1 USDT gasless (pending, relay)
  2. onchain_deposit  — 0.5 USDT on-chain (confirmed, LP-токены появляются)
  3. gasless_withdrawal — MAX LP-токенов gasless (pending, relay)

Каждая фикстура делает ONE операцию и сохраняет состояние.
Тесты проверяют аспекты независимо ("setup once, assert many").
"""

from dataclasses import dataclass
from decimal import Decimal

import allure
import pytest

from core.ui.helpers.mocks import mock_auth_connect
from core.ui.helpers.on_chain import USDT_ARB, get_erc20_balance
from core.ui.helpers.trx_provider import inject_trx_provider
from core.ui.pages.deposit_modal import DepositModal
from core.ui.pages.marketplace_page import MarketplacePage
from core.ui.pages.withdraw_modal import WithdrawModal


# ── Константы ─────────────────────────────────────────────────────────────────

GASLESS_DEPOSIT_AMOUNT = "1"    # 1 USDT gasless deposit (relay)
DEPOSIT_AMOUNT_ONCHAIN = "0.5"  # 0.5 USDT on-chain deposit (direct, with gas)
GASLESS_SIGNING_TIMEOUT_MS = 30_000

ARBISCAN_TX_URL = "https://arbiscan.io/tx/{tx_hash}"
ETHERSCAN_TX_URL = "https://etherscan.io/tx/{tx_hash}"


# ── Утилиты ───────────────────────────────────────────────────────────────────


def attach_tx_link(tx_hash: str, chain: str = "arbitrum") -> None:
    """Прикрепляет ссылку на транзакцию в блокчейн-эксплорере к Allure-отчёту.

    Вызывать в теле каждого теста с on-chain транзакцией.
    Ссылка видна в отчёте независимо от результата теста.

    Args:
        tx_hash: хэш транзакции (0x...)
        chain: "arbitrum" → Arbiscan, "ethereum" → Etherscan
    """
    if not tx_hash:
        return
    if chain == "ethereum":
        url = ETHERSCAN_TX_URL.format(tx_hash=tx_hash)
        name = f"Etherscan: {tx_hash[:10]}…"
    else:
        url = ARBISCAN_TX_URL.format(tx_hash=tx_hash)
        name = f"Arbiscan: {tx_hash[:10]}…"
    allure.dynamic.link(url, name=name)


def _read_my_requests_first_row(page) -> dict | None:
    """JS: читает первую строку таблицы «My requests».

    Колонки: Request date | Expiration date | Type | Pool tokens | Current value, $
    Возвращает dict с ключами: request_date, expiration_date, type, tokens, value.
    Пробелы нормализованы (replace /\\s+/ → ' ').
    """
    return page.evaluate("""() => {
        const panel = document.querySelector('[role="tabpanel"][aria-labelledby*="tab-requests"]');
        if (!panel) return null;
        const firstRow = panel.querySelector('tbody tr');
        if (!firstRow) return null;
        const cells = firstRow.querySelectorAll('td');
        const norm = el => el ? el.textContent.replace(/\\s+/g, ' ').trim() : '';
        return {
            request_date:    norm(cells[0]),
            expiration_date: norm(cells[1]),
            type:            norm(cells[2]),
            tokens:          norm(cells[3]),
            value:           norm(cells[4]),
        };
    }""")


# ── Dataclasses ────────────────────────────────────────────────────────────────


@dataclass
class GaslessDepositResult:
    """Состояние после gasless депозита (собирается фикстурой gasless_deposit).

    Фикстура делает ONE операцию и хранит скриншоты + данные здесь.
    Каждый тест сам решает что показать в Allure через step / attach.
    """
    request_submitted_appeared: bool   # UI показал модалку «Request submitted»
    pending_approval_appeared: bool    # страница пула показала «pending approval»
    screenshot_modal: bytes            # скриншот модалки «Request submitted»
    screenshot_pending: bytes          # скриншот страницы пула с pending approval
    screenshot_requests_tab: bytes     # скриншот таба «My requests»
    requests_row: dict                 # первая строка таблицы My Requests
    deposit_amount: str                # = GASLESS_DEPOSIT_AMOUNT ("1")


@dataclass
class OnchainDepositResult:
    """Состояние до и после on-chain депозита (собирается фикстурой onchain_deposit).

    Фикстура хранит скриншоты и данные здесь. Каждый тест сам решает
    что показать в своём body через allure.step / allure.attach.
    """
    tx_hash: str                        # хэш on-chain транзакции (для ссылки на Arbiscan)
    deposit_confirmed_modal_appeared: bool  # UI показал модалку «Deposit confirmed»
    screenshot_modal: bytes             # скриншот модалки «Deposit confirmed»
    screenshot_after: bytes             # скриншот страницы пула после обновления UI
    usdt_before: Decimal                # USDT on-chain до депозита
    tokens_before: float                # LP tokens в UI до депозита
    usdt_after: Decimal                 # USDT on-chain после депозита
    tokens_after: float                 # LP tokens в UI после депозита
    pool_usd_after: Decimal             # MY BALANCE USD в UI после депозита
    wallet_usd_after: Decimal           # MY WALLET USD в UI после депозита


@dataclass
class GaslessWithdrawalResult:
    """Состояние после gasless вывода (собирается фикстурой gasless_withdrawal).

    Фикстура делает ONE операцию (MAX LP-токенов) и хранит данные здесь.
    """
    request_submitted_appeared: bool   # UI показал модалку «Request submitted»
    screenshot_modal: bytes            # скриншот модалки «Request submitted»
    screenshot_requests_tab: bytes     # скриншот таба «My requests»
    requests_row: dict                 # первая строка таблицы My Requests (свежий вывод)
    withdrawal_amount: str             # LP-токены из MAX, нормализованные ("0.5")


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def trx_wallet_address(request) -> str:
    """Адрес кошелька для транзакционных тестов."""
    override = request.config.getoption("--wallet-trx-address", default=None)
    value = override or pytest.importorskip("config.settings").settings.wallet_trx_address
    if not value:
        pytest.skip("WALLET_TRX_ADDRESS not set")
    return value


@pytest.fixture(scope="session")
def trx_wallet_private_key(request) -> str:
    """Приватный ключ кошелька для транзакционных тестов."""
    override = request.config.getoption("--wallet-trx-private-key", default=None)
    value = override or pytest.importorskip("config.settings").settings.wallet_trx_private_key
    if not value:
        pytest.skip("WALLET_TRX_PRIVATE_KEY not set")
    return value


@pytest.fixture(scope="session")
def page_with_trx_wallet(
    browser, base_url, test_pool_id, trx_wallet_address, trx_wallet_private_key
):
    """Страница пула с реальным Ethereum-провайдером (подписывает транзакции).

    scope="session" — страница создаётся один раз и переиспользуется
    в test_deposit_trx.py и test_withdraw_trx.py.

    Два слоя инжекции:
    1. inject_trx_provider (ДО goto) — устанавливает window.ethereum с реальным сайнером,
       чтобы wagmi подхватил провайдер при инициализации.
    2. inject_wallet (ПОСЛЕ goto) — устанавливает wagmi store state в "connected",
       чтобы UI показал адрес кошелька и кнопку Deposit.
    """
    from core.ui.helpers.wallet_injection import inject_wallet

    context = browser.new_context()
    page = context.new_page()
    mock_auth_connect(page)

    inject_trx_provider(page, private_key=trx_wallet_private_key)
    page.goto(f"{base_url}/marketplace/pool/{test_pool_id}", wait_until="networkidle")
    inject_wallet(page, trx_wallet_address)
    page.wait_for_load_state("networkidle", timeout=15_000)

    yield page
    context.close()


@pytest.fixture(scope="session")
def gasless_deposit(page_with_trx_wallet) -> GaslessDepositResult:
    """Выполняет gasless депозит GASLESS_DEPOSIT_AMOUNT USDT и возвращает состояние.

    scope="session" — операция выполняется ОДИН РАЗ.
    Relay принимает подписи (2x EIP-712) и создаёт pending запись.
    LP-баланс НЕ растёт до одобрения управляющим фонда.

    Запускается до onchain_deposit и gasless_withdrawal:
    тест-файлы выполняются в алфавитном порядке (deposit → withdraw),
    а pytest инициализирует session-фикстуры при первом обращении.
    """
    page = page_with_trx_wallet
    mp = MarketplacePage(page)
    modal = DepositModal(page)

    with allure.step(f"Открываем модалку Deposit (gasless {GASLESS_DEPOSIT_AMOUNT} USDT)"):
        page.locator(".mantine-Modal-overlay").wait_for(state="hidden", timeout=5_000)
        mp.deposit_button().click()
        modal.wait_for()

    with allure.step(f"Вводим {GASLESS_DEPOSIT_AMOUNT} USDT, отправляем gasless request"):
        modal.amount_input().fill(GASLESS_DEPOSIT_AMOUNT)
        modal.submit_button().click()

    with allure.step("Ждём модалку «Request submitted» (relay принял EIP-712 подписи)"):
        request_submitted_appeared = False
        try:
            page.get_by_text("Request submitted").wait_for(timeout=GASLESS_SIGNING_TIMEOUT_MS)
            request_submitted_appeared = True
        except Exception:
            pass
        screenshot_modal = page.screenshot()

    with allure.step("Закрываем модалку, проверяем «pending approval» на странице пула"):
        pending_approval_appeared = False
        try:
            page.get_by_role("button", name="CLOSE").click()
            page.get_by_text("Your deposit request is pending approval").wait_for(timeout=5_000)
            pending_approval_appeared = True
        except Exception:
            pass
        screenshot_pending = page.screenshot()

    with allure.step("Переходим на таб «My requests», читаем первую строку"):
        tab = mp.my_requests_tab()
        tab.scroll_into_view_if_needed()
        tab.click()
        first_row_locator = page.locator(
            '[role="tabpanel"][aria-labelledby*="tab-requests"] tbody tr'
        ).first
        first_row_locator.wait_for(state="visible", timeout=10_000)
        first_row_locator.scroll_into_view_if_needed()
        requests_row = _read_my_requests_first_row(page) or {}
        screenshot_requests_tab = page.screenshot()

    return GaslessDepositResult(
        request_submitted_appeared=request_submitted_appeared,
        pending_approval_appeared=pending_approval_appeared,
        screenshot_modal=screenshot_modal,
        screenshot_pending=screenshot_pending,
        screenshot_requests_tab=screenshot_requests_tab,
        requests_row=requests_row,
        deposit_amount=GASLESS_DEPOSIT_AMOUNT,
    )


@pytest.fixture(scope="session")
def onchain_deposit(page_with_trx_wallet, trx_wallet_address) -> OnchainDepositResult:
    """Выполняет on-chain депозит 0.5 USDT и возвращает состояние до/после.

    scope="session" — транзакция выполняется ОДИН РАЗ на всю сессию.
    Зависимые тесты из разных файлов (deposit, withdraw) получают один объект.

    Если фикстура упадёт (tx не прошла) — все зависимые тесты → ERROR.
    """
    page = page_with_trx_wallet
    mp = MarketplacePage(page)
    modal = DepositModal(page)

    with allure.step("Фиксируем состояние до депозита"):
        usdt_before = get_erc20_balance(trx_wallet_address, USDT_ARB)
        tokens_before = mp.get_pool_balance_tokens()

    with allure.step("Открываем модалку Deposit, отключаем gasless"):
        page.locator(".mantine-Modal-overlay").wait_for(state="hidden", timeout=5_000)
        mp.deposit_button().click()
        modal.wait_for()
        modal.gasless_toggle().evaluate("el => el.click()")
        assert not modal.gasless_toggle().is_checked(), "Gasless toggle должен быть выключен"

    with allure.step(f"Вводим {DEPOSIT_AMOUNT_ONCHAIN} USDT и отправляем"):
        modal.amount_input().fill(DEPOSIT_AMOUNT_ONCHAIN)
        modal.submit_button().click()
        page.wait_for_function("() => !!window.__last_tx_hash", timeout=30_000)
        tx_hash = page.evaluate("window.__last_tx_hash") or ""

    with allure.step("Ждём модалку «Deposit confirmed» (tx подтверждена on-chain)"):
        page.get_by_text("Deposit confirmed").wait_for(timeout=60_000)
        deposit_confirmed = page.get_by_text("Deposit confirmed").is_visible()
        screenshot_modal = page.screenshot()

    with allure.step("Закрываем модалку, ждём обновления UI"):
        page.get_by_role("button", name="CLOSE").click()
        mp.wait_for_pool_tokens_above(tokens_before)

    with allure.step("Читаем состояние после депозита"):
        usdt_after = get_erc20_balance(trx_wallet_address, USDT_ARB)
        tokens_after = mp.get_pool_balance_tokens()
        pool_usd_after = mp.get_pool_balance_usd()
        wallet_usd_after = mp.get_wallet_balance_usd()
        screenshot_after = page.screenshot()

    return OnchainDepositResult(
        tx_hash=tx_hash,
        deposit_confirmed_modal_appeared=deposit_confirmed,
        screenshot_modal=screenshot_modal,
        screenshot_after=screenshot_after,
        usdt_before=usdt_before,
        tokens_before=tokens_before,
        usdt_after=usdt_after,
        tokens_after=tokens_after,
        pool_usd_after=pool_usd_after,
        wallet_usd_after=wallet_usd_after,
    )


@pytest.fixture(scope="session")
def gasless_withdrawal(page_with_trx_wallet, onchain_deposit) -> GaslessWithdrawalResult:
    """Выполняет gasless вывод всех LP-токенов (MAX) и возвращает состояние.

    Зависит от onchain_deposit — гарантирует наличие LP-токенов для вывода.
    scope="session" — операция выполняется ОДИН РАЗ.
    Relay принимает EIP-712 подпись и создаёт pending запись.
    LP-баланс и USDT возвращаются только после одобрения управляющим фонда.
    """
    page = page_with_trx_wallet
    mp = MarketplacePage(page)
    modal = WithdrawModal(page)

    with allure.step("Ожидаем кнопку Withdraw (LP-токены доступны после on-chain депозита)"):
        mp.wait_for_withdraw_button()
        page.locator(".mantine-Modal-overlay").wait_for(state="hidden", timeout=5_000)

    with allure.step("Открываем модалку Withdraw, выбираем MAX"):
        mp.withdraw_button().click()
        modal.wait_for()
        modal.max_button().click()
        raw_amount = modal.pool_token_input().input_value()
        withdrawal_amount = raw_amount.replace(",", ".").strip()
        allure.attach(
            page.screenshot(),
            name="Withdraw modal with MAX",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step(f"Отправляем gasless withdrawal ({withdrawal_amount} LP-токенов)"):
        modal.request_withdrawal_button().click()

    with allure.step("Ждём модалку «Request submitted» (relay принял EIP-712 подпись)"):
        request_submitted_appeared = False
        try:
            page.get_by_text("Request submitted").wait_for(timeout=GASLESS_SIGNING_TIMEOUT_MS)
            request_submitted_appeared = True
        except Exception:
            pass
        screenshot_modal = page.screenshot()

    with allure.step("Закрываем модалку"):
        page.get_by_role("button", name="CLOSE").click()

    with allure.step("Переходим на таб «My requests», читаем первую строку (свежий вывод)"):
        tab = mp.my_requests_tab()
        tab.scroll_into_view_if_needed()
        tab.click()
        first_row_locator = page.locator(
            '[role="tabpanel"][aria-labelledby*="tab-requests"] tbody tr'
        ).first
        first_row_locator.wait_for(state="visible", timeout=10_000)
        first_row_locator.scroll_into_view_if_needed()
        requests_row = _read_my_requests_first_row(page) or {}
        screenshot_requests_tab = page.screenshot()

    return GaslessWithdrawalResult(
        request_submitted_appeared=request_submitted_appeared,
        screenshot_modal=screenshot_modal,
        screenshot_requests_tab=screenshot_requests_tab,
        requests_row=requests_row,
        withdrawal_amount=withdrawal_amount,
    )
