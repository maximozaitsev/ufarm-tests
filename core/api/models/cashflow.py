"""Модели ответа API для cashflow (история транзакций пула).

Endpoint: GET /pool/{poolAddress}/transactions/cashflows
Query params: investorAddress, type (Deposit|Withdrawal), limit, page
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class CashflowItem(BaseModel):
    id: str
    requestHash: Optional[str] = None
    poolAddress: str
    tokenAddresses: list[str] = []
    date: str
    type: str          # "Deposit" | "Withdrawal"
    poolTokens: str    # кол-во LP-токенов (строка, напр. "0.5")
    totalValue: str    # сумма в базовом токене (строка)
    investorAddress: str
    status: str        # "Completed" | "Pending" | ...
    blockNumber: Optional[int] = None
    tokenAmounts: Optional[list[Any]] = None
    approvedBy: Optional[Any] = None
    limit: Optional[Any] = None


class CashflowResponse(BaseModel):
    data: list[CashflowItem]
    count: int
    page: int
    total: int
    pageCount: int
