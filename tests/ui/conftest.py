import allure
import pytest


@pytest.fixture(autouse=True)
def screenshot_on_failure(request):
    """Прикрепляет скриншот к Allure-отчёту при падении UI-теста.

    Покрывает оба статуса Allure:
      - failed  → AssertionError (rep_call.failed)
      - broken  → любой другой exception, включая TimeoutError (rep_call.failed)
      - broken  → ошибка в фикстуре (rep_setup.failed)

    Работает с фикстурами page и page_with_wallet.
    """
    yield
    setup_failed = getattr(getattr(request.node, "rep_setup", None), "failed", False)
    call_failed = getattr(getattr(request.node, "rep_call", None), "failed", False)
    if not (setup_failed or call_failed):
        return

    page = None
    for fixture_name in ("page", "page_with_wallet", "page_with_wallet_on_pool"):
        try:
            page = request.getfixturevalue(fixture_name)
            break
        except Exception:
            continue

    if page is None:
        return

    try:
        allure.attach(
            page.screenshot(full_page=True),
            name="Screenshot on failure",
            attachment_type=allure.attachment_type.PNG,
        )
    except Exception:
        pass  # страница в bad state — не роняем teardown
