from core.api.client import APIClient
from core.api.models.pool import PoolListResponse


def test_pools_list_validates_against_model(api_client):
    # Сортировка по valueManaged desc происходит на стороне UI, не API.
    # Этот тест проверяет, что структура ответа соответствует модели.
    response = api_client.get(
        "/pool",
        params={"type": "public", "status": "active", "limit": 500},
    )

    assert response.status_code == 200

    pools = PoolListResponse.model_validate(response.json()).data

    print(f"\n  Total pools: {len(pools)}")
    for pool in pools:
        print(f"    '{pool.pool}' | valueManaged={pool.valueManaged} | status={pool.status} | type={pool.type}")

    assert len(pools) > 0, "Pool list must not be empty"
    assert all(int(p.valueManaged) >= 0 for p in pools), "All valueManaged must be >= 0"


def test_pools_list_returns_active_public_pools(api_url):
    client = APIClient(api_url)

    response = client.get(
        "/pool",
        params={
            "type": "public",
            "limit": 500,
            "status": "active",
        },
    )

    assert response.status_code == 200

    body = response.json()
    assert isinstance(body, dict)
    assert "data" in body
    pools = body["data"]
    assert isinstance(pools, list)
    assert len(pools) > 0

    print(f"\n  Total pools returned: {len(pools)}")
    for pool in pools:
        print(f"    '{pool['pool']}' | valueManaged={pool['valueManaged']} | status={pool['status']} | type={pool['type']}")

    # собираем список valueManaged и убеждаемся, что значения корректные (положительные int)
    value_managed_list = [int(p["valueManaged"]) for p in pools]
    assert all(v >= 0 for v in value_managed_list)

    for pool in pools:
        # базовые обязательные поля
        for key in (
            "id",
            "pool",
            "status",
            "type",
            "decimals",
            "poolAddress",
            "fundAddress",
            "valueManaged",
            "totalDeposited",
            "revenue",
            "fees",
            "limits",
            "poolMetric",
            "assetAllocation",
        ):
            assert key in pool

        # инварианты по фильтрам
        assert pool["status"] == "active"
        assert pool["type"] == "public"

        # типы для некоторых полей
        assert isinstance(pool["pool"], str)
        assert isinstance(pool["decimals"], int)
        assert isinstance(pool["poolAddress"], str)
        assert isinstance(pool["fundAddress"], str)

        # числовые поля приходят строками, но должны быть парсабельны в int
        for numeric_str_key in ("valueManaged", "totalDeposited", "revenue"):
            assert isinstance(pool[numeric_str_key], str)
            int(pool[numeric_str_key])

        # структура метрик пула
        metric = pool["poolMetric"]
        assert isinstance(metric, dict)
        for key in (
            "nav",
            "blockNumber",
            "totalSupply",
            "tokenPrice",
            "customers",
            "deposits",
            "date",
        ):
            assert key in metric

        # структура аллокаций
        asset_allocation = pool["assetAllocation"]
        assert isinstance(asset_allocation, list)
        assert len(asset_allocation) > 0
        for item in asset_allocation:
            for key in ("id", "tokenType", "asset", "balance", "value", "allocation", "extraInfo"):
                assert key in item

