from core.api.client import APIClient
from core.api.models.pool import PoolDetailResponse


def test_pool_detail_returns_correct_structure(api_client, test_pool_id):
    response = api_client.get(f"/pool/{test_pool_id}")

    assert response.status_code == 200

    body = response.json()
    assert "pool" in body

    detail = PoolDetailResponse.model_validate(body)
    pool = detail.pool

    print(f"\n  Pool: '{pool.pool}' (id={pool.id})")
    print(f"  status={pool.status}, type={pool.type}, decimals={pool.decimals}")
    print(f"  poolAddress={pool.poolAddress}")
    print(f"  fundAddress={pool.fundAddress}")

    assert pool.id == test_pool_id, f"Expected id={test_pool_id}, got {pool.id}"
    assert pool.status == "active", f"Expected status=active, got {pool.status}"
    assert pool.type == "public", f"Expected type=public, got {pool.type}"
    assert pool.decimals > 0, f"Expected decimals > 0, got {pool.decimals}"
    assert pool.poolAddress.startswith("0x"), f"poolAddress must start with 0x: {pool.poolAddress}"
    assert pool.fundAddress.startswith("0x"), f"fundAddress must start with 0x: {pool.fundAddress}"


def test_pool_detail_financials_are_consistent(api_client, test_pool_id):
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

    assert value_managed >= 0, f"valueManaged must be >= 0, got {value_managed}"
    assert total_deposited >= 0, f"totalDeposited must be >= 0, got {total_deposited}"
    assert value_managed == total_deposited + revenue, (
        f"valueManaged ({value_managed}) != totalDeposited ({total_deposited}) + revenue ({revenue})"
    )

    metric = pool.poolMetric
    print(f"\n  poolMetric.nav         = {metric.nav}  (expected == valueManaged {value_managed})")
    print(f"  poolMetric.tokenPrice  = {metric.tokenPrice}")
    print(f"  poolMetric.totalSupply = {metric.totalSupply}")
    print(f"  poolMetric.customers   = {metric.customers}")

    assert int(metric.nav) == value_managed, (
        f"poolMetric.nav ({metric.nav}) != valueManaged ({value_managed})"
    )
    assert float(metric.tokenPrice) > 0, f"tokenPrice must be > 0, got {metric.tokenPrice}"
    assert int(metric.totalSupply) > 0, f"totalSupply must be > 0, got {metric.totalSupply}"
    assert metric.customers >= 0, f"customers must be >= 0, got {metric.customers}"


def test_pool_detail_asset_allocation_sums_to_100(api_client, test_pool_id):
    response = api_client.get(f"/pool/{test_pool_id}")
    pool = PoolDetailResponse.model_validate(response.json()).pool

    assert len(pool.assetAllocation) > 0, "assetAllocation is empty"

    print(f"\n  Pool: '{pool.pool}', assets: {len(pool.assetAllocation)}")
    total_allocation = 0.0
    for asset in pool.assetAllocation:
        print(f"    {asset.asset[:10]}... | tokenType={asset.tokenType} | allocation={asset.allocation}%")
        total_allocation += asset.allocation

    print(f"  Total allocation: {total_allocation:.2f}%  (expected 99–101%)")

    assert 99.0 <= total_allocation <= 101.0, (
        f"Asset allocation sum is {total_allocation:.2f}%, expected ~100%"
    )
