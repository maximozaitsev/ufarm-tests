import allure
import pytest


@pytest.fixture(autouse=True)
def screenshot_on_failure(request, page):
    """Прикрепляет скриншот к Allure-отчёту при падении UI-теста.

    Покрывает оба статуса Allure:
      - failed  → AssertionError (rep_call.failed)
      - broken  → любой другой exception, включая TimeoutError (rep_call.failed)
      - broken  → ошибка в фикстуре (rep_setup.failed)
    """
    yield
    setup_failed = getattr(getattr(request.node, "rep_setup", None), "failed", False)
    call_failed = getattr(getattr(request.node, "rep_call", None), "failed", False)
    if setup_failed or call_failed:
        try:
            allure.attach(
                page.screenshot(full_page=True),
                name="Screenshot on failure",
                attachment_type=allure.attachment_type.PNG,
            )
        except Exception:
            pass  # страница в bad state — не роняем teardown
