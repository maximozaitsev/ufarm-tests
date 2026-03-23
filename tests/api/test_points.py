import json

import allure
import pytest

from core.api.models.leaderboard import LeaderboardResponse
from core.api.models.portfolio import Portfolio


@pytest.mark.api
@pytest.mark.smoke
@allure.epic("Market")
@allure.feature("API")
@allure.story("Points")
@allure.title("Portfolio points match leaderboard points for top addresses")
@allure.severity(allure.severity_level.CRITICAL)
@allure.link("https://api.ufarm.digital/api/v1/docs#/", name="Swagger")
def test_points_portfolio_matches_leaderboard(leaderboard_api_client):
    """
    Берём первые 10 адресов из лидерборда и для каждого сравниваем
    portfolio.points с leaderboard.points.
    Оба эндпоинта — PROD ETH /api/v2.
    """
    with allure.step("Получаем первые 10 адресов из лидерборда (PROD ETH /api/v2)"):
        resp = leaderboard_api_client.get("/points/leaderboard", params={"limit": 10, "page": 1})
        assert resp.status_code == 200
        leaderboard = LeaderboardResponse.model_validate(resp.json())
        allure.attach(
            json.dumps(resp.json(), indent=2),
            name="Leaderboard top-10",
            attachment_type=allure.attachment_type.JSON,
        )

    print(f"\n  Адресов в лидерборде: {leaderboard.total}")
    print(f"  Проверяем {len(leaderboard.data)} адресов:")

    mismatches = []

    for item in leaderboard.data:
        address = item.userAddress
        leaderboard_points = item.points

        with allure.step(f"Запрашиваем portfolio для {address} (PROD ETH /api/v2)"):
            portfolio_resp = leaderboard_api_client.get(f"/user/portfolio/{address}")
            assert portfolio_resp.status_code == 200, (
                f"portfolio для {address} вернул {portfolio_resp.status_code}"
            )
            portfolio = Portfolio.model_validate(portfolio_resp.json())
            portfolio_points = portfolio.points

        print(
            f"    {address} | leaderboard={leaderboard_points} | portfolio={portfolio_points} "
            f"| {'OK' if leaderboard_points == portfolio_points else 'MISMATCH'}"
        )

        if leaderboard_points != portfolio_points:
            mismatches.append({
                "address": address,
                "leaderboard_points": leaderboard_points,
                "portfolio_points": portfolio_points,
            })

    if mismatches:
        allure.attach(
            json.dumps(mismatches, indent=2),
            name="Points mismatches",
            attachment_type=allure.attachment_type.JSON,
        )

    with allure.step(f"Все {len(leaderboard.data)} адресов: portfolio.points == leaderboard.points"):
        assert not mismatches, (
            f"Расхождение поинтов у {len(mismatches)} адресов:\n"
            + "\n".join(
                f"  {m['address']}: leaderboard={m['leaderboard_points']}, portfolio={m['portfolio_points']}"
                for m in mismatches
            )
        )
