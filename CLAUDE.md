# ufarm-tests

Проект автоматического тестирования DeFi-приложения Ufarm.
Подробный контекст: `TESTED_PROJECT_CONTEXT.md`
План тестирования: `TEST_PLAN.md`

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
                          #   page_with_zero_wallet_on_min_deposit_pool (scope=module),
                          #   pool_single_token_id, pool_min_deposit_id, wallet_zero_balance
                          # _mock_auth_connect() — мок GET /auth/connect/{addr} до page.goto()
pytest.ini                # регистрация marks: api, ui, trx, smoke, regression, extended
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
      deposit_modal.py    # DepositModal: инпут, MAX, gasless toggle, submit (#poolDepositConfirm)
      withdraw_modal.py   # WithdrawModal: sellCoin/buyCoin инпуты, MAX, Request Withdrawal
      fund_wallet_modal.py # FundWalletModal: title, hint_text, buy crypto / receive funds
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
      test_marketplace_no_wallet.py   # smoke: загрузка, хедер, карточки, навигация, модалка
      test_marketplace_with_wallet.py # smoke: адрес в хедере, my-portfolio, deposit/withdraw кнопки
      test_deposit_modal.py           # smoke: Pool A (single-token) + Pool B (multi-token)
      test_withdraw_modal.py          # smoke: Pool B + TEST_WALLET_ADDRESS (кошелёк с балансом)
      test_fund_wallet_modal.py       # smoke: Pool C + WALLET_ZERO_BALANCE
    fund/                 # тесты фонда (будущее)
scripts/
  dump_markup.py          # разведка: дампит HTML и PNG страниц (результат в scripts/markup/, gitignored)
```

## Переменные окружения

**`.env` (тестовые данные):**
```
TEST_POOL_ID=<uuid>              # Pool B — multi-token пул, кошелёк с балансом
TEST_WALLET_ADDRESS=<0x...>      # WALLET_WITH_BALANCE — кошелёк с ненулевым балансом в Pool B
POOL_SINGLE_TOKEN_ID=<uuid>      # Pool A — single-token пул
POOL_MIN_DEPOSIT_ID=<uuid>       # Pool C — пул с заметным min deposit
WALLET_ZERO_BALANCE=<0x...>      # кошелёк с балансом < min deposit Pool C
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

Четыре фикстуры в `conftest.py` инкапсулируют этот флоу:
- `page_with_wallet` — открывает `/marketplace`, инжектирует кошелёк. Для тестов на главной и SPA-навигации.
- `page_with_wallet_on_pool` — открывает `/marketplace/pool/{TEST_POOL_ID}` (Pool B), инжектирует кошелёк, ждёт `networkidle`. Для тестов Deposit/Withdraw модалок (кошелёк с ненулевым балансом).
- `page_with_wallet_on_single_token_pool` — открывает `/marketplace/pool/{POOL_SINGLE_TOKEN_ID}` (Pool A). Для тестов single-token deposit modal.
- `page_with_zero_wallet_on_min_deposit_pool` — открывает `/marketplace/pool/{POOL_MIN_DEPOSIT_ID}` (Pool C), кошелёк WALLET_ZERO_BALANCE. **scope=module** — страница загружается один раз на весь модуль. Для тестов Fund wallet modal.

**Почему scope=module для Pool C:** Pool C делает долгие polling-запросы (networkidle недостижим). Первый клик Deposit занимает ~15 сек (on-chain RPC). Module-scope позволяет загрузить страницу и прогреть кеш балансов один раз на все 7 тестов.

**Важно:** inject_wallet выполняется ПОСЛЕ `page.goto()` на нужную страницу. `page.goto()` вызывает полный reload — состояние wagmi store сбрасывается. Поэтому нельзя инжектировать на `/marketplace` и потом делать `page.goto(pool_url)` — кошелёк потеряется.

**Что не работает** (задокументировано в `wallet_injection.py`):
- `window.ethereum` mock + `add_init_script` — AppKit не читает провайдер автоматически
- Pre-populate localStorage — wagmi сбрасывает состояние (UID коннектора генерируется случайно)
- Модальный UI-флоу — MetaMask показывает QR, Browser Wallet не обнаруживается в headless Chromium

## Текущий статус

- [x] Шаг 1: API-тесты (healthcheck, pool list, pool detail, portfolio)
- [x] Шаг 1.5: API-тесты лидерборда и поинтов (leaderboard structure/sort/pagination, points cross-validation)
- [x] Шаг 2: UI-тесты без кошелька (marketplace load, header, pool cards, navigation, pool page, portfolio tab)
- [x] Шаг 3: UI-тесты с мок-кошельком — базовые (адрес в хедере, my-portfolio, deposit/withdraw кнопки)
- [x] Шаг 3.5: UI-тесты модалок депозита (Pool A + Pool B), вывода (Pool B), Fund wallet (Pool C)
- [ ] Шаг 4: UI-тесты on-chain транзакций (signing flow, верификация через API)
- [ ] Шаг 5: TRX-тесты (on-chain транзакции)
