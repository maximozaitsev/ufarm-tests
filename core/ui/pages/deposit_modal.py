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
        """Враппер текущего токена (клик → открывает дропдаун в multi-token пуле).

        Кликабелен только в multi-token пуле (нет _noPointer_ класса).
        """
        return self._body.locator("[class*='current']")

    def token_selector_arrow(self):
        """Стрелка дропдауна рядом с иконкой токена.

        Присутствует только в multi-token пуле.
        В single-token пуле отсутствует — элемент имеет класс _noPointer_ и не кликабелен.
        """
        return self._body.locator("[class*='arrowWrapper']")

    def current_token_ticker(self) -> str:
        """Тикер текущего выбранного токена, например 'USDT'.

        В deposit modal селектор показывает баланс ('Balance\\n2 USDC') вместо отдельного
        ticker-элемента. Тикер извлекается как последнее слово из тега <p>.
        """
        text = self._body.locator("[class*='current'] [class*='balance'] p").inner_text()
        # "2 USDC" → "USDC"
        return text.strip().split()[-1]

    def token_option(self, ticker: str):
        """Конкретная опция в дропдауне по тикеру (например 'USDC').

        В dropdown каждый элемент содержит [class*='balance'] p с текстом вида '1.82 USDC'.
        Фильтруем <p> по вхождению тикера — 'USDC' найдёт '1.82 USDC'.
        """
        return self.token_dropdown().locator("[class*='balance'] p").filter(has_text=ticker)

    def close(self):
        self.page.keyboard.press("Escape")
        self._content.wait_for(state="hidden", timeout=3_000)
