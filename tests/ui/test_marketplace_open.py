from core.ui.pages.marketplace_page import MarketplacePage


def test_marketplace_open(page, base_url):
    mp = MarketplacePage(page)
    mp.open(base_url + "/marketplace")

    assert mp.is_loaded()