from __future__ import annotations

from pydantic import BaseModel


class LeaderboardItem(BaseModel):
    userAddress: str
    points: float


class LeaderboardResponse(BaseModel):
    data: list[LeaderboardItem]
    total: int
    count: int
    page: int
    pageCount: int
