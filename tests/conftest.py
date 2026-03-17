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
