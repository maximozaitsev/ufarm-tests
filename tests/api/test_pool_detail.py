import json
import pytest
import allure

from core.api.models.pool import PoolDetailResponse


@pytest.mark.api
@pytest.mark.smoke
@allure.epic("Market")
@allure.feature("API")
@allure.story("Pool Detail")
@allure.title("Pool detail returns correct structure")
@allure.severity(allure.severity_level.NORMAL)
@allure.link("https://api.ufarm.digital/api/v1/docs#/", name="Swagger")
def test_pool_detail_returns_correct_structure(api_client, test_pool_id):
    with allure.step(f"Отправляем GET /pool/{test_pool_id}"):
        response = api_client.get(f"/pool/{test_pool_id}")

    with allure.step(f"Статус ответа == 200 (получен {response.status_code})"):
        assert response.status_code == 200

    body = response.json()

    with allure.step("Тело ответа содержит ключ 'pool'"):
        assert "pool" in body

    with allure.step("Валидируем ответ через Pydantic-модель PoolDetailResponse"):
        detail = PoolDetailResponse.model_validate(body)
        pool = detail.pool
        allure.attach(
            json.dumps({"id": pool.id, "pool": pool.pool, "status": pool.status,
                        "type": pool.type, "poolAddress": pool.poolAddress}, indent=2),
            name="Pool",
            attachment_type=allure.attachment_type.JSON,
        )

    print(f"\n  Pool: '{pool.pool}' (id={pool.id})")
    print(f"  status={pool.status}, type={pool.type}, decimals={pool.decimals}")
    print(f"  poolAddress={pool.poolAddress}")
    print(f"  fundAddress={pool.fundAddress}")

    with allure.step(f"id == {test_pool_id}"):
        assert pool.id == test_pool_id, f"Expected id={test_pool_id}, got {pool.id}"

    with allure.step(f"status == active (получен '{pool.status}')"):
        assert pool.status == "active", f"Expected status=active, got {pool.status}"

    with allure.step(f"type == public (получен '{pool.type}')"):
        assert pool.type == "public", f"Expected type=public, got {pool.type}"

    with allure.step(f"decimals > 0 (получен {pool.decimals})"):
        assert pool.decimals > 0, f"Expected decimals > 0, got {pool.decimals}"

    with allure.step(f"poolAddress начинается с 0x ({pool.poolAddress})"):
        assert pool.poolAddress.startswith("0x"), f"poolAddress must start with 0x: {pool.poolAddress}"

    with allure.step(f"fundAddress начинается с 0x ({pool.fundAddress})"):
        assert pool.fundAddress.startswith("0x"), f"fundAddress must start with 0x: {pool.fundAddress}"


@pytest.mark.api
@pytest.mark.regression
@allure.epic("Market")
@allure.feature("API")
@allure.story("Pool Detail")
@allure.title("Pool financials are consistent: valueManaged = totalDeposited + revenue")
@allure.severity(allure.severity_level.CRITICAL)
@allure.link("https://api.ufarm.digital/api/v1/docs#/", name="Swagger")
def test_pool_detail_financials_are_consistent(api_client, test_pool_id):
    with allure.step(f"Отправляем GET /pool/{test_pool_id}"):
        response = api_client.get(f"/pool/{test_pool_id}")

    pool = PoolDetailResponse.model_validate(response.json()).pool

    value_managed = int(pool.valueManaged)
    total_deposited = int(pool.totalDeposited)
    revenue = int(pool.revenue)

    print(f"\n  Pool: '{pool.pool}'")
    print(f"  valueManaged    = {value_managed}")
    print(f"  totalDeposited  = {total_deposited}")
    print(f"  revenue         = {revenue}")
    print(f"  check: {total_deposited} + {revenue} = {total_deposited + revenue}  (expected == {value_managed})")

    with allure.step(f"valueManaged >= 0 (получен {value_managed})"):
        assert value_managed >= 0, f"valueManaged must be >= 0, got {value_managed}"

    with allure.step(f"totalDeposited >= 0 (получен {total_deposited})"):
        assert total_deposited >= 0, f"totalDeposited must be >= 0, got {total_deposited}"

    with allure.step(f"valueManaged ({value_managed}) == totalDeposited ({total_deposited}) + revenue ({revenue})"):
        assert value_managed == total_deposited + revenue, (
            f"valueManaged ({value_managed}) != totalDeposited ({total_deposited}) + revenue ({revenue})"
        )

    metric = pool.poolMetric

    print(f"\n  poolMetric.nav         = {metric.nav}  (expected == valueManaged {value_managed})")
    print(f"  poolMetric.tokenPrice  = {metric.tokenPrice}")
    print(f"  poolMetric.totalSupply = {metric.totalSupply}")
    print(f"  poolMetric.customers   = {metric.customers}")

    with allure.step(f"poolMetric.nav ({metric.nav}) == valueManaged ({value_managed})"):
        assert int(metric.nav) == value_managed, (
            f"poolMetric.nav ({metric.nav}) != valueManaged ({value_managed})"
        )

    with allure.step(f"tokenPrice > 0 (получен {metric.tokenPrice})"):
        assert float(metric.tokenPrice) > 0, f"tokenPrice must be > 0, got {metric.tokenPrice}"

    with allure.step(f"totalSupply > 0 (получен {metric.totalSupply})"):
        assert int(metric.totalSupply) > 0, f"totalSupply must be > 0, got {metric.totalSupply}"

    with allure.step(f"customers >= 0 (получен {metric.customers})"):
        assert metric.customers >= 0, f"customers must be >= 0, got {metric.customers}"


@pytest.mark.api
@pytest.mark.regression
@allure.epic("Market")
@allure.feature("API")
@allure.story("Pool Detail")
@allure.title("Pool asset allocations sum to ~100%")
@allure.severity(allure.severity_level.NORMAL)
@allure.link("https://api.ufarm.digital/api/v1/docs#/", name="Swagger")
def test_pool_detail_asset_allocation_sums_to_100(api_client, test_pool_id):
    with allure.step(f"Отправляем GET /pool/{test_pool_id}"):
        response = api_client.get(f"/pool/{test_pool_id}")

    pool = PoolDetailResponse.model_validate(response.json()).pool

    with allure.step(f"assetAllocation не пустой (найдено {len(pool.assetAllocation)} активов)"):
        assert len(pool.assetAllocation) > 0, "assetAllocation is empty"

    print(f"\n  Pool: '{pool.pool}', assets: {len(pool.assetAllocation)}")
    total_allocation = 0.0
    for asset in pool.assetAllocation:
        print(f"    {asset.asset[:10]}... | tokenType={asset.tokenType} | allocation={asset.allocation}%")
        total_allocation += asset.allocation

    print(f"  Total allocation: {total_allocation:.2f}%  (expected 99–101%)")

    allure.attach(
        json.dumps([{"asset": a.asset, "tokenType": a.tokenType, "allocation": a.allocation}
                    for a in pool.assetAllocation], indent=2),
        name="Asset Allocation",
        attachment_type=allure.attachment_type.JSON,
    )

    with allure.step(f"Сумма аллокаций {total_allocation:.2f}% в диапазоне [99%, 101%]"):
        assert 99.0 <= total_allocation <= 101.0, (
            f"Asset allocation sum is {total_allocation:.2f}%, expected ~100%"
        )
