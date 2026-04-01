"""
Tests for MAS-134: XSS prevention via thread_id/agent_id validation.
Tests for ChatAttachment.file_id validation (prevents S3 URI injection).

Validates that ChatRequest rejects values containing characters unsafe for
XML attribute interpolation. XML escaping in the rendering layer is the
primary defense; these validators are defense-in-depth.
"""
import pytest
from pydantic import ValidationError

from bondable.rest.models.chat import ChatRequest, ChatAttachment


class TestThreadIdValidation:
    """thread_id field validation on ChatRequest."""

    def test_valid_thread_id_accepted(self):
        req = ChatRequest(thread_id="thread_abc123", agent_id="agent_1", prompt="hi")
        assert req.thread_id == "thread_abc123"

    def test_none_thread_id_accepted(self):
        req = ChatRequest(thread_id=None, agent_id="agent_1", prompt="hi")
        assert req.thread_id is None

    def test_hyphenated_thread_id_accepted(self):
        req = ChatRequest(thread_id="thread-abc-123", agent_id="agent_1", prompt="hi")
        assert req.thread_id == "thread-abc-123"

    def test_xss_script_tag_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(thread_id='<script>alert(1)</script>', agent_id="a", prompt="hi")

    def test_xss_attribute_breakout_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(thread_id='"><img src=x onerror=alert(1)>', agent_id="a", prompt="hi")

    def test_xml_entities_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(thread_id='thread&amp;id', agent_id="a", prompt="hi")

    def test_quotes_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(thread_id='thread"id', agent_id="a", prompt="hi")

    def test_spaces_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(thread_id='thread id', agent_id="a", prompt="hi")


class TestAgentIdValidation:
    """agent_id field validation on ChatRequest."""

    def test_valid_agent_id_accepted(self):
        req = ChatRequest(agent_id="bedrock_agent_abc123", prompt="hi")
        assert req.agent_id == "bedrock_agent_abc123"

    def test_simple_agent_id_accepted(self):
        req = ChatRequest(agent_id="agent_1", prompt="hi")
        assert req.agent_id == "agent_1"

    def test_empty_agent_id_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(agent_id="", prompt="hi")

    def test_xss_payload_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(agent_id='"><script>alert(1)</script>', prompt="hi")

    def test_angle_brackets_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(agent_id="agent<bad>", prompt="hi")

    def test_slash_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(agent_id="agent/../../etc", prompt="hi")


class TestAttachmentFileIdValidation:
    """ChatAttachment.file_id validation — prevents S3 URI injection."""

    def test_valid_opaque_id_accepted(self):
        att = ChatAttachment(file_id="bond_file_abc123def456", suggested_tool="file_search")
        assert att.file_id == "bond_file_abc123def456"

    def test_s3_uri_rejected(self):
        """Raw S3 URIs must not be accepted from clients."""
        with pytest.raises(ValidationError):
            ChatAttachment(file_id="s3://some-bucket/files/bond_file_abc", suggested_tool="file_search")

    def test_cross_bucket_s3_uri_rejected(self):
        with pytest.raises(ValidationError):
            ChatAttachment(file_id="s3://other-bucket/secrets.csv", suggested_tool="file_search")

    def test_empty_file_id_rejected(self):
        with pytest.raises(ValidationError):
            ChatAttachment(file_id="", suggested_tool="file_search")

    def test_arbitrary_string_rejected(self):
        with pytest.raises(ValidationError):
            ChatAttachment(file_id="not_a_valid_id", suggested_tool="file_search")

    def test_path_traversal_rejected(self):
        with pytest.raises(ValidationError):
            ChatAttachment(file_id="../../../etc/passwd", suggested_tool="file_search")

    def test_valid_id_in_chat_request(self):
        req = ChatRequest(
            agent_id="agent_1",
            prompt="hi",
            attachments=[ChatAttachment(file_id="bond_file_aabb1122", suggested_tool="code_interpreter")]
        )
        assert req.attachments[0].file_id == "bond_file_aabb1122"

    def test_s3_uri_in_chat_request_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(
                agent_id="agent_1",
                prompt="hi",
                attachments=[ChatAttachment(file_id="s3://bucket/file", suggested_tool="file_search")]
            )
