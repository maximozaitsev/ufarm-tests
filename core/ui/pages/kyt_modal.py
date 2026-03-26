"""Page object для KYT-блокировочной модалки (Wallet verification issue).

Появляется когда кошелёк не прошёл KYT-проверку (tier из /user/verification
меньше minClientTier пула).
"""


class KytBlockModal:
    def __init__(self, page):
        self._page = page
        self._body = page.locator(".mantine-Modal-body")

    def heading(self):
        """Заголовок 'Wallet verification issue'."""
        return self._body.get_by_role("heading", name="Wallet verification issue")

    def close_button(self):
        return self._body.get_by_role("button", name="Close")

    def wait_opened(self, timeout: int = 10_000):
        self.heading().wait_for(state="visible", timeout=timeout)
