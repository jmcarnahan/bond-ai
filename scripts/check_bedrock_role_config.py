#!/usr/bin/env python3
"""
Check the Bedrock agent role configuration and trust policies.
"""

import boto3
import json
import os
from dotenv import load_dotenv

load_dotenv()

def check_agent_role():
    """Check the Bedrock agent role configuration."""
    iam = boto3.client('iam')
    role_arn = os.getenv('BEDROCK_AGENT_ROLE_ARN')
    
    if not role_arn:
        print("❌ BEDROCK_AGENT_ROLE_ARN not set in environment")
        return
    
    role_name = role_arn.split('/')[-1]
    print(f"Checking role: {role_name}")
    print("=" * 60)
    
    try:
        # Get role details
        response = iam.get_role(RoleName=role_name)
        role = response['Role']
        
        print("\n=== Trust Policy ===")
        trust_policy = role['AssumeRolePolicyDocument']
        print(json.dumps(trust_policy, indent=2))
        
        # Check if bedrock can assume this role
        bedrock_trusted = False
        for statement in trust_policy.get('Statement', []):
            if statement.get('Effect') == 'Allow' and statement.get('Action') == 'sts:AssumeRole':
                principal = statement.get('Principal', {})
                if isinstance(principal, dict):
                    service = principal.get('Service', [])
                    if isinstance(service, str):
                        service = [service]
                    if 'bedrock.amazonaws.com' in service:
                        bedrock_trusted = True
                        break
        
        if bedrock_trusted:
            print("\n✓ Role trusts bedrock.amazonaws.com")
        else:
            print("\n❌ Role does NOT trust bedrock.amazonaws.com")
        
        # List attached policies
        print("\n=== Attached Policies ===")
        
        # Managed policies
        managed_policies = iam.list_attached_role_policies(RoleName=role_name)
        for policy in managed_policies['AttachedPolicies']:
            print(f"  - {policy['PolicyName']} (Managed)")
        
        # Inline policies
        inline_policies = iam.list_role_policies(RoleName=role_name)
        for policy_name in inline_policies['PolicyNames']:
            print(f"  - {policy_name} (Inline)")
            
            # Get inline policy details
            policy_response = iam.get_role_policy(
                RoleName=role_name,
                PolicyName=policy_name
            )
            print(f"    Policy Document:")
            print(json.dumps(policy_response['PolicyDocument'], indent=6))
        
        # Check specific permissions needed for knowledge bases
        print("\n=== Checking Knowledge Base Permissions ===")
        required_actions = [
            'bedrock:InvokeModel',
            'bedrock:Retrieve',
            'bedrock:RetrieveAndGenerate',
            'aoss:APIAccessAll',
            's3:GetObject',
            's3:ListBucket'
        ]
        
        print("Required actions for knowledge bases:")
        for action in required_actions:
            print(f"  - {action}")
        
        print("\nNote: Verify these permissions are granted by the attached policies")
        
    except Exception as e:
        print(f"❌ Error checking role: {str(e)}")

def check_opensearch_data_access_policy():
    """Check OpenSearch data access policies."""
    print("\n\n=== OpenSearch Data Access Policies ===")
    
    aoss = boto3.client('opensearchserverless', region_name=os.getenv('AWS_REGION', 'us-west-2'))
    
    try:
        # List all data access policies
        response = aoss.list_access_policies(type='data')
        
        for policy_summary in response.get('accessPolicySummaries', []):
            print(f"\nPolicy: {policy_summary['name']}")
            
            # Get full policy details
            policy_response = aoss.get_access_policy(
                name=policy_summary['name'],
                type='data'
            )
            
            policy_detail = policy_response['accessPolicyDetail']
            policy_doc = json.loads(policy_detail['policy'])
            
            print("Policy Document:")
            print(json.dumps(policy_doc, indent=2))
            
            # Check if Bedrock role is included
            role_arn = os.getenv('BEDROCK_AGENT_ROLE_ARN')
            if role_arn and role_arn in json.dumps(policy_doc):
                print(f"✓ This policy includes the Bedrock agent role")
            else:
                print(f"⚠️  This policy does NOT include the Bedrock agent role")
                
    except Exception as e:
        print(f"❌ Error checking OpenSearch policies: {str(e)}")

def suggest_fixes():
    """Suggest potential fixes based on the findings."""
    print("\n\n=== Suggested Fixes ===")
    print("1. Ensure the Bedrock agent role has the following permissions:")
    print("   - bedrock:InvokeModel")
    print("   - bedrock:Retrieve") 
    print("   - bedrock:RetrieveAndGenerate")
    print("   - aoss:APIAccessAll")
    print("   - s3:GetObject and s3:ListBucket for your S3 bucket")
    print("\n2. Update OpenSearch data access policies to include:")
    print("   - The Bedrock agent role ARN")
    print("   - Permissions for all index operations")
    print("\n3. Try creating a knowledge base with:")
    print("   - A new OpenSearch collection specifically for testing")
    print("   - Simple S3 bucket with minimal policies")
    print("   - Default Titan embedding model")

def main():
    check_agent_role()
    check_opensearch_data_access_policy()
    suggest_fixes()

if __name__ == "__main__":
    main()