"""Tests for file_link message opaque ID usage.

Verifies that file_link messages created during agent streaming use opaque IDs
(bond_file_xxx) instead of full S3 URIs, preventing nginx merge_slashes from
corrupting s3:// in download URLs.
"""
import json
import pytest
from unittest.mock import MagicMock
from dataclasses import dataclass

from bondable.bond.providers.files import to_opaque_id
from bondable.rest.routers.files import _resolve_file_id


@dataclass
class MockFileDetails:
    file_id: str
    file_path: str
    file_size: int
    mime_type: str
    file_hash: str = "abc123"
    owner_user_id: str = "user_1"


class TestFileLinkOpaqueId:
    """Verify that file_link messages use opaque IDs, not S3 URIs."""

    def test_file_link_message_uses_opaque_id(self):
        """file_link message content must contain opaque ID, not S3 URI."""
        s3_uri = "s3://bond-bedrock-files-019593708315/files/bond_file_deadbeef1234"
        file_details = MockFileDetails(
            file_id=s3_uri,
            file_path="hello_world.html",
            file_size=2500,
            mime_type="text/html",
        )

        message_content = json.dumps({
            'file_id': to_opaque_id(file_details.file_id),
            'file_name': file_details.file_path,
            'file_size': file_details.file_size,
            'mime_type': file_details.mime_type
        })

        parsed = json.loads(message_content)

        assert parsed['file_id'] == "bond_file_deadbeef1234"
        assert "s3://" not in parsed['file_id']
        assert "bond-bedrock-files" not in parsed['file_id']
        assert "019593708315" not in parsed['file_id']

    def test_opaque_id_safe_for_nginx_proxy(self):
        """Opaque IDs must not contain characters that nginx would mangle."""
        test_uris = [
            "s3://bond-bedrock-files-123/files/bond_file_aabbccdd",
            "s3://my-bucket/files/bond_file_11223344aabbccdd",
            "s3://bond-bedrock-files-000000000000/files/bond_file_deadbeef",
        ]

        for uri in test_uris:
            opaque_id = to_opaque_id(uri)
            assert "/" not in opaque_id, f"Opaque ID '{opaque_id}' contains slash (from {uri})"
            assert ":" not in opaque_id, f"Opaque ID '{opaque_id}' contains colon (from {uri})"
            # Simulate nginx merge_slashes — opaque ID must be unchanged
            assert opaque_id.replace("//", "/") == opaque_id

    def test_mangled_s3_uri_fails_resolve(self):
        """Prove that nginx merge_slashes on an S3 URI causes the 400 error."""
        s3_uri = "s3://bond-bedrock-files-123/files/bond_file_aabb"
        mangled_uri = s3_uri.replace("//", "/")  # s3:/bond-bedrock-files-123/files/bond_file_aabb

        provider = MagicMock()
        provider.files.bucket_name = "bond-bedrock-files-123"

        with pytest.raises(ValueError):
            _resolve_file_id(mangled_uri, provider)


class TestBedrockAgentFileEvent:
    """Verify BedrockAgent._handle_file_event produces opaque IDs."""

    def test_handle_file_event_uses_opaque_id(self):
        """The actual BedrockAgent code path must produce opaque file IDs."""
        from bondable.bond.providers.bedrock.BedrockAgent import BedrockAgent

        # Build a minimal agent with mocked provider
        agent = object.__new__(BedrockAgent)
        agent.agent_id = "test_agent"
        agent.model = "test_model"
        agent.bedrock_agent_id = "bedrock_123"

        mock_provider = MagicMock()
        agent.bond_provider = mock_provider

        s3_uri = "s3://bond-bedrock-files-019593708315/files/bond_file_aabbccdd1122"
        mock_provider.files.get_or_create_file_id.return_value = MockFileDetails(
            file_id=s3_uri,
            file_path="report.html",
            file_size=4096,
            mime_type="text/html",
        )
        mock_provider.threads.add_message.return_value = "msg_123"

        # _handle_file_event is a generator — consume it to trigger side effects
        file_info = {
            'bytes': b'<html><body>Hello</body></html>',
            'name': 'report.html',
            'type': 'text/html',
        }

        list(agent._handle_file_event(
            file_info=file_info,
            thread_id="thread_1",
            user_id="user_1",
        ))

        # Verify add_message was called with opaque ID in content
        mock_provider.threads.add_message.assert_called_once()
        call_kwargs = mock_provider.threads.add_message.call_args.kwargs
        parsed = json.loads(call_kwargs['content'])

        assert parsed['file_id'] == "bond_file_aabbccdd1122"
        assert "s3://" not in parsed['file_id']
        assert parsed['file_name'] == "report.html"
        assert parsed['mime_type'] == "text/html"
        assert call_kwargs['message_type'] == 'file_link'
