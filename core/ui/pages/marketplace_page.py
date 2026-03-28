import re
from decimal import Decimal

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
    # Каждая карточка пула — это mantine-Paper-root содержащий h2 (название пула).
    # Исключаем обёртку секции, у которой есть h1 ("All products") + вложенные h2 карточек.
    # :not(:has(h1)) — отфильтровывает контейнер-обёртку, у индивидуальных карточек h1 нет.
    POOL_CARD_CSS = ".mantine-Paper-root:has(h2):not(:has(h1))"

    # ── Navigation ────────────────────────────────────────────────────────────

    def open(self, url: str):
        self.page.goto(url, wait_until="domcontentloaded")

    def wait_for_pool_cards(self, timeout: int = 15_000):
        self.page.wait_for_selector(self.POOL_CARD_CSS, timeout=timeout)

    def wait_for_pool_page(self, timeout: int = 15_000):
        """Ждёт появления h1 с названием пула и исчезновения любого модального оверлея.

        После inject_wallet приложение кратковременно (<200мс) открывает Reown-модалку
        при инициализации wallet connection state. Эта модалка блокирует клики.
        Ждём пока оверлей исчезнет чтобы тесты не падали на race condition.
        """
        self.page.get_by_role("heading", level=1).wait_for(timeout=timeout)
        self.page.locator(".mantine-Modal-overlay").wait_for(state="hidden", timeout=10_000)

    # ── Header ───────────────────────────────────────────────────────────────
    # На странице пула присутствуют два <header>: навигационный и секционный.
    # nav_header() фильтрует по #connectWallet — кнопка есть только в навигационном.

    def nav_header(self):
        """Основной навигационный хедер (логотип, табы, кнопка кошелька)."""
        return self.page.locator("header").filter(has=self.page.locator("#connectWallet"))

    def logo(self):
        """Логотип UFarm (img с alt='logo' в навигационном хедере)."""
        return self.nav_header().locator("img[alt='logo']")

    def tab_all_products(self):
        """Таб 'All products' в навигационном хедере."""
        return self.nav_header().get_by_text("All products", exact=True)

    def tab_my_portfolio(self):
        """Таб 'My portfolio' в навигационном хедере."""
        return self.nav_header().get_by_text("My portfolio", exact=True)

    def connect_wallet_button(self):
        """Кнопка Connect Wallet (первая — в хедере)."""
        return self.page.get_by_role("button", name="Connect Wallet").first

    # ── Marketplace — pool list ───────────────────────────────────────────────

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

    def my_history_tab(self):
        """Таб «My history» в секции истории на странице пула.

        DOM: <button role="tab"><span class="mantine-Tabs-tabLabel">My history</span></button>
        CSS делает текст uppercase визуально; DOM-текст — «My history».
        Используем case-insensitive фильтр чтобы не зависеть от регистра.
        """
        return self.page.get_by_role("tab").filter(
            has_text=re.compile(r"my history", re.IGNORECASE)
        )

    def my_requests_tab(self):
        """Таб «My requests» в секции истории на странице пула.

        Содержит pending gasless deposits/withdrawals, ожидающих одобрения управляющего.
        """
        return self.page.get_by_role("tab").filter(
            has_text=re.compile(r"my requests", re.IGNORECASE)
        )

    def history_table_rows(self):
        """Строки таблицы истории транзакций (видимые после выбора таба).

        Таблица рендерится под табами — строки содержат тип (Deposit/Withdrawal),
        дату, количество токенов, сумму и адрес.
        Исключаем заголовочную строку через filter(has_not=columnheader).
        """
        return self.page.get_by_role("row").filter(has_not=self.page.get_by_role("columnheader"))

    def wait_for_history_row_with_text(self, text: str, timeout: int = 15_000):
        """Ждёт появления строки в таблице истории, содержащей заданный текст."""
        self.page.get_by_role("row").filter(has_text=text).first.wait_for(
            state="visible", timeout=timeout
        )

    # ── Pool page — action buttons (with wallet connected) ───────────────────
    # Кнопки — div-элементы (не ARIA button), поэтому get_by_text.

    def deposit_button(self):
        """Кнопка 'Deposit' на странице пула (видна только с подключённым кошельком).

        Используем get_by_text — get_by_role("button", name="Deposit") не подходит,
        потому что совпадает с кнопкой подтверждения внутри открытой модалки депозита.
        """
        return self.page.get_by_text("Deposit", exact=True).first

    def withdraw_button(self):
        """Кнопка 'Withdraw' на странице пула (видна только при ненулевом балансе).

        Примечание: "Withdrawal" (с -al) — это тип операции в таблице истории транзакций,
        не эта кнопка. Кнопка действия называется "Withdraw".
        """
        return self.page.get_by_role("button", name="Withdraw", exact=True).first

    def wait_for_withdraw_button(self, timeout: int = 15_000):
        """Ждёт появления кнопки Withdraw.

        Кнопка рендерится только после загрузки баланса пользователя по API —
        это занимает время после inject_wallet.
        """
        self.withdraw_button().wait_for(state="visible", timeout=timeout)

    # ── Connect Wallet modal (Reown / Web3Modal) ──────────────────────────────
    # data-testid из библиотеки Reown — стабилен между сборками.
    # Playwright автоматически пробивает shadow DOM.

    def connect_wallet_modal(self):
        """Модалка подключения кошелька (Reown Web3Modal)."""
        return self.page.locator("[data-testid='w3m-modal-card']")

    # ── Wallet menu modal (custom, not Reown) ─────────────────────────────────
    # Открывается кликом на кнопку #connectWallet в хедере (в connected-состоянии).
    # Disconnect в меню не работает с inject_wallet — коннектор не реализует disconnect().

    def wallet_header_button(self):
        """Кнопка кошелька в хедере (в connected-состоянии открывает меню кошелька).

        id="connectWallet" — стабильный атрибут, не зависит от CSS-модульных хэшей.
        """
        return self.page.locator("#connectWallet")

    # ── Pool page — MY BALANCE (позиция в пуле) ───────────────────────────────
    # HTML:
    #   <div class="..._usdt_..."><p>$</p>2</div>     ← USD-стоимость позиции
    #   <p class="..._tokens_...">2,01 tokens</p>      ← количество LP-токенов
    #
    # Используем [class*=_usdt_] и [class*=_tokens_] — семантические префиксы
    # в CSS-модульных классах (аналогично portfolio_page.py).

    def get_pool_balance_usd(self) -> Decimal:
        """USD-стоимость позиции в пуле (секция MY BALANCE).

        HTML: <div class="..._usdt_..."><p>$</p>2</div>
        Число — text-узел после тега <p>$</p>, скопированное из childNodes.
        Scope: ищем от heading «MY BALANCE» вверх по DOM.
        """
        value = self.page.evaluate("""() => {
            const heading = [...document.querySelectorAll('*')]
                .find(el => el.childElementCount === 0 && el.textContent.trim() === 'MY BALANCE');
            if (!heading) return '';
            let node = heading.parentElement;
            for (let i = 0; i < 6; i++) {
                if (!node) break;
                const div = node.querySelector('[class*=_usdt_]');
                if (div) {
                    return [...div.childNodes]
                        .filter(n => n.nodeType === 3)
                        .map(n => n.textContent.trim())
                        .filter(Boolean)
                        .join('');
                }
                node = node.parentElement;
            }
            return '';
        }""")
        return Decimal(value.replace(",", ".")) if value else Decimal("0")

    def get_pool_balance_tokens(self) -> float:
        """Количество LP-токенов в пуле (секция MY BALANCE).

        HTML: <p class="..._tokens_...">2,01 tokens</p>
        Возвращает float, например 2.01. Запятая — десятичный разделитель (EU).
        """
        text = self.page.evaluate("""() => {
            const p = document.querySelector('[class*=_tokens_]');
            return p ? p.textContent.trim() : null;
        }""")
        if not text:
            return 0.0
        return float(text.split()[0].replace(",", "."))

    def wait_for_pool_tokens_above(self, threshold: float, timeout: int = 30_000):
        """Ждёт пока LP-токены в UI станут строго больше threshold.

        Используется после on-chain депозита — баланс обновляется асинхронно
        после подтверждения tx и перерисовки UI.
        """
        self.page.wait_for_function(
            f"""() => {{
                const p = document.querySelector('[class*=_tokens_]');
                if (!p) return false;
                const num = parseFloat(p.textContent.trim().split(' ')[0].replace(',', '.'));
                return num > {threshold};
            }}""",
            timeout=timeout,
        )

    # ── Pool page — MY WALLET (баланс кошелька) ───────────────────────────────

    def get_wallet_balance_usd(self) -> Decimal:
        """USDT-баланс кошелька на странице пула (секция My wallet).

        Ищем <h2>My wallet</h2>, поднимаемся до корня карточки,
        берём первый [class*=_row_] — число после <p>$</p>.
        """
        value = self.page.evaluate("""() => {
            const h2 = [...document.querySelectorAll('h2')]
                .find(el => el.textContent.trim() === 'My wallet');
            if (!h2) return '';
            // h2 → _header_ → _line_ → карточка-корень (содержит _values_ c _row_)
            let node = h2.parentElement;
            for (let i = 0; i < 5; i++) {
                if (!node) break;
                const row = node.querySelector('[class*=_row_]');
                if (row) {
                    return [...row.childNodes]
                        .filter(n => n.nodeType === 3)
                        .map(n => n.textContent.trim())
                        .filter(Boolean)
                        .join('');
                }
                node = node.parentElement;
            }
            return '';
        }""")
        return Decimal(value.replace(",", ".")) if value else Decimal("0")
