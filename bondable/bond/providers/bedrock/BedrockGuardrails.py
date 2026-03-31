"""
BedrockGuardrails - Helper for AWS Bedrock Guardrails configuration.

Reads guardrail ID and version from environment variables and provides
configuration dicts for both agent-level and converse-level guardrails.
"""

import os
import logging
from typing import Optional, Dict

LOGGER = logging.getLogger(__name__)

GUARDRAIL_BLOCK_MESSAGE = (
    "I'm unable to process that request due to our content safety policy. "
    "Please rephrase your message and try again."
)


def get_guardrail_id() -> Optional[str]:
    val = os.getenv('BEDROCK_GUARDRAIL_ID', '').strip()
    return val if val else None


def get_guardrail_version() -> Optional[str]:
    val = os.getenv('BEDROCK_GUARDRAIL_VERSION', '').strip()
    return val if val else None


def get_agent_guardrail_config() -> Optional[Dict[str, str]]:
    """Return guardrailConfiguration for create_agent/update_agent, or None if not configured."""
    gid = get_guardrail_id()
    gver = get_guardrail_version()
    if gid and gver:
        return {
            "guardrailIdentifier": gid,
            "guardrailVersion": gver,
        }
    return None


def get_converse_guardrail_config() -> Optional[Dict[str, str]]:
    """Return guardrailConfig for converse() calls, or None if not configured."""
    gid = get_guardrail_id()
    gver = get_guardrail_version()
    if gid and gver:
        return {
            "guardrailIdentifier": gid,
            "guardrailVersion": gver,
            "trace": "enabled",
        }
    return None
