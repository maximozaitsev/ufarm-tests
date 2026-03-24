from playwright.sync_api import Page


class DepositModal:
    """Page Object для модалки депозита.

    Открывается по клику на кнопку Deposit на странице пула.

    Selector notes:
      - #poolDepositConfirm  — стабильный id кнопки подтверждения
      - input[type='checkbox'][role='switch']  — тоглер Gasless transaction
      - input.mantine-NumberInput-input  — инпут суммы
      - img[alt='token'] в modal body  — иконка токена; клик по родителю открывает
        дропдаун токенов (только в multi-token пуле)
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

    def title(self):
        return self._body.get_by_role("heading")
    
    def token_dropdown(self):
        return self._body.locator("[class*='tokensList']")

    def amount_input(self):
        """Инпут суммы депозита."""
        return self._body.locator("input.mantine-NumberInput-input").first

    def max_button(self):
        return self._body.get_by_role("button", name="Max")

    def gasless_toggle(self):
        """Тоглер Gasless transaction (checkbox с role=switch)."""
        return self._body.get_by_role("switch")

    def submit_button(self):
        """Кнопка подтверждения (Request Deposit / Instant Deposit).

        id="poolDepositConfirm" — стабильный идентификатор.
        Отключена (data-disabled=true) пока инпут пустой.
        """
        return self.page.locator("#poolDepositConfirm")

    def submit_button_text(self) -> str:
        """Текст кнопки подтверждения в нижнем регистре."""
        return self.page.locator("#poolDepositConfirm .mantine-Button-label").inner_text().lower()

    def token_selector(self):
        """Иконка токена в форме (клик → открывает дропдаун в multi-token пуле)."""
        return self._body.locator("img[alt='token']").first

    def close(self):
        self.page.keyboard.press("Escape")
        self._content.wait_for(state="hidden", timeout=3_000)
