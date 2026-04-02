#!/usr/bin/env python3
"""
Batch migrate existing Bedrock agents to use guardrails.

Reads all agents from the Aurora metadata DB and/or local SQLite DB,
then calls update_agent with guardrailConfiguration for each one.

Usage:
    # Dry run - list agents without modifying
    python scripts/migrate_guardrails.py --dry-run

    # Migrate a single agent for testing
    python scripts/migrate_guardrails.py --agent-id ABCDEF1234

    # Full migration in batches of 10
    python scripts/migrate_guardrails.py --batch-size 10

    # Remove guardrails from all agents
    python scripts/migrate_guardrails.py --remove

Environment variables:
    BEDROCK_GUARDRAIL_ID       - Guardrail ID to attach
    BEDROCK_GUARDRAIL_VERSION  - Guardrail version to use
    AURORA_CLUSTER_ARN         - Aurora cluster ARN for metadata DB
    DATABASE_SECRET_ARN        - Secrets Manager ARN for DB credentials
    DATABASE_NAME              - Database name (default: bondai)
    METADATA_DB_URL            - SQLite URL for local metadata DB (e.g. sqlite:///.metadata.db)
    AWS_PROFILE                - AWS profile (default: default)
    AWS_REGION                 - AWS region (default: us-west-2)
"""

import argparse
import json
import logging
import os
import sys
import time

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
LOGGER = logging.getLogger(__name__)

# Aurora connection details (from environment)
CLUSTER_ARN = os.environ.get('AURORA_CLUSTER_ARN', '')
SECRET_ARN = os.environ.get('DATABASE_SECRET_ARN', '')
DATABASE = os.environ.get('DATABASE_NAME', 'bondai')

DEFAULT_BATCH_SIZE = 10
DEFAULT_DELAY = 5  # seconds between batches
PREPARE_WAIT_MAX = 60  # max seconds to wait for prepare_agent
PREPARE_POLL_INTERVAL = 3  # seconds between status polls
THROTTLE_MAX_RETRIES = 3
THROTTLE_BASE_DELAY = 2  # seconds


def get_session():
    profile = os.getenv('AWS_PROFILE', 'default')
    region = os.getenv('AWS_REGION', 'us-west-2')
    return boto3.Session(profile_name=profile, region_name=region)


def get_agent_ids_from_aurora(session):
    """Query Aurora for all bedrock_agent_id values."""
    if not CLUSTER_ARN or not SECRET_ARN:
        return []
    rds_data = session.client('rds-data')
    resp = rds_data.execute_statement(
        resourceArn=CLUSTER_ARN,
        secretArn=SECRET_ARN,
        database=DATABASE,
        sql="SELECT bedrock_agent_id FROM bedrock_agent_options WHERE bedrock_agent_id IS NOT NULL AND bedrock_agent_id != ''"
    )
    agent_ids = []
    for record in resp.get('records', []):
        val = record[0].get('stringValue', '')
        if val:
            agent_ids.append(val)
    return agent_ids


def get_agent_ids_from_sqlite(db_url):
    """Query local SQLite for all bedrock_agent_id values."""
    import sqlite3

    # Extract file path from SQLite URL (sqlite:///path or sqlite:////abs/path)
    path = db_url
    if path.startswith('sqlite:///'):
        path = path[len('sqlite:///'):]

    if not os.path.exists(path):
        LOGGER.debug(f"SQLite DB not found at {path}, skipping")
        return []

    try:
        conn = sqlite3.connect(path)
        try:
            cursor = conn.execute(
                "SELECT bedrock_agent_id FROM bedrock_agent_options "
                "WHERE bedrock_agent_id IS NOT NULL AND bedrock_agent_id != ''"
            )
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()
    except Exception as e:
        LOGGER.warning(f"Failed to query SQLite DB at {path}: {e}")
        return []


def get_all_agent_ids(session):
    """Collect agent IDs from all configured metadata sources (Aurora + SQLite).

    Returns a deduplicated list. Agents present in both databases (same
    bedrock_agent_id) are only migrated once.
    """
    all_ids = set()

    # Aurora
    if CLUSTER_ARN and SECRET_ARN:
        LOGGER.info("Querying Aurora for agent IDs...")
        aurora_ids = get_agent_ids_from_aurora(session)
        LOGGER.info(f"  Aurora: {len(aurora_ids)} agents")
        all_ids.update(aurora_ids)
    else:
        LOGGER.info("Aurora not configured (AURORA_CLUSTER_ARN/DATABASE_SECRET_ARN not set), skipping")

    # Local SQLite
    sqlite_url = os.environ.get('METADATA_DB_URL', '')
    if sqlite_url and sqlite_url.startswith('sqlite'):
        LOGGER.info("Querying local SQLite for agent IDs...")
        sqlite_ids = get_agent_ids_from_sqlite(sqlite_url)
        new_ids = set(sqlite_ids) - all_ids
        LOGGER.info(f"  SQLite: {len(sqlite_ids)} agents ({len(new_ids)} not already in Aurora)")
        all_ids.update(sqlite_ids)
    else:
        LOGGER.debug("METADATA_DB_URL not set or not SQLite, skipping local DB")

    if not all_ids:
        LOGGER.error("No agent sources configured. Set AURORA_CLUSTER_ARN+DATABASE_SECRET_ARN and/or METADATA_DB_URL.")
        sys.exit(1)

    return sorted(all_ids)


def get_agent_config(client, agent_id):
    """Get current agent configuration."""
    resp = client.get_agent(agentId=agent_id)
    return resp['agent']


def _wait_for_prepared(client, agent_id):
    """Poll until agent reaches PREPARED (or NOT_PREPARED) status."""
    elapsed = 0
    while elapsed < PREPARE_WAIT_MAX:
        agent = get_agent_config(client, agent_id)
        status = agent.get('agentStatus', '')
        if status in ('PREPARED', 'NOT_PREPARED'):
            LOGGER.debug(f"Agent {agent_id} reached status {status} after ~{elapsed}s")
            return status
        time.sleep(PREPARE_POLL_INTERVAL)
        elapsed += PREPARE_POLL_INTERVAL
    LOGGER.warning(f"Agent {agent_id} did not reach PREPARED within {PREPARE_WAIT_MAX}s (last status: {status})")
    return status


def _call_with_throttle_retry(fn, *args, **kwargs):
    """Call an AWS API function with throttle-aware retry."""
    for attempt in range(THROTTLE_MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except ClientError as e:
            if e.response['Error']['Code'] == 'ThrottlingException' and attempt < THROTTLE_MAX_RETRIES:
                delay = THROTTLE_BASE_DELAY * (2 ** attempt)
                LOGGER.warning(f"Throttled, retrying in {delay}s (attempt {attempt + 1}/{THROTTLE_MAX_RETRIES})")
                time.sleep(delay)
            else:
                raise


def _update_aliases_to_latest(client, agent_id):
    """Update aliases so they pick up the latest prepared DRAFT config.

    Calling update_agent_alias without routingConfiguration causes the alias
    to re-resolve to the latest prepared version (same pattern as BedrockCRUD).
    """
    aliases_resp = client.list_agent_aliases(agentId=agent_id)
    for alias in aliases_resp.get('agentAliasSummaries', []):
        alias_id = alias['agentAliasId']
        if alias_id == 'TSTALIASID':
            continue
        LOGGER.info(f"  Updating alias {alias_id} to pick up latest prepared version")
        _call_with_throttle_retry(
            client.update_agent_alias,
            agentId=agent_id,
            agentAliasId=alias_id,
            agentAliasName=alias['agentAliasName'],
            description="Updated by guardrail migration",
        )


def migrate_agent(client, agent_id, guardrail_id, guardrail_version, remove=False):
    """Add or remove guardrail from a single agent. Returns status string."""
    try:
        agent = get_agent_config(client, agent_id)
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            return "not_found"
        raise

    current_guardrail = agent.get('guardrailConfiguration')

    if remove:
        if not current_guardrail:
            return "skipped_no_guardrail"
        # Update without guardrail config
        _call_with_throttle_retry(
            client.update_agent,
            agentId=agent_id,
            agentName=agent['agentName'],
            agentResourceRoleArn=agent['agentResourceRoleArn'],
            instruction=agent.get('instruction', ''),
            foundationModel=agent['foundationModel'],
            description=agent.get('description', ''),
            idleSessionTTLInSeconds=agent.get('idleSessionTTLInSeconds', 3600),
        )
        _call_with_throttle_retry(client.prepare_agent, agentId=agent_id)
        _wait_for_prepared(client, agent_id)
        _update_aliases_to_latest(client, agent_id)
        return "removed"

    # Check if already has the correct guardrail on DRAFT AND aliases are up to date
    if current_guardrail:
        if (current_guardrail.get('guardrailIdentifier') == guardrail_id and
                current_guardrail.get('guardrailVersion') == guardrail_version):
            # Verify aliases point to a version that has the guardrail too
            aliases_resp = client.list_agent_aliases(agentId=agent_id)
            aliases_need_update = False
            for alias in aliases_resp.get('agentAliasSummaries', []):
                if alias['agentAliasId'] == 'TSTALIASID':
                    continue
                routing = alias.get('routingConfiguration', [])
                if routing:
                    ver = routing[0].get('agentVersion', '')
                    if ver and ver != 'DRAFT':
                        # Check if this version has the guardrail
                        try:
                            ver_resp = client.get_agent_version(agentId=agent_id, agentVersion=ver)
                            ver_guardrail = ver_resp['agentVersion'].get('guardrailConfiguration')
                            if not ver_guardrail or ver_guardrail.get('guardrailIdentifier') != guardrail_id:
                                aliases_need_update = True
                        except ClientError:
                            aliases_need_update = True
            if aliases_need_update:
                LOGGER.info(f"  DRAFT has guardrail but aliases point to old version — updating")
                _call_with_throttle_retry(client.prepare_agent, agentId=agent_id)
                _wait_for_prepared(client, agent_id)
                _update_aliases_to_latest(client, agent_id)
                return "migrated"
            return "skipped_already_configured"

    # Update with guardrail
    _call_with_throttle_retry(
        client.update_agent,
        agentId=agent_id,
        agentName=agent['agentName'],
        agentResourceRoleArn=agent['agentResourceRoleArn'],
        instruction=agent.get('instruction', ''),
        foundationModel=agent['foundationModel'],
        description=agent.get('description', ''),
        idleSessionTTLInSeconds=agent.get('idleSessionTTLInSeconds', 3600),
        guardrailConfiguration={
            "guardrailIdentifier": guardrail_id,
            "guardrailVersion": guardrail_version,
        }
    )
    _call_with_throttle_retry(client.prepare_agent, agentId=agent_id)
    _wait_for_prepared(client, agent_id)
    _update_aliases_to_latest(client, agent_id)
    return "migrated"


def main():
    parser = argparse.ArgumentParser(description="Migrate Bedrock agents to use guardrails")
    parser.add_argument('--dry-run', action='store_true', help="List agents without modifying")
    parser.add_argument('--agent-id', type=str, help="Migrate a single agent by ID")
    parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE, help="Agents per batch")
    parser.add_argument('--delay', type=int, default=DEFAULT_DELAY, help="Seconds between batches")
    parser.add_argument('--remove', action='store_true', help="Remove guardrails from agents")
    args = parser.parse_args()

    guardrail_id = os.getenv('BEDROCK_GUARDRAIL_ID', '').strip()
    guardrail_version = os.getenv('BEDROCK_GUARDRAIL_VERSION', '').strip()

    if not args.remove and (not guardrail_id or not guardrail_version):
        LOGGER.error("BEDROCK_GUARDRAIL_ID and BEDROCK_GUARDRAIL_VERSION must be set")
        sys.exit(1)

    session = get_session()
    bedrock_agent_client = session.client('bedrock-agent')

    # Get agent IDs
    if args.agent_id:
        agent_ids = [args.agent_id]
    else:
        agent_ids = get_all_agent_ids(session)

    LOGGER.info(f"Found {len(agent_ids)} agents")

    if args.dry_run:
        LOGGER.info("DRY RUN - no changes will be made")
        for i, aid in enumerate(agent_ids):
            try:
                agent = get_agent_config(bedrock_agent_client, aid)
                guardrail = agent.get('guardrailConfiguration', {})
                status = agent.get('agentStatus', 'UNKNOWN')
                gid = guardrail.get('guardrailIdentifier', 'none')
                LOGGER.info(f"  [{i+1}/{len(agent_ids)}] {aid} status={status} guardrail={gid}")
            except ClientError as e:
                LOGGER.warning(f"  [{i+1}/{len(agent_ids)}] {aid} ERROR: {e}")
        return

    # Process in batches
    counts = {"migrated": 0, "removed": 0, "skipped_already_configured": 0,
              "skipped_no_guardrail": 0, "not_found": 0, "error": 0}

    for i, aid in enumerate(agent_ids):
        try:
            result = migrate_agent(
                bedrock_agent_client, aid,
                guardrail_id, guardrail_version,
                remove=args.remove
            )
            counts[result] = counts.get(result, 0) + 1
            LOGGER.info(f"  [{i+1}/{len(agent_ids)}] {aid}: {result}")
        except Exception as e:
            counts["error"] += 1
            LOGGER.error(f"  [{i+1}/{len(agent_ids)}] {aid}: ERROR - {e}")

        # Batch delay
        if (i + 1) % args.batch_size == 0 and i + 1 < len(agent_ids):
            LOGGER.info(f"Batch complete, waiting {args.delay}s...")
            time.sleep(args.delay)

    LOGGER.info(f"Migration complete: {json.dumps(counts, indent=2)}")


if __name__ == '__main__':
    main()
