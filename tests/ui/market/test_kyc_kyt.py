"""UI-тесты Compliance: KYT (Strict, minClientTier=10) и No KYT (minClientTier=0).

Подход — мокирование POST /user/verification (tier в ответе):
  - tier=10 >= minClientTier=10  → DEPOSIT форма (KYT пройден)
  - tier<10  < minClientTier=10  → KYT-блокировка
  - tier=0   >= minClientTier=0  → DEPOSIT форма (No KYT пул, любой кошелёк)

Terms предотвращаются через _mock_auth_connect() из conftest.
Для KYT-блокировки verification переопределяется поверх (Playwright LIFO).

Пулы:
  Pool A (POOL_SINGLE_TOKEN_ID) — minClientTier=10 (Strict KYT)
  Pool B (TEST_POOL_ID)         — minClientTier=0  (No KYT)

KYC-тесты (minClientTier=20) — TODO: требуют мока wallet signing.
"""
import json
import random

import allure
import pytest

from core.ui.pages.marketplace_page import MarketplacePage
from core.ui.pages.deposit_modal import DepositModal
from core.ui.pages.kyt_modal import KytBlockModal


pytestmark = [pytest.mark.ui, pytest.mark.smoke]


def _override_verification_tier(page, tier: int) -> None:
    """Переопределяет мок POST /user/verification, возвращая указанный tier.

    Регистрируется ПОСЛЕ _mock_auth_connect() — Playwright вызывает handlers
    в порядке LIFO, поэтому этот handler будет вызван первым.
    """
    def _handler(route, _request):
        route.fulfill(
            status=201,
            content_type="application/json",
            body=json.dumps({
                "signature": "0x0",
                "tier": tier,
                "validTill": 9999999999,
            }),
        )
    page.route("**/user/verification**", _handler)


# ══════════════════════════════════════════════════════════════════════════════
# KYT — Pool A (minClientTier=10)
# ══════════════════════════════════════════════════════════════════════════════

@allure.epic("Market")
@allure.feature("UI")
@allure.story("Compliance")
@allure.title("KYT passed: deposit form opens when wallet tier meets pool requirement")
@allure.severity(allure.severity_level.CRITICAL)
def test_kyt_passed_shows_deposit_form(page_with_wallet_on_single_token_pool):
    """tier=10 (дефолтный мок) >= minClientTier=10 → открывается DEPOSIT форма."""
    page = page_with_wallet_on_single_token_pool
    mp = MarketplacePage(page)
    modal = DepositModal(page)

    with allure.step("Кликаем Deposit (verification возвращает tier=10)"):
        mp.wait_for_pool_page()
        mp.deposit_button().click()
        modal.wait_for()

    with allure.step("Открылась форма DEPOSIT (не блокировка KYT)"):
        page.get_by_role("heading", name="DEPOSIT").wait_for(
            state="visible", timeout=15_000
        )
        assert page.get_by_role("heading", name="DEPOSIT").is_visible()

    with allure.step("Скриншот: DEPOSIT форма при пройденном KYT"):
        allure.attach(
            page.screenshot(),
            name="KYT passed — deposit form",
            attachment_type=allure.attachment_type.PNG,
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Compliance")
@allure.title("KYT blocked: wallet with insufficient tier cannot open deposit form")
@allure.severity(allure.severity_level.CRITICAL)
def test_kyt_blocked_shows_modal(page_with_wallet_on_single_token_pool):
    """tier ∈ {0, 5} < minClientTier=10 → модалка 'Wallet verification issue' с кнопкой Close.

    Tier выбирается случайно из допустимых значений ниже порога пула.
    """
    page = page_with_wallet_on_single_token_pool
    mp = MarketplacePage(page)
    modal = KytBlockModal(page)

    blocked_tier = random.choice([0, 5])

    with allure.step(f"Переопределяем verification: tier={blocked_tier} (ниже требования пула tier=10)"):
        _override_verification_tier(page, tier=blocked_tier)

    with allure.step("Кликаем Deposit"):
        mp.wait_for_pool_page()
        mp.deposit_button().click()

    with allure.step("Открылась модалка 'Wallet verification issue'"):
        modal.wait_opened(timeout=10_000)
        assert modal.heading().is_visible()

    with allure.step("Присутствует кнопка Close"):
        assert modal.close_button().is_visible()

    with allure.step("DEPOSIT форма не открылась"):
        assert not page.get_by_role("heading", name="DEPOSIT").is_visible()

    with allure.step("Скриншот KYT-блокировки"):
        allure.attach(
            page.screenshot(),
            name=f"KYT blocked (tier={blocked_tier}) — Wallet verification issue",
            attachment_type=allure.attachment_type.PNG,
        )


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Compliance")
@allure.title("KYT blocked: Close button dismisses the modal")
@allure.severity(allure.severity_level.NORMAL)
def test_kyt_blocked_close_button_dismisses_modal(page_with_wallet_on_single_token_pool):
    """Кнопка Close закрывает модалку блокировки, страница пула остаётся."""
    page = page_with_wallet_on_single_token_pool
    mp = MarketplacePage(page)
    modal = KytBlockModal(page)

    with allure.step("Переопределяем verification: tier=5"):
        _override_verification_tier(page, tier=5)

    with allure.step("Кликаем Deposit → появляется блокировочная модалка"):
        mp.wait_for_pool_page()
        mp.deposit_button().click()
        modal.wait_opened(timeout=10_000)

    with allure.step("Нажимаем Close"):
        modal.close_button().click()

    with allure.step("Модалка закрылась"):
        modal.heading().wait_for(state="hidden", timeout=5_000)
        assert not modal.heading().is_visible()

    with allure.step("Страница пула по-прежнему отображается"):
        mp.wait_for_pool_page()


@allure.epic("Market")
@allure.feature("UI")
@allure.story("Compliance")
@allure.title("KYT blocked: re-clicking Deposit shows block modal again")
@allure.severity(allure.severity_level.NORMAL)
def test_kyt_blocked_retry_same_result(page_with_wallet_on_single_token_pool):
    """После закрытия блокировки повторный клик Deposit снова показывает блокировку."""
    page = page_with_wallet_on_single_token_pool
    mp = MarketplacePage(page)
    modal = KytBlockModal(page)

    with allure.step("Переопределяем verification: tier=5"):
        _override_verification_tier(page, tier=5)

    with allure.step("Первый клик Deposit → блокировка"):
        mp.wait_for_pool_page()
        mp.deposit_button().click()
        modal.wait_opened(timeout=10_000)

    with allure.step("Закрываем модалку"):
        modal.close_button().click()
        modal.heading().wait_for(state="hidden", timeout=5_000)

    with allure.step("Повторный клик Deposit → снова блокировка"):
        mp.deposit_button().click()
        modal.wait_opened(timeout=10_000)
        assert modal.heading().is_visible()

    with allure.step("Скриншот повторной блокировки"):
        allure.attach(
            page.screenshot(),
            name="KYT blocked retry",
            attachment_type=allure.attachment_type.PNG,
        )


# ══════════════════════════════════════════════════════════════════════════════
# No KYT — Pool B (minClientTier=0)
# ══════════════════════════════════════════════════════════════════════════════

@allure.epic("Market")
@allure.feature("UI")
@allure.story("Compliance")
@allure.title("No KYT pool: deposit form opens for wallet with any tier")
@allure.severity(allure.severity_level.CRITICAL)
def test_no_kyt_pool_allows_low_tier(page_with_wallet_on_pool):
    """Pool B (minClientTier=0): verification возвращает tier=0 → DEPOSIT форма.

    Проверяет что пул без KYT требований не блокирует ни один кошелёк.
    """
    page = page_with_wallet_on_pool
    mp = MarketplacePage(page)
    modal = DepositModal(page)

    with allure.step("Переопределяем verification: tier=0 (минимально возможный)"):
        _override_verification_tier(page, tier=0)

    with allure.step("Кликаем Deposit"):
        mp.wait_for_pool_page()
        mp.deposit_button().click()
        modal.wait_for()

    with allure.step("Открылась форма DEPOSIT (No KYT пул не блокирует)"):
        page.get_by_role("heading", name="DEPOSIT").wait_for(
            state="visible", timeout=15_000
        )
        assert page.get_by_role("heading", name="DEPOSIT").is_visible()

    with allure.step("Скриншот: DEPOSIT форма на No KYT пуле при tier=0"):
        allure.attach(
            page.screenshot(),
            name="No KYT pool — deposit form (tier=0)",
            attachment_type=allure.attachment_type.PNG,
        )
