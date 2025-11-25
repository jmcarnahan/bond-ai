"""
Integration tests for file download functionality.

This test suite verifies that non-image files returned by Bedrock agents
can be properly downloaded by users.

Prerequisites:
- Backend server running: uvicorn bondable.rest.main:app --reload
- AWS credentials configured for Bedrock access
"""

import pytest
import requests
import re
import json
from datetime import datetime, timedelta, timezone
from jose import jwt
from typing import Optional, Dict
from urllib.parse import quote


def create_auth_token(user_email: str = "filetest@example.com") -> str:
    """Create a JWT token for authentication."""
    from bondable.bond.config import Config
    jwt_config = Config.config().get_jwt_config()

    token_data = {
        "sub": user_email,
        "name": "File Test User",
        "user_id": f"test_user_{user_email.split('@')[0]}",
        "provider": "google",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=jwt_config.ACCESS_TOKEN_EXPIRE_MINUTES)
    }

    token = jwt.encode(token_data, jwt_config.JWT_SECRET_KEY, algorithm=jwt_config.JWT_ALGORITHM)
    return token


class TestFileDownloadIntegration:
    """Integration tests for file download functionality."""

    BASE_URL = "http://localhost:8000"

    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Create authenticated headers for API requests."""
        token = create_auth_token()
        return {"Authorization": f"Bearer {token}"}

    @pytest.fixture(scope="class")
    def home_agent_id(self, auth_headers):
        """Get the Home (default) agent ID."""
        response = requests.get(f"{self.BASE_URL}/agents/default", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get default agent: {response.text}"

        agent_data = response.json()
        agent_id = agent_data["agent_id"]
        print(f"\n✓ Got Home agent: {agent_id}")
        return agent_id

    @pytest.fixture
    def test_thread(self, auth_headers):
        """Create a test thread and clean it up after the test."""
        # Create thread
        response = requests.post(
            f"{self.BASE_URL}/threads",
            headers=auth_headers,
            json={"name": "File Download Test Thread"}
        )
        assert response.status_code == 201, f"Failed to create thread: {response.text}"

        thread_data = response.json()
        thread_id = thread_data["id"]
        print(f"✓ Created test thread: {thread_id}")

        yield thread_id

        # Cleanup: Delete thread
        delete_response = requests.delete(
            f"{self.BASE_URL}/threads/{thread_id}",
            headers=auth_headers
        )
        if delete_response.status_code == 204:
            print(f"✓ Cleaned up thread: {thread_id}")

    def test_health_check(self):
        """Verify backend is running."""
        response = requests.get(f"{self.BASE_URL}/health")
        assert response.status_code == 200
        print("\n✓ Backend health check passed")

    def test_authentication(self, auth_headers):
        """Verify authentication works."""
        response = requests.get(f"{self.BASE_URL}/users/me", headers=auth_headers)
        assert response.status_code == 200

        user_data = response.json()
        assert user_data["email"] == "filetest@example.com"
        print(f"✓ Authentication successful for {user_data['email']}")

    def test_file_creation_and_download(self, auth_headers, home_agent_id, test_thread):
        """
        Test complete file creation and download workflow:
        1. Ask Home agent to create a text file
        2. Parse the file_link message from response
        3. Download the file
        4. Verify file contents
        """
        print(f"\n{'='*60}")
        print("Testing File Creation and Download")
        print(f"{'='*60}")

        # Step 1: Send chat message to create file
        chat_request = {
            "thread_id": test_thread,
            "agent_id": home_agent_id,
            "prompt": "Create a text file named 'test.txt' containing exactly the text 'hello world' and return it to me."
        }

        print(f"\n1. Sending chat request to create file...")
        response = requests.post(
            f"{self.BASE_URL}/chat",
            headers=auth_headers,
            json=chat_request,
            stream=True
        )
        assert response.status_code == 200, f"Chat request failed: {response.text}"

        # Step 2: Parse streaming response for file_link message
        print("2. Parsing streaming response...")
        full_response = ""
        file_metadata = None

        # Collect all chunks first
        for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
            if chunk:
                full_response += chunk

        # Now extract file metadata from complete response
        file_metadata = self._extract_file_metadata(full_response)

        if file_metadata:
            print(f"   ✓ Found file_link message!")
            print(f"   - File ID: {file_metadata.get('file_id', 'N/A')}")
            print(f"   - File Name: {file_metadata.get('file_name', 'N/A')}")
            print(f"   - File Size: {file_metadata.get('file_size', 'N/A')} bytes")
            print(f"   - MIME Type: {file_metadata.get('mime_type', 'N/A')}")

        # Verify we got file metadata
        assert file_metadata is not None, f"No file_link found in response. Response preview: {full_response[:1000]}"
        assert "file_id" in file_metadata, "file_id not found in file metadata"

        file_id = file_metadata["file_id"]

        # Step 3: Download the file
        print(f"\n3. Downloading file: {file_id}...")
        # The backend route uses :path converter, so we can pass the S3 URI directly
        download_url = f"{self.BASE_URL}/files/download/{file_id}"
        print(f"   Download URL: {download_url}")
        download_response = requests.get(download_url, headers=auth_headers)

        print(f"   Response status: {download_response.status_code}")
        if download_response.status_code != 200:
            print(f"   Response body: {download_response.text}")

        assert download_response.status_code == 200, f"Download failed with {download_response.status_code}: {download_response.text}"

        # Step 4: Verify file content
        print("4. Verifying file contents...")
        file_content = download_response.content.decode('utf-8')

        print(f"   Downloaded content: '{file_content}'")
        assert "hello world" in file_content.lower(), f"Expected 'hello world' in file, got: {file_content}"

        # Verify headers
        assert "content-disposition" in download_response.headers, "Missing Content-Disposition header"
        assert "attachment" in download_response.headers["content-disposition"], "Not set as attachment"

        print(f"\n{'='*60}")
        print("✓ File download test PASSED!")
        print(f"{'='*60}")

    def _extract_file_metadata(self, response_text: str) -> Optional[Dict]:
        """
        Extract file metadata from bondmessage XML in the response.

        The message should look like:
        <_bondmessage type="file_link" ...>
        {"file_id": "...", "file_name": "...", "file_size": ..., "mime_type": "..."}
        </_bondmessage>
        """
        # Look for file_link bondmessage
        pattern = r'<_bondmessage[^>]*type="file_link"[^>]*>(.*?)</_bondmessage>'
        matches = re.findall(pattern, response_text, re.DOTALL)

        if not matches:
            return None

        # Get the last match (in case there are multiple files)
        content = matches[-1].strip()

        try:
            # Try to parse as JSON
            return json.loads(content)
        except json.JSONDecodeError:
            # Content might not be JSON yet, return None
            return None


class TestFileDownloadSecurity:
    """Test security aspects of file downloads."""

    BASE_URL = "http://localhost:8000"

    def test_download_requires_authentication(self):
        """Verify that file download requires authentication."""
        # Try to download without auth header
        response = requests.get(f"{self.BASE_URL}/files/download/some_file_id")
        assert response.status_code == 401, "Download should require authentication"
        print("\n✓ Download correctly requires authentication")

    def test_download_nonexistent_file(self):
        """Verify proper error for non-existent file."""
        token = create_auth_token()
        headers = {"Authorization": f"Bearer {token}"}

        response = requests.get(
            f"{self.BASE_URL}/files/download/nonexistent_file_12345",
            headers=headers
        )
        assert response.status_code in [404, 403], f"Expected 404 or 403, got {response.status_code}"
        print("✓ Non-existent file returns proper error")


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "-s"])
