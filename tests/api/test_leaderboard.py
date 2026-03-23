import json
import re

import allure
import pytest

from core.api.models.leaderboard import LeaderboardResponse

ETHEREUM_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


@pytest.mark.api
@pytest.mark.smoke
@allure.epic("Market")
@allure.feature("API")
@allure.story("Leaderboard")
@allure.title("Leaderboard response matches Pydantic model")
@allure.severity(allure.severity_level.NORMAL)
@allure.link("https://api.ufarm.digital/api/v1/docs#/", name="Swagger")
def test_leaderboard_returns_correct_structure(leaderboard_api_client):
    with allure.step("Отправляем GET /points/leaderboard?limit=10&page=1"):
        response = leaderboard_api_client.get(
            "/points/leaderboard",
            params={"limit": 10, "page": 1},
        )

    with allure.step(f"Статус ответа == 200 (получен {response.status_code})"):
        assert response.status_code == 200

    with allure.step("Валидируем ответ через Pydantic-модель LeaderboardResponse"):
        body = LeaderboardResponse.model_validate(response.json())
        allure.attach(
            json.dumps(response.json(), indent=2),
            name="Leaderboard response",
            attachment_type=allure.attachment_type.JSON,
        )

    print(f"\n  total={body.total}, count={body.count}, page={body.page}, pageCount={body.pageCount}")
    for item in body.data:
        print(f"    {item.userAddress} | points={item.points}")

    with allure.step(f"count={body.count} <= limit=10"):
        assert body.count <= 10, f"count={body.count} превышает limit=10"

    with allure.step(f"page={body.page} <= pageCount={body.pageCount}"):
        assert body.page <= body.pageCount, f"page={body.page} > pageCount={body.pageCount}"

    with allure.step("Все points >= 0"):
        for item in body.data:
            assert item.points >= 0, f"Отрицательные поинты у {item.userAddress}: {item.points}"


@pytest.mark.api
@pytest.mark.regression
@allure.epic("Market")
@allure.feature("API")
@allure.story("Leaderboard")
@allure.title("Leaderboard entries are sorted by points descending")
@allure.severity(allure.severity_level.CRITICAL)
@allure.link("https://api.ufarm.digital/api/v1/docs#/", name="Swagger")
def test_leaderboard_sorted_by_points_desc(leaderboard_api_client):
    limit = 50

    with allure.step(f"Загружаем первые 2 страницы (limit={limit})"):
        resp1 = leaderboard_api_client.get("/points/leaderboard", params={"limit": limit, "page": 1})
        assert resp1.status_code == 200
        page1 = LeaderboardResponse.model_validate(resp1.json())

        all_items = list(page1.data)

        if page1.pageCount >= 2:
            resp2 = leaderboard_api_client.get("/points/leaderboard", params={"limit": limit, "page": 2})
            assert resp2.status_code == 200
            page2 = LeaderboardResponse.model_validate(resp2.json())
            all_items.extend(page2.data)

    print(f"\n  Проверяем сортировку по {len(all_items)} записям")

    with allure.step(f"Записи отсортированы по убыванию points (проверяем {len(all_items)} записей)"):
        for i in range(len(all_items) - 1):
            a, b = all_items[i], all_items[i + 1]
            print(f"    [{i}] {a.userAddress} points={a.points} >= [{i+1}] {b.userAddress} points={b.points}")
            assert a.points >= b.points, (
                f"Нарушение сортировки: [{i}] {a.userAddress} points={a.points} "
                f"< [{i+1}] {b.userAddress} points={b.points}"
            )

    if page1.pageCount >= 2:
        last_page1 = page1.data[-1]
        first_page2 = page2.data[0]
        with allure.step(
            f"Последний элемент страницы 1 (points={last_page1.points}) >= первому элементу страницы 2 (points={first_page2.points})"
        ):
            print(f"\n  Граница страниц: page1[-1].points={last_page1.points} >= page2[0].points={first_page2.points}")
            assert last_page1.points >= first_page2.points, (
                f"Нарушение сортировки на границе страниц: "
                f"page1[-1].points={last_page1.points} < page2[0].points={first_page2.points}"
            )


@pytest.mark.api
@pytest.mark.regression
@allure.epic("Market")
@allure.feature("API")
@allure.story("Leaderboard")
@allure.title("Leaderboard pagination invariants hold across all pages")
@allure.severity(allure.severity_level.NORMAL)
@allure.link("https://api.ufarm.digital/api/v1/docs#/", name="Swagger")
def test_leaderboard_pagination_invariants(leaderboard_api_client):
    limit = 100

    with allure.step(f"Получаем первую страницу для определения pageCount (limit={limit})"):
        resp = leaderboard_api_client.get("/points/leaderboard", params={"limit": limit, "page": 1})
        assert resp.status_code == 200
        first_page = LeaderboardResponse.model_validate(resp.json())

    total = first_page.total
    page_count = first_page.pageCount
    print(f"\n  total={total}, pageCount={page_count}, limit={limit}")

    total_count = first_page.count
    print(f"  Страница 1: count={first_page.count}")

    with allure.step(f"Итерируем все {page_count} страниц и суммируем count"):
        for page_num in range(2, page_count + 1):
            resp = leaderboard_api_client.get("/points/leaderboard", params={"limit": limit, "page": page_num})
            assert resp.status_code == 200, f"Страница {page_num} вернула {resp.status_code}"
            page = LeaderboardResponse.model_validate(resp.json())

            print(f"  Страница {page_num}: count={page.count}, page={page.page}, pageCount={page.pageCount}")

            with allure.step(f"Страница {page_num}: count={page.count} <= limit={limit}"):
                assert page.count <= limit, f"Страница {page_num}: count={page.count} > limit={limit}"

            with allure.step(f"Страница {page_num}: page={page.page} <= pageCount={page.pageCount}"):
                assert page.page <= page.pageCount

            total_count += page.count

    with allure.step(f"Сумма count по всем страницам ({total_count}) == total ({total})"):
        print(f"\n  Итого count по страницам: {total_count}, ожидаемый total: {total}")
        assert total_count == total, (
            f"Сумма count по страницам ({total_count}) != total ({total})"
        )


@pytest.mark.api
@pytest.mark.regression
@allure.epic("Market")
@allure.feature("API")
@allure.story("Leaderboard")
@allure.title("Leaderboard user addresses are unique across all pages")
@allure.severity(allure.severity_level.NORMAL)
@allure.link("https://api.ufarm.digital/api/v1/docs#/", name="Swagger")
def test_leaderboard_user_addresses_are_unique(leaderboard_api_client):
    limit = 100

    with allure.step("Загружаем все страницы лидерборда"):
        resp = leaderboard_api_client.get("/points/leaderboard", params={"limit": limit, "page": 1})
        assert resp.status_code == 200
        first_page = LeaderboardResponse.model_validate(resp.json())

        all_addresses = [item.userAddress for item in first_page.data]

        for page_num in range(2, first_page.pageCount + 1):
            resp = leaderboard_api_client.get("/points/leaderboard", params={"limit": limit, "page": page_num})
            assert resp.status_code == 200
            page = LeaderboardResponse.model_validate(resp.json())
            all_addresses.extend(item.userAddress for item in page.data)

    print(f"\n  Всего адресов: {len(all_addresses)}, уникальных: {len(set(all_addresses))}")

    with allure.step(f"Все {len(all_addresses)} адресов уникальны"):
        seen = set()
        duplicates = []
        for addr in all_addresses:
            if addr in seen:
                duplicates.append(addr)
            seen.add(addr)
        assert not duplicates, f"Дублирующиеся адреса: {duplicates}"


@pytest.mark.api
@pytest.mark.regression
@allure.epic("Market")
@allure.feature("API")
@allure.story("Leaderboard")
@allure.title("Leaderboard user addresses are valid Ethereum addresses")
@allure.severity(allure.severity_level.NORMAL)
@allure.link("https://api.ufarm.digital/api/v1/docs#/", name="Swagger")
def test_leaderboard_addresses_are_valid_ethereum(leaderboard_api_client):
    limit = 100

    with allure.step("Загружаем первые 2 страницы лидерборда"):
        resp = leaderboard_api_client.get("/points/leaderboard", params={"limit": limit, "page": 1})
        assert resp.status_code == 200
        first_page = LeaderboardResponse.model_validate(resp.json())

        items = list(first_page.data)
        if first_page.pageCount >= 2:
            resp2 = leaderboard_api_client.get("/points/leaderboard", params={"limit": limit, "page": 2})
            assert resp2.status_code == 200
            items.extend(LeaderboardResponse.model_validate(resp2.json()).data)

    print(f"\n  Проверяем {len(items)} адресов")

    with allure.step(f"Все {len(items)} адресов соответствуют формату 0x + 40 hex-символов"):
        invalid = [item.userAddress for item in items if not ETHEREUM_ADDRESS_RE.match(item.userAddress)]
        for addr in items[:5]:
            print(f"    {addr.userAddress}")
        assert not invalid, f"Невалидные Ethereum-адреса: {invalid}"
