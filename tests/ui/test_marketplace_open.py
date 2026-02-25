from core.ui.pages.marketplace_page import MarketplacePage
from config.settings import settings


def test_marketplace_open(page):
    mp = MarketplacePage(page)
    mp.open(settings.base_url + "/marketplace")

    assert mp.is_loaded()