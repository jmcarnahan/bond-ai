#!/usr/bin/env python3
"""
Create the missing AWSServiceRoleForAmazonBedrock service-linked role.
This role is required for Bedrock to access other AWS services like OpenSearch.
"""

import boto3
import json
import sys
from dotenv import load_dotenv

load_dotenv()

def create_bedrock_service_linked_role():
    """Create the service-linked role for Amazon Bedrock."""
    iam = boto3.client('iam')
    
    try:
        # Check if role already exists
        try:
            response = iam.get_role(RoleName='AWSServiceRoleForAmazonBedrock')
            print("✓ AWSServiceRoleForAmazonBedrock already exists")
            print(f"  ARN: {response['Role']['Arn']}")
            return response['Role']['Arn']
        except iam.exceptions.NoSuchEntityException:
            print("AWSServiceRoleForAmazonBedrock not found. Creating...")
        
        # Create the service-linked role
        response = iam.create_service_linked_role(
            AWSServiceName='bedrock.amazonaws.com',
            Description='Service-linked role for Amazon Bedrock'
        )
        
        role_arn = response['Role']['Arn']
        print(f"✓ Successfully created AWSServiceRoleForAmazonBedrock")
        print(f"  ARN: {role_arn}")
        print(f"  Role ID: {response['Role']['RoleId']}")
        
        # The role may take a moment to propagate
        print("\nWaiting for role to propagate...")
        import time
        time.sleep(10)
        
        return role_arn
        
    except iam.exceptions.InvalidInputException as e:
        if "has been taken" in str(e):
            print("⚠️  Service-linked role already exists (may be in a different state)")
            # Try to get it again
            try:
                response = iam.get_role(RoleName='AWSServiceRoleForAmazonBedrock')
                return response['Role']['Arn']
            except:
                pass
        else:
            print(f"❌ Error creating service-linked role: {str(e)}")
            raise
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        print("\nNote: You may need to:")
        print("1. Ensure your IAM user has permission to create service-linked roles")
        print("2. Check if your AWS account has SCPs that prevent this")
        print("3. Try creating the role through the AWS Console")
        raise

def verify_bedrock_permissions():
    """Verify that Bedrock can now access required services."""
    print("\n=== Verifying Bedrock Permissions ===")
    
    # Check that we can list Bedrock resources
    bedrock = boto3.client('bedrock-agent', region_name='us-west-2')
    
    try:
        # Try to list knowledge bases (even if none exist)
        response = bedrock.list_knowledge_bases()
        print("✓ Can list knowledge bases")
        
        # Try to list agents
        response = bedrock.list_agents()
        print("✓ Can list agents")
        
        print("\nBedrock permissions look good!")
        
    except Exception as e:
        print(f"⚠️  Error verifying permissions: {str(e)}")

def main():
    print("Creating Service-Linked Role for Amazon Bedrock")
    print("=" * 60)
    
    try:
        role_arn = create_bedrock_service_linked_role()
        verify_bedrock_permissions()
        
        print("\n" + "=" * 60)
        print("✓ Service-linked role setup complete!")
        print("\nNext steps:")
        print("1. Try creating the knowledge base again in the console")
        print("2. If it still fails, check the console for more detailed error messages")
        print("3. Ensure your OpenSearch collections have the correct access policies")
        
    except Exception as e:
        print(f"\n❌ Failed to create service-linked role: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()