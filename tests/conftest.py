import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run integration tests (requires running backend)",
    )
    parser.addoption(
        "--docker",
        action="store_true",
        default=False,
        help="Run Docker-based tests (requires Docker daemon)",
    )
    parser.addoption(
        "--investigation",
        action="store_true",
        default=False,
        help="Run concurrency investigation tests",
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--integration"):
        skip_integration = pytest.mark.skip(reason="needs --integration flag to run")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)

    if not config.getoption("--docker"):
        skip_docker = pytest.mark.skip(reason="needs --docker flag to run")
        for item in items:
            if "docker" in item.keywords:
                item.add_marker(skip_docker)

    if not config.getoption("--investigation"):
        skip_investigation = pytest.mark.skip(reason="needs --investigation flag to run")
        for item in items:
            if "investigation" in item.keywords:
                item.add_marker(skip_investigation)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset slowapi rate limiter before each test.

    Multiple tests across the suite hit rate-limited auth endpoints
    (e.g. /auth/cognito/callback at 10/min). Without per-test reset,
    later tests in the suite see 429s purely from earlier tests' calls.
    """
    try:
        from bondable.rest.routers.auth import limiter
        limiter.reset()
    except Exception:
        # Don't fail collection if the import path changes; the fixture is best-effort.
        pass
    yield
