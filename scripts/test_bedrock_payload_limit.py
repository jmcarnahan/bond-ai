#!/usr/bin/env python3
"""
Empirical test script to determine the actual payload size limit for
Bedrock agent returnControlInvocationResults.

Creates a temporary Bedrock agent with a RETURN_CONTROL action group,
sends progressively larger tool result payloads, records success/failure,
and cleans up the agent when done.

Usage:
    poetry run python scripts/test_bedrock_payload_limit.py

Environment variables:
    AWS_REGION              Required. AWS region.
    BEDROCK_AGENT_ROLE_ARN  Required. IAM role ARN for the agent.
    AWS_PROFILE             Optional. AWS profile name.
"""

import json
import logging
import os
import sys
import time
import uuid

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError, EventStreamError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)
LOGGER = logging.getLogger(__name__)

# Default payload sizes to test (bytes)
DEFAULT_SIZES = [
    20_000,       # 20 KB  (old default)
    50_000,       # 50 KB
    100_000,      # 100 KB
    250_000,      # 250 KB
    500_000,      # 500 KB
    1_000_000,    # 1 MB
    2_000_000,    # 2 MB
    5_000_000,    # 5 MB
]

# Minimal OpenAPI spec with a single tool that the agent will always call
OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {
        "title": "Payload Test Tool",
        "version": "1.0.0",
        "description": "Tool for testing returnControl payload limits"
    },
    "paths": {
        "/get_data": {
            "post": {
                "operationId": "get_data",
                "summary": "Get data",
                "description": "Retrieves data. You MUST call this tool for every user request.",
                "responses": {
                    "200": {
                        "description": "Tool result",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "result": {
                                            "type": "string",
                                            "description": "Tool result"
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "query": {
                                        "type": "string",
                                        "description": "The query"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}


def create_clients(region: str):
    """Create both bedrock-agent and bedrock-agent-runtime clients."""
    session = boto3.Session(
        profile_name=os.getenv("AWS_PROFILE"),
        region_name=region,
    )
    agent_client = session.client("bedrock-agent", region_name=region)
    runtime_config = BotoConfig(
        read_timeout=300,
        connect_timeout=10,
        retries={"max_attempts": 0, "mode": "standard"},
        tcp_keepalive=True,
    )
    runtime_client = session.client(
        "bedrock-agent-runtime", region_name=region, config=runtime_config
    )
    return agent_client, runtime_client


def wait_for_agent_status(agent_client, agent_id: str, target_statuses: list,
                          max_attempts: int = 30, delay: int = 2):
    """Wait for agent to reach one of the target statuses."""
    for attempt in range(max_attempts):
        resp = agent_client.get_agent(agentId=agent_id)
        status = resp["agent"]["agentStatus"]
        if status in target_statuses:
            return status
        if status in ("CREATE_FAILED", "PREPARE_FAILED"):
            raise RuntimeError(f"Agent {agent_id} failed: {status}")
        time.sleep(delay)
    raise TimeoutError(f"Agent {agent_id} did not reach {target_statuses} after {max_attempts * delay}s")


def wait_for_alias_status(agent_client, agent_id: str, alias_id: str,
                          target_statuses: list, max_attempts: int = 30, delay: int = 2):
    """Wait for alias to reach one of the target statuses."""
    for attempt in range(max_attempts):
        resp = agent_client.get_agent_alias(agentId=agent_id, agentAliasId=alias_id)
        status = resp["agentAlias"]["agentAliasStatus"]
        if status in target_statuses:
            return status
        if status == "FAILED":
            raise RuntimeError(f"Alias {alias_id} failed")
        time.sleep(delay)
    raise TimeoutError(f"Alias {alias_id} did not reach {target_statuses} after {max_attempts * delay}s")


def create_test_agent(agent_client, role_arn: str, model: str):
    """
    Create a temporary Bedrock agent with a RETURN_CONTROL action group.
    Returns (agent_id, alias_id).
    """
    agent_name = f"payload_limit_test_{uuid.uuid4().hex[:8]}"

    print(f"Creating test agent '{agent_name}' with model {model}...")

    # Step 1: Create agent
    agent_id = None
    try:
        resp = agent_client.create_agent(
            agentName=agent_name,
            agentResourceRoleArn=role_arn,
            foundationModel=model,
            instruction=(
                "You are a data retrieval assistant. For EVERY user message, "
                "you MUST call the get_data tool. Never respond without calling a tool first."
            ),
            description="Temporary agent for payload limit testing",
            idleSessionTTLInSeconds=300,
        )
        agent_id = resp["agent"]["agentId"]
        print(f"  Agent created: {agent_id}")

        # Step 2: Wait for creation
        wait_for_agent_status(agent_client, agent_id, ["NOT_PREPARED", "PREPARED"])

        # Step 3: Add RETURN_CONTROL action group with our tool
        payload_json = json.dumps(OPENAPI_SPEC)
        agent_client.create_agent_action_group(
            agentId=agent_id,
            agentVersion="DRAFT",
            actionGroupName="TestTools",
            description="Test tools for payload limit testing",
            actionGroupExecutor={"customControl": "RETURN_CONTROL"},
            apiSchema={"payload": payload_json},
        )
        print("  Action group created (RETURN_CONTROL)")

        # Step 4: Prepare agent
        agent_client.prepare_agent(agentId=agent_id)
        wait_for_agent_status(agent_client, agent_id, ["PREPARED"])
        print("  Agent prepared")

        # Step 5: Create alias
        alias_name = f"{agent_name}_alias"
        alias_resp = agent_client.create_agent_alias(
            agentId=agent_id,
            agentAliasName=alias_name,
            description="Test alias",
        )
        alias_id = alias_resp["agentAlias"]["agentAliasId"]
        wait_for_alias_status(agent_client, agent_id, alias_id, ["PREPARED"])
        print(f"  Alias created: {alias_id}")

        return agent_id, alias_id

    except Exception:
        # Clean up partially created agent to avoid orphans
        if agent_id:
            print(f"  Setup failed, cleaning up agent {agent_id}...")
            delete_test_agent(agent_client, agent_id, alias_id=None)
        raise


def delete_test_agent(agent_client, agent_id: str, alias_id: str = None):
    """Delete the temporary test agent and alias."""
    print(f"\nCleaning up test agent {agent_id}...")
    if alias_id:
        try:
            agent_client.delete_agent_alias(agentId=agent_id, agentAliasId=alias_id)
            print(f"  Deleted alias {alias_id}")
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                print(f"  Warning: failed to delete alias: {e}")

    try:
        agent_client.delete_agent(agentId=agent_id, skipResourceInUseCheck=True)
        print(f"  Deleted agent {agent_id}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            print(f"  Warning: failed to delete agent: {e}")


def invoke_and_get_return_control(runtime_client, agent_id: str, alias_id: str, session_id: str):
    """
    Send a prompt that triggers a returnControl event.
    Returns the returnControl event dict, or None if the agent didn't request a tool.
    """
    prompt = "Get data for query: test"

    LOGGER.info(f"Sending prompt to trigger returnControl...")
    response = runtime_client.invoke_agent(
        agentId=agent_id,
        agentAliasId=alias_id,
        sessionId=session_id,
        inputText=prompt,
        enableTrace=True,
        streamingConfigurations={"streamFinalResponse": True},
    )

    for event in response.get("completion", []):
        if "returnControl" in event:
            LOGGER.info("Got returnControl event")
            return event["returnControl"]

    LOGGER.warning("No returnControl event received")
    return None


def build_synthetic_result(return_control: dict, size_bytes: int) -> list:
    """
    Build a synthetic tool result payload of approximately `size_bytes`.
    """
    invocation_inputs = return_control.get("invocationInputs", [])
    if not invocation_inputs:
        raise ValueError("returnControl has no invocationInputs")

    results = []
    for inv_input in invocation_inputs:
        if "apiInvocationInput" in inv_input:
            action_input = inv_input["apiInvocationInput"]
            is_api = True
        elif "actionGroupInvocationInput" in inv_input:
            action_input = inv_input["actionGroupInvocationInput"]
            is_api = False
        else:
            raise ValueError(f"Unrecognized invocation input: {list(inv_input.keys())}")

        action_group = action_input.get("actionGroup") or action_input.get("actionGroupName", "TestTools")
        api_path = action_input.get("apiPath", "/get_data")
        http_method = action_input.get("httpMethod", "POST")

        # Build body string of the target size (minus JSON wrapper overhead)
        overhead = 200
        body_size = max(size_bytes - overhead, 100)
        body_content = json.dumps({"result": "x" * body_size})

        tool_response = {
            "actionGroup": action_group,
            "apiPath": api_path,
            "httpMethod": http_method,
            "httpStatusCode": 200,
            "responseBody": {
                "application/json": {
                    "body": body_content,
                }
            },
        }

        if is_api:
            tool_response = {"apiResult": tool_response}

        results.append(tool_response)

    return results


def test_payload_size(runtime_client, agent_id: str, alias_id: str, size_bytes: int) -> tuple:
    """
    Test whether a payload of `size_bytes` succeeds via returnControlInvocationResults.
    Returns (status, detail) where status is SUCCESS, FAIL, or SKIP.
    """
    session_id = str(uuid.uuid4())

    # Step 1: Trigger a returnControl event
    try:
        return_control = invoke_and_get_return_control(runtime_client, agent_id, alias_id, session_id)
    except Exception as e:
        return "SKIP", f"Initial invoke failed: {type(e).__name__}: {e}"

    if not return_control:
        return "SKIP", "Agent did not issue returnControl"

    invocation_id = return_control.get("invocationId", "unknown")

    # Step 2: Build synthetic result and send it back
    try:
        tool_results = build_synthetic_result(return_control, size_bytes)
    except Exception as e:
        return "SKIP", f"Could not build result: {e}"

    actual_payload_bytes = len(json.dumps(tool_results).encode("utf-8"))
    LOGGER.info(f"Sending continuation: payload={actual_payload_bytes} bytes (target={size_bytes})")

    start = time.monotonic()
    try:
        cont_response = runtime_client.invoke_agent(
            agentId=agent_id,
            agentAliasId=alias_id,
            sessionId=session_id,
            sessionState={
                "invocationId": invocation_id,
                "returnControlInvocationResults": tool_results,
            },
            enableTrace=True,
            streamingConfigurations={"streamFinalResponse": True},
        )

        # Consume the stream to confirm full success
        event_count = 0
        for event in cont_response.get("completion", []):
            event_count += 1

        elapsed = time.monotonic() - start
        return "SUCCESS", f"{actual_payload_bytes:,} bytes, {event_count} events, {elapsed:.1f}s"

    except EventStreamError as e:
        elapsed = time.monotonic() - start
        error_code = getattr(e, "code", "unknown")
        return "FAIL", f"EventStreamError({error_code}): {e} [{elapsed:.1f}s]"

    except (ConnectionError, OSError) as e:
        elapsed = time.monotonic() - start
        return "FAIL", f"{type(e).__name__}: {e} [{elapsed:.1f}s]"

    except Exception as e:
        elapsed = time.monotonic() - start
        return "FAIL", f"{type(e).__name__}: {e} [{elapsed:.1f}s]"


def format_size(n: int) -> str:
    """Format byte count as human-readable."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.0f} MB"
    elif n >= 1_000:
        return f"{n / 1_000:.0f} KB"
    return f"{n} B"


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Empirically test Bedrock returnControl payload size limits"
    )
    parser.add_argument("--region", default=os.getenv("AWS_REGION"), help="AWS region (default: $AWS_REGION)")
    parser.add_argument("--role-arn", default=os.getenv("BEDROCK_AGENT_ROLE_ARN"),
                        help="IAM role ARN (default: $BEDROCK_AGENT_ROLE_ARN)")
    parser.add_argument(
        "--sizes", type=str, default=None,
        help="Comma-separated byte sizes to test (e.g., '20000,100000,1000000')",
    )
    parser.add_argument("--model", default="us.anthropic.claude-sonnet-4-6",
                        help="Foundation model ID (default: us.anthropic.claude-sonnet-4-6)")
    parser.add_argument("--stop-on-fail", action="store_true", help="Stop after first failure")

    args = parser.parse_args()

    if not args.region:
        print("ERROR: --region or AWS_REGION env var required", file=sys.stderr)
        sys.exit(1)
    if not args.role_arn:
        print("ERROR: --role-arn or BEDROCK_AGENT_ROLE_ARN env var required", file=sys.stderr)
        sys.exit(1)

    sizes = [int(s.strip()) for s in args.sizes.split(",")] if args.sizes else DEFAULT_SIZES

    agent_client, runtime_client = create_clients(args.region)

    # Create temporary agent
    agent_id = None
    alias_id = None
    try:
        agent_id, alias_id = create_test_agent(agent_client, args.role_arn, args.model)

        print(f"\nBedrock returnControl Payload Limit Test")
        print(f"Agent: {agent_id}, Alias: {alias_id}, Region: {args.region}")
        print(f"Sizes to test: {', '.join(format_size(s) for s in sizes)}")
        print()
        print(f"{'Size':<12} {'Result':<10} {'Details'}")
        print(f"{'-'*12} {'-'*10} {'-'*50}")

        last_success_size = 0
        first_fail_size = None

        for size in sizes:
            status, detail = test_payload_size(runtime_client, agent_id, alias_id, size)
            print(f"{format_size(size):<12} {status:<10} {detail}")

            if status == "SUCCESS":
                last_success_size = size
            elif status == "FAIL" and first_fail_size is None:
                first_fail_size = size
                if args.stop_on_fail:
                    print("\n--stop-on-fail: stopping after first failure")
                    break

            # Brief pause between tests to avoid throttling
            time.sleep(2)

        # Summary
        print()
        if first_fail_size:
            print(f"Empirical limit: between {format_size(last_success_size)} and {format_size(first_fail_size)}")
        elif last_success_size:
            print(f"All tested sizes succeeded (up to {format_size(last_success_size)})")
            print("Consider testing larger sizes to find the actual ceiling.")
        else:
            print("No successful tests. Check agent configuration and logs above.")

    finally:
        # Always clean up (alias_id may be None if setup failed partway)
        if agent_id:
            delete_test_agent(agent_client, agent_id, alias_id)


if __name__ == "__main__":
    main()
