"""
Реальный EIP-1193 Ethereum-провайдер для транзакционных UI-тестов.

Инжектирует в браузер кастомный window.ethereum, который:
  - Возвращает адрес тестового кошелька для eth_accounts / eth_requestAccounts
  - Подписывает и отправляет транзакции через Python (eth_account + Arbitrum RPC)
  - Поддерживает eth_estimateGas, eth_getTransactionReceipt и базовые eth_call
  - Подписывает EIP-712 сообщения (gasless: personal_sign + eth_signTypedData_v4)

Взаимодействие Python ↔ JS:
  Playwright page.expose_function() делает Python-callback доступным из JS как async-функция.
  JS-провайдер вызывает window.__eth_rpc(method, params) → Python отправляет JSON-RPC на Arbitrum.
  JS-провайдер вызывает window.__eth_sign_and_send(txParams) → Python подписывает + отправляет tx.
  JS-провайдер вызывает window.__eth_personal_sign(params) → Python подписывает EIP-191.
  JS-провайдер вызывает window.__eth_sign_typed_data(addr, data) → Python подписывает EIP-712.

Перехват wagmi publicClient:
  wagmi's read-only publicClient делает прямые HTTP-запросы к arbitrum-one-rpc.publicnode.com,
  минуя window.ethereum. Этот endpoint медленный (~60s) из браузера.
  page.route() перехватывает эти запросы и проксирует через Python (быстрый RPC).
  Важно: JSON-RPC id из запроса сохраняется в ответе — иначе wagmi отбросит ответ.

Использование::

    from core.ui.helpers.trx_provider import inject_trx_provider, wait_for_tx

    inject_trx_provider(page, private_key="0x...", rpc_url=ARB_RPC)
    page.goto(url, wait_until="networkidle")
    # ... взаимодействие с UI, отправка транзакции ...
    tx_hash = page.evaluate("window.__last_tx_hash")
    wait_for_tx(tx_hash)

Ограничения:
  - Не переключает сети (chainId зафиксирован — Arbitrum One 0xa4b1).
"""
import json
import time

import requests
from eth_account import Account
from eth_account.messages import encode_defunct, encode_typed_data
from eth_account.signers.local import LocalAccount

ARB_MAINNET_RPC = "https://arb1.arbitrum.io/rpc"
ARB_CHAIN_ID = 42161


def _rpc(method: str, params: list, rpc_url: str) -> dict:
    resp = requests.post(
        rpc_url,
        json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def inject_trx_provider(
    page,
    private_key: str,
    rpc_url: str = ARB_MAINNET_RPC,
) -> LocalAccount:
    """Инжектирует реальный Ethereum-провайдер в браузерную страницу.

    Должен вызываться ДО page.goto() — add_init_script и expose_function
    применяются только к следующей загрузке страницы.

    Возвращает eth_account.LocalAccount для использования в тестах
    (например, для проверки адреса или подписи вне браузера).

    Args:
        page: Playwright Page
        private_key: приватный ключ тестового кошелька (hex, без 0x или с 0x)
        rpc_url: JSON-RPC endpoint (по умолчанию Arbitrum Mainnet)
    """
    account: LocalAccount = Account.from_key(private_key)
    address = account.address

    # ── Python-side RPC proxy (expose_function) ────────────────────────────
    # JS вызывает window.__eth_rpc(method, params_json) → Python отправляет
    # запрос на Arbitrum и возвращает result.

    def _py_rpc(method: str, params_json: str) -> str:
        params = json.loads(params_json)
        result = _rpc(method, params, rpc_url)
        if "error" in result:
            raise RuntimeError(result["error"]["message"])
        return json.dumps(result["result"])

    # ── Python-side transaction signer (expose_function) ───────────────────
    # JS вызывает window.__eth_sign_and_send(tx_params_json) → Python
    # заполняет пустые поля, подписывает и отправляет raw tx.

    def _py_sign_and_send(tx_params_json: str) -> str:
        tx_params = json.loads(tx_params_json)

        # Получаем nonce
        nonce_result = _rpc("eth_getTransactionCount", [address, "latest"], rpc_url)
        nonce = int(nonce_result["result"], 16)

        # Получаем gas price
        gas_price_result = _rpc("eth_gasPrice", [], rpc_url)
        gas_price = int(gas_price_result["result"], 16)
        # +10% для надёжности прохождения
        gas_price = int(gas_price * 1.1)

        # Оцениваем gas limit
        gas_estimate_result = _rpc(
            "eth_estimateGas",
            [{"from": address, "to": tx_params["to"], "data": tx_params.get("data", "0x")}],
            rpc_url,
        )
        gas_limit = int(int(gas_estimate_result["result"], 16) * 1.2)

        tx = {
            "nonce": nonce,
            "gasPrice": gas_price,
            "gas": gas_limit,
            "to": tx_params["to"],
            "value": int(tx_params.get("value", "0x0"), 16),
            "data": tx_params.get("data", "0x"),
            "chainId": ARB_CHAIN_ID,
        }

        signed = account.sign_transaction(tx)
        raw_hex = "0x" + signed.raw_transaction.hex()

        send_result = _rpc("eth_sendRawTransaction", [raw_hex], rpc_url)
        if "error" in send_result:
            raise RuntimeError(send_result["error"]["message"])
        return send_result["result"]  # txHash

    # ── Python-side personal_sign (expose_function) ───────────────────────
    # JS вызывает window.__eth_personal_sign(params_json) → Python подписывает
    # сообщение с EIP-191 префиксом (\x19Ethereum Signed Message:\n).

    def _py_personal_sign(params_json: str) -> str:
        params = json.loads(params_json)
        # MetaMask convention: personal_sign(message_hex, address)
        msg_hex = params[0]
        signed = account.sign_message(encode_defunct(hexstr=msg_hex))
        return "0x" + signed.signature.hex()

    # ── Python-side eth_signTypedData_v4 (expose_function) ────────────────
    # JS вызывает window.__eth_sign_typed_data(address, typed_data_json) →
    # Python подписывает EIP-712 structured data.

    def _py_sign_typed_data(address_arg: str, typed_data_json: str) -> str:
        data = json.loads(typed_data_json)
        signed = account.sign_message(encode_typed_data(full_message=data))
        return "0x" + signed.signature.hex()

    page.expose_function("__eth_rpc", _py_rpc)
    page.expose_function("__eth_sign_and_send", _py_sign_and_send)
    page.expose_function("__eth_personal_sign", _py_personal_sign)
    page.expose_function("__eth_sign_typed_data", _py_sign_typed_data)

    # ── Intercept wagmi publicClient RPC calls ─────────────────────────────
    # wagmi's read-only publicClient makes direct HTTP calls to its configured
    # RPC endpoint (arbitrum-one-rpc.publicnode.com), bypassing window.ethereum.
    # This endpoint is often very slow (~60s) from the browser. We intercept
    # these calls and proxy them through Python (using a faster RPC endpoint).
    #
    # Critical: preserve the JSON-RPC "id" from the original request.
    # If we return a response with a different id, wagmi's JSON-RPC client
    # discards it and waits indefinitely (the original bug was id always = 1).

    def _handle_node_rpc_route(route) -> None:
        try:
            body = json.loads(route.request.post_data or "{}")
            if isinstance(body, list):
                # Batch JSON-RPC request
                results = []
                for req in body:
                    r = _rpc(req.get("method", "eth_blockNumber"), req.get("params", []), rpc_url)
                    r["id"] = req.get("id", 1)
                    results.append(r)
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(results),
                )
            else:
                result = _rpc(body.get("method", "eth_blockNumber"), body.get("params", []), rpc_url)
                result["id"] = body.get("id", 1)
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(result),
                )
        except Exception as exc:
            # Ignore errors when page/context is already closed (teardown race)
            try:
                route.fulfill(status=500, body=str(exc))
            except Exception:
                pass

    page.route("https://arbitrum-one-rpc.publicnode.com/**", _handle_node_rpc_route)

    # ── JS: window.ethereum provider ──────────────────────────────────────
    provider_js = f"""
    (function() {{
        const ADDRESS = '{address}';
        const CHAIN_ID = '0xa4b1';
        const NETWORK_VERSION = '42161';

        const _listeners = {{}};

        window.ethereum = {{
            isMetaMask: true,
            isConnected: () => true,
            selectedAddress: ADDRESS,
            networkVersion: NETWORK_VERSION,
            chainId: CHAIN_ID,
            __lastTxHash: null,

            request: async function({{ method, params = [] }}) {{
                switch (method) {{
                    case 'eth_requestAccounts':
                    case 'eth_accounts':
                        return [ADDRESS];

                    case 'eth_chainId':
                        return CHAIN_ID;

                    case 'net_version':
                        return NETWORK_VERSION;

                    case 'eth_sendTransaction': {{
                        const txHash = await window.__eth_sign_and_send(
                            JSON.stringify(params[0])
                        );
                        window.ethereum.__lastTxHash = txHash;
                        window.__last_tx_hash = txHash;
                        return txHash;
                    }}

                    case 'personal_sign': {{
                        return await window.__eth_personal_sign(JSON.stringify(params));
                    }}

                    case 'eth_signTypedData_v4': {{
                        return await window.__eth_sign_typed_data(params[0], params[1]);
                    }}

                    default:
                        // Проксируем всё остальное через Python → Arbitrum RPC
                        const result = await window.__eth_rpc(
                            method,
                            JSON.stringify(params)
                        );
                        return JSON.parse(result);
                }}
            }},

            on: function(event, callback) {{
                if (!_listeners[event]) _listeners[event] = [];
                _listeners[event].push(callback);
            }},

            removeListener: function(event, callback) {{
                if (_listeners[event]) {{
                    _listeners[event] = _listeners[event].filter(cb => cb !== callback);
                }}
            }},

            emit: function(event, ...args) {{
                (_listeners[event] || []).forEach(cb => cb(...args));
            }},
        }};

        // Уведомляем wagmi/AppKit о появлении провайдера
        window.dispatchEvent(new Event('ethereum#initialized'));
    }})();
    """

    page.add_init_script(provider_js)

    return account


def wait_for_tx(
    tx_hash: str,
    rpc_url: str = ARB_MAINNET_RPC,
    timeout: int = 30,
    poll_interval: float = 1.0,
) -> dict:
    """Ждёт подтверждения транзакции и возвращает receipt.

    Args:
        tx_hash: хэш транзакции (0x...)
        rpc_url: JSON-RPC endpoint
        timeout: максимальное время ожидания в секундах
        poll_interval: интервал проверки в секундах

    Raises:
        TimeoutError: если транзакция не подтверждена за timeout секунд
        RuntimeError: если транзакция reverted (status=0x0)
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = _rpc("eth_getTransactionReceipt", [tx_hash], rpc_url)
        receipt = result.get("result")
        if receipt is not None:
            if receipt["status"] == "0x0":
                raise RuntimeError(f"Transaction reverted: {tx_hash}")
            return receipt
        time.sleep(poll_interval)
    raise TimeoutError(f"Transaction {tx_hash} not confirmed in {timeout}s")


def get_erc20_balance_raw(wallet: str, token: str, rpc_url: str = ARB_MAINNET_RPC) -> int:
    """Возвращает raw (без деления на decimals) ERC20 баланс кошелька."""
    padded = wallet[2:].lower().zfill(64)
    result = _rpc("eth_call", [{"to": token, "data": f"0x70a08231{padded}"}, "latest"], rpc_url)
    return int(result["result"], 16)
