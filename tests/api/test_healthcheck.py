import pytest
import allure

from core.api.client import APIClient
from config.settings import settings


@pytest.mark.api
@pytest.mark.smoke
@allure.feature("API")
@allure.story("Healthcheck")
@allure.title("API documentation endpoint is available")
@allure.severity(allure.severity_level.NORMAL)
@allure.link("https://api.ufarm.digital/api/v1/docs#/", name="Swagger")
def test_api_docs_available():
    client = APIClient(settings.api_url)

    with allure.step("Отправляем GET /docs"):
        response = client.get("/docs")

    with allure.step(f"Статус ответа == 200 (получен {response.status_code})"):
        assert response.status_code == 200
