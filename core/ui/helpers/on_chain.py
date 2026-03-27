"""
Получение on-chain балансов ERC20-токенов через публичный Arbitrum RPC.

Использует прямые JSON-RPC вызовы (без дополнительных зависимостей, только requests).
"""
from decimal import Decimal

import requests

ARB_MAINNET_RPC = "https://arb1.arbitrum.io/rpc"

# Arbitrum One ERC20 token contracts
USDT_ARB = "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9"
USDC_ARB = "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"

# Символ → адрес контракта на Arbitrum
TOKEN_CONTRACTS_ARB: dict[str, str] = {
    "usdt": USDT_ARB,
    "usdc": USDC_ARB,
}


def get_erc20_balance(
    wallet: str,
    token_contract: str,
    rpc_url: str = ARB_MAINNET_RPC,
    decimals: int = 6,
) -> Decimal:
    """Возвращает баланс ERC20-токена как Decimal с учётом decimals.

    Пример::

        from core.ui.helpers.on_chain import get_erc20_balance, USDT_ARB
        balance = get_erc20_balance("0xabc...", USDT_ARB)
        # Decimal("2.027758")
    """
    # balanceOf(address) selector = keccak256("balanceOf(address)")[:4] = 0x70a08231
    padded_address = wallet[2:].lower().zfill(64)
    data = f"0x70a08231{padded_address}"
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{"to": token_contract, "data": data}, "latest"],
        "id": 1,
    }
    resp = requests.post(rpc_url, json=payload, timeout=15)
    resp.raise_for_status()
    result = resp.json()["result"]
    raw = int(result, 16)
    return Decimal(raw) / Decimal(10 ** decimals)
