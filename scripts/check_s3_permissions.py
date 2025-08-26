#!/usr/bin/env python3
"""
Check S3 permissions for Bedrock Agent role
"""

import os
import sys
import boto3
import json
from botocore.exceptions import ClientError

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_s3_permissions():
    """Check S3 permissions for the Bedrock Agent role"""
    
    # S3 bucket and file info from the error
    bucket_name = "bond-bedrock-files-119684128788"
    test_key = "files/bond_file_85e7defb2c484d3e92676ae4ac8fd9ed"
    role_arn = "arn:aws:iam::119684128788:role/BondAIBedrockAgentRole"
    
    # Initialize clients
    iam_client = boto3.client('iam')
    s3_client = boto3.client('s3')
    
    print(f"Checking permissions for role: {role_arn}")
    print(f"Target bucket: {bucket_name}")
    print(f"Test file: {test_key}")
    print("=" * 80)
    
    try:
        # 1. Get the role details
        role_name = role_arn.split('/')[-1]
        print(f"\n1. Getting role details for: {role_name}")
        
        role_response = iam_client.get_role(RoleName=role_name)
        role = role_response['Role']
        
        print(f"   Role created: {role['CreateDate']}")
        print(f"   Trust policy allows assume from:")
        trust_policy = role['AssumeRolePolicyDocument']
        for statement in trust_policy.get('Statement', []):
            principal = statement.get('Principal', {})
            if 'Service' in principal:
                services = principal['Service'] if isinstance(principal['Service'], list) else [principal['Service']]
                for service in services:
                    print(f"      - {service}")
        
        # 2. Get attached policies
        print(f"\n2. Checking attached policies:")
        
        # Get managed policies
        attached_policies = iam_client.list_attached_role_policies(RoleName=role_name)
        for policy in attached_policies['AttachedPolicies']:
            print(f"   - Managed Policy: {policy['PolicyName']} ({policy['PolicyArn']})")
            
            # Get policy details
            try:
                policy_version = iam_client.get_policy(PolicyArn=policy['PolicyArn'])
                default_version = policy_version['Policy']['DefaultVersionId']
                
                policy_doc = iam_client.get_policy_version(
                    PolicyArn=policy['PolicyArn'],
                    VersionId=default_version
                )
                
                # Check for S3 permissions
                policy_statements = policy_doc['PolicyVersion']['Document']['Statement']
                for stmt in policy_statements:
                    if 's3:' in str(stmt.get('Action', [])):
                        print(f"     Found S3 permissions in {policy['PolicyName']}:")
                        print(f"       Actions: {stmt.get('Action')}")
                        print(f"       Resources: {stmt.get('Resource')}")
            except:
                pass
        
        # Get inline policies
        inline_policies = iam_client.list_role_policies(RoleName=role_name)
        for policy_name in inline_policies['PolicyNames']:
            print(f"   - Inline Policy: {policy_name}")
            
            # Get inline policy document
            policy_response = iam_client.get_role_policy(
                RoleName=role_name,
                PolicyName=policy_name
            )
            policy_doc = policy_response['PolicyDocument']
            
            # Check for S3 permissions
            for stmt in policy_doc.get('Statement', []):
                if 's3:' in str(stmt.get('Action', [])):
                    print(f"     Found S3 permissions:")
                    print(f"       Actions: {stmt.get('Action')}")
                    print(f"       Resources: {stmt.get('Resource')}")
        
        # 3. Check bucket policy
        print(f"\n3. Checking bucket policy for {bucket_name}:")
        try:
            bucket_policy = s3_client.get_bucket_policy(Bucket=bucket_name)
            policy = json.loads(bucket_policy['Policy'])
            
            print("   Bucket policy statements:")
            for stmt in policy.get('Statement', []):
                print(f"   - Effect: {stmt.get('Effect')}")
                print(f"     Principal: {stmt.get('Principal')}")
                print(f"     Actions: {stmt.get('Action')}")
                print(f"     Resources: {stmt.get('Resource')}")
                
                # Check if this statement allows the role
                principal = stmt.get('Principal', {})
                if isinstance(principal, dict) and 'AWS' in principal:
                    aws_principals = principal['AWS'] if isinstance(principal['AWS'], list) else [principal['AWS']]
                    if role_arn in aws_principals or '*' in aws_principals:
                        print(f"     ✓ This statement includes the Bedrock role!")
                        
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchBucketPolicy':
                print("   No bucket policy found")
            else:
                print(f"   Error getting bucket policy: {e}")
        
        # 4. Check if the file exists
        print(f"\n4. Checking if file exists in S3:")
        try:
            s3_client.head_object(Bucket=bucket_name, Key=test_key)
            print(f"   ✓ File exists: s3://{bucket_name}/{test_key}")
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                print(f"   ✗ File not found: s3://{bucket_name}/{test_key}")
            else:
                print(f"   Error checking file: {e}")
        
        # 5. Test role assumption
        print(f"\n5. Testing role assumption:")
        sts_client = boto3.client('sts')
        
        try:
            # Get current identity
            caller_identity = sts_client.get_caller_identity()
            print(f"   Current identity: {caller_identity['Arn']}")
            
            # Try to assume the role
            assume_response = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName='s3-permission-test'
            )
            
            print(f"   ✓ Successfully assumed role")
            
            # Create S3 client with assumed role credentials
            assumed_credentials = assume_response['Credentials']
            assumed_s3_client = boto3.client(
                's3',
                aws_access_key_id=assumed_credentials['AccessKeyId'],
                aws_secret_access_key=assumed_credentials['SecretAccessKey'],
                aws_session_token=assumed_credentials['SessionToken']
            )
            
            # Test S3 access with assumed role
            try:
                assumed_s3_client.head_object(Bucket=bucket_name, Key=test_key)
                print(f"   ✓ Assumed role CAN access the file!")
            except ClientError as e:
                print(f"   ✗ Assumed role CANNOT access the file: {e}")
                
        except ClientError as e:
            print(f"   ✗ Cannot assume role: {e}")
            print("   Note: This is expected if you're not allowed to assume the Bedrock role")
        
        # 6. Recommendations
        print("\n6. Recommendations:")
        print("   If the Bedrock Agent role cannot access S3, you need to:")
        print("   a) Add an S3 policy to the role that allows s3:GetObject on the bucket")
        print("   b) Or add a bucket policy that allows the role to access objects")
        print("\n   Example inline policy for the role:")
        print(json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:ListBucket"
                    ],
                    "Resource": [
                        f"arn:aws:s3:::{bucket_name}",
                        f"arn:aws:s3:::{bucket_name}/*"
                    ]
                }
            ]
        }, indent=2))
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    check_s3_permissions()