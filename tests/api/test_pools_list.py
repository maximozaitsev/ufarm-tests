import json
import pytest
import allure

from core.api.client import APIClient
from core.api.models.pool import PoolListResponse


@pytest.mark.api
@pytest.mark.smoke
@allure.epic("Market")
@allure.feature("API")
@allure.story("Pool List")
@allure.title("Pool list response matches Pydantic model")
@allure.severity(allure.severity_level.NORMAL)
@allure.link("https://api.ufarm.digital/api/v1/docs#/", name="Swagger")
def test_pools_list_validates_against_model(api_client):
    # Сортировка по valueManaged desc происходит на стороне UI, не API.
    # Этот тест проверяет, что структура ответа соответствует модели.

    with allure.step("Отправляем GET /pool?type=public&status=active&limit=500"):
        response = api_client.get(
            "/pool",
            params={"type": "public", "status": "active", "limit": 500},
        )

    with allure.step(f"Статус ответа == 200 (получен {response.status_code})"):
        assert response.status_code == 200

    with allure.step("Валидируем ответ через Pydantic-модель PoolListResponse"):
        pools = PoolListResponse.model_validate(response.json()).data
        allure.attach(
            json.dumps([{"pool": p.pool, "valueManaged": p.valueManaged, "status": p.status} for p in pools], indent=2),
            name="Pools",
            attachment_type=allure.attachment_type.JSON,
        )

    print(f"\n  Total pools: {len(pools)}")
    for pool in pools:
        print(f"    '{pool.pool}' | valueManaged={pool.valueManaged} | status={pool.status} | type={pool.type}")

    with allure.step(f"Список не пустой (найдено {len(pools)} пулов)"):
        assert len(pools) > 0, "Pool list must not be empty"

    with allure.step("Все valueManaged >= 0"):
        assert all(int(p.valueManaged) >= 0 for p in pools), "All valueManaged must be >= 0"


@pytest.mark.api
@pytest.mark.regression
@allure.epic("Market")
@allure.feature("API")
@allure.story("Pool List")
@allure.title("Pool list returns only active public pools with valid fields")
@allure.severity(allure.severity_level.NORMAL)
@allure.link("https://api.ufarm.digital/api/v1/docs#/", name="Swagger")
def test_pools_list_returns_active_public_pools(api_url):
    client = APIClient(api_url)

    with allure.step("Отправляем GET /pool?type=public&status=active&limit=500"):
        response = client.get(
            "/pool",
            params={"type": "public", "limit": 500, "status": "active"},
        )

    with allure.step(f"Статус ответа == 200 (получен {response.status_code})"):
        assert response.status_code == 200

    body = response.json()

    with allure.step("Тело ответа содержит ключ 'data' со списком пулов"):
        assert isinstance(body, dict)
        assert "data" in body
        pools = body["data"]
        assert isinstance(pools, list)
        assert len(pools) > 0

    print(f"\n  Total pools returned: {len(pools)}")
    for pool in pools:
        print(f"    '{pool['pool']}' | valueManaged={pool['valueManaged']} | status={pool['status']} | type={pool['type']}")

    with allure.step("Все valueManaged >= 0 и парсируются в int"):
        value_managed_list = [int(p["valueManaged"]) for p in pools]
        assert all(v >= 0 for v in value_managed_list)

    with allure.step("Каждый пул содержит обязательные поля и соответствует фильтрам"):
        for pool in pools:
            for key in (
                "id", "pool", "status", "type", "decimals",
                "poolAddress", "fundAddress", "valueManaged",
                "totalDeposited", "revenue", "fees", "limits",
                "poolMetric", "assetAllocation",
            ):
                assert key in pool

            assert pool["status"] == "active"
            assert pool["type"] == "public"
            assert isinstance(pool["pool"], str)
            assert isinstance(pool["decimals"], int)
            assert isinstance(pool["poolAddress"], str)
            assert isinstance(pool["fundAddress"], str)

            for numeric_str_key in ("valueManaged", "totalDeposited", "revenue"):
                assert isinstance(pool[numeric_str_key], str)
                int(pool[numeric_str_key])

            metric = pool["poolMetric"]
            assert isinstance(metric, dict)
            for key in ("nav", "blockNumber", "totalSupply", "tokenPrice", "customers", "deposits", "date"):
                assert key in metric

            asset_allocation = pool["assetAllocation"]
            assert isinstance(asset_allocation, list)
            assert len(asset_allocation) > 0
            for item in asset_allocation:
                for key in ("id", "tokenType", "asset", "balance", "value", "allocation", "extraInfo"):
                    assert key in item
