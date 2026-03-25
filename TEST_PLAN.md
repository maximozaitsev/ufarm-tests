ПЛАН АВТОТЕСТОВ: Ufarm (ufarm-tests)

Связанный контекст по системе: `TESTED_PROJECT_CONTEXT.md`

## 1. Цели автотестов
- **Краткосрочно**: проверить базовые happy-path сценарии инвестора в DEMO-окружении (депозит, вывод, отображение портфолио и истории).
- **Среднесрочно**: расширить покрытие UI и API для ключевых сценариев маркета и фонда.
- **Долгосрочно**: добавить проверку смарт-контрактов и ончейн-транзакций.

---

## 2. API-тесты (Шаг 1 — реализовано)

> Тесты запускаются без кошелька. Проверяют корректность данных и контракт API.
> Файлы: `tests/api/`
>
> Разметка тестов: `@pytest.mark.api` + `@pytest.mark.smoke|regression|extended`
> Запуск по маркам: `pytest -m "api and smoke"`, `pytest -m "api and regression"` и т.д.

### 2.1 Список пулов — `tests/api/test_pools_list.py`

#### `test_pools_list_validates_against_model` · smoke
- **Что:** Структура каждого пула в списке соответствует Pydantic-модели `Pool`, все `valueManaged >= 0`.
- **Как:** Передаёт весь ответ в `PoolListResponse.model_validate()`. Pydantic проверяет типы, обязательные поля, вложенные объекты.
- **Зачем:** "Контракт" между тестами и API. Если бэкенд переименует поле или сменит тип — тест упадёт сразу, даже если другие тесты этого не заметят.
- **Severity:** Normal
- **Примечание:** Сортировка по `valueManaged` происходит на стороне UI, не API — на уровне API порядок не гарантирован.

#### `test_pools_list_returns_active_public_pools` · regression
- **Что:** API возвращает непустой список публичных активных пулов с корректными полями и типами.
- **Как:** GET `/pool?type=public&status=active&limit=500`. Проверяет наличие `data`, статус 200, обязательные поля каждого пула, типы данных, фильтры (`status == active`, `type == public`).
- **Зачем:** Детальная регрессия структуры. Ловит грубые регрессии — пустой список, неверные статусы, сломанная структура.
- **Severity:** Normal

---

### 2.2 Детальный пул — `tests/api/test_pool_detail.py`

> Тестовый пул: задаётся через `TEST_POOL_ID` в `.env` или флаг `--test-pool-id`.

#### `test_pool_detail_returns_correct_structure` · smoke
- **Что:** GET `/pool/{id}` возвращает объект конкретного пула с корректным `id`, статусом `active`, типом `public`, валидными блокчейн-адресами.
- **Как:** Валидирует через `PoolDetailResponse`, затем проверяет: `pool.id == test_pool_id`, `poolAddress` и `fundAddress` начинаются с `0x`.
- **Зачем:** Smoke-тест эндпоинта детального пула. Убеждаемся, что пул доступен и его ключевые атрибуты соответствуют ожидаемым.
- **Severity:** Normal

#### `test_pool_detail_financials_are_consistent` · regression
- **Что:** Финансовые поля пула консистентны: `valueManaged = totalDeposited + revenue`, `poolMetric.nav == valueManaged`, `tokenPrice > 0`, `totalSupply > 0`.
- **Как:** Парсит строковые числа в `int`, проверяет равенства. Также проверяет метрики пула.
- **Зачем:** Бизнес-инвариант: стоимость пула = вложенное + доходность. Нарушение означает баг в расчётах на бэкенде или рассинхрон данных между сервисами. Такие баги трудно заметить вручную.
- **Severity:** Critical

#### `test_pool_detail_asset_allocation_sums_to_100` · regression
- **Что:** Сумма `allocation` по всем активам пула составляет ~100% (допуск ±1% на округление).
- **Как:** Суммирует `allocation` по всем элементам `assetAllocation`, проверяет диапазон `[99.0, 101.0]`.
- **Зачем:** Инвариант целостности данных. Если сумма не 100% — какой-то актив не учтён или значения считаются неверно. Для финансового приложения это критично.
- **Severity:** Normal

---

### 2.3 Портфолио инвестора — `tests/api/test_portfolio.py`

> Тестовый кошелёк: задаётся через `TEST_WALLET_ADDRESS` в `.env` или флаг `--test-wallet-address`.

#### `test_portfolio_returns_correct_structure` · smoke
- **Что:** GET `/user/portfolio/{address}` возвращает корректную структуру: суммарные депозиты и выводы ≥ 0, список пулов, числовые `points`.
- **Как:** Полная Pydantic-валидация через `Portfolio`. Дополнительные проверки типов и минимальных значений.
- **Зачем:** Базовый контракт портфолио-эндпоинта. Первая линия защиты от структурных изменений в API.
- **Severity:** Normal

#### `test_portfolio_pool_stats_are_consistent` · regression
- **Что:** Для каждого пула в портфолио выполняется формула баланса: `totalBalance = allDeposited − allWithdrawals + realizedPnL + unrealizedPnL`.
- **Как:** Итерирует по всем пулам, считает правую часть формулы, сравнивает с `totalBalance`. При ошибке выводит конкретные числа.
- **Зачем:** Главная финансовая инвариант для инвестора. Если баланс не сходится — бэкенд считает неверно или данные из разных источников рассинхронизированы. Такие баги критичны и плохо видны при ручном тестировании.
- **Severity:** Critical

#### `test_portfolio_totals_match_pool_stats` · regression
- **Что:** Верхнеуровневые поля портфолио (`allDeposited`, `allWithdrawals`) равны сумме аналогичных полей по всем пулам.
- **Как:** Суммирует `poolStat.allDeposited` и `poolStat.allWithdrawals` по всем пулам, сравнивает с `portfolio.allDeposited` и `portfolio.allWithdrawals`.
- **Зачем:** Агрегация не должна расходиться с деталями. Если общий депозит 6000, а сумма по пулам 5000 — потеряли 1000. Критический баг для финансового приложения.
- **Severity:** Critical

---

## 3. UI-тесты без кошелька (Шаг 2 — реализовано)

> Playwright (Chromium, headless), без подключения кошелька. Проверяют навигацию и структуру страниц.
> Файл: `tests/ui/market/test_marketplace_no_wallet.py`
> Разметка: `@pytest.mark.ui` + `@pytest.mark.smoke`

#### `test_marketplace_page_loads` · smoke · CRITICAL
- **Что:** Страница `/marketplace` открывается, карточки пулов загружаются, `<title>` == `"Marketplace"`.

#### `test_header_elements_visible` · smoke · NORMAL
- **Что:** В хедере видны: логотип UFarm, таб `All products`, таб `My portfolio`, кнопка `Connect Wallet`.

#### `test_pool_cards_displayed` · smoke · CRITICAL
- **Что:** На странице отображается минимум 1 карточка пула.

#### `test_pool_card_navigation` · smoke · CRITICAL
- **Что:** Клик на карточку пула → переход на URL вида `/marketplace/pool/{uuid}`.

#### `test_connect_wallet_button_opens_modal` · smoke · NORMAL
- **Что:** Клик на `Connect Wallet` в хедере → появляется модалка Reown (`w3m-modal-card`).

#### `test_pool_page_elements_visible` · smoke · CRITICAL
- **Что:** На странице пула виден `h1` с названием пула, блок депозита, кнопка `Connect wallet to deposit`.

#### `test_pool_page_history_tabs_visible` · smoke · NORMAL
- **Что:** На странице пула присутствуют ARIA-табы `Transactions` и `actions`.

#### `test_my_portfolio_no_wallet` · smoke · NORMAL
- **Что:** Клик на таб `My portfolio` → появляется модалка Reown (навигации на `/my-portfolio` не происходит без кошелька).

> **Примечание по селекторам:** Используются ARIA-роли (`get_by_role`), видимый текст (`get_by_text`) и классы UI-библиотеки Mantine (`.mantine-Paper-root`). CSS-классы с хэшами CSS-модулей (`_offer_1uf7l_1` и т.п.) не используются — они нестабильны между сборками.

> **Отладка:** `HEADED=1 SLOWMO=800 pytest tests/ui/ -v -s` — в видимом браузере. `PWDEBUG=1` — Playwright Inspector.

---

## 4. UI-тесты с кошельком (Шаг 3 — реализовано)

> Playwright + `inject_wallet()` — программная инжекция через React Fiber в wagmi store.
> Фикстуры: `page_with_wallet`, `page_with_wallet_on_pool`, `page_with_wallet_on_single_token_pool`, `page_with_zero_wallet_on_min_deposit_pool`.
> Мок `_mock_auth_connect` — подменяет `GET /auth/connect/{address}` до `page.goto()`, чтобы `userData.createdAt` был доступен в React-состоянии сразу (иначе вместо Deposit открывается PROOF OF AGREEMENT).

### 4.1 Базовые тесты — `tests/ui/market/test_marketplace_with_wallet.py`

> Фикстура: `page_with_wallet` (открывает `/marketplace`, инжектирует кошелёк, хедер показывает адрес).

#### `test_wallet_address_shown_in_header` · smoke · CRITICAL
- **Что:** После инжекции кошелька хедер показывает адрес вместо "Connect Wallet".
- **Как:** `page_with_wallet` → `inject_wallet()` → проверяет `header.inner_text()` содержит начало адреса.

#### `test_my_portfolio_accessible_with_wallet` · smoke · CRITICAL
- **Что:** С подключённым кошельком клик на таб "My portfolio" ведёт на `/marketplace/my-portfolio`, а не открывает Reown-модалку.
- **Как:** `page_with_wallet` → клик на таб → `wait_for_url("**/my-portfolio**")` → проверяет отсутствие Reown-модалки.
- **Примечание:** SPA-навигация (click, не goto) — wallet state в памяти сохраняется.

#### `test_deposit_withdrawal_buttons_visible_with_wallet` · smoke · CRITICAL
- **Что:** На странице пула с кошельком видны кнопки Deposit и Withdraw, кнопка "Connect wallet to deposit" скрыта.
- **Как:** `page_with_wallet_on_pool` → `wait_for_pool_page()` → `deposit_button().is_visible()` → `wait_for_withdraw_button()` (ждёт загрузки баланса) → проверяет отсутствие "Connect wallet to deposit".
- **Примечание:** Кнопка "Withdraw" появляется только после загрузки баланса пользователя по API (~5-10 сек после inject_wallet). "Withdrawal" (с -al) — это тип операции в таблице истории, не кнопка.

#### `test_deposit_modal_opens` · smoke · CRITICAL
- **Что:** Клик на кнопку Deposit открывает модалку с переключателем "Gasless transaction".
- **Как:** `page_with_wallet_on_pool` → `deposit_button().click()` → `deposit_modal().wait_for(visible)` → проверяет наличие "Gasless transaction".

#### `test_withdraw_modal_opens` · smoke · CRITICAL
- **Что:** Клик на кнопку Withdraw открывает модалку с кнопкой "Request Withdrawal".
- **Как:** `page_with_wallet_on_pool` → `wait_for_withdraw_button()` → `withdraw_button().click()` → ждёт `get_by_text("Request Withdrawal").visible`.

---

### 4.2 Модалка депозита — `tests/ui/market/test_deposit_modal.py`

> Вспомогательная функция `open_deposit_modal()` — кликает Deposit, ждёт heading "DEPOSIT" с таймаутом 15 сек. Если появился Terms/PROOF OF AGREEMENT — пропускает тест (`pytest.skip`).

**Pool A (single-token):** фикстура `page_with_wallet_on_single_token_pool` (POOL_SINGLE_TOKEN_ID + TEST_WALLET_ADDRESS)

#### `test_deposit_modal_opens_single_token` · smoke · CRITICAL
- **Что:** Модалка депозита открывается на single-token пуле.
- **Как:** `open_deposit_modal()` → скриншот.

#### `test_deposit_modal_single_token_no_dropdown` · smoke · NORMAL
- **Что:** В single-token пуле нет дропдауна выбора токена (role=combobox или listbox).
- **Как:** После открытия модалки проверяет отсутствие `[role='combobox']` и `[role='listbox']` внутри `.mantine-Modal-body`.

#### `test_deposit_modal_input_visible` · smoke · CRITICAL
- **Что:** Поле ввода суммы видно.
- **Как:** `modal.amount_input().is_visible()`.

#### `test_deposit_modal_empty_input_button_disabled` · smoke · CRITICAL
- **Что:** Кнопка submit отключена когда инпут пустой или = "0".
- **Как:** `modal.submit_button().is_disabled()`.

#### `test_deposit_modal_max_button_fills_wallet_balance` · smoke · CRITICAL
- **Что:** Клик MAX заполняет инпут on-chain USDT балансом кошелька (погрешность < 1%).
- **Как:** Сравнивает `amount_input().input_value()` с `wallet_usdt_balance` (фикстура из conftest).
- **После MAX:** кнопка submit становится активной.

#### `test_deposit_modal_gasless_on_by_default` · smoke · NORMAL
- **Что:** Тоглер Gasless включён по умолчанию, текст кнопки = "request deposit".
- **Как:** `modal.gasless_toggle().is_checked()` + `modal.submit_button_text()`.

#### `test_deposit_modal_gasless_off_shows_instant_deposit` · smoke · CRITICAL
- **Что:** Отключение Gasless меняет текст кнопки на "instant deposit".
- **Как:** `gasless_toggle().evaluate("el => el.click()")` → проверяет текст кнопки.

#### `test_deposit_modal_gasless_on_shows_request_deposit` · smoke · NORMAL
- **Что:** Повторное включение Gasless возвращает текст "request deposit".
- **Как:** Выключить → включить → проверить текст.

**Pool B (multi-token):** фикстура `page_with_wallet_on_pool` (TEST_POOL_ID + TEST_WALLET_ADDRESS)

#### `test_deposit_modal_opens_multi_token` · smoke · CRITICAL
- **Что:** Модалка депозита открывается на multi-token пуле.
- **Как:** `open_deposit_modal()` → скриншот.

#### `test_deposit_modal_multi_token_has_dropdown` · smoke · NORMAL
- **Что:** Клик по иконке токена открывает дропдаун, в котором видны варианты из `availableValueTokens` пула (из API).
- **Как:** `modal.token_selector().click()` → `modal.token_dropdown().wait_for(visible)` → проверяет видимость каждого токена.

#### `test_deposit_triggers_signing` · smoke · CRITICAL (TBD)
- **Что:** Клик submit после MAX запускает signing flow.
- **Статус:** Ожидаем наблюдения в `HEADED=1` — assertion не добавлен.

---

### 4.3 Модалка Fund wallet — `tests/ui/market/test_fund_wallet_modal.py`

> Фикстура: `page_with_zero_wallet_on_min_deposit_pool` — scope=module, страница загружается один раз.
> Пул Pool C (POOL_MIN_DEPOSIT_ID) + WALLET_ZERO_BALANCE (баланс < min deposit пула).
>
> Вспомогательная функция `open_fund_wallet_modal()` — закрывает предыдущую модалку (module-scope), кликает Deposit, ждёт heading "Fund wallet" до 20 сек. Если не появился — `pytest.skip`.
>
> Первый тест ~15 сек (on-chain RPC проверка баланса), последующие быстро (кеш приложения).

#### `test_fund_wallet_modal_opens` · smoke · CRITICAL
- **Что:** Модалка Fund wallet открывается при нулевом балансе кошелька (< min deposit пула).
- **Как:** `open_fund_wallet_modal()` → `modal.wait_opened()`.

#### `test_fund_wallet_modal_title` · smoke · NORMAL
- **Что:** Заголовок модалки — "Fund wallet".
- **Как:** `modal.title().is_visible()`.

#### `test_fund_wallet_modal_text_contains_min_deposit` · smoke · CRITICAL
- **Что:** Текст-подсказка содержит минимальную сумму депозита из API пула.
- **Как:** Вычисляет `display_amount` из `pool_info_min_deposit.limits.deposit_min / 10^decimals` → ищет в `modal.hint_text()`.

#### `test_fund_wallet_modal_text_contains_token` · smoke · CRITICAL
- **Что:** Текст содержит тикер токена из `availableValueTokens` пула.
- **Как:** Проверяет что любой из `tokens.upper()` присутствует в `modal.hint_text()`.

#### `test_fund_wallet_modal_text_contains_network` · smoke · NORMAL
- **Что:** Текст содержит название сети текущего окружения (Arbitrum / Ethereum).
- **Как:** Использует фикстуру `network_name` → ищет в `modal.hint_text()`.

#### `test_fund_wallet_modal_has_buy_crypto` · smoke · NORMAL
- **Что:** Кнопка "buy crypto" видна.
- **Как:** `modal.buy_crypto_button().is_visible()`.

#### `test_fund_wallet_modal_has_receive_funds` · smoke · NORMAL
- **Что:** Кнопка "receive funds" видна.
- **Как:** `modal.receive_funds_button().is_visible()`.

---

### 4.4 Модалка вывода — `tests/ui/market/test_withdraw_modal.py`

> Фикстура: `page_with_wallet_on_pool` (TEST_POOL_ID + TEST_WALLET_ADDRESS, кошелёк с ненулевым балансом).
>
> **Важно по закрытию модалки:** Escape не закрывает модалку — только клик по иконке крестика `[class*='closeIcon']`. `WithdrawModal.close()` реализован через клик, не через Escape.
>
> **Расчёт баланса в токенах пула:** `api_balance_tokens = totalBalance / 10^6 / tokenPrice`, где `totalBalance` из portfolio API — USDT-стоимость инвестиции в наименьших единицах (6 decimals на Arbitrum), `tokenPrice` — из `pool.poolMetric.tokenPrice`.

#### `test_withdraw_modal_opens` · smoke · CRITICAL
- **Что:** Клик Withdraw открывает модалку вывода, дожидается видимости кнопки Request Withdrawal (модалка полностью отрисована).
- **Как:** `wait_for_withdraw_button()` → `withdraw_button().click()` → `modal.wait_for()` → `request_withdrawal_button().wait_for(visible)` → скриншот.

#### `test_withdraw_modal_shows_pool_balance` · smoke · CRITICAL
- **Что:** Баланс в модалке (pool tokens) соответствует portfolio API с учётом tokenPrice (погрешность < 5%).
- **Как:** `api_balance_tokens = totalBalance / 10^6 / tokenPrice` → парсит "Balance: X" → сравнивает с допуском 5%.
- **Фикстуры:** `wallet_portfolio`, `test_pool_id`, `pool_info_multi_token`.

#### `test_withdraw_modal_has_request_withdrawal_button` · smoke · CRITICAL
- **Что:** Кнопка "Request Withdrawal" видна и недоступна при пустом инпуте.
- **Как:** `request_withdrawal_button().wait_for(state="visible")` + `is_disabled()`.

#### `test_withdraw_modal_pool_input_updates_token_input` · smoke · CRITICAL
- **Что:** Ввод случайного количества pool tokens в sellCoin пересчитывает buyCoin (USDT). Точность: `buy ≈ sell × tokenPrice` (погрешность < 2%).
- **Как:** Генерирует `sell_amount = random(0.1, api_balance_tokens)` с 1 децималом → `fill(sell_amount)` → сравнивает `buy_value` с `sell_amount × tokenPrice`.
- **Фикстуры:** `wallet_portfolio`, `test_pool_id`, `pool_info_multi_token`.

#### `test_withdraw_modal_token_input_updates_pool_input` · smoke · CRITICAL
- **Что:** Ввод случайной суммы USDT в buyCoin пересчитывает sellCoin (pool tokens). Точность: `sell ≈ buy / tokenPrice` (погрешность < 2%).
- **Как:** Генерирует `buy_amount = random(0.1, api_balance_usdt)` с 1 децималом → `fill(buy_amount)` → сравнивает `sell_value` с `buy_amount / tokenPrice`.
- **Фикстуры:** `wallet_portfolio`, `test_pool_id`, `pool_info_multi_token`.

#### `test_withdraw_modal_max_button` · smoke · CRITICAL
- **Что:** Клик MAX заполняет sellCoin полным балансом (погрешность < 1% от отображаемого "Balance: X").
- **Как:** Сохраняет значение из "Balance: X" → `max_button().click()` → сравнивает float значения с допуском 1%.

**Негативные сценарии:**

#### `test_withdraw_modal_amount_exceeds_balance_shows_error` · smoke · CRITICAL
- **Что:** Ввод в sellCoin суммы > баланса показывает ошибку "Not enough pool tokens..." и дизейблит кнопку.
- **Как:** Вводит `api_balance_tokens × 1.1 + 1` → ждёт текст "Not enough pool tokens" → `request_withdrawal_button().is_disabled()`.

#### `test_withdraw_modal_usdt_exceeds_balance_shows_error` · smoke · CRITICAL
- **Что:** Ввод в buyCoin суммы USDT > баланса показывает ту же ошибку "Not enough pool tokens..." через второй инпут.
- **Как:** Вводит `api_balance_usdt × 1.1 + 1` в `withdraw_token_input` → ждёт ошибку → `is_disabled()`.

#### `test_withdraw_modal_zero_amount_shows_error` · smoke · NORMAL
- **Что:** Ввод 0 в sellCoin показывает ошибку "Please indicate the withdrawal sum...".
- **Как:** `pool_token_input().fill("0")` → ждёт текст "Please indicate the withdrawal sum".

#### `test_withdraw_modal_clear_input_disables_button` · smoke · NORMAL
- **Что:** После очистки инпута (ввели "1", потом "") кнопка снова дизейблится.
- **Как:** `fill("1")` → `fill("")` → `request_withdrawal_button().is_disabled()`.

#### `test_withdraw_modal_reopen_resets_inputs` · smoke · NORMAL
- **Что:** После закрытия и повторного открытия оба инпута сброшены в пустое/нулевое состояние.
- **Как:** Вводит "1" → `modal.close()` (клик по крестику) → `withdraw_button().click()` → проверяет что `sellCoin` и `buyCoin` пустые или "0".

#### `test_withdraw_triggers_signing` · smoke · CRITICAL (TBD)
- **Что:** Клик Request Withdrawal после MAX запускает signing flow.
- **Статус:** Ожидаем наблюдения в `HEADED=1` — assertion не добавлен.

---

## 5. UI-тесты: on-chain транзакции (Шаг 4 — запланировано)

> Playwright + мок-провайдер + верификация через API после действия.

### 5.1 Депозит через All products
- Предусловия: мок-кошелёк с балансом USDC/USDT, пул принимает стейблкоин.
- Шаги:
  1. Открыть `/marketplace`.
  2. Убедиться, что таб `All products` активен, список пулов отображается.
  3. Перейти на страницу тестового пула.
  4. Нажать `DEPOSIT`, выбрать стейблкоин, ввести сумму или нажать `MAX`.
  5. Подтвердить депозит (`INSTANT DEPOSIT`).
  6. Дождаться обновления страницы.
  7. Перейти в `/marketplace/my-portfolio`, убедиться, что пул появился/обновился.
  8. Проверить `My history` — есть запись `Deposit` с корректной суммой.
- Верификация через API: `GET /user/portfolio/{address}` — баланс увеличился.

### 5.2 Вывод через My portfolio
- Предусловия: активная позиция инвестора в пуле.
- Шаги:
  1. Открыть `/marketplace/my-portfolio`.
  2. Перейти на страницу пула с ненулевым балансом.
  3. Нажать `WITHDRAW`, ввести количество пул-токенов или `MAX`.
  4. Проверить блок `You receive` — стейблкоин и рассчитанная сумма.
  5. Нажать `REQUEST WITHDRAWAL`.
  6. Проверить вкладку `My requests` — запрос создан.
  7. Проверить `My history` — запись о выводе с корректным значением.
- Верификация через API: `GET /user/portfolio/{address}` — баланс уменьшился.

---

## 6. CI/CD и Allure-отчёты (реализовано)

### Запуск через GitHub Actions

Файл: `.github/workflows/tests.yml`

Запуск — только вручную (`workflow_dispatch`) через кнопку **Run workflow** в GitHub Actions.

**Параметры запуска:**

| Параметр | Значения | Описание |
|---|---|---|
| `test_type` | `api`, `ui`, `trx`, `all` | Тип тестов |
| `test_suite` | `smoke`, `regression`, `extended`, `all` | Набор тестов |
| `environment` | `demo` | Окружение |

Названия наборов задают `pytest.ini` marks:
- `smoke` — критичные happy-path проверки
- `regression` — стандартные регрессионные проверки
- `extended` — глубокие и edge-case проверки

Пример: `test_type=api, test_suite=smoke` → `pytest -m "api and smoke"`

Secrets: `TEST_POOL_ID`, `TEST_WALLET_ADDRESS`, `POOL_SINGLE_TOKEN_ID`, `POOL_MIN_DEPOSIT_ID`, `WALLET_ZERO_BALANCE` (добавить в Settings → Secrets → Actions).

### Allure-отчёты

- `allure-pytest` генерирует результаты в `allure-results/`
- `simple-elf/allure-report-action` строит HTML-отчёт с историей
- `peaceiris/actions-gh-pages` публикует на **GitHub Pages** (ветка `gh-pages`)
- История хранится 50 последних прогонов — даёт **trendline** и **flaky test** статистику

**Allure-разметка тестов:**
- `@allure.epic` — модуль: `"Market"` или `"Fund"`
- `@allure.feature` — тип: `"API"` или `"UI"`
- `@allure.story` — фича: `"Leaderboard"`, `"Deposit"` и т.д.
- `@allure.epic` / `@allure.feature` / `@allure.story` / `@allure.title` — на английском
- `with allure.step(...)` — на русском, содержит конкретные значения
- `@allure.severity` — CRITICAL / NORMAL (финансовые инварианты → CRITICAL)
- `@allure.link` — ссылка на Swagger
- `allure.attach(JSON)` — тело ответа прикреплено к каждому тесту
- `environment.properties` — в отчёте отображается окружение, URL, версия Python

**Активировать GitHub Pages:** Settings → Pages → Source → ветка `gh-pages`.

**Локальный просмотр отчёта:**
```bash
pytest tests/api/ -v --alluredir=allure-results
allure serve allure-results
```

---

## 7. Leaderboard & Points (Шаг 5 — запланировано)

> Тесты лидерборда и поинтов **всегда** обращаются к PROD ETH (`https://api.ufarm.digital/api/v2`), независимо от параметра `--env`.
>
> Разметка: `@pytest.mark.api` + `@pytest.mark.smoke|regression|extended`
>
> Файлы: `tests/api/test_leaderboard.py`, `tests/api/test_points.py`

### 7.1 Структура и пагинация лидерборда — `tests/api/test_leaderboard.py`

#### `test_leaderboard_returns_correct_structure` · smoke
- **Что:** `GET /api/v2/points/leaderboard?limit=10&page=1` возвращает корректный ответ со всеми обязательными полями.
- **Как:** Pydantic-валидация `LeaderboardResponse`. Проверяет: `data` — список, `total >= 0`, `count <= limit`, поля каждого элемента (`userAddress`, `points`).
- **Зачем:** Базовый контракт эндпоинта. Первая линия защиты от структурных изменений.
- **Severity:** Normal

#### `test_leaderboard_sorted_by_points_desc` · regression
- **Что:** Элементы лидерборда отсортированы строго по убыванию поинтов.
- **Как:** Берёт несколько страниц, проверяет `data[i].points >= data[i+1].points` на каждой странице. Проверяет, что последний элемент предыдущей страницы `>= первому элементу следующей.
- **Зачем:** Нарушение сортировки — прямая ошибка пользователя (неправильный ранг). Критично для финансового рейтинга.
- **Severity:** Critical

#### `test_leaderboard_pagination_invariants` · regression
- **Что:** Пагинация консистентна: `count ≤ limit`, `page ≤ pageCount`, сумма `count` по всем страницам = `total`.
- **Как:** Итерирует по всем страницам (пока `page <= pageCount`), суммирует `count`, сравнивает с `total`.
- **Зачем:** Сломанная пагинация означает, что пользователи видят неполный или дублированный список. Баг трудно заметить вручную при большом количестве участников.
- **Severity:** Normal

#### `test_leaderboard_user_addresses_are_unique` · regression
- **Что:** Каждый `userAddress` встречается в лидерборде ровно один раз.
- **Как:** Собирает все адреса со всех страниц, проверяет отсутствие дубликатов.
- **Зачем:** Дублирующийся адрес означает двойной учёт — неверный ранг участника.
- **Severity:** Normal

#### `test_leaderboard_addresses_are_valid_ethereum` · regression
- **Что:** Все `userAddress` — валидные Ethereum-адреса (начинаются с `0x`, длина 42 символа).
- **Как:** Проходит по всем адресам, проверяет regex `^0x[0-9a-fA-F]{40}$`.
- **Зачем:** Невалидный адрес означает баг в хранении или обработке данных на бэкенде.
- **Severity:** Normal

---

### 7.2 Расчёт поинтов — `tests/api/test_points.py`

> Бизнес-логика для проверки описана в `TESTED_PROJECT_CONTEXT.md`, раздел 6.
>
> **Конфиг Season 1:** `balanceMultiplier=0.0005`, `seasonMultiplier=5`, `rewardEpochDays=90`, `holderPointMultiplier=0.0001`, `referralMultiplier=0.05`.
>
> **Формула поинтов за эпоху (1 час):**
> `pointsAccrued = (balance_usd × 0.0005 + bonusPoints) × 5`

#### `test_points_portfolio_matches_leaderboard` · smoke
- **Что:** `portfolio.points` для адреса из лидерборда совпадает с его значением в лидерборде.
- **Как:** Берёт первые 10 адресов из лидерборда, для каждого запрашивает `/user/portfolio/{address}`, сравнивает `portfolio.points` с `leaderboard.points`.
- **Зачем:** Два эндпоинта должны показывать одинаковые данные одному пользователю. Расхождение означает рассинхрон данных между сервисами.
- **Severity:** Critical

#### `test_points_base_rate_calculation` · regression
- **Что:** Поинты за последние N часов при известном балансе соответствуют формуле `balance × 0.0005 × 5 × N` (без бонуса).
- **Как:** Использует тестовый кошелёк **Wallet A** (свежий депозит, без холдер-бонуса, без реферала). Берёт историю депозитов → вычисляет ожидаемые поинты → сравнивает с `portfolio.points`.
- **Зачем:** Проверяет корректность базового начисления — основного механизма расчёта доходности поинтов.
- **Severity:** Critical
- **Тестовые данные:** Wallet A — сделать свежий депозит. Записать сумму и время депозита в `.env` или тестовые данные.

#### `test_points_referral_bonus` · regression
- **Что:** Реферер получает 5% от `pointsAccrued` реферала за каждую эпоху.
- **Как:** Использует тестовую пару **Wallet B** (реферал) + **Wallet R** (реферер). Вычисляет поинты реферала → 5% → добавляет к базовым поинтам реферера → сравнивает с `portfolio.points` реферера.
- **Зачем:** Реферальная программа — ключевая функция привлечения. Ошибка в расчёте реферальных бонусов прямо влияет на доход пользователей.
- **Severity:** Critical
- **Тестовые данные:** Wallet B зарегистрирован с реферальным кодом Wallet R. Оба с активными депозитами. Время депозитов зафиксировано.

#### `test_holder_bonus_activates_after_90_days` · extended
- **Что:** Холдер-бонус активируется ровно через 90 дней непрерывного ненулевого баланса (от первой эпохи с ненулевым балансом).
- **Как:** Использует тестовый кошелёк **Wallet C** (депозит без гэпа до первой эпохи). Через 90 дней + несколько часов проверяет, что `portfolio.points` содержит холдер-бонус, а до 90 дней — нет.
- **Зачем:** Холдер-бонус — многократный мультипликатор. Если он не активируется или активируется слишком рано — пользователь получает неверное вознаграждение.
- **Severity:** Critical
- **Тестовые данные:** Wallet C — сделать депозит в момент первой регистрации в системе (нет гэпа). Зафиксировать время.

#### `test_holder_bonus_fires_once_not_multiple_times` · extended
- **Что:** Ретроактивный холдер-бонус срабатывает ровно один раз, даже если до первого депозита было N часов нулевого баланса.
- **Как:** Использует тестовый кошелёк **Wallet D** (сначала зарегистрирован в системе, депозит сделан позже — через N часов). Проверяет поинты после `90 дней + N часов`: должен быть только один ретроактивный бонус.
- **Зачем:** Документированный потенциальный баг в `getBonusPoints()`: если до первого депозита было N нулевых эпох, Case A может сработать N раз вместо одного. Этот тест верифицирует корректное поведение.
- **Severity:** Critical
- **Тестовые данные:** Wallet D — зарегистрировать в системе (например, посетить сайт), подождать N часов, затем сделать депозит. Зафиксировать N и время депозита.

#### `test_holder_ongoing_bonus_uses_min_balance` · extended
- **Что:** После активации холдер-бонуса каждая эпоха начисляет `minBalance_за_90_дней × 0.0001 × seasonMultiplier`.
- **Как:** Использует Wallet C с частичным выводом (уменьшил баланс). Вычисляет `minBalance` за последние 90 дней из истории транзакций → ожидаемый бонус → сравнивает с фактическими поинтами.
- **Зачем:** Частичный вывод должен снижать бонус пропорционально. Полный вывод обнуляет бонус. Ошибка в расчёте minBalance ведёт к завышенному вознаграждению.
- **Severity:** Critical

---

### 7.3 Тестовые кошельки для Leaderboard & Points

> Создать на PROD ETH. Зафиксировать адреса, суммы и точное время операций — это тестовые данные для расчётов.

| Кошелёк | Назначение | Что сделать |
|---|---|---|
| **Wallet A** | Базовая ставка, нет бонусов | Свежий депозит без реферала. Записать время и сумму. |
| **Wallet B** | Реферал для проверки 5% бонуса | Зарегистрироваться с реферальным кодом Wallet R. Сделать депозит. |
| **Wallet R** | Реферер Wallet B | Активный депозит. Зафиксировать адрес для сравнения поинтов. |
| **Wallet C** | Холдер-бонус (нет гэпа) | Депозит сразу при первом появлении в системе. Ждать 90+ дней для `extended`-теста. |
| **Wallet D** | Баг с множественным срабатыванием | Сначала зарегистрировать (открыть сайт), подождать N часов, затем депозит. Фиксировать N. |

---

## 8. Ограничения

- Все тесты API/UI/TRX запускаются только против DEMO-окружения.
- Тесты лидерборда и поинтов **всегда** используют PROD ETH (`api.ufarm.digital/api/v2`), независимо от `--env`.
- UI-тесты не валидируют точные числовые значения доходности — фокус на навигации и консистентности данных.
- KYT/KYC, термы и полный ончейн-флоу будут детализированы отдельно.
- Тесты холдер-бонуса (`extended`) требуют ожидания 90 дней — выполняются на специально подготовленных кошельках с известной историей.

---

## 8. Бэклог

- Негативные сценарии: отмена транзакции, ошибки сети, недостаточный баланс.
- Валидации сумм: минимальный депозит, превышение баланса.
- Вкладки `Transactions` и `Actions` на странице пула.
- Тесты для модуля фонда: создание и редактирование пулов, управление активами.
- Тестирование смарт-контрактов и ончейн-транзакций.
- Allure: `@allure.issue` — ссылки на баги в трекере (когда появятся тикеты).
- Allure: `@allure.testcase` — ссылки на тест-кейсы в Confluence/TestRail.
- Allure: `categories.json` — кастомные категории падений (infrastructure error, product bug и т.д.).
