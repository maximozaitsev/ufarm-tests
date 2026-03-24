from playwright.sync_api import Page


class FundWalletModal:
    """Page Object для модалки Fund wallet.

    Открывается вместо модалки депозита когда on-chain баланс кошелька = 0
    (нет средств для депозита в пул).

    Содержит:
      - текст с необходимым минимальным балансом, токеном и сетью
      - кнопки BUY CRYPTO и RECEIVE FUNDS
    """

    def __init__(self, page: Page):
        self.page = page
        self._content = page.locator(".mantine-Modal-content")
        self._root = page.get_by_role("dialog")
        self._title = self._root.get_by_role("heading", name="Fund wallet")

    # ── Состояние ─────────────────────────────────────────────────────────

    def is_visible(self) -> bool:
        return self._content.is_visible()

    def wait_for(self, timeout: int = 10_000):
        self._content.wait_for(state="visible", timeout=timeout)

    def wait_opened(self):
         self._title.filter(has_text="Fund wallet").wait_for(state="visible")

    # ── Элементы ──────────────────────────────────────────────────────────

    def title(self):
        return self._content.get_by_role("heading", name="Fund wallet")

    def hint_text(self) -> str:
        """Полный текст подсказки: 'To invest in the vault, make sure your wallet has ...'"""
        return self._content.locator("span").filter(
            has_text="To invest in the vault"
        ).inner_text()

    def buy_crypto_button(self):
        """Кнопка BUY CRYPTO (div-элемент со span текстом 'buy crypto')."""
        return self._content.get_by_text("buy crypto")

    def receive_funds_button(self):
        """Кнопка RECEIVE FUNDS (div-элемент со span текстом 'receive funds')."""
        return self._content.get_by_text("receive funds")

    def close(self):
        self.page.keyboard.press("Escape")
        self._content.wait_for(state="hidden", timeout=3_000)
