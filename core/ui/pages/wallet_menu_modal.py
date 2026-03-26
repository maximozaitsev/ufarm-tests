from playwright.sync_api import Page


class WalletMenuModal:
    """Page Object для модалки кошелька (открывается кликом на адрес в хедере).

    Содержит:
      - Блок с адресом кошелька и кнопкой копирования
      - Балансы токенов (USDT, USDC, ETH)
      - Кнопки: fund wallet, Send, Disconnect

    Sub-страницы (навигация внутри модалки):
      fund wallet  → buy crypto    → форма покупки → Unlimit виджет
                   → receive funds → QR-код + Copy address
      Send         → форма отправки
    """

    def __init__(self, page: Page):
        self.page = page
        # data-modal-content="true" — стабильный атрибут кастомной модалки кошелька.
        # Отличает её от mantine-Modal-content депозит/вывод модалок.
        self._root = page.locator("[data-modal-content='true']")

    # ── Состояние ─────────────────────────────────────────────────────────

    def wait_opened(self, timeout: int = 10_000):
        """Ждёт открытия модалки на главной странице ('My wallet' текст виден)."""
        self._root.wait_for(state="visible", timeout=timeout)
        self._root.get_by_text("My wallet").wait_for(state="visible", timeout=timeout)

    def is_visible(self) -> bool:
        return self._root.is_visible()

    def close(self):
        self.page.keyboard.press("Escape")
        self._root.wait_for(state="hidden", timeout=5_000)

    # ── Главная страница: блок адреса ──────────────────────────────────────

    def my_wallet_label(self):
        """Метка 'My wallet'."""
        return self._root.get_by_text("My wallet", exact=True)

    def address_display(self):
        """Блок с сокращённым адресом кошелька (0xXXXX...XXXX).

        CSS-паттерн [class*='address'] матчит класс _address_1w3m4_1.
        .first — исключаем родительский блок _addressInfo_, у которого тоже есть 'address'.
        """
        return self._root.locator("[class*='myWallet'] [class*='address']")

    def copy_address_icon(self):
        """Иконка копирования рядом с адресом."""
        return self._root.locator("[class*='copyWrapper']")

    # ── Главная страница: балансы токенов ──────────────────────────────────

    def usdt_balance_label(self):
        """Метка 'USDT' в строке баланса."""
        return self._root.locator("p").filter(has_text="USDT").first

    def usdc_balance_label(self):
        """Метка 'USDC' в строке баланса."""
        return self._root.locator("p").filter(has_text="USDC").first

    def eth_balance_label(self):
        """Метка 'ETH' в строке баланса."""
        return self._root.locator("p").filter(has_text="ETH").first

    def get_balance_value(self, token: str) -> str:
        """Возвращает числовую часть баланса токена (без названия) через JS.

        Ищет <p> с точным именем токена внутри модалки, берёт его parentElement
        и извлекает только text-узлы (nodeType=3) — т.е. число без дочерних элементов.

        Примеры возвращаемых значений: '5,8', '2', '0.00230363'

        XPath '..' не используется: в ряде версий Playwright он возвращает
        исходный элемент, а не родителя.
        """
        return self.page.evaluate(
            """([sel, token]) => {
                const modal = document.querySelector(sel);
                if (!modal) return '';
                const p = [...modal.querySelectorAll('p')]
                    .find(el => el.textContent.trim() === token);
                if (!p) return '';
                return [...p.parentElement.childNodes]
                    .filter(n => n.nodeType === 3)
                    .map(n => n.textContent.trim())
                    .filter(Boolean)
                    .join('');
            }""",
            ["[data-modal-content='true']", token],
        )

    # ── Главная страница: кнопки действий ─────────────────────────────────

    def fund_wallet_button(self):
        """Кнопка 'fund wallet' (переходит на sub-страницу выбора способа пополнения)."""
        return self._root.get_by_text("fund wallet", exact=True)

    def send_nav_button(self):
        """Кнопка 'Send' (переходит на форму отправки)."""
        return self._root.get_by_text("Send", exact=True)

    def disconnect_button(self):
        """Кнопка 'Disconnect'.

        Примечание: с inject_wallet disconnect не работает — коннектор
        не реализует disconnect(). Кнопка визуально присутствует, но
        wagmi state не сбрасывается.
        """
        return self._root.get_by_text("Disconnect", exact=True)

    # ── Sub-страница: выбор способа пополнения ─────────────────────────────

    def buy_crypto_option(self):
        """Кнопка 'buy crypto' на sub-странице fund wallet."""
        return self._root.get_by_text("buy crypto", exact=True)

    def receive_funds_option(self):
        """Кнопка 'receive funds' на sub-странице fund wallet."""
        return self._root.get_by_text("receive funds", exact=True)

    # ── Sub-страница: форма покупки (buy crypto) ───────────────────────────

    def page_heading(self):
        """Заголовок текущей sub-страницы (h3 в шапке модалки).

        На главной странице h3 пустой. На sub-страницах содержит заголовок:
        'buy', 'receive funds', 'SEND' и т.д.
        """
        return self._root.locator("h3")

    def buy_token_selector(self):
        """Дропдаун выбора токена на форме покупки."""
        return self._root.locator("[class*='current']")

    def buy_amount_input(self):
        """Инпут суммы (минимум 15).

        Используем mantine-NumberInput-input — mantine-класс стабильнее хэшированного.
        Исключает скрытые checkbox/switch инпуты которые попадают под locator("input").first.
        """
        return self._root.locator("input.mantine-NumberInput-input").first

    def fund_my_wallet_label(self):
        """Строка 'fund my wallet: Arbitrum network' под инпутом."""
        return self._root.get_by_text("fund my wallet", exact=False)

    def buy_form_wallet_address(self):
        """Адрес кошелька в блоке 'fund my wallet' (полный, не сокращённый).

        Структура HTML:
          <div>fund my wallet: <div>Arbitrum network</div></div>
          <span>0xFULL_ADDRESS</span>   ← этот span
        """
        return self._root.locator("[class*='address'] span").filter(has_text="0x")

    def buy_continue_button(self):
        """Кнопка Continue для перехода к виджету Unlimit.

        Disabled пока инпут суммы пуст или сумма < минимальной (15).
        """
        return self._root.get_by_role("button", name="Continue")

    # ── Unlimit виджет (после нажатия continue в форме покупки) ───────────

    def unlimit_widget_container(self):
        """Контейнер Unlimit/GateFi виджета (#gatefi-widget).

        После клика continue SDK заполняет этот div своим UI.
        Виджет может рендериться в iframe внутри контейнера.
        """
        return self.page.locator("#gatefi-widget")

    # ── Sub-страница: receive funds ────────────────────────────────────────

    def qr_code_element(self):
        """QR-код (canvas) на странице receive funds."""
        return self._root.locator("canvas").first

    def copy_address_button(self):
        """Кнопка 'Copy address' на странице receive funds."""
        return self._root.get_by_text("Copy address", exact=False)

    # ── Sub-страница: send ────────────────────────────────────────────────

    def send_token_dropdown(self):
        """Дропдаун токена с балансом на форме отправки."""
        return self._root.locator("[class*='current']")

    def send_amount_input(self):
        """Инпут суммы для отправки (mantine NumberInput)."""
        return self._root.locator("input.mantine-NumberInput-input").first

    def send_max_button(self):
        """Кнопка Max — заполняет максимальный доступный баланс."""
        return self._root.get_by_text("Max", exact=True)

    def send_to_input(self):
        """Поле адреса получателя (textarea, плейсхолдер: 'Address on {network} network').

        Используется <textarea>, не <input>.
        """
        return self._root.locator("textarea[placeholder*='Address on']")

    def send_submit_button(self):
        """Кнопка Send (активна когда сумма > 0 и адрес валиден)."""
        return self._root.get_by_role("button", name="Send")
