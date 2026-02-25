from core.ui.base_page import BasePage


class MarketplacePage(BasePage):

    def open(self, url):
        self.page.goto(url)

    def is_loaded(self):
        return self.page.title() != ""