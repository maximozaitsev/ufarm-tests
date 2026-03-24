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

from core.ui.wallet_injection import inject_wallet

BASE_URL = os.environ.get("BASE_URL", "https://app.demo.ufarm.digital")
TEST_POOL_ID = os.environ.get("TEST_POOL_ID", "")
TEST_WALLET_ADDRESS = os.environ.get("TEST_WALLET_ADDRESS", "")

OUT_DIR = pathlib.Path("scripts/markup")
OUT_DIR.mkdir(exist_ok=True)


def dump_page(page, url: str, name: str, wait_selector: str = None):
    print(f"Opening {url} ...")
    page.goto(url, wait_until="domcontentloaded")
    if wait_selector:
        print(f"  Waiting for: {wait_selector}")
        page.wait_for_selector(wait_selector, timeout=20_000)
    else:
        page.wait_for_load_state("networkidle", timeout=20_000)

    page.screenshot(path=str(OUT_DIR / f"{name}.png"), full_page=False)
    (OUT_DIR / f"{name}.html").write_text(page.content(), encoding="utf-8")
    print(f"  Saved {name}.html and {name}.png")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()

    # ── Без кошелька ────────────────────────────────────────────────────────
    dump_page(page, f"{BASE_URL}/marketplace", "marketplace",
              wait_selector=".mantine-Paper-root:has(h2)")
    dump_page(page, f"{BASE_URL}/marketplace/my-portfolio", "my_portfolio_no_wallet")

    # Страница пула без кошелька (по TEST_POOL_ID или первой карточке)
    if TEST_POOL_ID:
        pool_url = f"{BASE_URL}/marketplace/pool/{TEST_POOL_ID}"
        dump_page(page, pool_url, "pool_page_no_wallet")

    # ── С инжектированным кошельком ─────────────────────────────────────────
    if not TEST_WALLET_ADDRESS:
        print("\n⚠ TEST_WALLET_ADDRESS не задан — пропускаем дамп с кошельком.")
        print("  Задайте переменную: TEST_WALLET_ADDRESS=0x... python scripts/dump_markup.py")
    else:
        print(f"\nИнжектируем кошелёк: {TEST_WALLET_ADDRESS[:10]}...")

        # Маркетплейс с кошельком
        page.goto(f"{BASE_URL}/marketplace", wait_until="networkidle")
        inject_wallet(page, TEST_WALLET_ADDRESS)
        page.wait_for_selector(".mantine-Paper-root:has(h2)", timeout=15_000)
        page.screenshot(path=str(OUT_DIR / "marketplace_with_wallet.png"), full_page=False)
        (OUT_DIR / "marketplace_with_wallet.html").write_text(page.content(), encoding="utf-8")
        print("  Saved marketplace_with_wallet.html and .png")

        # My portfolio с кошельком — инжектируем ПОСЛЕ goto (full reload сбрасывает состояние)
        page.goto(f"{BASE_URL}/marketplace/my-portfolio", wait_until="networkidle")
        inject_wallet(page, TEST_WALLET_ADDRESS)
        page.wait_for_timeout(2000)
        page.screenshot(path=str(OUT_DIR / "my_portfolio_with_wallet.png"), full_page=False)
        (OUT_DIR / "my_portfolio_with_wallet.html").write_text(page.content(), encoding="utf-8")
        print("  Saved my_portfolio_with_wallet.html and .png")

        # Страница пула с кошельком — только по TEST_POOL_ID
        pool_url_w = f"{BASE_URL}/marketplace/pool/{TEST_POOL_ID}" if TEST_POOL_ID else None

        if pool_url_w:
            page.goto(pool_url_w, wait_until="networkidle")
            inject_wallet(page, TEST_WALLET_ADDRESS)
            page.get_by_role("heading", level=1).wait_for(timeout=15_000)
            page.screenshot(path=str(OUT_DIR / "pool_page_with_wallet.png"), full_page=False)
            (OUT_DIR / "pool_page_with_wallet.html").write_text(page.content(), encoding="utf-8")
            print("  Saved pool_page_with_wallet.html and .png")

            # Открываем модалку DEPOSIT и дампим
            # Кнопка — div с текстом "Deposit", не ARIA button
            deposit_btn = page.get_by_text("Deposit", exact=True).first
            if deposit_btn.is_visible():
                deposit_btn.click()
                try:
                    page.wait_for_selector("[role='dialog']", timeout=5_000)
                    page.screenshot(path=str(OUT_DIR / "deposit_modal.png"), full_page=False)
                    (OUT_DIR / "deposit_modal.html").write_text(page.content(), encoding="utf-8")
                    print("  Saved deposit_modal.html and .png")
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(500)
                except Exception as e:
                    print(f"  ⚠ Deposit modal did not appear: {e}")
            else:
                print("  ⚠ Deposit button not visible")

            # Открываем модалку WITHDRAW и дампим
            withdraw_btn = page.get_by_text("Withdrawal", exact=True).first
            if withdraw_btn.is_visible():
                withdraw_btn.click()
                try:
                    page.wait_for_selector("[role='dialog']", timeout=5_000)
                    page.screenshot(path=str(OUT_DIR / "withdraw_modal.png"), full_page=False)
                    (OUT_DIR / "withdraw_modal.html").write_text(page.content(), encoding="utf-8")
                    print("  Saved withdraw_modal.html and .png")
                    page.keyboard.press("Escape")
                except Exception as e:
                    print(f"  ⚠ Withdraw modal did not appear: {e}")
            else:
                print("  ⚠ Withdrawal button not visible")

    browser.close()

print(f"\nДамп сохранён в {OUT_DIR.resolve()}")
