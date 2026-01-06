#!/usr/bin/env python3
"""
Fix Aurora KB Schema

Adds missing columns to the Aurora KB table for metadata filtering.
Run this once to fix existing deployments.

Usage:
    poetry run python scripts/fix_aurora_kb_schema.py
"""

import os
import json
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError

load_dotenv()


def get_cluster_info():
    """Get Aurora cluster info from AWS."""
    region = os.getenv('AWS_REGION', 'us-west-2')

    # Get cluster ARN and secret ARN from tags or by listing
    bedrock_agent_client = boto3.client('bedrock-agent', region_name=region)

    kb_id = os.getenv('BEDROCK_KNOWLEDGE_BASE_ID')
    if not kb_id:
        print("ERROR: BEDROCK_KNOWLEDGE_BASE_ID not set")
        return None

    try:
        response = bedrock_agent_client.get_knowledge_base(knowledgeBaseId=kb_id)
        kb = response.get('knowledgeBase', {})
        storage_config = kb.get('storageConfiguration', {})

        if storage_config.get('type') != 'RDS':
            print(f"ERROR: Knowledge Base is not using RDS storage (type: {storage_config.get('type')})")
            return None

        rds_config = storage_config.get('rdsConfiguration', {})
        return {
            'cluster_arn': rds_config.get('resourceArn'),
            'secret_arn': rds_config.get('credentialsSecretArn'),
            'database': rds_config.get('databaseName'),
            'table_name': rds_config.get('tableName'),
            'region': region
        }
    except Exception as e:
        print(f"ERROR: Failed to get KB info: {e}")
        return None


def execute_sql(rds_data_client, cluster_arn, secret_arn, database, sql):
    """Execute SQL statement."""
    try:
        response = rds_data_client.execute_statement(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database=database,
            sql=sql
        )
        return True, response
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        error_msg = e.response.get('Error', {}).get('Message', '')
        return False, f"{error_code}: {error_msg}"


def main():
    print("=" * 60)
    print("AURORA KB SCHEMA FIX")
    print("=" * 60)
    print()

    # Get cluster info
    info = get_cluster_info()
    if not info:
        return 1

    print(f"Cluster ARN: {info['cluster_arn']}")
    print(f"Database: {info['database']}")
    print(f"Table: {info['table_name']}")
    print()

    # Initialize RDS Data client
    rds_data = boto3.client('rds-data', region_name=info['region'])

    # Check current table structure
    print("Checking current table structure...")
    success, result = execute_sql(
        rds_data,
        info['cluster_arn'],
        info['secret_arn'],
        info['database'],
        f"SELECT column_name, data_type FROM information_schema.columns WHERE table_schema || '.' || table_name = '{info['table_name']}' ORDER BY ordinal_position;"
    )

    if success:
        print("Current columns:")
        for record in result.get('records', []):
            col_name = record[0].get('stringValue', '')
            col_type = record[1].get('stringValue', '')
            print(f"  - {col_name}: {col_type}")
    else:
        print(f"WARNING: Could not check columns: {result}")
    print()

    # Add missing columns
    columns_to_add = [
        ("agent_id", "varchar(255)"),
        ("file_id", "varchar(255)"),
        ("file_name", "varchar(500)")
    ]

    for col_name, col_type in columns_to_add:
        print(f"Adding column: {col_name} ({col_type})...")
        success, result = execute_sql(
            rds_data,
            info['cluster_arn'],
            info['secret_arn'],
            info['database'],
            f"ALTER TABLE {info['table_name']} ADD COLUMN IF NOT EXISTS {col_name} {col_type};"
        )
        if success:
            print(f"  OK")
        else:
            # Check if column already exists
            if "already exists" in str(result).lower() or "duplicate" in str(result).lower():
                print(f"  Already exists")
            else:
                print(f"  ERROR: {result}")

    # Create index on agent_id
    print(f"Creating index on agent_id...")
    table_short_name = info['table_name'].split('.')[-1]
    success, result = execute_sql(
        rds_data,
        info['cluster_arn'],
        info['secret_arn'],
        info['database'],
        f"CREATE INDEX IF NOT EXISTS {table_short_name}_agent_id_idx ON {info['table_name']} (agent_id);"
    )
    if success:
        print(f"  OK")
    else:
        print(f"  Result: {result}")

    # Drop custom_metadata column if it exists (not needed)
    print(f"Dropping custom_metadata column if exists...")
    success, result = execute_sql(
        rds_data,
        info['cluster_arn'],
        info['secret_arn'],
        info['database'],
        f"ALTER TABLE {info['table_name']} DROP COLUMN IF EXISTS custom_metadata;"
    )
    if success:
        print(f"  OK")
    else:
        print(f"  Result: {result}")

    # Verify final structure
    print()
    print("Final table structure:")
    success, result = execute_sql(
        rds_data,
        info['cluster_arn'],
        info['secret_arn'],
        info['database'],
        f"SELECT column_name, data_type FROM information_schema.columns WHERE table_schema || '.' || table_name = '{info['table_name']}' ORDER BY ordinal_position;"
    )

    if success:
        for record in result.get('records', []):
            col_name = record[0].get('stringValue', '')
            col_type = record[1].get('stringValue', '')
            print(f"  - {col_name}: {col_type}")

    print()
    print("Schema fix complete!")
    return 0


if __name__ == "__main__":
    exit(main())
