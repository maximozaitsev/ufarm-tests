from decimal import Decimal

from playwright.sync_api import Page


class PortfolioPage:
    """Page Object для страницы My Portfolio (/marketplace/my-portfolio).

    Структура страницы:
      - Overview section (h1 "Overview"):
          - My wallet card       — баланс кошелька в $
          - My Investments card  — суммарный баланс инвестиций в $ + UF-POINTS
          - All-time profit card — общий P&L + realized/unrealized breakdown
      - My portfolio section (h1 "My portfolio"):
          - Карточки пулов, отсортированные по "My vault balance" убыванию
          - Каждая карточка: название, Last month return %, My vault balance $, Vault all-time profit $
    """

    def __init__(self, page: Page):
        self.page = page

    def wait_for(self, timeout: int = 15_000):
        """Ждёт загрузки страницы: секции, заголовки и финансовые данные.

        Заголовки Overview и My portfolio появляются сразу, но значение
        MY INVESTMENTS приходит асинхронно (API-запрос за портфолио).
        Ждём пока значение станет ненулевым.
        """
        self.page.get_by_role("heading", level=1, name="Overview").wait_for(
            state="visible", timeout=timeout
        )
        self.page.get_by_role("heading", level=1, name="My portfolio").wait_for(
            state="visible", timeout=timeout
        )
        # Ждём загрузки финансовых данных — значение меняется с "0" на реальное
        self.page.wait_for_function(
            """() => {
                const h2 = [...document.querySelectorAll('h2')]
                    .find(el => el.textContent.trim() === 'My Investments');
                if (!h2) return false;
                let node = h2.parentElement;
                for (let i = 0; i < 6; i++) {
                    if (!node) break;
                    const valueDiv = node.querySelector('[class*=_usdt_]');
                    if (valueDiv) {
                        const text = [...valueDiv.childNodes]
                            .filter(n => n.nodeType === 3)
                            .map(n => n.textContent.trim())
                            .find(t => t && t !== '0');
                        if (text) return true;
                    }
                    node = node.parentElement;
                }
                return false;
            }""",
            timeout=timeout,
        )

    # ── Overview: My wallet ────────────────────────────────────────────────

    def my_wallet_heading(self):
        return self.page.get_by_role("heading", level=2, name="My wallet")

    # ── Overview: My Investments ───────────────────────────────────────────

    def my_investments_heading(self):
        return self.page.get_by_role("heading", level=2, name="My Investments")

    def get_investments_usd(self) -> Decimal:
        """Парсит числовое значение MY INVESTMENTS из Overview.

        HTML-структура:
          <h2>My Investments</h2>
          ...
          <div class="..._usdt_..."><p>$</p>39.9</div>

        Значение — text-узел в div с классом *_usdt_* внутри карточки.
        """
        value = self.page.evaluate("""() => {
            const h2 = [...document.querySelectorAll('h2')]
                .find(el => el.textContent.trim() === 'My Investments');
            if (!h2) return '';
            // My Investments → _line_ div → _header_ div → h2
            // Поднимаемся к карточке через 3-4 уровня
            let card = h2.parentElement;
            for (let i = 0; i < 4; i++) {
                if (!card) break;
                const valueDiv = card.querySelector('[class*=_usdt_]');
                if (valueDiv) {
                    const text = [...valueDiv.childNodes]
                        .filter(n => n.nodeType === 3)
                        .map(n => n.textContent.trim())
                        .filter(Boolean)
                        .join('');
                    if (text) return text;
                }
                card = card.parentElement;
            }
            return '';
        }""")
        if not value:
            return Decimal("0")
        return Decimal(value.replace(",", "."))

    def get_uf_points(self) -> int:
        """Парсит значение UF-POINTS из карточки My Investments.

        HTML: <p class="..._points_...">69,742<span>UF-POINTS</span></p>
        Возвращает целое число, например 69742.
        """
        text = self.page.evaluate("""() => {
            const span = [...document.querySelectorAll('span')]
                .find(s => s.textContent.trim() === 'UF-POINTS');
            if (!span) return '';
            const p = span.parentElement;
            if (!p) return '';
            return [...p.childNodes]
                .filter(n => n.nodeType === 3)
                .map(n => n.textContent.trim())
                .filter(Boolean)
                .join('');
        }""")
        if not text:
            return 0
        return int(text.replace(",", "").replace(" ", "").replace("\xa0", ""))

    # ── Overview: All-time profit ──────────────────────────────────────────

    def all_time_profit_heading(self):
        return self.page.get_by_role("heading", level=2, name="all-time profit")

    def realized_profit_label(self):
        """Строка 'realized' с суммой в блоке All-time profit."""
        return self.page.get_by_text("realized", exact=False)

    def unrealized_profit_label(self):
        """Строка 'unrealized' с суммой в блоке All-time profit."""
        return self.page.get_by_text("unrealized", exact=False)

    # ── My portfolio: карточки пулов ───────────────────────────────────────

    def pool_cards(self):
        """Все карточки пулов в секции My portfolio."""
        return self.page.locator("h1", has_text="My portfolio").locator("..").locator(
            "h2.semibold"
        )

    def get_pool_vault_balances(self) -> list[Decimal]:
        """Возвращает список значений 'My vault balance' по всем карточкам пулов.

        Порядок соответствует порядку отображения карточек.

        HTML-структура каждой карточки (фрагмент):
          <p class="..._title_...">My vault balance</p>
          <div class="..._valueManaged_...">
            <p class="..._symbol_...">$</p>
            10.84          ← text-узел
          </div>
        """
        values = self.page.evaluate("""() => {
            const titles = [...document.querySelectorAll('p')]
                .filter(p => p.textContent.trim() === 'My vault balance');
            return titles.map(p => {
                const parent = p.parentElement;
                if (!parent) return null;
                const valueDiv = parent.querySelector('[class*=_valueManaged_]');
                if (!valueDiv) return null;
                const text = [...valueDiv.childNodes]
                    .filter(n => n.nodeType === 3)
                    .map(n => n.textContent.trim())
                    .filter(Boolean)
                    .join('');
                return text || null;
            }).filter(v => v !== null);
        }""")
        return [Decimal(v.replace(",", ".")) for v in values]
