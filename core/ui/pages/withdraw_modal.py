from playwright.sync_api import Page


class WithdrawModal:
    """Page Object для модалки вывода (Withdraw).

    Открывается по клику на кнопку Withdraw на странице пула.
    Доступна только если у кошелька есть активные депозиты в пуле.

    Selector notes:
      - data-path="withdraw-sellCoin"  — инпут суммы в токенах пула
      - data-path="withdraw-buyCoin"   — инпут суммы токена для получения
      Оба инпута взаимозаменяемы: изменение одного пересчитывает другой.
    """

    def __init__(self, page: Page):
        self.page = page
        self._content = page.locator(".mantine-Modal-content")
        self._body = page.locator(".mantine-Modal-body")

    # ── Состояние ─────────────────────────────────────────────────────────

    def is_visible(self) -> bool:
        return self._content.is_visible()

    def wait_for(self, timeout: int = 10_000):
        self._content.wait_for(state="visible", timeout=timeout)

    # ── Элементы ──────────────────────────────────────────────────────────

    def pool_token_input(self):
        """Инпут суммы в токенах пула (sell coin — сколько pool-токенов отдаём)."""
        return self.page.locator("[data-path='withdraw-sellCoin']")

    def withdraw_token_input(self):
        """Инпут суммы токена для получения (buy coin — сколько USDT/USDC получим)."""
        return self.page.locator("[data-path='withdraw-buyCoin']")

    def max_button(self):
        return self._body.get_by_role("button", name="Max")

    def request_withdrawal_button(self):
        return self.page.get_by_role("button", name="Request Withdrawal")

    def balance_text(self) -> str:
        """Текст отображения баланса пула, например 'Balance: 3.005'."""
        return self._body.locator("text=Balance:").first.inner_text()

    def close(self):
        """Закрывает модалку кликом по иконке крестика.

        Escape не работает — модалка закрывается только через UI-кнопку закрытия.
        [class*='closeIcon'] — substring match, устойчив к хэшам CSS-модулей.
        """
        self._content.locator("[class*='closeIcon']").click()
        self._content.wait_for(state="hidden", timeout=3_000)
