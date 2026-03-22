from __future__ import annotations

from pydantic import BaseModel
from core.api.models.pool import Pool


class PoolStat(BaseModel):
    allDeposited: str
    allWithdrawals: str
    realizedPnL: str
    unrealizedPnL: str
    totalBalance: str


class PortfolioPool(Pool):
    poolStat: PoolStat


class Portfolio(BaseModel):
    allDeposited: str
    allWithdrawals: str
    realizedPnL: str
    unrealizedPnL: str
    totalBalance: str
    points: float
    pools: list[PortfolioPool]
