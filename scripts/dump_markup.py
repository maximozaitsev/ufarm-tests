"""
Дамп разметки страниц маркетплейса для изучения селекторов.
Запуск: python scripts/dump_markup.py

Дампит страницы как без кошелька, так и с инжектированным кошельком.
Результат сохраняется в scripts/markup/.
"""
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from playwright.sync_api import sync_playwright

from core.ui.helpers.wallet_injection import inject_wallet

BASE_URL = os.environ.get("BASE_URL", "https://app.demo.ufarm.digital")

# Существующие
TEST_POOL_ID = os.environ.get("TEST_POOL_ID", "f1b36414-7275-497f-abcb-6f19cb9566f4")
TEST_WALLET_ADDRESS = os.environ.get("TEST_WALLET_ADDRESS", "0xd2692CCEbC8d34EFd74185908956e5f75FF71cA3")

# Новые
POOL_SINGLE_TOKEN_ID = os.environ.get("POOL_SINGLE_TOKEN_ID", "6ad86620-2fa9-4c18-a1fd-20ab8cc0edaa")
POOL_MULTI_TOKEN_ID = os.environ.get("POOL_MULTI_TOKEN_ID", TEST_POOL_ID)
POOL_MIN_DEPOSIT_ID = os.environ.get("POOL_MIN_DEPOSIT_ID", "b25eb748-6fa5-4966-8ae0-dfd4666b02dc")

WALLET_WITH_BALANCE = os.environ.get("WALLET_WITH_BALANCE", TEST_WALLET_ADDRESS)
WALLET_ZERO_BALANCE = os.environ.get("WALLET_ZERO_BALANCE", "0x3078b1370F6e154AaF632b4f48D7548Ea83A3A52")

OUT_DIR = pathlib.Path("scripts/markup")
OUT_DIR.mkdir(exist_ok=True)


def save(page, name: str):
    page.screenshot(path=str(OUT_DIR / f"{name}.png"), full_page=False)
    (OUT_DIR / f"{name}.html").write_text(page.content(), encoding="utf-8")
    print(f"  Saved {name}.html and .png")


def open_pool_with_wallet(page, pool_id: str, wallet: str):
    """Открывает страницу пула с инжектированным кошельком."""
    page.goto(f"{BASE_URL}/marketplace/pool/{pool_id}", wait_until="networkidle")
    inject_wallet(page, wallet)
    page.wait_for_load_state("networkidle", timeout=15_000)
    page.get_by_role("heading", level=1).wait_for(timeout=15_000)


def dump_deposit_modal(page, name: str):
    """Кликает Deposit и дампит открытую модалку."""
    deposit_btn = page.get_by_text("Deposit", exact=True).first
    if not deposit_btn.is_visible():
        print(f"  ⚠ Deposit button not visible for {name}")
        return
    deposit_btn.click()
    try:
        page.locator(".mantine-Modal-content").wait_for(state="visible", timeout=10_000)
        save(page, name)
    except Exception as e:
        print(f"  ⚠ Deposit modal did not appear for {name}: {e}")
        save(page, f"{name}_failed")
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)


def dump_fund_wallet_modal(page, name: str):
    """Кликает Deposit у пула с min deposit > баланс кошелька → Fund wallet модалка."""
    deposit_btn = page.get_by_text("Deposit", exact=True).first
    if not deposit_btn.is_visible():
        print(f"  ⚠ Deposit button not visible for {name}")
        return
    deposit_btn.click()
    try:
        page.locator(".mantine-Modal-content").wait_for(state="visible", timeout=10_000)
        save(page, name)
    except Exception as e:
        print(f"  ⚠ Fund wallet modal did not appear for {name}: {e}")
        save(page, f"{name}_failed")
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)


def dump_withdraw_modal(page, name: str):
    """Кликает Withdraw и дампит модалку вывода."""
    withdraw_btn = page.get_by_role("button", name="Withdraw")
    try:
        withdraw_btn.wait_for(state="visible", timeout=15_000)
    except Exception:
        print(f"  ⚠ Withdraw button not visible for {name}")
        return
    withdraw_btn.click()
    try:
        page.get_by_text("Request Withdrawal").wait_for(state="visible", timeout=5_000)
        save(page, name)
    except Exception as e:
        print(f"  ⚠ Withdraw modal did not appear for {name}: {e}")
        save(page, f"{name}_failed")
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()

    # ── Без кошелька ────────────────────────────────────────────────────────
    print("\n=== Без кошелька ===")
    page.goto(f"{BASE_URL}/marketplace", wait_until="domcontentloaded")
    page.wait_for_selector(".mantine-Paper-root:has(h2)", timeout=20_000)
    save(page, "marketplace")

    page.goto(f"{BASE_URL}/marketplace/my-portfolio", wait_until="networkidle")
    save(page, "my_portfolio_no_wallet")

    page.goto(f"{BASE_URL}/marketplace/pool/{TEST_POOL_ID}", wait_until="networkidle")
    save(page, "pool_page_no_wallet")

    # ── Pool A (single token) + Wallet with balance ──────────────────────────
    print(f"\n=== Pool A (single token) {POOL_SINGLE_TOKEN_ID[:8]}... + Wallet with balance ===")
    open_pool_with_wallet(page, POOL_SINGLE_TOKEN_ID, WALLET_WITH_BALANCE)
    save(page, "pool_a_single_token_with_wallet")

    dump_deposit_modal(page, "pool_a_deposit_modal")

    # повторно открываем (Escape закрыл), снова открываем страницу
    open_pool_with_wallet(page, POOL_SINGLE_TOKEN_ID, WALLET_WITH_BALANCE)
    dump_withdraw_modal(page, "pool_a_withdraw_modal")

    # ── Pool B (multi token) + Wallet with balance ───────────────────────────
    print(f"\n=== Pool B (multi token) {POOL_MULTI_TOKEN_ID[:8]}... + Wallet with balance ===")
    open_pool_with_wallet(page, POOL_MULTI_TOKEN_ID, WALLET_WITH_BALANCE)
    save(page, "pool_b_multi_token_with_wallet")

    dump_deposit_modal(page, "pool_b_deposit_modal")

    open_pool_with_wallet(page, POOL_MULTI_TOKEN_ID, WALLET_WITH_BALANCE)
    dump_withdraw_modal(page, "pool_b_withdraw_modal")

    # ── Pool C (min deposit 5000) + Wallet zero balance ──────────────────────
    print(f"\n=== Pool C (min deposit) {POOL_MIN_DEPOSIT_ID[:8]}... + Wallet zero balance ===")
    open_pool_with_wallet(page, POOL_MIN_DEPOSIT_ID, WALLET_ZERO_BALANCE)
    save(page, "pool_c_min_deposit_with_zero_wallet")

    dump_fund_wallet_modal(page, "pool_c_fund_wallet_modal")

    # Pool C + Wallet with balance (на случай если баланс > 5000 — увидим обычную модалку)
    print(f"\n=== Pool C (min deposit) + Wallet with balance ===")
    open_pool_with_wallet(page, POOL_MIN_DEPOSIT_ID, WALLET_WITH_BALANCE)
    save(page, "pool_c_with_balance_wallet")
    dump_deposit_modal(page, "pool_c_deposit_modal_with_balance")

    # ── Маркетплейс с кошельком ──────────────────────────────────────────────
    print("\n=== Маркетплейс с кошельком ===")
    page.goto(f"{BASE_URL}/marketplace", wait_until="networkidle")
    inject_wallet(page, WALLET_WITH_BALANCE)
    page.wait_for_selector(".mantine-Paper-root:has(h2)", timeout=15_000)
    save(page, "marketplace_with_wallet")

    browser.close()

print(f"\nДамп сохранён в {OUT_DIR.resolve()}")
