#!/usr/bin/env python3
"""
Safely delete orphaned Bedrock agents that exist in AWS but NOT in Aurora DB.

Double-verifies each agent against the live Aurora database before deletion.

Usage:
    # Dry run (default) - reports what would be deleted
    python scripts/delete_orphaned_agents.py --dry-run

    # Delete a single agent for testing
    python scripts/delete_orphaned_agents.py --execute --agent-id RGRHD9OGTJ

    # Full deletion in batches of 10
    python scripts/delete_orphaned_agents.py --execute --batch-size 10

Environment variables:
    AWS_PROFILE  - AWS profile (default: agent-space)
    AWS_REGION   - AWS region (default: us-west-2)
"""

import argparse
import logging
import os
import re
import sys
import time

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
LOGGER = logging.getLogger(__name__)

# Aurora connection details
CLUSTER_ARN = "arn:aws:rds:us-west-2:019593708315:cluster:bond-ai-dev-aurora"
SECRET_ARN = "arn:aws:secretsmanager:us-west-2:019593708315:secret:bond-ai-dev-db-20251112200642294900000001-I7dOwA"  # nosec B105
DATABASE = "bondai"

DEFAULT_BATCH_SIZE = 10
DEFAULT_DELAY = 3  # seconds between batches
THROTTLE_MAX_RETRIES = 3
THROTTLE_BASE_DELAY = 2

ORPHANED_AGENTS_FILE = os.path.join(os.path.dirname(__file__), "orphaned_agents.txt")


def get_session():
    profile = os.getenv('AWS_PROFILE', 'agent-space')
    region = os.getenv('AWS_REGION', 'us-west-2')
    return boto3.Session(profile_name=profile, region_name=region)


def get_db_agent_ids(session):
    """Query Aurora for all tracked bedrock_agent_id and agent_id values."""
    rds_data = session.client('rds-data')

    # Get all AWS Bedrock agent IDs (10-char)
    resp = rds_data.execute_statement(
        resourceArn=CLUSTER_ARN,
        secretArn=SECRET_ARN,
        database=DATABASE,
        sql="SELECT bedrock_agent_id FROM bedrock_agent_options WHERE bedrock_agent_id IS NOT NULL AND bedrock_agent_id != ''"
    )
    bedrock_ids = set()
    for record in resp.get('records', []):
        val = record[0].get('stringValue', '')
        if val:
            bedrock_ids.add(val)

    # Get all bond agent IDs (bedrock_agent_<uuid>)
    resp2 = rds_data.execute_statement(
        resourceArn=CLUSTER_ARN,
        secretArn=SECRET_ARN,
        database=DATABASE,
        sql="SELECT agent_id FROM bedrock_agent_options WHERE agent_id IS NOT NULL AND agent_id != ''"
    )
    bond_ids = set()
    for record in resp2.get('records', []):
        val = record[0].get('stringValue', '')
        if val:
            bond_ids.add(val)

    return bedrock_ids, bond_ids


def parse_orphaned_agents(filepath):
    """Parse orphaned_agents.txt, returning list of (aws_id, bond_name) tuples."""
    agents = []
    pattern = re.compile(r'^([A-Z0-9]{10})\s+#\s+(bedrock_agent_\w+)')
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            m = pattern.match(line)
            if m:
                agents.append((m.group(1), m.group(2)))
    return agents


def delete_agent_with_retry(client, agent_id):
    """Delete a Bedrock agent with throttle retry."""
    for attempt in range(THROTTLE_MAX_RETRIES):
        try:
            client.delete_agent(agentId=agent_id, skipResourceInUseCheck=True)
            return True
        except ClientError as e:
            code = e.response['Error']['Code']
            if code == 'ThrottlingException' and attempt < THROTTLE_MAX_RETRIES - 1:
                delay = THROTTLE_BASE_DELAY * (2 ** attempt)
                LOGGER.warning("Throttled deleting %s, retrying in %ds...", agent_id, delay)
                time.sleep(delay)
            elif code == 'ResourceNotFoundException':
                LOGGER.warning("Agent %s already deleted (not found in AWS)", agent_id)
                return True
            else:
                raise
    return False


def main():
    parser = argparse.ArgumentParser(description="Delete orphaned Bedrock agents safely")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--dry-run', action='store_true', default=True,
                       help='Report only, do not delete (default)')
    group.add_argument('--execute', action='store_true',
                       help='Actually delete the agents')
    parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE,
                        help=f'Agents per batch (default: {DEFAULT_BATCH_SIZE})')
    parser.add_argument('--agent-id', type=str,
                        help='Delete a single agent ID only')
    parser.add_argument('--file', type=str, default=ORPHANED_AGENTS_FILE,
                        help='Path to orphaned agents file')
    args = parser.parse_args()

    dry_run = not args.execute

    if dry_run:
        LOGGER.info("=== DRY RUN MODE — no agents will be deleted ===")
    else:
        LOGGER.info("=== EXECUTE MODE — agents WILL be deleted ===")

    session = get_session()

    # Step 1: Query Aurora for all tracked agents
    LOGGER.info("Querying Aurora DB for tracked agents...")
    db_bedrock_ids, db_bond_ids = get_db_agent_ids(session)
    LOGGER.info("Found %d bedrock_agent_ids and %d bond agent_ids in Aurora",
                len(db_bedrock_ids), len(db_bond_ids))

    # Step 2: Parse orphaned agents file
    orphans = parse_orphaned_agents(args.file)
    LOGGER.info("Parsed %d orphaned agents from %s", len(orphans), args.file)

    if args.agent_id:
        orphans = [(aws_id, bond_name) for aws_id, bond_name in orphans if aws_id == args.agent_id]
        if not orphans:
            LOGGER.error("Agent ID %s not found in orphaned agents file", args.agent_id)
            sys.exit(1)
        LOGGER.info("Filtered to single agent: %s", args.agent_id)

    # Step 3: Double-verify each agent
    to_delete = []
    skipped = []
    for aws_id, bond_name in orphans:
        in_bedrock_col = aws_id in db_bedrock_ids
        in_bond_col = bond_name in db_bond_ids
        if in_bedrock_col or in_bond_col:
            reason = []
            if in_bedrock_col:
                reason.append(f"bedrock_agent_id={aws_id} found in DB")
            if in_bond_col:
                reason.append(f"agent_id={bond_name} found in DB")
            LOGGER.warning("SKIPPING %s (%s) — %s", aws_id, bond_name, "; ".join(reason))
            skipped.append((aws_id, bond_name, "; ".join(reason)))
        else:
            to_delete.append((aws_id, bond_name))

    LOGGER.info("Verified: %d safe to delete, %d skipped (found in DB)", len(to_delete), len(skipped))

    if skipped:
        LOGGER.warning("--- SKIPPED AGENTS (found in Aurora DB) ---")
        for aws_id, bond_name, reason in skipped:
            LOGGER.warning("  %s  # %s  — %s", aws_id, bond_name, reason)

    if dry_run:
        LOGGER.info("--- WOULD DELETE %d agents ---", len(to_delete))
        for aws_id, bond_name in to_delete:
            LOGGER.info("  %s  # %s", aws_id, bond_name)
        LOGGER.info("=== DRY RUN COMPLETE — re-run with --execute to delete ===")
        return

    # Step 4: Delete in batches
    client = session.client('bedrock-agent')
    deleted = 0
    errors = []

    for i in range(0, len(to_delete), args.batch_size):
        batch = to_delete[i:i + args.batch_size]
        batch_num = (i // args.batch_size) + 1
        total_batches = (len(to_delete) + args.batch_size - 1) // args.batch_size
        LOGGER.info("--- Batch %d/%d (%d agents) ---", batch_num, total_batches, len(batch))

        for aws_id, bond_name in batch:
            try:
                delete_agent_with_retry(client, aws_id)
                LOGGER.info("DELETED %s  # %s", aws_id, bond_name)
                deleted += 1
            except ClientError as e:
                LOGGER.error("FAILED to delete %s: %s", aws_id, e)
                errors.append((aws_id, bond_name, str(e)))

        if i + args.batch_size < len(to_delete):
            LOGGER.info("Waiting %ds before next batch...", DEFAULT_DELAY)
            time.sleep(DEFAULT_DELAY)

    # Summary
    LOGGER.info("=== SUMMARY ===")
    LOGGER.info("Total orphaned: %d", len(orphans))
    LOGGER.info("Skipped (in DB): %d", len(skipped))
    LOGGER.info("Deleted: %d", deleted)
    LOGGER.info("Errors: %d", len(errors))
    if errors:
        LOGGER.error("--- FAILED DELETIONS ---")
        for aws_id, bond_name, err in errors:
            LOGGER.error("  %s  # %s  — %s", aws_id, bond_name, err)


if __name__ == '__main__':
    main()
