from core.api.client import APIClient
from config.settings import settings


def test_api_docs_available():
    client = APIClient(settings.api_url)
    response = client.get("/docs")
    assert response.status_code == 200