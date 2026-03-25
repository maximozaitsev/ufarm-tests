"""Утилиты для мокирования сетевых запросов в UI-тестах."""
import json


def mock_auth_connect(page) -> None:
    """Мокает эндпоинты авторизации и верификации — предотвращает показ PROOF OF AGREEMENT.

    Два мока устанавливаются ДО page.goto():

    1. GET /auth/connect/{address} → {"createdAt": ..., "lastTopUp": null}
       createdAt != null означает что пользователь уже зарегистрирован.
       Без мока React не успевает получить createdAt до клика Deposit → Terms появляются.

    2. POST /user/verification → {"signature": "0x0", "tier": 10, "validTill": 9999999999}
       Эндпоинт возвращает подпись верификации пользователя.
       Без мока приложение может посчитать верификацию не пройденной и показать Terms.
    """
    def _auth_handler(route, _request):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"createdAt": "2024-01-01T00:00:00.000Z", "lastTopUp": None}),
        )

    def _verification_handler(route, _request):
        route.fulfill(
            status=201,
            content_type="application/json",
            body=json.dumps({"signature": "0x0", "tier": 10, "validTill": 9999999999}),
        )

    page.route("**/auth/connect/**", _auth_handler)
    page.route("**/user/verification**", _verification_handler)
