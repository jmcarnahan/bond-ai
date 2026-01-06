#!/usr/bin/env python3
"""
Cognito User Pool Setup Script

Creates or validates a Cognito user pool configuration for the Bond AI application.
Replicates the configuration from an existing setup and outputs the required .env variables.

The script is idempotent:
- If pool exists: validates it and outputs env vars (no changes made)
- If pool doesn't exist: creates it with all required configuration
- With --recreate: deletes existing pool and recreates from scratch

Usage:
    # Create new pool (or validate existing)
    python scripts/setup_cognito.py --profile <aws-profile>

    # Validate existing pool only
    python scripts/setup_cognito.py --profile <aws-profile> --validate-only

    # Delete and recreate existing pool
    python scripts/setup_cognito.py --profile <aws-profile> --recreate

    # Create with test user
    python scripts/setup_cognito.py --profile <aws-profile> --create-user test@example.com --temp-password TempPass123!
"""

import argparse
import sys
import json
import boto3
from botocore.exceptions import ClientError


def get_cognito_client(profile: str, region: str):
    """Create a Cognito IDP client with the specified profile."""
    session = boto3.Session(profile_name=profile, region_name=region)
    return session.client('cognito-idp')


def find_existing_pool(client, pool_name: str) -> dict | None:
    """Find an existing user pool by name."""
    paginator = client.get_paginator('list_user_pools')
    for page in paginator.paginate(MaxResults=60):
        for pool in page['UserPools']:
            if pool['Name'] == pool_name:
                return pool
    return None


def get_pool_details(client, pool_id: str) -> dict:
    """Get detailed information about a user pool."""
    response = client.describe_user_pool(UserPoolId=pool_id)
    return response['UserPool']


def get_pool_clients(client, pool_id: str) -> list:
    """Get all app clients for a user pool."""
    clients = []
    paginator = client.get_paginator('list_user_pool_clients')
    for page in paginator.paginate(UserPoolId=pool_id, MaxResults=60):
        for app_client in page['UserPoolClients']:
            details = client.describe_user_pool_client(
                UserPoolId=pool_id,
                ClientId=app_client['ClientId']
            )
            clients.append(details['UserPoolClient'])
    return clients


def create_user_pool(client, pool_name: str, region: str) -> dict:
    """Create a new Cognito user pool with the standard configuration."""
    print(f"Creating user pool: {pool_name}")

    response = client.create_user_pool(
        PoolName=pool_name,
        Policies={
            'PasswordPolicy': {
                'MinimumLength': 8,
                'RequireUppercase': True,
                'RequireLowercase': True,
                'RequireNumbers': True,
                'RequireSymbols': True,
                'TemporaryPasswordValidityDays': 7
            }
        },
        DeletionProtection='ACTIVE',
        AutoVerifiedAttributes=['email'],
        UsernameAttributes=['email'],
        VerificationMessageTemplate={
            'DefaultEmailOption': 'CONFIRM_WITH_CODE'
        },
        MfaConfiguration='OFF',
        EmailConfiguration={
            'EmailSendingAccount': 'COGNITO_DEFAULT'
        },
        AdminCreateUserConfig={
            'AllowAdminCreateUserOnly': True,
            'UnusedAccountValidityDays': 7
        },
        UsernameConfiguration={
            'CaseSensitive': False
        },
        AccountRecoverySetting={
            'RecoveryMechanisms': [
                {'Priority': 1, 'Name': 'verified_email'},
                {'Priority': 2, 'Name': 'verified_phone_number'}
            ]
        },
        UserPoolTier='ESSENTIALS'
    )

    pool = response['UserPool']
    print(f"  Created user pool: {pool['Id']}")
    return pool


def create_user_pool_domain(client, pool_id: str, region: str) -> str:
    """Create a Cognito domain for the user pool."""
    # Generate a domain prefix based on region and pool ID
    # Format: {region}{pool_id_suffix} (lowercase, no special chars)
    pool_suffix = pool_id.split('_')[1].lower()
    domain_prefix = f"{region.replace('-', '')}{pool_suffix}"

    print(f"Creating domain: {domain_prefix}")

    try:
        client.create_user_pool_domain(
            Domain=domain_prefix,
            UserPoolId=pool_id
        )
        print(f"  Created domain: {domain_prefix}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'InvalidParameterException':
            # Domain might already exist or be taken
            print(f"  Domain creation failed: {e.response['Error']['Message']}")
            # Try with a shorter/different prefix
            import hashlib
            short_hash = hashlib.md5(pool_id.encode()).hexdigest()[:8]
            domain_prefix = f"bondai{short_hash}"
            print(f"  Trying alternative domain: {domain_prefix}")
            client.create_user_pool_domain(
                Domain=domain_prefix,
                UserPoolId=pool_id
            )
            print(f"  Created domain: {domain_prefix}")
        else:
            raise

    return domain_prefix


def create_app_client(client, pool_id: str, client_name: str, callback_url: str) -> dict:
    """Create an app client for the user pool."""
    print(f"Creating app client: {client_name}")

    response = client.create_user_pool_client(
        UserPoolId=pool_id,
        ClientName=client_name,
        GenerateSecret=False,  # No secret for public clients (SPA/mobile)
        RefreshTokenValidity=5,
        AccessTokenValidity=60,
        IdTokenValidity=60,
        TokenValidityUnits={
            'AccessToken': 'minutes',
            'IdToken': 'minutes',
            'RefreshToken': 'days'
        },
        ExplicitAuthFlows=[
            'ALLOW_REFRESH_TOKEN_AUTH',
            'ALLOW_USER_AUTH',
            'ALLOW_USER_SRP_AUTH'
        ],
        SupportedIdentityProviders=['COGNITO'],
        CallbackURLs=[callback_url],
        AllowedOAuthFlows=['code'],
        AllowedOAuthScopes=['email', 'openid', 'phone'],
        AllowedOAuthFlowsUserPoolClient=True,
        PreventUserExistenceErrors='ENABLED',
        EnableTokenRevocation=True,
        AuthSessionValidity=3
    )

    app_client = response['UserPoolClient']
    print(f"  Created app client: {app_client['ClientId']}")
    return app_client


def delete_user_pool(client, pool_id: str):
    """Delete a user pool and its domain."""
    print(f"Deleting user pool: {pool_id}")

    # First, get pool details to check for domain
    try:
        pool = get_pool_details(client, pool_id)
        domain = pool.get('Domain')

        # Delete domain first if it exists
        if domain:
            print(f"  Deleting domain: {domain}")
            client.delete_user_pool_domain(
                Domain=domain,
                UserPoolId=pool_id
            )

        # Disable deletion protection if enabled
        if pool.get('DeletionProtection') == 'ACTIVE':
            print("  Disabling deletion protection...")
            client.update_user_pool(
                UserPoolId=pool_id,
                DeletionProtection='INACTIVE'
            )

        # Delete the pool
        client.delete_user_pool(UserPoolId=pool_id)
        print(f"  Deleted user pool: {pool_id}")

    except ClientError as e:
        print(f"  Error deleting pool: {e.response['Error']['Message']}")
        raise


def create_test_user(client, pool_id: str, email: str, temp_password: str):
    """Create a test user in the user pool."""
    print(f"Creating test user: {email}")

    try:
        response = client.admin_create_user(
            UserPoolId=pool_id,
            Username=email,
            UserAttributes=[
                {'Name': 'email', 'Value': email},
                {'Name': 'email_verified', 'Value': 'true'}
            ],
            TemporaryPassword=temp_password,
            MessageAction='SUPPRESS'  # Don't send welcome email
        )
        print(f"  Created user: {email}")
        print(f"  User status: {response['User']['UserStatus']}")
        print(f"  Temporary password: {temp_password}")
        print("  Note: User will need to change password on first login")
        return response['User']
    except ClientError as e:
        if e.response['Error']['Code'] == 'UsernameExistsException':
            print(f"  User already exists: {email}")
            return None
        raise


def output_env_variables(domain: str, client_id: str, region: str, callback_url: str):
    """Output the .env variables needed for the application."""
    print("\n" + "=" * 60)
    print("Add these to your .env file:")
    print("=" * 60)
    print(f'''
COGNITO_DOMAIN="https://{domain}.auth.{region}.amazoncognito.com"
COGNITO_CLIENT_ID="{client_id}"
COGNITO_REDIRECT_URI="{callback_url}"
COGNITO_SCOPES="openid,email,phone"
COGNITO_REGION="{region}"
''')
    print("=" * 60)


def validate_pool(client, pool_id: str, region: str):
    """Validate and display information about an existing pool."""
    pool = get_pool_details(client, pool_id)
    clients = get_pool_clients(client, pool_id)

    print("\n" + "=" * 60)
    print("User Pool Configuration")
    print("=" * 60)
    print(f"  Pool ID: {pool['Id']}")
    print(f"  Pool Name: {pool['Name']}")
    print(f"  ARN: {pool['Arn']}")
    print(f"  Domain: {pool.get('Domain', 'Not configured')}")
    print(f"  MFA: {pool['MfaConfiguration']}")
    print(f"  Deletion Protection: {pool.get('DeletionProtection', 'INACTIVE')}")
    print(f"  Estimated Users: {pool.get('EstimatedNumberOfUsers', 0)}")

    password_policy = pool.get('Policies', {}).get('PasswordPolicy', {})
    print(f"  Password Policy:")
    print(f"    Min Length: {password_policy.get('MinimumLength', 'N/A')}")
    print(f"    Require Uppercase: {password_policy.get('RequireUppercase', 'N/A')}")
    print(f"    Require Lowercase: {password_policy.get('RequireLowercase', 'N/A')}")
    print(f"    Require Numbers: {password_policy.get('RequireNumbers', 'N/A')}")
    print(f"    Require Symbols: {password_policy.get('RequireSymbols', 'N/A')}")

    print("\nApp Clients:")
    for app_client in clients:
        print(f"  - {app_client['ClientName']} ({app_client['ClientId']})")
        print(f"    OAuth Scopes: {', '.join(app_client.get('AllowedOAuthScopes', []))}")
        print(f"    Callback URLs: {', '.join(app_client.get('CallbackURLs', []))}")

    # Output env variables if we have the info
    if pool.get('Domain') and clients:
        output_env_variables(
            domain=pool['Domain'],
            client_id=clients[0]['ClientId'],
            region=region,
            callback_url=clients[0].get('CallbackURLs', ['http://localhost:8000/auth/cognito/callback'])[0]
        )


def main():
    parser = argparse.ArgumentParser(
        description='Create or validate a Cognito user pool for Bond AI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Create new pool (or use existing if already exists)
  python scripts/setup_cognito.py --profile my-aws-profile

  # Validate existing pool only
  python scripts/setup_cognito.py --profile my-aws-profile --validate-only

  # Delete and recreate existing pool
  python scripts/setup_cognito.py --profile my-aws-profile --recreate

  # Create with test user
  python scripts/setup_cognito.py --profile my-aws-profile \\
      --create-user test@example.com --temp-password TempPass123!
'''
    )

    parser.add_argument(
        '--profile',
        required=True,
        help='AWS profile name to use for authentication'
    )
    parser.add_argument(
        '--region',
        default='us-west-2',
        help='AWS region (default: us-west-2)'
    )
    parser.add_argument(
        '--pool-name',
        default='AgentSpaceDev User Pool',
        help='Name for the user pool (default: AgentSpaceDev User Pool)'
    )
    parser.add_argument(
        '--client-name',
        default='AgentSpaceDev',
        help='Name for the app client (default: AgentSpaceDev)'
    )
    parser.add_argument(
        '--callback-url',
        default='http://localhost:8000/auth/cognito/callback',
        help='OAuth callback URL (default: http://localhost:8000/auth/cognito/callback)'
    )
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate existing pool, do not create'
    )
    parser.add_argument(
        '--recreate',
        action='store_true',
        help='Delete existing pool and recreate from scratch'
    )
    parser.add_argument(
        '--create-user',
        metavar='EMAIL',
        help='Create a test user with this email address'
    )
    parser.add_argument(
        '--temp-password',
        default='TempPass123!',
        help='Temporary password for test user (default: TempPass123!)'
    )

    args = parser.parse_args()

    print(f"Using AWS profile: {args.profile}")
    print(f"Region: {args.region}")
    print()

    try:
        client = get_cognito_client(args.profile, args.region)
    except Exception as e:
        print(f"Error: Failed to create AWS session with profile '{args.profile}'")
        print(f"  {e}")
        sys.exit(1)

    # Check for existing pool
    existing = find_existing_pool(client, args.pool_name)

    if existing:
        print(f"Found existing user pool: {existing['Name']} ({existing['Id']})")

        if args.validate_only:
            # Just validate and output config
            validate_pool(client, existing['Id'], args.region)
            return

        if args.recreate:
            # Delete existing and recreate
            print("Recreate flag set - deleting existing pool...")
            delete_user_pool(client, existing['Id'])
            existing = None  # Fall through to creation
        else:
            # Default: validate existing pool and output env vars
            print("Using existing pool (use --recreate to delete and recreate)")

            pool_id = existing['Id']
            pool_details = get_pool_details(client, pool_id)
            domain = pool_details.get('Domain')

            # Check for existing app client
            clients = get_pool_clients(client, pool_id)
            app_client = None
            for c in clients:
                if c['ClientName'] == args.client_name:
                    app_client = c
                    break

            if not app_client:
                # Create app client if it doesn't exist
                app_client = create_app_client(client, pool_id, args.client_name, args.callback_url)
            else:
                print(f"Using existing app client: {app_client['ClientName']} ({app_client['ClientId']})")

            # Create domain if missing
            if not domain:
                domain = create_user_pool_domain(client, pool_id, args.region)

    if not existing:
        # Create new pool (either no pool existed or --recreate was used)
        if args.validate_only:
            print(f"No user pool found with name: {args.pool_name}")
            sys.exit(1)

        # Create new pool
        pool = create_user_pool(client, args.pool_name, args.region)
        pool_id = pool['Id']

        # Create domain
        domain = create_user_pool_domain(client, pool_id, args.region)

        # Create app client
        app_client = create_app_client(client, pool_id, args.client_name, args.callback_url)

    # Create test user if requested
    if args.create_user:
        create_test_user(client, pool_id, args.create_user, args.temp_password)

    # Get the domain if we don't have it yet
    if not domain:
        pool_details = get_pool_details(client, pool_id)
        domain = pool_details.get('Domain')

    # Output the env variables
    if domain and app_client:
        output_env_variables(
            domain=domain,
            client_id=app_client['ClientId'],
            region=args.region,
            callback_url=args.callback_url
        )
    else:
        print("\nWarning: Could not determine all configuration values.")
        print("Please check your Cognito setup manually.")

    print("\nDone!")


if __name__ == '__main__':
    main()
