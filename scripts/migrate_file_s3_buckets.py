#!/usr/bin/env python3
"""
Migrate file records from orphaned S3 buckets to the canonical bucket.

Background:
  A bug in BedrockFilesProvider caused each App Runner container instance to
  generate a random S3 bucket name (bond-bedrock-files-<uuid>) when the
  BEDROCK_S3_BUCKET env var was not set. This created orphaned buckets and
  caused intermittent file download failures when different instances handled
  the upload vs. download request.

  This script:
  1. Finds all file records whose file_id points to the wrong bucket
  2. Copies each S3 object from the old bucket to the canonical bucket
  3. Updates the file_id in the database to point to the canonical bucket
  4. Updates old message content from full S3 URIs to opaque bond_file_xxx IDs
  5. Optionally deletes the object from the old bucket after successful copy

Usage:
    # Dry run against local SQLite (default):
    poetry run python scripts/migrate_file_s3_buckets.py

    # Dry run against deployed Aurora via RDS Data API:
    poetry run python scripts/migrate_file_s3_buckets.py --use-data-api \
        --cluster-arn arn:aws:rds:REGION:ACCOUNT:cluster:CLUSTER_NAME \
        --secret-arn arn:aws:secretsmanager:REGION:ACCOUNT:secret:SECRET_NAME

    # Execute the migration:
    poetry run python scripts/migrate_file_s3_buckets.py --execute

    # Execute with full cleanup:
    poetry run python scripts/migrate_file_s3_buckets.py --execute --delete-old --remove-empty-buckets

Environment variables:
    METADATA_DB_URL         Database connection string (local dev, e.g. sqlite:///...)
    AURORA_CLUSTER_ARN      RDS cluster ARN (for --use-data-api)
    DATABASE_SECRET_ARN     AWS Secrets Manager ARN for DB credentials
    BEDROCK_S3_BUCKET       Canonical S3 bucket (or S3_BUCKET_NAME as fallback)
    S3_BUCKET_NAME          Canonical S3 bucket (terraform-managed)
    AWS_REGION              AWS region (required for S3 and Data API operations)
"""

import argparse
import json
import logging
import os
import re
import sys
from urllib.parse import quote_plus

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import create_engine, text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)
LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Database abstraction — SQLAlchemy for local, RDS Data API for deployed
# ---------------------------------------------------------------------------

class SqlAlchemyDb:
    """Database operations via SQLAlchemy (local SQLite or direct PostgreSQL)."""

    def __init__(self, db_url):
        self.db_url = db_url
        self.engine = create_engine(db_url)
        self.is_sqlite = 'sqlite' in db_url

    def label(self):
        return re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', self.db_url)

    def query_files(self, canonical_prefix):
        with self.engine.connect() as conn:
            result = conn.execute(text(
                "SELECT file_id, file_path, owner_user_id FROM files "
                "WHERE file_id LIKE 's3://%' AND file_id NOT LIKE :prefix"
            ), {"prefix": f"{canonical_prefix}%"})
            return [(r[0], r[1], r[2]) for r in result.fetchall()]

    def check_file_exists(self, file_id):
        with self.engine.connect() as conn:
            return conn.execute(text(
                "SELECT 1 FROM files WHERE file_id = :id"
            ), {"id": file_id}).fetchone() is not None

    def update_file_id(self, old_id, new_id):
        with self.engine.begin() as conn:
            conn.execute(text(
                "UPDATE files SET file_id = :new_id WHERE file_id = :old_id"
            ), {"new_id": new_id, "old_id": old_id})

    def query_messages_with_s3_uris(self):
        with self.engine.connect() as conn:
            if self.is_sqlite:
                result = conn.execute(text(
                    "SELECT id, content FROM bedrock_messages "
                    "WHERE type = 'file_link' AND content LIKE '%s3://%'"
                ))
            else:
                result = conn.execute(text(
                    "SELECT id, content::text FROM bedrock_messages "
                    "WHERE type = 'file_link' AND content::text LIKE '%s3://%'"
                ))
            return [(r[0], r[1]) for r in result.fetchall()]

    def update_message_content(self, msg_id, new_content_json):
        with self.engine.begin() as conn:
            if self.is_sqlite:
                conn.execute(text(
                    "UPDATE bedrock_messages SET content = json(:content) WHERE id = :id"
                ), {"content": new_content_json, "id": msg_id})
            else:
                conn.execute(text(
                    "UPDATE bedrock_messages SET content = :content::jsonb WHERE id = :id"
                ), {"content": new_content_json, "id": msg_id})


class RdsDataApiDb:
    """Database operations via AWS RDS Data API (no VPC access required)."""

    def __init__(self, cluster_arn, secret_arn, database, region):
        self.cluster_arn = cluster_arn
        self.secret_arn = secret_arn
        self.database = database
        self.client = boto3.client('rds-data', region_name=region)

    def label(self):
        # Extract cluster name from ARN
        name = self.cluster_arn.rsplit(':', 1)[-1] if ':' in self.cluster_arn else self.cluster_arn
        return f"rds-data-api://{name}/{self.database}"

    def _exec(self, sql, params=None):
        kwargs = {
            'resourceArn': self.cluster_arn,
            'secretArn': self.secret_arn,
            'database': self.database,
            'sql': sql,
        }
        if params:
            kwargs['parameters'] = params
        return self.client.execute_statement(**kwargs)

    def _param(self, name, value):
        return {'name': name, 'value': {'stringValue': value}}

    def query_files(self, canonical_prefix):
        resp = self._exec(
            "SELECT file_id, file_path, owner_user_id FROM files "
            "WHERE file_id LIKE 's3://%' AND file_id NOT LIKE :prefix",
            [self._param('prefix', f"{canonical_prefix}%")]
        )
        rows = []
        for r in resp.get('records', []):
            rows.append((r[0]['stringValue'], r[1]['stringValue'], r[2]['stringValue']))
        return rows

    def check_file_exists(self, file_id):
        resp = self._exec(
            "SELECT 1 FROM files WHERE file_id = :id",
            [self._param('id', file_id)]
        )
        return len(resp.get('records', [])) > 0

    def update_file_id(self, old_id, new_id):
        self._exec(
            "UPDATE files SET file_id = :new_id WHERE file_id = :old_id",
            [self._param('new_id', new_id), self._param('old_id', old_id)]
        )

    def query_messages_with_s3_uris(self):
        resp = self._exec(
            "SELECT id, content::text FROM bedrock_messages "
            "WHERE type = 'file_link' AND content::text LIKE '%s3://%'"
        )
        rows = []
        for r in resp.get('records', []):
            rows.append((r[0]['stringValue'], r[1]['stringValue']))
        return rows

    def update_message_content(self, msg_id, new_content_json):
        self._exec(
            "UPDATE bedrock_messages SET content = :content::jsonb WHERE id = :id",
            [self._param('content', new_content_json), self._param('id', msg_id)]
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_db_url() -> str:
    """Resolve database URL from environment, matching Config.get_metadata_db_url() logic."""
    url = os.getenv('METADATA_DB_URL', '')
    if url:
        return url

    db_secret_arn = os.getenv('DATABASE_SECRET_ARN', '')
    if db_secret_arn:
        region = os.getenv('AWS_REGION', 'us-west-2')
        client = boto3.client('secretsmanager', region_name=region)
        resp = client.get_secret_value(SecretId=db_secret_arn)
        db = json.loads(resp['SecretString'])
        username = db.get('username', '')
        password = db.get('password', '')
        host = db.get('host', '')
        port = db.get('port', 5432)
        dbname = db.get('dbname', 'bondai')
        if username and password and host:
            return f"postgresql://{quote_plus(username)}:{quote_plus(password)}@{host}:{port}/{dbname}?sslmode=require"
        else:
            LOGGER.error("DATABASE_SECRET_ARN secret missing required fields")
            sys.exit(1)

    local_db = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.metadata.db')
    return f'sqlite:///{local_db}'


def get_canonical_bucket() -> str:
    bucket = os.getenv('BEDROCK_S3_BUCKET') or os.getenv('S3_BUCKET_NAME')
    if not bucket:
        LOGGER.error("Cannot determine canonical bucket. Set BEDROCK_S3_BUCKET or S3_BUCKET_NAME env var.")
        sys.exit(1)
    return bucket


def rewrite_message_content(raw_content):
    """Rewrite S3 URIs in message content to opaque IDs. Returns (new_json, changed)."""
    try:
        content = json.loads(raw_content) if isinstance(raw_content, str) else raw_content
    except (json.JSONDecodeError, TypeError):
        return None, False

    changed = False
    for item in (content if isinstance(content, list) else [content]):
        text_val = item.get('text', '') if isinstance(item, dict) else ''
        if 's3://' not in text_val:
            continue
        try:
            file_data = json.loads(text_val)
        except (json.JSONDecodeError, TypeError):
            continue
        fid = file_data.get('file_id', '')
        if not fid.startswith('s3://'):
            continue
        match = re.search(r'(bond_file_[0-9a-f]+)$', fid)
        opaque_id = match.group(1) if match else (fid.rsplit('/', 1)[-1] if '/' in fid else fid)
        file_data['file_id'] = opaque_id
        item['text'] = json.dumps(file_data)
        changed = True

    return json.dumps(content) if changed else None, changed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Migrate file records from orphaned S3 buckets to the canonical bucket"
    )
    parser.add_argument("--execute", action="store_true",
                        help="Actually perform the migration (default is dry-run)")
    parser.add_argument("--delete-old", action="store_true",
                        help="Delete objects from old buckets after successful copy (requires --execute)")
    parser.add_argument("--remove-empty-buckets", action="store_true",
                        help="Delete orphaned buckets that are empty after migration (requires --delete-old)")
    parser.add_argument("--db-url", default=None,
                        help="Override database URL (default: auto-detect from env)")
    parser.add_argument("--bucket", default=None,
                        help="Override canonical bucket name")
    parser.add_argument("--use-data-api", action="store_true",
                        help="Use RDS Data API instead of direct connection (no VPC access needed)")
    parser.add_argument("--cluster-arn", default=os.getenv('AURORA_CLUSTER_ARN'),
                        help="RDS cluster ARN (for --use-data-api, default: $AURORA_CLUSTER_ARN)")
    parser.add_argument("--secret-arn", default=os.getenv('DATABASE_SECRET_ARN'),
                        help="Secrets Manager ARN (for --use-data-api, default: $DATABASE_SECRET_ARN)")
    parser.add_argument("--database", default=os.getenv('DATABASE_NAME', 'bondai'),
                        help="Database name (for --use-data-api, default: bondai)")
    args = parser.parse_args()

    if args.delete_old and not args.execute:
        parser.error("--delete-old requires --execute")
    if args.remove_empty_buckets and not args.delete_old:
        parser.error("--remove-empty-buckets requires --delete-old")
    if args.use_data_api and not args.cluster_arn:
        parser.error("--use-data-api requires --cluster-arn or AURORA_CLUSTER_ARN env var")
    if args.use_data_api and not args.secret_arn:
        parser.error("--use-data-api requires --secret-arn or DATABASE_SECRET_ARN env var")

    canonical_bucket = args.bucket or get_canonical_bucket()
    region = os.getenv('AWS_REGION', 'us-west-2')

    # Initialize DB backend
    if args.use_data_api:
        db = RdsDataApiDb(args.cluster_arn, args.secret_arn, args.database, region)
    else:
        db_url = args.db_url or get_db_url()
        db = SqlAlchemyDb(db_url)

    LOGGER.info(f"Database: {db.label()}")
    LOGGER.info(f"Canonical bucket: {canonical_bucket}")
    LOGGER.info(f"Mode: {'EXECUTE' if args.execute else 'DRY RUN'}")
    if args.delete_old:
        LOGGER.info("Will delete old objects after successful copy")
    print()

    s3 = boto3.client('s3', region_name=region)

    # Verify the canonical bucket exists
    try:
        s3.head_bucket(Bucket=canonical_bucket)
    except ClientError as e:
        code = e.response['Error']['Code']
        if code == '404':
            LOGGER.error(f"Canonical bucket '{canonical_bucket}' does not exist")
        elif code == '403':
            LOGGER.error(f"Access denied to canonical bucket '{canonical_bucket}'")
        else:
            LOGGER.error(f"Cannot access canonical bucket '{canonical_bucket}': {e}")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Phase 1: Migrate file records
    # -----------------------------------------------------------------------
    canonical_prefix = f"s3://{canonical_bucket}/"
    rows = db.query_files(canonical_prefix)

    if not rows:
        print("No file records need migration. All files already point to the canonical bucket.")
    else:
        print(f"Found {len(rows)} file record(s) pointing to non-canonical buckets:\n")

    bucket_counts = {}
    for file_id, _, _ in rows:
        parts = file_id[5:].split('/', 1)
        src_bucket = parts[0] if len(parts) == 2 else "unknown"
        bucket_counts[src_bucket] = bucket_counts.get(src_bucket, 0) + 1

    for bucket, count in sorted(bucket_counts.items(), key=lambda x: -x[1]):
        print(f"  {bucket}: {count} file(s)")
    if rows:
        print()

    migrated = 0
    skipped = 0
    errors = 0

    for old_file_id, file_path, owner in rows:
        old_parts = old_file_id[5:].split('/', 1)
        if len(old_parts) != 2:
            LOGGER.warning(f"  SKIP (malformed URI): {old_file_id}")
            skipped += 1
            continue

        old_bucket = old_parts[0]
        s3_key = old_parts[1]
        new_file_id = f"s3://{canonical_bucket}/{s3_key}"

        LOGGER.info(f"  {file_path} ({owner})")
        LOGGER.info(f"    FROM: {old_file_id}")
        LOGGER.info(f"    TO:   {new_file_id}")

        if not args.execute:
            migrated += 1
            continue

        # Copy S3 object
        try:
            s3.head_object(Bucket=old_bucket, Key=s3_key)
        except ClientError as e:
            code = e.response['Error']['Code']
            if code in ('404', '403'):
                LOGGER.warning(f"    SKIP ({code} on source): {old_file_id}")
                skipped += 1
                continue
            LOGGER.error(f"    ERROR checking source: {e}")
            errors += 1
            continue

        try:
            s3.copy_object(CopySource={'Bucket': old_bucket, 'Key': s3_key},
                           Bucket=canonical_bucket, Key=s3_key)
            LOGGER.info(f"    Copied to {canonical_bucket}/{s3_key}")
        except ClientError as e:
            LOGGER.error(f"    ERROR copying: {e}")
            errors += 1
            continue

        # Update DB (check for PK collision)
        try:
            if db.check_file_exists(new_file_id):
                LOGGER.warning(f"    SKIP (target file_id already exists): {new_file_id}")
                skipped += 1
                continue
            db.update_file_id(old_file_id, new_file_id)
            LOGGER.info(f"    Updated DB record")
        except Exception as e:
            LOGGER.error(f"    ERROR updating DB: {e}")
            try:
                s3.delete_object(Bucket=canonical_bucket, Key=s3_key)
            except Exception as cleanup_err:
                LOGGER.warning(f"    Could not roll back copied object: {cleanup_err}")
            errors += 1
            continue

        # Optionally delete from old bucket
        if args.delete_old:
            try:
                s3.delete_object(Bucket=old_bucket, Key=s3_key)
                LOGGER.info(f"    Deleted from old bucket")
            except ClientError as e:
                LOGGER.warning(f"    WARNING: failed to delete from old bucket: {e}")  # nosec B608 — log message, not SQL

        migrated += 1

    # -----------------------------------------------------------------------
    # Phase 2: Migrate message content (S3 URIs → opaque IDs)
    # -----------------------------------------------------------------------
    print("\nMigrating file_link message content to opaque IDs...")
    msg_migrated = 0
    msg_errors = 0

    msg_rows = db.query_messages_with_s3_uris()

    if not msg_rows:
        print("  No file_link messages need updating.")
    else:
        print(f"  Found {len(msg_rows)} file_link message(s) with S3 URIs in content")

        for msg_id, raw_content in msg_rows:
            new_json, changed = rewrite_message_content(raw_content)
            if not changed:
                continue

            LOGGER.info(f"  Message {msg_id}: file_id → opaque ID")

            if not args.execute:
                msg_migrated += 1
                continue

            try:
                db.update_message_content(msg_id, new_json)
                msg_migrated += 1
            except Exception as e:
                LOGGER.error(f"  ERROR updating message {msg_id}: {e}")
                msg_errors += 1

        print(f"  {'DRY RUN ' if not args.execute else ''}Messages updated: {msg_migrated}")
        if msg_errors > 0:
            print(f"  Message errors: {msg_errors}")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print()
    print(f"{'DRY RUN ' if not args.execute else ''}Summary:")
    print(f"  Files migrated:    {migrated}")
    print(f"  Files skipped:     {skipped}")
    print(f"  File errors:       {errors}")
    print(f"  Messages updated:  {msg_migrated}")
    if msg_errors > 0:
        print(f"  Message errors:    {msg_errors}")

    if not args.execute and (migrated > 0 or msg_migrated > 0):
        print(f"\nRe-run with --execute to perform the migration.")

    # -----------------------------------------------------------------------
    # Phase 3: Remove empty orphaned buckets
    # -----------------------------------------------------------------------
    if args.remove_empty_buckets and errors == 0:
        print(f"\nCleaning up empty orphaned buckets...")
        buckets_deleted = 0
        buckets_skipped = 0
        for bucket_name in bucket_counts:
            if bucket_name == canonical_bucket or bucket_name == "unknown":
                continue
            try:
                response = s3.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
                if response.get('KeyCount', 0) > 0:
                    LOGGER.info(f"  SKIP (not empty): {bucket_name}")
                    buckets_skipped += 1
                    continue
                s3.delete_bucket(Bucket=bucket_name)
                LOGGER.info(f"  Deleted empty bucket: {bucket_name}")
                buckets_deleted += 1
            except ClientError as e:
                code = e.response['Error']['Code']
                if code == 'BucketNotEmpty':
                    LOGGER.info(f"  SKIP (not empty): {bucket_name}")
                    buckets_skipped += 1
                else:
                    LOGGER.warning(f"  WARNING: failed to delete bucket {bucket_name}: {e}")
                    buckets_skipped += 1
        print(f"  Buckets deleted: {buckets_deleted}")
        if buckets_skipped > 0:
            print(f"  Buckets skipped (not empty or error): {buckets_skipped}")


if __name__ == "__main__":
    main()
