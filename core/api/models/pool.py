from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel


class PoolFees(BaseModel):
    management: int
    performance: str


class PoolLimits(BaseModel):
    deposit_min: str
    withdraw_delay: int
    deposit_approve: str
    withdraw_lockup: int


class PoolMetric(BaseModel):
    nav: str
    blockNumber: int
    totalSupply: str
    tokenPrice: float
    customers: int
    deposits: str
    date: str


class AssetAllocationToken(BaseModel):
    token: str
    value: float


class AssetAllocationExtraInfo(BaseModel):
    token0: Optional[str] = None
    value0: Optional[float] = None
    token1: Optional[str] = None
    value1: Optional[float] = None
    poolAddress: Optional[str] = None
    tickLower: Optional[int] = None
    tickUpper: Optional[int] = None
    project_id: Optional[str] = None
    adapter_id: Optional[str] = None
    fee: Optional[Any] = None
    tokens: Optional[list[AssetAllocationToken]] = None


class AssetAllocation(BaseModel):
    id: str
    tokenType: str
    asset: str
    tokenId: Optional[Any] = None
    balance: str
    value: str
    allocation: float
    extraInfo: AssetAllocationExtraInfo


class Pool(BaseModel):
    id: str
    pool: str
    logo: Optional[str] = None
    minClientTier: Optional[int] = None
    targetApy: Optional[float] = None
    availableValueTokens: Optional[list[str]] = None
    description: Optional[dict[str, str]] = None
    customers: int
    valueManaged: str
    totalDeposited: str
    revenue: str
    maxDrawdown: Optional[float] = None
    returnRisk: Optional[float] = None
    riskFactor: Optional[str] = None
    dayReturn: Optional[float] = None
    weekReturn: Optional[float] = None
    monthReturn: Optional[float] = None
    sixMonthReturnEst: Optional[float] = None
    yearReturnEst: Optional[float] = None
    yearToDate: Optional[float] = None
    fundShare: Optional[float] = None
    fees: PoolFees
    limits: PoolLimits
    status: str
    type: str
    decimals: int
    poolAddress: str
    poolAdminAddress: Optional[str] = None
    fundAddress: str
    poolMetric: Optional[PoolMetric] = None
    assetAllocation: list[AssetAllocation]
    createdAt: Optional[str] = None
    strategyLaunched: Optional[str] = None


class PoolListResponse(BaseModel):
    data: list[Pool]


class PoolDetailResponse(BaseModel):
    pool: Pool
