"""
Утилита для программного подключения кошелька в тестах Playwright.

Reown AppKit v4 + wagmi v2 хранит состояние подключения в памяти через
zustand-store внутри wagmi-конфига. localStorage-подход не работает,
поскольку connector UID генерируется случайно при каждой загрузке страницы
и не совпадает с тем, что закешировано в wagmi.store.

Рабочий подход — post-load injection:
  1. page.goto(...) + wait_for_load_state("networkidle")
  2. page.evaluate(INJECT_WALLET_JS, [address, chain_id])

Механизм:
  - Находим wagmi-конфиг через React Fiber (компонент с injected-connector
    и _internal.store.setState), используя поиск по структуре объекта,
    а не по минифицированному имени компонента.
  - Вызываем store.setState({ status: "connected", connections: Map(...) }).
  - Дополнительно эмитируем событие "connect" на emitter инжектированного
    коннектора — AppKit использует этот сигнал для обновления своего
    внутреннего состояния (баланс, ENS и т.д.).
  - React перерисовывает хедер: вместо "Connect Wallet" показывается адрес.

Ограничения:
  - Работает только для SPA-навигации внутри одной вкладки (без full reload).
  - После page.goto() на другой URL (full reload) нужно повторить инжекцию.
  - AppKit localStorage-ключ @appkit/connection_status остаётся "disconnected"
    (не критично: UI управляется состоянием wagmi store, а не localStorage).
  - Подписи транзакций невозможны — у нас нет реального приватного ключа.
"""

# Полный JavaScript для инжекции состояния подключённого кошелька.
# Вызывается через page.evaluate(INJECT_WALLET_JS, [address, chain_id]).
INJECT_WALLET_JS = """
([address, chainId]) => {
    chainId = chainId || 42161;

    // Находим wagmi-конфиг через React Fiber.
    // Используем поиск по структуре объекта, а не по минифицированному имени
    // компонента — это устойчиво к пересборкам бандла.
    var root = document.getElementById('root');
    if (!root) throw new Error('No #root element found');

    var fiberKey = Object.keys(root).find(function(k) {
        return k.startsWith('__reactContainer');
    });
    if (!fiberKey) throw new Error('No React fiber found on #root');

    var fiber = root[fiberKey];
    var wagmiConfig = null;
    var visited = 0;

    function walk(f, depth) {
        if (!f || visited > 2000 || depth > 300 || wagmiConfig) return;
        visited++;
        try {
            if (
                f.memoizedState &&
                f.memoizedState.queue &&
                f.memoizedState.memoizedState
            ) {
                var s = f.memoizedState.memoizedState;
                // Идентифицируем wagmi-конфиг по уникальной форме объекта
                if (
                    s.connectors &&
                    Array.isArray(s.connectors) &&
                    s._internal &&
                    s._internal.store &&
                    typeof s._internal.store.setState === 'function'
                ) {
                    wagmiConfig = s;
                    return;
                }
            }
        } catch (e) {}
        walk(f.child, depth + 1);
        walk(f.sibling, depth);
    }
    walk(fiber, 0);

    if (!wagmiConfig) {
        throw new Error(
            'wagmi config not found in React fiber tree. ' +
            'Make sure the page is fully loaded before calling injectWallet().'
        );
    }

    // Ищем injected-коннектор (MetaMask/Browser Wallet).
    // Если его нет — берём первый доступный.
    var connector = wagmiConfig.connectors.find(function(c) {
        return c.id === 'injected';
    }) || wagmiConfig.connectors[0];

    if (!connector) {
        throw new Error('No connectors found in wagmi config');
    }

    var connUid = connector.uid;

    // Шаг 1: Устанавливаем состояние wagmi store.
    // connections — это Map (zustand persist сериализует его через {__type: "Map"}).
    wagmiConfig._internal.store.setState({
        chainId: chainId,
        status: 'connected',
        current: connUid,
        connections: new Map([[connUid, {
            accounts: [address],
            chainId: chainId,
            connector: connector,
        }]]),
    });

    // Шаг 2: Уведомляем AppKit через внутренний эмиттер коннектора.
    // AppKit подписан на событие 'connect' для обновления своего состояния
    // (ENS-имя, баланс нативного токена, etc.).
    try {
        connector.emitter._emitter.emit('connect', {
            accounts: [address],
            chainId: chainId,
        });
    } catch (e) {
        // Некритично: UI обновляется через wagmi store независимо от AppKit.
    }

    return {
        success: true,
        address: address,
        chainId: chainId,
        connectorId: connector.id,
        connectorUid: connUid,
    };
}
"""


def inject_wallet(page, address: str, chain_id: int = 42161) -> dict:
    """Программно подключает кошелёк в wagmi/AppKit без реальной подписи.

    Должна вызываться после того, как страница полностью загружена
    (wait_for_load_state("networkidle")).

    Args:
        page: Playwright Page object.
        address: Ethereum-адрес кошелька (0x...).
        chain_id: ID сети (по умолчанию 42161 = Arbitrum One).

    Returns:
        dict с ключами success, address, chainId, connectorId, connectorUid.

    Raises:
        Exception: если wagmi config не найден или инжекция не удалась.

    Example::

        page.goto(f"{base_url}/marketplace", wait_until="networkidle")
        inject_wallet(page, "0xd2692CCEbC8d34EFd74185908956e5f75FF71cA3")
        # Хедер теперь показывает адрес вместо "Connect Wallet"
    """
    result = page.evaluate(INJECT_WALLET_JS, [address, chain_id])
    if not result or not result.get("success"):
        raise RuntimeError(f"inject_wallet failed: {result}")
    return result
