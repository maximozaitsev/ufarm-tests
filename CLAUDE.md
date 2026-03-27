# ufarm-tests

Проект автоматического тестирования DeFi-приложения Ufarm.
Подробный контекст: `TESTED_PROJECT_CONTEXT.md`
План тестирования: `TEST_PLAN.md`

## Принцип верификации финансовых данных

**Это DeFi-приложение — финансовые проверки должны быть независимыми, а не доверять API.**

- Балансы токенов → считать через on-chain JSON-RPC (`eth_call` / `eth_getBalance`), сверять с UI и API
- Агрегаты (MY INVESTMENTS, all-time profit, UF-POINTS) → считать самостоятельно из детальных источников (пул за пулом, транзакция за транзакцией), сверять с итоговым значением API и UI
- Нельзя брать значение из API и сравнивать его с UI — это проверяет только согласованность, но не корректность расчёта
- Допустимые отклонения должны быть обоснованы (округление, задержка индексации), а не взяты с запасом

## Стек

- Python 3.12+, pytest, Playwright (Chromium), requests, Pydantic, allure-pytest
- Виртуальное окружение: `.venv/` (не коммитится)

## Запуск тестов

```bash
# активировать venv
source .venv/bin/activate

# все тесты
pytest

# только API
pytest tests/api/ -v

# только UI
pytest tests/ui/ -v

# по маркам
pytest -m "api and smoke"
pytest -m "api and regression"
pytest -m "ui and smoke"

# с выводом print()
pytest tests/api/ -v -s

# с генерацией Allure-результатов (--clean-alluredir очищает старые результаты)
pytest tests/api/ -v --alluredir=allure-results --clean-alluredir
pytest tests/ui/ -v --alluredir=allure-results --clean-alluredir

# просмотр Allure-отчёта локально
allure serve allure-results

# UI-тесты в видимом браузере (для отладки)
HEADED=1 SLOWMO=800 pytest tests/ui/ -v -s

# Пошаговый дебаггер Playwright (Inspector)
PWDEBUG=1 pytest tests/ui/market/test_marketplace_no_wallet.py::test_pool_card_navigation -v -s
```

## Структура проекта

```
conftest.py               # фикстуры: api_client, leaderboard_api_client, browser, page,
                          #   page_with_wallet, page_with_wallet_on_pool,
                          #   page_with_wallet_on_single_token_pool,
                          #   page_with_no_eth_wallet_on_single_token_pool,
                          #   page_with_zero_wallet_on_min_deposit_pool (scope=module),
                          #   page_with_zero_wallet_on_pool,
                          #   pool_single_token_id, pool_min_deposit_id,
                          #   wallet_zero_balance, wallet_no_eth, wallet_active
                          # _mock_auth_connect() — мок GET /auth/connect/{addr} И
                          #   POST /user/verification до page.goto() (предотвращает Terms)
pytest.ini                # регистрация marks: api, ui, trx, smoke, regression, extended,
                          #   cross_verified (независимая верификация — вычисляем сами, не берём из API)
config/settings.py        # pydantic-settings, читает .env
core/
  api/
    client.py             # APIClient (get, post)
    models/
      pool.py             # Pool, PoolListResponse, PoolDetailResponse (poolMetric — Optional)
      portfolio.py        # Portfolio, PortfolioPool, PoolStat
      leaderboard.py      # LeaderboardItem, LeaderboardResponse
  ui/
    base_page.py
    wallet_injection.py   # inject_wallet(): React Fiber → wagmi store → connected state без модалки
    on_chain.py           # get_erc20_balance(): on-chain USDT/USDC баланс через JSON-RPC
    pages/
      marketplace_page.py # MarketplacePage: пул-карточки, хедер, кнопки Deposit/Withdraw
      deposit_modal.py    # DepositModal: инпут, MAX, gasless toggle, submit (#poolDepositConfirm),
                          #   token_selector() → [class*='current'], token_selector_arrow(),
                          #   current_token_ticker() → парсит [class*='balance'] p,
                          #   token_option(ticker), token_dropdown()
      withdraw_modal.py   # WithdrawModal: sellCoin/buyCoin инпуты, MAX, Request Withdrawal,
                          #   token_selector() → [class*='current'], token_selector_arrow(),
                          #   current_token_ticker() → [class*='ticker'], token_option(ticker)
      fund_wallet_modal.py # FundWalletModal: title, hint_text, buy crypto / receive funds
      kyt_modal.py        # KytBlockModal: heading ("Wallet verification issue"), close_button,
                          #   wait_opened(timeout)
      wallet_menu_modal.py # WalletMenuModal: адрес, балансы (USDT/USDC/ETH), кнопки
                          #   fund_wallet / send_nav / disconnect; sub-страницы:
                          #   buy_crypto (токен, сумма, buy_form_wallet_address, Continue),
                          #   receive_funds (QR canvas, copy_address),
                          #   send (token dropdown, amount, textarea To, Max, Send)
      portfolio_page.py   # PortfolioPage: /marketplace/my-portfolio;
                          #   wait_for() — ждёт заголовков + ненулевого MY INVESTMENTS (async load),
                          #   get_investments_usd() → Decimal (JS evaluate, class*=_usdt_),
                          #   get_uf_points() → int (JS evaluate, span UF-POINTS),
                          #   get_pool_vault_balances() → list[Decimal] (в порядке отображения),
                          #   headings: my_wallet, my_investments, all_time_profit
tests/
  api/                    # pytest.mark.api
    test_healthcheck.py
    test_pools_list.py
    test_pool_detail.py
    test_portfolio.py
    test_leaderboard.py   # структура, сортировка, пагинация, уникальность адресов
    test_points.py        # portfolio.points == leaderboard.points
  api/
    conftest.py           # leaderboard_reachable (skip при 403 от Cloudflare/CI IP-блокировки)
  ui/
    conftest.py           # screenshot_on_failure (autouse)
    market/               # pytest.mark.ui
      conftest.py         # pool_info_single_token, pool_info_multi_token, pool_info_min_deposit,
                          # wallet_usdt_balance, wallet_portfolio, network_name
                          # page_with_whale_wallet_on_min_deposit_pool (scope=module) —
                          #   Pool C + Binance hot wallet (_WHALE_WALLET, ~173M USDT),
                          #   скип если баланс < 5000 USDT
      test_marketplace_no_wallet.py   # smoke: загрузка, хедер, карточки, навигация, модалка
      test_marketplace_with_wallet.py # smoke: адрес в хедере, my-portfolio, deposit/withdraw кнопки,
                          #   кошелёк без депозитов не видит Withdraw, SPA-навигация
      test_deposit_modal.py           # smoke: Pool A + Pool B; токен-дропдаун; инпут суммы
                          #   (позитив/негатив); min deposit; Terms для нового пользователя
                          #   page_with_new_user_on_pool — локальная фикстура для теста Terms
                          #   _random_valid_deposit() — хелпер рандомной суммы (min_dep, balance)
      test_withdraw_modal.py          # smoke: Pool B + TEST_WALLET_ADDRESS; Pool A (withdraw)
                          #   токен-дропдаун; single-token без дропдауна
      test_fund_wallet_modal.py       # smoke: Pool C + WALLET_ZERO_BALANCE
      test_wallet_menu_modal.py       # smoke: модалка кошелька (открывается из хедера);
                          #   main page: адрес, балансы, кнопки; fund wallet: buy crypto,
                          #   receive funds; buy crypto: форма, Continue disabled до ввода,
                          #   Unlimit iframe (USDT + network); receive funds: QR, copy→clipboard;
                          #   send: форма (textarea To, Max), disabled/enabled кнопка
                          #   page_with_wallet_clipboard — локальная фикстура с clipboard-read/write
      test_kyc_kyt.py                 # smoke: Compliance KYT — мок POST /user/verification;
                          #   Pool A (minClientTier=10): passed, blocked, close, retry
                          #   Pool B (minClientTier=0): no-KYT любой tier → DEPOSIT
      test_portfolio_page.py          # smoke: страница My Portfolio + wallet_active;
                          #   cross_verified: Σ(balanceOf(pool) × tokenPrice) = API totalBalance = UI
                          #   структура Overview (3 карточки + realized/unrealized),
                          #   UF-POINTS в UI совпадают с API, сортировка карточек по vault balance
                          #   portfolio_onchain_breakdown — разбивка on-chain по пулам (session fixture)
                          #   portfolio.wait_for() ждёт ненулевого MY INVESTMENTS (async API load)
    fund/                 # тесты фонда (будущее)
scripts/
  dump_markup.py          # разведка: дампит HTML и PNG страниц (результат в scripts/markup/, gitignored)
```

## Переменные окружения

**`.env` (тестовые данные):**
```
TEST_POOL_ID=<uuid>              # Pool B — multi-token пул, minClientTier=0 (No KYT)
TEST_WALLET_ADDRESS=<0x...>      # WALLET_WITH_BALANCE — кошелёк с ненулевым балансом в Pool B
POOL_SINGLE_TOKEN_ID=<uuid>      # Pool A — single-token пул, minClientTier=10 (Strict KYT)
POOL_MIN_DEPOSIT_ID=<uuid>       # Pool C — пул с заметным min deposit
WALLET_ZERO_BALANCE=<0x...>      # кошелёк с балансом < min deposit Pool C
WALLET_NO_ETH=<0x...>            # кошелёк с небольшим USDT, но без ETH для газа
# WALLET_ACTIVE не обязателен — дефолт задан в settings.py (0x2AB1aB42...)
WALLET_ACTIVE=<0x...>            # активный кошелёк ручного тестирования: богатая история,
                                 # баланс постоянно меняется. Подходит для структуры портфолио
                                 # и реалтайм-расчётов. НЕ для проверок конкретных сумм.
```
`base_url`, `fund_url`, `api_url` имеют дефолты на DEMO — в CI не нужны.

**Env-переменные для запуска UI-тестов (не хранятся в файлах):**
| Переменная | Значение | Что делает |
|---|---|---|
| `HEADED` | `1` | Открывает браузер (не headless) |
| `SLOWMO` | мс, напр. `800` | Замедляет каждое действие Playwright |
| `PWDEBUG` | `1` | Открывает Playwright Inspector (пошаговый дебаггер) |

## Окружения

| Флаг | UI | API |
|---|---|---|
| `--env demo` (default) | app.demo.ufarm.digital | api.demo.ufarm.digital/api/v1 |
| `--env prod_arb` | app.ufarm.digital | api.ufarm.digital/api/v1 |
| `--env prod_eth` | black.ufarm.digital | api.ufarm.digital/api/v2 |

Тесты лидерборда и поинтов используют фикстуру `leaderboard_api_client` — всегда `api.ufarm.digital/api/v2`, независимо от `--env`.

## Allure-разметка (соглашение)

- `@allure.epic` — модуль: `"Market"` или `"Fund"`
- `@allure.feature` — тип тестов: `"API"` или `"UI"`
- `@allure.story` — конкретная фича: `"Leaderboard"`, `"Deposit"` и т.д.
- Все три декоратора + `@allure.title` — **английский**
- `with allure.step(...)` — **русский**, содержит конкретные значения
- `@allure.severity` — CRITICAL для финансовых инвариантов, NORMAL для структуры
- `@allure.link` — ссылка на Swagger
- `@allure.tag("cross-verified: on-chain")` + `@pytest.mark.cross_verified` — тесты где ожидаемое значение вычислено независимо (on-chain / per-item), а не взято из API. Запуск: `pytest -m cross_verified`

## Скриншоты в Allure (UI-тесты)

**При падении** — автоматически, ничего делать не нужно (`tests/ui/conftest.py`, фикстура `screenshot_on_failure`).

**В конкретном шаге вручную** (например после открытия модалки):
```python
with allure.step("Открылась модалка"):
    modal.wait_for(state="visible", timeout=5_000)
    allure.attach(page.screenshot(), name="Modal opened", attachment_type=allure.attachment_type.PNG)
    assert modal.is_visible()
```

## CI/CD

GitHub Actions, только ручной запуск (`workflow_dispatch`).
Параметры: `test_type` (api/ui/trx/all), `test_suite` (smoke/regression/extended/all), `environment` (demo).
Secrets: `TEST_POOL_ID`, `TEST_WALLET_ADDRESS`, `POOL_SINGLE_TOKEN_ID`, `POOL_MIN_DEPOSIT_ID`, `WALLET_ZERO_BALANCE`.
Allure-отчёт → GitHub Pages (ветка `gh-pages`).

## Инжекция кошелька (UI-тесты с wallet)

Используется `core/ui/wallet_injection.py` — обходит Reown-модалку через React Fiber:
1. После `page.goto(..., wait_until="networkidle")` вызывается `inject_wallet(page, address)`
2. Функция находит wagmi-конфиг в дереве React Fiber через `document.getElementById('root').__reactContainer*`
3. Вызывает `wagmiConfig._internal.store.setState({ status: "connected", connections: Map(...) })`
4. Хедер перерисовывается: вместо "Connect Wallet" отображается адрес кошелька

Фикстуры в `conftest.py` и `tests/ui/market/conftest.py`:
- `page_with_wallet` — открывает `/marketplace`, инжектирует кошелёк. Для тестов на главной и SPA-навигации.
- `page_with_wallet_on_pool` — открывает `/marketplace/pool/{TEST_POOL_ID}` (Pool B), инжектирует кошелёк, ждёт `networkidle`. Для тестов Deposit/Withdraw модалок (кошелёк с ненулевым балансом).
- `page_with_wallet_on_single_token_pool` — открывает `/marketplace/pool/{POOL_SINGLE_TOKEN_ID}` (Pool A). TEST_WALLET_ADDRESS имеет депозит в Pool A → видна кнопка Withdraw.
- `page_with_zero_wallet_on_min_deposit_pool` — Pool C + WALLET_ZERO_BALANCE. **scope=module**. Для тестов Fund wallet modal.
- `page_with_zero_wallet_on_pool` — Pool B + WALLET_ZERO_BALANCE. Для проверки что Withdraw кнопка не появляется без депозитов.
- `page_with_no_eth_wallet_on_single_token_pool` — Pool A + WALLET_NO_ETH (есть USDT, нет ETH). Для теста gasless toggle locked when no ETH.
- `page_with_whale_wallet_on_min_deposit_pool` (market conftest, scope=module) — Pool C + Binance hot wallet (`0xF977814e...`, ~173M USDT). Для теста `deposit_below_min_deposit`. Проверяет баланс при старте, скипает если < 5000 USDT.
- `page_on_portfolio` (локальная в `test_portfolio_page.py`, scope=module) — открывает `/marketplace`, инжектирует `wallet_active`, SPA-навигация на `/my-portfolio`, ждёт `portfolio.wait_for()` (заголовки + ненулевой MY INVESTMENTS).

**Почему scope=module для Pool C:** Pool C делает долгие polling-запросы (networkidle недостижим). Первый клик Deposit занимает ~15 сек (on-chain RPC). Module-scope позволяет загрузить страницу и прогреть кеш балансов один раз на все 7 тестов.

**Важно:** inject_wallet выполняется ПОСЛЕ `page.goto()` на нужную страницу. `page.goto()` вызывает полный reload — состояние wagmi store сбрасывается. Поэтому нельзя инжектировать на `/marketplace` и потом делать `page.goto(pool_url)` — кошелёк потеряется.

**Terms (PROOF OF AGREEMENT):** появляется когда `auth/connect` возвращает `createdAt: null` (новый пользователь) или `user/verification` возвращает ошибку. `_mock_auth_connect()` мокает оба эндпоинта до `page.goto()` — Terms гарантированно не появляются в обычных тестах. Для теста что Terms появляется используется `page_with_new_user_on_pool` (локальная фикстура в `test_deposit_modal.py`) с обратными моками.

**KYT-мокирование (тесты Compliance):** Используется Playwright LIFO route stacking. `_mock_auth_connect()` регистрирует базовый мок `POST /user/verification → tier=10`. Тест вызывает `_override_verification_tier(page, tier=N)` после `page.goto()` — это регистрирует ещё один handler для того же паттерна. Playwright вызывает handlers в порядке LIFO: переопределённый handler вызывается первым и вызывает `route.fulfill()`, останавливая цепочку. Базовый мок фикстуры не вызывается. Это позволяет задать любой tier без изменения фикстур.

**Настройки Compliance пулов:**
- Pool A (POOL_SINGLE_TOKEN_ID) — `minClientTier=10` (Strict KYT)
- Pool B (TEST_POOL_ID) — `minClientTier=0` (No KYT — любой кошелёк)
- Pool C (POOL_MIN_DEPOSIT_ID) — `minClientTier=0` (No KYT)

**Wallet Menu Modal (модалка кошелька):**
Открывается кликом на `#connectWallet` в хедере (в connected-состоянии). Корневой селектор — `[data-modal-content='true']` (стабильный data-атрибут, отличает от mantine deposit/withdraw модалок).

Нюансы реализации:
- **Disconnect** не работает с inject_wallet — коннектор не реализует disconnect(). Кнопка визуально присутствует, но wagmi state не сбрасывается.
- **Поле адреса получателя в Send** — `<textarea>`, не `<input>`. Используется `textarea[placeholder*='Address on']`.
- **MAX кнопка в Send** — текст `"Max"` (не `"MAX"`), кнопка Submit — `"Send"` (не `"SEND"`).
- **Кнопка Continue в buy crypto** — текст `"Continue"` (с заглавной), disabled пока инпут пустой.
- **Инпут суммы** в buy crypto и send — `input.mantine-NumberInput-input` (не `input` first, который находит скрытый switch из Mantine).
- **Unlimit виджет** загружается в `<iframe src="https://onramp.crypto.unlimit.com/?ucMode=SDK">` внутри `#gatefi-widget`. Playwright обходит cross-origin ограничения через CDP — используется `page.frame_locator("#gatefi-widget iframe")`. "USDT" и сеть ищутся напрямую в iframe, не через "You get" текст (тот содержит только лейбл без дочерних элементов).
- **Clipboard тесты** требуют отдельной фикстуры с `browser.new_context(permissions=["clipboard-read", "clipboard-write"])` — permissions нельзя добавить к уже созданному контексту.

**KYC-тесты (minClientTier=20):** отложены — требуют wallet signing. Когда пул требует tier=20, при tier<20 приложение показывает Terms (PROOF OF AGREEMENT), которые нельзя принять без подписи кошелька. inject_wallet не поддерживает signing.

**Что не работает** (задокументировано в `wallet_injection.py`):
- `window.ethereum` mock + `add_init_script` — AppKit не читает провайдер автоматически
- Pre-populate localStorage — wagmi сбрасывает состояние (UID коннектора генерируется случайно)
- Модальный UI-флоу — MetaMask показывает QR, Browser Wallet не обнаруживается в headless Chromium

## Независимость тестов (Test Isolation)

**Каждый UI-тест должен быть независим от остальных** — проходить в любом порядке, в любой комбинации, в полном suite.

### Как обеспечивается изоляция

**Браузерный контекст** — каждая фикстура создаёт изолированный контекст через `browser.new_context()`, а не `browser.new_page()`:
```python
context = browser.new_context()  # ← изолированный контекст
page = context.new_page()
...
yield page
context.close()  # ← закрывает и страницу, и контекст
```
`new_page()` создаёт страницу в **общем дефолтном контексте** браузера — все тесты делят localStorage, cookies и sessionStorage. `new_context()` даёт каждому тесту собственное окружение, полностью изолированное от других.

**Reown modal race condition** — после `inject_wallet()` Reown кратковременно (~100–200 мс) открывает overlay, пока reconcile-ит wallet connection state. `wait_for_pool_page()` явно ждёт исчезновения `.mantine-Modal-overlay` перед возвратом — иначе тест, запущенный в прогретой JVM после других тестов, кликает кнопку в этом окне и получает `overlay intercepts pointer events`.

**Мутации бэкенда** — нельзя кликать кнопки submit (Deposit, Request Withdrawal) в gasless-режиме без реальной подписи. Gasless-транзакция уходит на бэкенд с `signature=0x0` (мок) и создаёт `pending`-запись, которая заставляет приложение **автоматически открывать модалку** при следующей загрузке страницы с тем же кошельком — все последующие тесты падают. Тесты `test_deposit_triggers_signing` / `test_withdraw_triggers_signing` проверяют только что кнопка стала активной, без реального клика.

### Диагностика если тесты снова начнут падать в связке

1. Запустить подозрительный тест изолированно — если проходит, проблема в order-dependency.
2. Добавить `SLOWMO=200` ко всему suite — если проходит, проблема в timing (race condition).
3. Добавить `SLOWMO=200` только к подозрительному тесту и сравнить.
4. Проверить что фикстуры используют `browser.new_context()`, а не `browser.new_page()`.
5. Проверить что ни один тест не кликает submit-кнопки в gasless-режиме.

## Текущий статус

- [x] Шаг 1: API-тесты (healthcheck, pool list, pool detail, portfolio)
- [x] Шаг 1.5: API-тесты лидерборда и поинтов (leaderboard structure/sort/pagination, points cross-validation)
- [x] Шаг 2: UI-тесты без кошелька (marketplace load, header, pool cards, navigation, pool page, portfolio tab)
- [x] Шаг 3: UI-тесты с мок-кошельком — базовые (адрес в хедере, my-portfolio, deposit/withdraw кнопки)
- [x] Шаг 3.5: UI-тесты модалок депозита (Pool A + Pool B), вывода (Pool B), Fund wallet (Pool C)
- [x] Шаг 3.6: UI-тесты Compliance KYT (Pool A minClientTier=10, Pool B minClientTier=0) — мок верификации
- [x] Шаг 3.7: UI-тесты модалки кошелька (Wallet Menu Modal) — адрес/балансы, fund wallet flow, buy crypto + Unlimit widget, receive funds + clipboard, send form validation
- [x] Шаг 3.8: UI-тесты страницы My Portfolio — cross-verified: on-chain Σ(LP×tokenPrice) = API = UI; структура Overview; UF-POINTS; сортировка карточек
- [ ] Шаг 4: UI-тесты on-chain транзакций (signing flow, верификация через API)
- [ ] Шаг 5: TRX-тесты (on-chain транзакции)
