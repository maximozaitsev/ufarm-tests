import json
import pytest
import allure

from core.api.models.portfolio import Portfolio


@pytest.mark.api
@pytest.mark.smoke
@allure.feature("API")
@allure.story("Investor Portfolio")
@allure.title("Portfolio returns correct structure")
@allure.severity(allure.severity_level.NORMAL)
@allure.link("https://api.ufarm.digital/api/v1/docs#/", name="Swagger")
def test_portfolio_returns_correct_structure(api_client, test_wallet_address):
    with allure.step(f"Отправляем GET /user/portfolio/{test_wallet_address}"):
        response = api_client.get(f"/user/portfolio/{test_wallet_address}")

    with allure.step(f"Статус ответа == 200 (получен {response.status_code})"):
        assert response.status_code == 200

    with allure.step("Валидируем ответ через Pydantic-модель Portfolio"):
        portfolio = Portfolio.model_validate(response.json())
        allure.attach(
            json.dumps({
                "allDeposited": portfolio.allDeposited,
                "allWithdrawals": portfolio.allWithdrawals,
                "totalBalance": portfolio.totalBalance,
                "realizedPnL": portfolio.realizedPnL,
                "unrealizedPnL": portfolio.unrealizedPnL,
                "points": portfolio.points,
                "pools_count": len(portfolio.pools),
            }, indent=2),
            name="Portfolio Summary",
            attachment_type=allure.attachment_type.JSON,
        )

    print(f"\n  Wallet: {test_wallet_address}")
    print(f"  allDeposited   = {portfolio.allDeposited}")
    print(f"  allWithdrawals = {portfolio.allWithdrawals}")
    print(f"  totalBalance   = {portfolio.totalBalance}")
    print(f"  realizedPnL    = {portfolio.realizedPnL}")
    print(f"  unrealizedPnL  = {portfolio.unrealizedPnL}")
    print(f"  points         = {portfolio.points}")
    print(f"  pools count    = {len(portfolio.pools)}")

    with allure.step("pools — список"):
        assert isinstance(portfolio.pools, list), "pools must be a list"

    with allure.step(f"allDeposited >= 0 (получен {portfolio.allDeposited})"):
        assert int(portfolio.allDeposited) >= 0, f"allDeposited must be >= 0, got {portfolio.allDeposited}"

    with allure.step(f"allWithdrawals >= 0 (получен {portfolio.allWithdrawals})"):
        assert int(portfolio.allWithdrawals) >= 0, f"allWithdrawals must be >= 0, got {portfolio.allWithdrawals}"

    with allure.step(f"points — число (получен {portfolio.points})"):
        assert isinstance(portfolio.points, float), f"points must be float, got {type(portfolio.points)}"


@pytest.mark.api
@pytest.mark.regression
@allure.feature("API")
@allure.story("Investor Portfolio")
@allure.title("Portfolio pool balance formula: totalBalance = deposited − withdrawn + realizedPnL + unrealizedPnL")
@allure.severity(allure.severity_level.CRITICAL)
@allure.link("https://api.ufarm.digital/api/v1/docs#/", name="Swagger")
def test_portfolio_pool_stats_are_consistent(api_client, test_wallet_address):
    with allure.step(f"Отправляем GET /user/portfolio/{test_wallet_address}"):
        response = api_client.get(f"/user/portfolio/{test_wallet_address}")

    portfolio = Portfolio.model_validate(response.json())

    with allure.step(f"Портфолио содержит пулы (найдено {len(portfolio.pools)})"):
        assert len(portfolio.pools) > 0, "Test wallet has no pools in portfolio"

    print(f"\n  Wallet: {test_wallet_address}, pools: {len(portfolio.pools)}")

    for pool in portfolio.pools:
        stat = pool.poolStat

        deposited = int(stat.allDeposited)
        withdrawn = int(stat.allWithdrawals)
        balance = int(stat.totalBalance)
        realized_pnl = int(stat.realizedPnL)
        unrealized_pnl = int(stat.unrealizedPnL)
        expected = deposited - withdrawn + realized_pnl + unrealized_pnl

        print(f"\n  Pool: '{pool.pool}' (id={pool.id})")
        print(f"    allDeposited   = {deposited}")
        print(f"    allWithdrawals = {withdrawn}")
        print(f"    realizedPnL    = {realized_pnl}")
        print(f"    unrealizedPnL  = {unrealized_pnl}")
        print(f"    totalBalance   = {balance}")
        print(f"    check: {deposited} - {withdrawn} + {realized_pnl} + {unrealized_pnl} = {expected}  (expected == {balance})")

        with allure.step(f"Пул '{pool.pool}': {deposited} - {withdrawn} + {realized_pnl} + {unrealized_pnl} = {expected} == {balance}"):
            assert deposited >= 0, f"allDeposited must be >= 0, got {deposited}"
            assert withdrawn >= 0, f"allWithdrawals must be >= 0, got {withdrawn}"
            assert balance >= 0, f"totalBalance must be >= 0, got {balance}"
            assert balance == expected, (
                f"Balance inconsistency for pool '{pool.pool}': "
                f"{deposited} - {withdrawn} + {realized_pnl} + {unrealized_pnl} = {expected} != {balance}"
            )


@pytest.mark.api
@pytest.mark.regression
@allure.feature("API")
@allure.story("Investor Portfolio")
@allure.title("Portfolio totals match sum of per-pool stats")
@allure.severity(allure.severity_level.CRITICAL)
@allure.link("https://api.ufarm.digital/api/v1/docs#/", name="Swagger")
def test_portfolio_totals_match_pool_stats(api_client, test_wallet_address):
    with allure.step(f"Отправляем GET /user/portfolio/{test_wallet_address}"):
        response = api_client.get(f"/user/portfolio/{test_wallet_address}")

    portfolio = Portfolio.model_validate(response.json())

    total_deposited_from_pools = sum(int(p.poolStat.allDeposited) for p in portfolio.pools)
    total_withdrawn_from_pools = sum(int(p.poolStat.allWithdrawals) for p in portfolio.pools)

    print(f"\n  Wallet: {test_wallet_address}")
    print(f"  portfolio.allDeposited              = {portfolio.allDeposited}")
    print(f"  sum(pools[*].poolStat.allDeposited) = {total_deposited_from_pools}")
    print(f"  portfolio.allWithdrawals               = {portfolio.allWithdrawals}")
    print(f"  sum(pools[*].poolStat.allWithdrawals)  = {total_withdrawn_from_pools}")

    with allure.step(f"allDeposited: портфолио ({portfolio.allDeposited}) == сумма по пулам ({total_deposited_from_pools})"):
        assert int(portfolio.allDeposited) == total_deposited_from_pools, (
            f"allDeposited mismatch: portfolio={portfolio.allDeposited}, sum from pools={total_deposited_from_pools}"
        )

    with allure.step(f"allWithdrawals: портфолио ({portfolio.allWithdrawals}) == сумма по пулам ({total_withdrawn_from_pools})"):
        assert int(portfolio.allWithdrawals) == total_withdrawn_from_pools, (
            f"allWithdrawals mismatch: portfolio={portfolio.allWithdrawals}, sum from pools={total_withdrawn_from_pools}"
        )
