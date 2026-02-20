"""
Integration tests for XLSM file upload and Bedrock processing.

This test suite verifies that XLSM files are properly converted to XLSX
during upload and can be successfully processed by Bedrock agents.

Prerequisites:
- Backend server running: uvicorn bondable.rest.main:app --reload
- AWS credentials configured for Bedrock access
"""

import pytest
pytestmark = pytest.mark.skip(reason="Integration test: requires live AWS Bedrock and running backend server")
import requests
import io
import openpyxl
from datetime import datetime, timedelta, timezone
from jose import jwt
from typing import Optional


def create_auth_token(user_email: str = "xlsmtest@example.com") -> str:
    """Create a JWT token for authentication."""
    from bondable.bond.config import Config
    jwt_config = Config.config().get_jwt_config()

    token_data = {
        "sub": user_email,
        "name": "XLSM Test User",
        "user_id": f"test_user_{user_email.split('@')[0]}",
        "provider": "google",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=jwt_config.ACCESS_TOKEN_EXPIRE_MINUTES)
    }

    token = jwt.encode(token_data, jwt_config.JWT_SECRET_KEY, algorithm=jwt_config.JWT_ALGORITHM)
    return token


def create_sample_xlsm() -> io.BytesIO:
    """Create a sample XLSM file with test data"""
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Test Data"

    # Add headers
    sheet['A1'] = "Product"
    sheet['B1'] = "Sales"
    sheet['C1'] = "Cost"
    sheet['D1'] = "Profit"

    # Add sample data
    products = [
        ("Product A", 1000, 600, "=B2-C2"),
        ("Product B", 1500, 800, "=B3-C3"),
        ("Product C", 2000, 1200, "=B4-C4"),
    ]

    for i, (product, sales, cost, profit_formula) in enumerate(products, start=2):
        sheet[f'A{i}'] = product
        sheet[f'B{i}'] = sales
        sheet[f'C{i}'] = cost
        sheet[f'D{i}'] = profit_formula

    # Add total row
    sheet['A5'] = "Total"
    sheet['B5'] = "=SUM(B2:B4)"
    sheet['C5'] = "=SUM(C2:C4)"
    sheet['D5'] = "=SUM(D2:D4)"

    file_bytes = io.BytesIO()
    workbook.save(file_bytes)
    file_bytes.seek(0)

    return file_bytes


class TestXLSMBedrockIntegration:
    """Integration tests for XLSM file processing with Bedrock"""

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

    def test_health_check(self):
        """Verify backend is running."""
        response = requests.get(f"{self.BASE_URL}/health")
        assert response.status_code == 200
        print("\n✓ Backend health check passed")

    def test_xlsm_upload_conversion(self, auth_headers):
        """
        Test that XLSM file is uploaded and converted to XLSX.

        Verifies:
        1. File upload succeeds
        2. MIME type is changed to XLSX
        3. Filename extension is changed to .xlsx
        """
        print(f"\n{'='*60}")
        print("Testing XLSM Upload and Conversion")
        print(f"{'='*60}")

        # Create sample XLSM file
        xlsm_bytes = create_sample_xlsm()

        # Upload the file
        files = {
            'file': ('test_data.xlsm', xlsm_bytes, 'application/vnd.ms-excel.sheet.macroEnabled.12')
        }

        print(f"\n1. Uploading XLSM file...")
        response = requests.post(
            f"{self.BASE_URL}/files/upload",
            headers=auth_headers,
            files=files
        )

        assert response.status_code == 200, f"Upload failed: {response.text}"
        upload_data = response.json()

        print(f"   ✓ Upload successful")
        print(f"   - File ID: {upload_data.get('file_id', 'N/A')}")
        print(f"   - MIME type: {upload_data.get('mime_type', 'N/A')}")
        print(f"   - File name: {upload_data.get('file_name', 'N/A')}")
        print(f"   - Suggested tool: {upload_data.get('suggested_tool', 'N/A')}")

        # Verify conversion happened
        assert upload_data['mime_type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', \
            "MIME type should be XLSX after conversion"

        assert upload_data['file_name'].endswith('.xlsx'), \
            "Filename should end with .xlsx after conversion"

        assert upload_data['suggested_tool'] == 'code_interpreter', \
            "Excel files should suggest code_interpreter tool"

        print(f"\n{'='*60}")
        print("✓ XLSM Conversion Test PASSED!")
        print(f"{'='*60}")

    def test_xlsm_with_bedrock_agent(self, auth_headers, home_agent_id):
        """
        Test complete workflow: Upload XLSM, attach to thread, send to Bedrock agent.

        Verifies:
        1. XLSM uploads successfully
        2. File can be attached to a chat thread
        3. Bedrock agent accepts the converted file
        4. Agent can process the file data
        """
        print(f"\n{'='*60}")
        print("Testing XLSM with Bedrock Agent")
        print(f"{'='*60}")

        # Step 1: Create a thread
        print(f"\n1. Creating test thread...")
        thread_response = requests.post(
            f"{self.BASE_URL}/threads",
            headers=auth_headers,
            json={"name": "XLSM Test Thread"}
        )
        assert thread_response.status_code == 201, f"Thread creation failed: {thread_response.text}"
        thread_id = thread_response.json()["id"]
        print(f"   ✓ Thread created: {thread_id}")

        try:
            # Step 2: Upload XLSM file
            print(f"\n2. Uploading XLSM file...")
            xlsm_bytes = create_sample_xlsm()
            files = {
                'file': ('sales_data.xlsm', xlsm_bytes, 'application/vnd.ms-excel.sheet.macroEnabled.12')
            }

            upload_response = requests.post(
                f"{self.BASE_URL}/files/upload",
                headers=auth_headers,
                files=files
            )
            assert upload_response.status_code == 200, f"Upload failed: {upload_response.text}"
            file_id = upload_response.json()['file_id']
            print(f"   ✓ File uploaded: {file_id}")

            # Step 3: Send message with file attachment
            print(f"\n3. Sending message to Bedrock agent with file...")
            chat_request = {
                "thread_id": thread_id,
                "agent_id": home_agent_id,
                "prompt": "I've uploaded a sales data file. Can you tell me what's in it?",
                "attachments": [
                    {
                        "file_id": file_id,
                        "tools": [{"type": "code_interpreter"}]
                    }
                ]
            }

            chat_response = requests.post(
                f"{self.BASE_URL}/chat",
                headers=auth_headers,
                json=chat_request,
                stream=True
            )

            assert chat_response.status_code == 200, f"Chat request failed: {chat_response.text}"
            print(f"   ✓ Chat request sent successfully")

            # Step 4: Check for errors in response
            response_text = ""
            error_found = False

            for chunk in chat_response.iter_content(chunk_size=None, decode_unicode=True):
                if chunk:
                    response_text += chunk
                    if "validationException" in chunk or "Unable to determine MIME type" in chunk:
                        error_found = True
                        break

            assert not error_found, f"Bedrock validation error found in response: {response_text[:500]}"
            print(f"   ✓ Bedrock accepted the file without validation errors")

            print(f"\n{'='*60}")
            print("✓ XLSM Bedrock Integration Test PASSED!")
            print(f"{'='*60}")

        finally:
            # Cleanup: Delete thread
            delete_response = requests.delete(
                f"{self.BASE_URL}/threads/{thread_id}",
                headers=auth_headers
            )
            if delete_response.status_code == 204:
                print(f"\n✓ Cleaned up thread: {thread_id}")

    def test_xlsm_uppercase_extension(self, auth_headers):
        """Test that uppercase .XLSM extension is also handled"""
        xlsm_bytes = create_sample_xlsm()

        files = {
            'file': ('DATA.XLSM', xlsm_bytes, 'application/vnd.ms-excel.sheet.macroEnabled.12')
        }

        response = requests.post(
            f"{self.BASE_URL}/files/upload",
            headers=auth_headers,
            files=files
        )

        assert response.status_code == 200
        upload_data = response.json()

        # Should be converted to .xlsx (lowercase)
        assert upload_data['file_name'].endswith('.xlsx')
        assert upload_data['mime_type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

        print("\n✓ Uppercase .XLSM extension handled correctly")


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "-s"])
