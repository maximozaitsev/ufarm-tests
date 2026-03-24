import pytest

_leaderboard_reachable: bool | None = None


@pytest.fixture
def leaderboard_reachable(leaderboard_api_client):
    """Пропускает тест, если лидерборд API недоступен (403 — IP-блокировка).

    Первый вызов делает один HEAD-like GET запрос и кэширует результат.
    Все последующие вызовы используют кэш — без лишних сетевых запросов.
    """
    global _leaderboard_reachable
    if _leaderboard_reachable is None:
        resp = leaderboard_api_client.get("/points/leaderboard", params={"limit": 1, "page": 1})
        _leaderboard_reachable = resp.status_code == 200
    if not _leaderboard_reachable:
        pytest.skip("Leaderboard API вернул 403 — IP заблокирован (запускай локально или через VPN)")
