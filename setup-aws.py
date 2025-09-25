#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Set up AWS resources for Bond AI application",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "--account-id", 
        dest="account_id",
        required=True,
        help="AWS Account ID (12-digit number)"
    )
    
    parser.add_argument(
        "--region", 
        required=True,
        help="AWS Region (e.g., us-east-1)"
    )
    
    parser.add_argument(
        "--role-name",
        default="BondAIBedrockAgentRole",
        help="Name of the IAM role to create"
    )
    
    parser.add_argument(
        "--bucket-name",
        help="Name of the S3 bucket to create. Defaults to bondai-{account-id}"
    )
    
    parser.add_argument(
        "--profile",
        default="default",
        help="AWS CLI profile to use"
    )
    
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run in non-interactive mode (no prompts, use defaults)"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite of existing resources"
    )
    
    return parser.parse_args()


def validate_arguments(args):
    """Validate the provided command-line arguments."""
    # Check if account_id attribute exists (should already be properly named from argparse)
    if not hasattr(args, 'account_id'):
        print("Error: account_id attribute not found in arguments")
        sys.exit(1)
        
    # Validate AWS Account ID (should be 12 digits)
    if not args.account_id.isdigit() or len(args.account_id) != 12:
        print(f"Error: Invalid AWS Account ID: {args.account_id}")
        print("AWS Account ID should be a 12-digit number.")
        sys.exit(1)
    
    # Validate AWS region format (basic check)
    if not args.region.startswith(('us-', 'eu-', 'ap-', 'ca-', 'me-', 'sa-', 'af-')):
        print(f"Warning: Region '{args.region}' doesn't follow typical AWS region format.")
        if not args.non_interactive:
            response = input("Continue anyway? (y/n): ")
            if response.lower() != 'y':
                sys.exit(0)
        else:
            print("Continuing with the provided region due to non-interactive mode.")
    
    # Set default bucket name if not provided
    if not args.bucket_name:
        args.bucket_name = f"bondai-{args.account_id.lower()}"
    
    return args


def run_command(command, shell=False, check=True, capture_output=True, exit_on_error=False):
    """Run a shell command and return the result."""
    try:
        if not shell:
            command = command.split()
        
        result = subprocess.run(
            command,
            shell=shell,
            check=check,
            text=True,
            capture_output=capture_output
        )
        return result
    except subprocess.CalledProcessError as e:
        if exit_on_error:
            print(f"Error executing command: {command}")
            print(f"Error message: {e.stderr if e.stderr else e}")
            sys.exit(1)
        else:
            # Re-raise the exception for the caller to handle
            raise


def check_aws_cli():
    """Check if AWS CLI is installed and configured."""
    try:
        result = run_command("aws --version", exit_on_error=True)
        print(f"AWS CLI detected: {result.stdout.strip()}")
    except Exception:
        print("Error: AWS CLI not found. Please install it first:")
        print("https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html")
        sys.exit(1)


def check_aws_permissions(profile):
    """Check if the user has the necessary AWS permissions."""
    try:
        print(f"Checking AWS credentials for profile '{profile}'...")
        result = run_command(f"aws sts get-caller-identity --profile {profile}", exit_on_error=True)
        identity = json.loads(result.stdout)
        print(f"Authenticated as: {identity['Arn']}")
        return identity
    except Exception as e:
        print(f"Error: Unable to authenticate with AWS using profile '{profile}'")
        print(f"Error details: {e}")
        sys.exit(1)


def create_iam_role(args, policy_path):
    """Create IAM role with the required permissions."""
    role_name = args.role_name
    account_id = args.account_id
    profile = args.profile
    non_interactive = getattr(args, 'non_interactive', False)
    force = getattr(args, 'force', False)
    
    print(f"\nCreating IAM role '{role_name}'...")
    
    # Check if role already exists
    check_role_cmd = f"aws iam get-role --role-name {role_name} --profile {profile}"
    try:
        result = run_command(check_role_cmd)
        print(f"IAM role '{role_name}' already exists.")
        role_data = json.loads(result.stdout)
        role_arn = role_data['Role']['Arn']
        
        if args.non_interactive:
            if args.force:
                print("Updating permissions due to --force flag.")
            else:
                print("Skipping permission update due to non-interactive mode.")
                return role_arn
        else:
            overwrite = input("Do you want to update its permissions? (y/n): ")
            if overwrite.lower() != 'y':
                return role_arn
    except subprocess.CalledProcessError:
        # Role doesn't exist, create it
        # Create trust relationship policy document for assuming the role
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "Statement1",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "bedrock.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        
        trust_policy_file = "trust_policy_temp.json"
        with open(trust_policy_file, "w") as f:
            json.dump(trust_policy, f)
        
        # Create the role with trust policy
        create_role_cmd = (
            f"aws iam create-role --role-name {role_name} "
            f"--assume-role-policy-document file://{trust_policy_file} "
            f"--description 'Role for BondAI to use Bedrock' "
            f"--profile {profile}"
        )
        
        try:
            result = run_command(create_role_cmd, shell=True)
            print(f"Created IAM role: {role_name}")
        except Exception as e:
            print(f"Error creating IAM role: {e}")
            sys.exit(1)
        finally:
            # Clean up temporary file
            if os.path.exists(trust_policy_file):
                os.remove(trust_policy_file)
    
    # Attach the policy to the role
    try:
        policy_name = f"BondAIBedrockAgentPolicy"
        
        # Create policy if it doesn't exist
        try:
            policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"
            check_policy_cmd = f"aws iam get-policy --policy-arn {policy_arn} --profile {profile}"
            run_command(check_policy_cmd)
            print(f"Policy '{policy_name}' already exists with ARN: {policy_arn}")
        except subprocess.CalledProcessError:
            # Create the policy
            create_policy_cmd = (
                f"aws iam create-policy --policy-name {policy_name} "
                f"--policy-document file://{policy_path} "
                f"--description 'Policy for BondAI to use Bedrock' "
                f"--profile {profile}"
            )
            result = run_command(create_policy_cmd, shell=True)
            policy_result = json.loads(result.stdout)
            policy_arn = policy_result['Policy']['Arn']
            print(f"Created policy '{policy_name}' with ARN: {policy_arn}")
        
        # Attach policy to role
        attach_cmd = (
            f"aws iam attach-role-policy --role-name {role_name} "
            f"--policy-arn {policy_arn} --profile {profile}"
        )
        run_command(attach_cmd)
        print(f"Attached policy '{policy_name}' to role '{role_name}'")
        
        # Return the role ARN
        get_role_cmd = f"aws iam get-role --role-name {role_name} --profile {profile}"
        result = run_command(get_role_cmd, exit_on_error=True)
        role_data = json.loads(result.stdout)
        return role_data['Role']['Arn']
    
    except Exception as e:
        print(f"Error attaching policy to role: {e}")
        sys.exit(1)


def create_s3_bucket(args):
    """Create S3 bucket for the application."""
    bucket_name = args.bucket_name
    region = args.region
    profile = args.profile
    account_id = args.account_id
    non_interactive = getattr(args, 'non_interactive', False)
    force = getattr(args, 'force', False)
    
    print(f"\nCreating S3 bucket '{bucket_name}'...")
    
    # Check if bucket exists
    check_bucket_cmd = f"aws s3api head-bucket --bucket {bucket_name} --profile {profile}"
    try:
        run_command(check_bucket_cmd, exit_on_error=False)
        print(f"S3 bucket '{bucket_name}' already exists.")
        bucket_arn = f"arn:aws:s3:::{bucket_name}"
        return (bucket_name, bucket_arn)
    except subprocess.CalledProcessError:
        # Bucket doesn't exist or you don't have access to it
        pass
    
    # Create the bucket
    if region == 'us-east-1':
        # Special case for us-east-1 which doesn't accept LocationConstraint
        create_bucket_cmd = f"aws s3api create-bucket --bucket {bucket_name} --profile {profile}"
    else:
        create_bucket_cmd = (
            f"aws s3api create-bucket --bucket {bucket_name} "
            f"--create-bucket-configuration LocationConstraint={region} "
            f"--profile {profile}"
        )
    
    try:
        if region == 'us-east-1':
            # Special case for us-east-1 which doesn't accept LocationConstraint
            create_bucket_cmd = f"aws s3api create-bucket --bucket {bucket_name} --region us-east-1 --profile {profile}"
        else:
            create_bucket_cmd = (
                f"aws s3api create-bucket --bucket {bucket_name} "
                f"--create-bucket-configuration LocationConstraint={region} "
                f"--region {region} "
                f"--profile {profile}"
            )
            
        result = run_command(create_bucket_cmd, shell=True, exit_on_error=False)
        print(f"Created S3 bucket: {bucket_name}")
        
        # Set bucket policy for private access
        print("Setting bucket to private access...")
        private_cmd = (
            f"aws s3api put-public-access-block --bucket {bucket_name} "
            f"--public-access-block-configuration 'BlockPublicAcls=true,IgnorePublicAcls=true,"
            f"BlockPublicPolicy=true,RestrictPublicBuckets=true' "
            f"--profile {profile}"
        )
        run_command(private_cmd, shell=True)
        print("Bucket set to private access.")
        
        # Return bucket name and ARN
        bucket_arn = f"arn:aws:s3:::{bucket_name}"
        return (bucket_name, bucket_arn)
    except subprocess.CalledProcessError as e:
        print(f"Error creating S3 bucket: {str(e)}")
        if "BucketAlreadyExists" in str(e):
            print(f"The bucket name '{bucket_name}' is already taken by another AWS account.")
            print("Try a different bucket name.")
        elif "InvalidLocationConstraint" in str(e):
            print(f"Invalid location constraint for region {region}. Try using us-east-1.")
        else:
            print("Detailed error:")
            if hasattr(e, 'stderr'):
                print(e.stderr)
        print("\nSkipping S3 bucket creation. You can create the bucket manually later.")
        return None, None
    except Exception as e:
        print(f"Unexpected error creating S3 bucket: {str(e)}")
        print("\nSkipping S3 bucket creation. You can create the bucket manually later.")
        return None, None


def generate_config_file(args, role_arn, bucket_name, bucket_arn=None):
    """Generate a config file with the created resources."""
    config = {
        "AWS_ACCOUNT_ID": args.account_id,
        "AWS_REGION": args.region,
        "BEDROCK_AGENT_ROLE_ARN": role_arn
    }
    
    if bucket_name:
        config["S3_BUCKET_NAME"] = bucket_name
        if bucket_arn:
            config["S3_BUCKET_ARN"] = bucket_arn
    
    config_file = "aws_config.json"
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)
    
    print(f"\nConfiguration saved to {config_file}")
    print("You can use these values in your environment variables or application config.")


def main():
    """Main function to set up AWS resources."""
    print("Setting up AWS resources for Bond AI application...\n")
    
    # Check if AWS CLI is installed
    check_aws_cli()
    
    # Parse and validate arguments
    args = parse_arguments()
    args = validate_arguments(args)
    
    # Check AWS permissions
    identity = check_aws_permissions(args.profile)
    
    # Check if the provided account ID matches the authenticated account
    if identity['Account'] != args.account_id:
        print(f"Warning: The provided account ID ({args.account_id}) doesn't match")
        print(f"the authenticated account ID ({identity['Account']}).")
        if not args.non_interactive:
            response = input("Continue anyway? (y/n): ")
            if response.lower() != 'y':
                sys.exit(0)
        else:
            print("Continuing with the provided account ID due to non-interactive mode.")
    
    # Locate the policy file
    script_dir = Path(__file__).resolve().parent
    policy_path = script_dir / "bondai_bedrock_agent_policy.json"
    
    if not policy_path.exists():
        print(f"Error: Policy file not found at {policy_path}")
        sys.exit(1)
    
    # Create IAM role with required permissions
    role_arn = create_iam_role(args, policy_path)
    if not role_arn:
        print("\n⚠️ Warning: IAM role creation failed or was skipped.")
        print("You may need to create the role manually.")
        sys.exit(1)
    
    # Create S3 bucket
    bucket_result = create_s3_bucket(args)
    if bucket_result:
        if isinstance(bucket_result, tuple) and len(bucket_result) == 2:
            bucket_name, bucket_arn = bucket_result
        else:
            bucket_name = bucket_result
            bucket_arn = f"arn:aws:s3:::{bucket_name}" if bucket_name else None
    else:
        bucket_name = None
        bucket_arn = None
    
    # Generate config file
    generate_config_file(args, role_arn, bucket_name, bucket_arn)
    
    print("\n✅ AWS setup completed successfully!")
    print(f"- IAM Role: {args.role_name}")
    print(f"- IAM Role ARN: {role_arn}")
    if bucket_name:
        print(f"- S3 Bucket: {bucket_name}")
        if bucket_arn:
            print(f"- S3 Bucket ARN: {bucket_arn}")
    else:
        print("- S3 Bucket: [Creation skipped]")
    print(f"- Region: {args.region}")
    
    # Print environment variables format
    print("\nEnvironment Variables:")
    print(f"export AWS_ACCOUNT_ID={args.account_id}")
    print(f"export AWS_REGION={args.region}")
    print(f"export BEDROCK_AGENT_ROLE_ARN=\"{role_arn}\"")
    if bucket_name:
        print(f"export S3_BUCKET_NAME={bucket_name}")
        if bucket_arn:
            print(f"export S3_BUCKET_ARN=\"{bucket_arn}\"")

    print("\nNext steps:")
    print("1. Use these resources in your Bond AI application configuration")
    print("2. Make sure your application has the necessary credentials to use these resources")


if __name__ == "__main__":
    main()