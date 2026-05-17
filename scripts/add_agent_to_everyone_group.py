#!/usr/bin/env python3
"""
Add an agent to the Everyone group (grp_everyone) so all authenticated users can access it.

Usage:
    # Dry run - find the agent by slug and show what would be done
    python scripts/add_agent_to_everyone_group.py --slug fiery-crafting-brush

    # Execute the insert
    python scripts/add_agent_to_everyone_group.py --slug fiery-crafting-brush --execute

    # Use a specific agent ID directly
    python scripts/add_agent_to_everyone_group.py --agent-id "abc123" --execute

    # Set permission level (default: can_use)
    python scripts/add_agent_to_everyone_group.py --slug fiery-crafting-brush --permission can_edit --execute

Environment variables:
    AURORA_CLUSTER_ARN  - Aurora cluster ARN
    DATABASE_SECRET_ARN - Secrets Manager ARN for DB credentials
    DATABASE_NAME       - Database name (default: bondai)
    AWS_PROFILE         - AWS profile (default: default)
    AWS_REGION          - AWS region (default: us-west-2)
"""

import argparse
import logging
import os
import sys

import boto3

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
LOGGER = logging.getLogger(__name__)

CLUSTER_ARN = os.environ.get('AURORA_CLUSTER_ARN', '')
SECRET_ARN = os.environ.get('DATABASE_SECRET_ARN', '')
DATABASE = os.environ.get('DATABASE_NAME', 'bondai')
EVERYONE_GROUP_ID = 'grp_everyone'
VALID_PERMISSIONS = ('can_use', 'can_use_read_only', 'can_edit')


def get_session():
    profile = os.getenv('AWS_PROFILE', 'default')
    region = os.getenv('AWS_REGION', 'us-west-2')
    return boto3.Session(profile_name=profile, region_name=region)


def execute_sql(client, sql, parameters=None):
    """Execute a SQL statement via RDS Data API and return the response."""
    kwargs = dict(
        resourceArn=CLUSTER_ARN,
        secretArn=SECRET_ARN,
        database=DATABASE,
        sql=sql,
    )
    if parameters:
        kwargs['parameters'] = parameters
    return client.execute_statement(**kwargs)


def find_agent_by_slug(client, slug):
    """Find an agent by its unique slug."""
    resp = execute_sql(
        client,
        "SELECT agent_id, name, slug FROM agents WHERE slug = :slug",
        parameters=[{'name': 'slug', 'value': {'stringValue': slug}}]
    )
    records = resp.get('records', [])
    if not records:
        return None
    return {
        'agent_id': records[0][0].get('stringValue', ''),
        'name': records[0][1].get('stringValue', ''),
        'slug': records[0][2].get('stringValue', ''),
    }


def verify_everyone_group(client):
    """Check that the Everyone group exists."""
    resp = execute_sql(
        client,
        "SELECT id, name FROM groups WHERE id = :gid",
        parameters=[{'name': 'gid', 'value': {'stringValue': EVERYONE_GROUP_ID}}]
    )
    return len(resp.get('records', [])) > 0


def check_existing_association(client, agent_id):
    """Check if the agent is already in the Everyone group."""
    resp = execute_sql(
        client,
        "SELECT permission FROM agent_groups WHERE agent_id = :aid AND group_id = :gid",
        parameters=[
            {'name': 'aid', 'value': {'stringValue': agent_id}},
            {'name': 'gid', 'value': {'stringValue': EVERYONE_GROUP_ID}},
        ]
    )
    records = resp.get('records', [])
    if records:
        return records[0][0].get('stringValue', '')
    return None


def add_to_everyone_group(client, agent_id, permission):
    """Insert the agent into the Everyone group."""
    execute_sql(
        client,
        "INSERT INTO agent_groups (agent_id, group_id, permission, created_at) "
        "VALUES (:aid, :gid, :perm, NOW())",
        parameters=[
            {'name': 'aid', 'value': {'stringValue': agent_id}},
            {'name': 'gid', 'value': {'stringValue': EVERYONE_GROUP_ID}},
            {'name': 'perm', 'value': {'stringValue': permission}},
        ]
    )


def list_everyone_agents(client):
    """List all agents currently in the Everyone group."""
    resp = execute_sql(
        client,
        "SELECT a.name, ag.permission FROM agent_groups ag "
        "JOIN agents a ON ag.agent_id = a.agent_id "
        "WHERE ag.group_id = :gid ORDER BY a.name",
        parameters=[{'name': 'gid', 'value': {'stringValue': EVERYONE_GROUP_ID}}]
    )
    agents = []
    for record in resp.get('records', []):
        agents.append({
            'name': record[0].get('stringValue', ''),
            'permission': record[1].get('stringValue', ''),
        })
    return agents


def main():
    parser = argparse.ArgumentParser(description='Add an agent to the Everyone group')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--slug', help='Agent slug (unique identifier from the URL)')
    group.add_argument('--agent-id', help='Agent ID to add directly')
    parser.add_argument('--permission', default='can_use', choices=VALID_PERMISSIONS,
                        help='Permission level (default: can_use)')
    parser.add_argument('--execute', action='store_true',
                        help='Actually perform the insert (default is dry-run)')
    args = parser.parse_args()

    if not CLUSTER_ARN or not SECRET_ARN:
        LOGGER.error("AURORA_CLUSTER_ARN and DATABASE_SECRET_ARN must be set")
        sys.exit(1)

    session = get_session()
    client = session.client('rds-data')

    # Step 1: Verify Everyone group exists
    LOGGER.info("Checking for Everyone group...")
    if not verify_everyone_group(client):
        LOGGER.error("Everyone group (grp_everyone) not found! Has the application started at least once?")
        sys.exit(1)
    LOGGER.info("  Everyone group exists")

    # Step 2: Find the agent
    if args.slug:
        LOGGER.info(f"Looking up agent with slug '{args.slug}'...")
        agent = find_agent_by_slug(client, args.slug)
        if not agent:
            LOGGER.error(f"No agent found with slug '{args.slug}'")
            sys.exit(1)
        agent_id = agent['agent_id']
        agent_name = agent['name']
        LOGGER.info(f"  Found: {agent_name} (ID: {agent_id}, slug: {agent['slug']})")
    else:
        agent_id = args.agent_id
        agent_name = agent_id

    # Step 3: Check for existing association
    existing = check_existing_association(client, agent_id)
    if existing:
        LOGGER.info(f"  Agent '{agent_name}' is already in the Everyone group with permission: {existing}")
        if existing == args.permission:
            LOGGER.info("  Nothing to do.")
            sys.exit(0)
        else:
            LOGGER.info(f"  To change permission from '{existing}' to '{args.permission}', "
                        "remove the existing association first.")
            sys.exit(0)

    # Step 4: Add to Everyone group
    if not args.execute:
        LOGGER.info(f"  [DRY RUN] Would add '{agent_name}' to Everyone group with permission: {args.permission}")
        LOGGER.info("  Re-run with --execute to perform the insert.")
    else:
        LOGGER.info(f"  Adding '{agent_name}' to Everyone group with permission: {args.permission}...")
        add_to_everyone_group(client, agent_id, args.permission)
        LOGGER.info("  Done!")

    # Step 5: Show current Everyone group members
    LOGGER.info("")
    LOGGER.info("Current agents in Everyone group:")
    for a in list_everyone_agents(client):
        LOGGER.info(f"  {a['name']:40s}  {a['permission']}")


if __name__ == '__main__':
    main()
