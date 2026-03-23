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
conftest.py               # фикстуры: api_client, leaderboard_api_client, test_pool_id, test_wallet_address, browser, page
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
    pages/marketplace_page.py   # MarketplacePage: селекторы + методы навигации
tests/
  api/                    # pytest.mark.api
    test_healthcheck.py
    test_pools_list.py
    test_pool_detail.py
    test_portfolio.py
    test_leaderboard.py   # структура, сортировка, пагинация, уникальность адресов
    test_points.py        # portfolio.points == leaderboard.points
  ui/                     # pytest.mark.ui
    market/               # тесты маркетплейса
      test_marketplace_no_wallet.py  # smoke: загрузка, хедер, карточки, навигация, портфолио
    fund/                 # тесты фонда (будущее)
scripts/
  dump_markup.py          # разведка: дампит HTML и PNG страниц (результат в scripts/markup/, gitignored)
```

## Переменные окружения

**`.env` (тестовые данные):**
```
TEST_POOL_ID=<uuid>
TEST_WALLET_ADDRESS=<0x...>
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

## CI/CD

GitHub Actions, только ручной запуск (`workflow_dispatch`).
Параметры: `test_type` (api/ui/trx/all), `test_suite` (smoke/regression/extended/all), `environment` (demo).
Secrets: `TEST_POOL_ID`, `TEST_WALLET_ADDRESS`.
Allure-отчёт → GitHub Pages (ветка `gh-pages`).

## Текущий статус

- [x] Шаг 1: API-тесты (healthcheck, pool list, pool detail, portfolio)
- [x] Шаг 1.5: API-тесты лидерборда и поинтов (leaderboard structure/sort/pagination, points cross-validation)
- [x] Шаг 2: UI-тесты без кошелька (marketplace load, header, pool cards, navigation, pool page, portfolio tab)
- [ ] Шаг 3: UI-тесты с мок-кошельком
- [ ] Шаг 4: UI-тесты депозита и вывода
- [ ] Шаг 5: TRX-тесты (on-chain транзакции)
