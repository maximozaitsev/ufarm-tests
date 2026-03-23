from core.ui.base_page import BasePage


class MarketplacePage(BasePage):
    """
    Page Object для маркетплейса.

    Стратегия выбора селекторов (от лучшего к худшему):
      1. get_by_role()  — ARIA-роли (button, heading, tab) — самые стабильные
      2. get_by_text()  — видимый текст пользователя
      3. CSS-атрибуты   — img[alt=...], .mantine-* (классы UI-библиотеки, не хэши)
      4. CSS-классы с хэшами (_offer_1uf7l_1 и т.п.) — избегаем: меняются при пересборке
    """

    # ── Pool cards ───────────────────────────────────────────────────────────
    # Каждая карточка пула — это mantine-Paper-root содержащий h2.
    # mantine-* — класс UI-библиотеки, не хэш CSS-модуля → стабилен.
    POOL_CARD_CSS = ".mantine-Paper-root:has(h2)"

    # ── Page methods ─────────────────────────────────────────────────────────

    def open(self, url: str):
        self.page.goto(url, wait_until="domcontentloaded")

    def wait_for_pool_cards(self, timeout: int = 15_000):
        self.page.wait_for_selector(self.POOL_CARD_CSS, timeout=timeout)

    def wait_for_pool_page(self, timeout: int = 15_000):
        """Ждёт появления h1 с названием пула."""
        self.page.get_by_role("heading", level=1).wait_for(timeout=timeout)

    # ── Header ───────────────────────────────────────────────────────────────

    def logo(self):
        """Логотип UFarm (img с alt='logo' в хедере)."""
        return self.page.locator("header img[alt='logo']")

    def tab_all_products(self):
        """Таб 'All products' в хедере. Не ARIA-таб — обычный div с текстом."""
        return self.page.locator("header").get_by_text("All products", exact=True)

    def tab_my_portfolio(self):
        """Таб 'My portfolio' в хедере."""
        return self.page.locator("header").get_by_text("My portfolio", exact=True)

    def connect_wallet_button(self):
        """Кнопка Connect Wallet (первая — в хедере)."""
        return self.page.get_by_role("button", name="Connect Wallet").first

    # ── Marketplace — All products ────────────────────────────────────────────

    def pool_cards(self):
        return self.page.locator(self.POOL_CARD_CSS)

    def click_first_pool_card(self):
        self.pool_cards().first.click()

    # ── Pool page ─────────────────────────────────────────────────────────────

    def pool_name(self):
        """Название пула — единственный h1 на странице пула."""
        return self.page.get_by_role("heading", level=1)

    def connect_to_deposit_button(self):
        """Кнопка 'Connect wallet to deposit' (видна без подключённого кошелька)."""
        return self.page.get_by_role("button", name="Connect wallet to deposit")

    def history_tabs(self):
        """ARIA-табы истории на странице пула (Transactions, actions и др.)."""
        return self.page.get_by_role("tab")

    # ── Connect Wallet modal (Reown / Web3Modal) ──────────────────────────────
    # data-testid из самой библиотеки Reown — стабилен между сборками приложения.
    # Playwright автоматически пробивает shadow DOM при использовании locator().

    def connect_wallet_modal(self):
        """Модалка подключения кошелька (Reown Web3Modal)."""
        return self.page.locator("[data-testid='w3m-modal-card']")
