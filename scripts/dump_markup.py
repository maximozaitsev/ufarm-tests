"""
Дамп разметки страниц маркетплейса для изучения селекторов.
Запуск: python scripts/dump_markup.py
"""
import pathlib
from playwright.sync_api import sync_playwright

BASE_URL = "https://app.demo.ufarm.digital"
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

    # 1. Маркетплейс — ждём появления карточек пулов
    dump_page(page, f"{BASE_URL}/marketplace", "marketplace")

    # 2. My portfolio — без кошелька
    dump_page(page, f"{BASE_URL}/marketplace/my-portfolio", "my_portfolio")

    # 3. Страница пула — берём href первой карточки
    page.goto(f"{BASE_URL}/marketplace", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle", timeout=20_000)
    # ищем первую ссылку, ведущую на /marketplace/pool/
    pool_link = page.locator("a[href*='/marketplace/pool/']").first
    pool_href = pool_link.get_attribute("href")
    print(f"  First pool link: {pool_href}")
    if pool_href:
        pool_url = BASE_URL + pool_href if pool_href.startswith("/") else pool_href
        dump_page(page, pool_url, "pool_page")

    browser.close()

print(f"\nДамп сохранён в {OUT_DIR.resolve()}")
