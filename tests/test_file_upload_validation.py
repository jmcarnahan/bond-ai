import pytest
import os
import tempfile
from unittest.mock import MagicMock
from datetime import timedelta

# --- Test Database Setup ---
_test_db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
TEST_METADATA_DB_URL = f"sqlite:///{_test_db_file.name}"
os.environ['METADATA_DB_URL'] = TEST_METADATA_DB_URL
os.environ['OAUTH2_ENABLED_PROVIDERS'] = 'cognito'

# Import after setting environment
from fastapi.testclient import TestClient
from bondable.rest.main import app, create_access_token, get_bond_provider
from bondable.bond.providers.provider import Provider
from bondable.bond.providers.files import FilesProvider, FileDetails

# Test configuration
TEST_USER_EMAIL = "test@example.com"
TEST_USER_ID = "test-user-id-123"


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    """Clean up test database after session."""
    yield
    db_path = TEST_METADATA_DB_URL.replace("sqlite:///", "")
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def mock_provider():
    provider = MagicMock(spec=Provider)
    provider.files = MagicMock(spec=FilesProvider)
    return provider


@pytest.fixture
def auth_headers():
    token_data = {
        "sub": TEST_USER_EMAIL,
        "name": "Test User",
        "provider": "cognito",
        "user_id": TEST_USER_ID,
    }
    access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=15))
    return {"Authorization": f"Bearer {access_token}"}


def _make_file_details(file_path="test.pdf", mime_type="application/pdf"):
    return FileDetails(
        file_id="s3://bond-bedrock-files-000000000000/files/bond_file_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        file_path=file_path,
        file_hash="abc123",
        mime_type=mime_type,
        owner_user_id=TEST_USER_ID,
    )


def _upload(test_client, auth_headers, filename, content=b"fake content", content_type="application/octet-stream"):
    return test_client.post(
        "/files",
        files={"file": (filename, content, content_type)},
        headers=auth_headers,
    )


# --- Allowed extension tests ---

def test_allowed_extension_pdf(test_client, mock_provider, auth_headers):
    mock_provider.files.get_or_create_file_id.return_value = _make_file_details("test.pdf", "application/pdf")
    app.dependency_overrides[get_bond_provider] = lambda: mock_provider
    response = _upload(test_client, auth_headers, "test.pdf", content_type="application/pdf")
    assert response.status_code == 200
    app.dependency_overrides.pop(get_bond_provider, None)


def test_allowed_extension_csv(test_client, mock_provider, auth_headers):
    mock_provider.files.get_or_create_file_id.return_value = _make_file_details("data.csv", "text/csv")
    app.dependency_overrides[get_bond_provider] = lambda: mock_provider
    response = _upload(test_client, auth_headers, "data.csv", content_type="text/csv")
    assert response.status_code == 200
    app.dependency_overrides.pop(get_bond_provider, None)


def test_allowed_extension_png(test_client, mock_provider, auth_headers):
    mock_provider.files.get_or_create_file_id.return_value = _make_file_details("image.png", "image/png")
    app.dependency_overrides[get_bond_provider] = lambda: mock_provider
    response = _upload(test_client, auth_headers, "image.png", content_type="image/png")
    assert response.status_code == 200
    app.dependency_overrides.pop(get_bond_provider, None)


# --- Blocked extension tests ---

def test_blocked_extension_exe(test_client, mock_provider, auth_headers):
    app.dependency_overrides[get_bond_provider] = lambda: mock_provider
    response = _upload(test_client, auth_headers, "malware.exe")
    assert response.status_code == 422
    assert "not allowed" in response.json()["detail"]
    app.dependency_overrides.pop(get_bond_provider, None)


def test_blocked_extension_sh(test_client, mock_provider, auth_headers):
    app.dependency_overrides[get_bond_provider] = lambda: mock_provider
    response = _upload(test_client, auth_headers, "script.sh")
    assert response.status_code == 422
    assert "not allowed" in response.json()["detail"]
    app.dependency_overrides.pop(get_bond_provider, None)


def test_blocked_extension_bat(test_client, mock_provider, auth_headers):
    app.dependency_overrides[get_bond_provider] = lambda: mock_provider
    response = _upload(test_client, auth_headers, "run.bat")
    assert response.status_code == 422
    assert "not allowed" in response.json()["detail"]
    app.dependency_overrides.pop(get_bond_provider, None)


# --- Unknown extension tests ---

def test_unknown_extension_rb(test_client, mock_provider, auth_headers):
    app.dependency_overrides[get_bond_provider] = lambda: mock_provider
    response = _upload(test_client, auth_headers, "script.rb")
    assert response.status_code == 422
    assert "not supported" in response.json()["detail"]
    app.dependency_overrides.pop(get_bond_provider, None)


def test_no_extension(test_client, mock_provider, auth_headers):
    app.dependency_overrides[get_bond_provider] = lambda: mock_provider
    response = _upload(test_client, auth_headers, "Makefile")
    assert response.status_code == 422
    assert "not supported" in response.json()["detail"]
    app.dependency_overrides.pop(get_bond_provider, None)


# --- Case insensitivity tests ---

def test_case_insensitive_PDF(test_client, mock_provider, auth_headers):
    mock_provider.files.get_or_create_file_id.return_value = _make_file_details("report.PDF", "application/pdf")
    app.dependency_overrides[get_bond_provider] = lambda: mock_provider
    response = _upload(test_client, auth_headers, "report.PDF", content_type="application/pdf")
    assert response.status_code == 200
    app.dependency_overrides.pop(get_bond_provider, None)


def test_case_insensitive_EXE(test_client, mock_provider, auth_headers):
    app.dependency_overrides[get_bond_provider] = lambda: mock_provider
    response = _upload(test_client, auth_headers, "malware.EXE")
    assert response.status_code == 422
    app.dependency_overrides.pop(get_bond_provider, None)


# --- Double extension test ---

def test_double_extension_tar_gz(test_client, mock_provider, auth_headers):
    app.dependency_overrides[get_bond_provider] = lambda: mock_provider
    response = _upload(test_client, auth_headers, "archive.tar.gz")
    assert response.status_code == 422
    app.dependency_overrides.pop(get_bond_provider, None)
