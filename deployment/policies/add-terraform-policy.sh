#!/bin/bash

# Script to add Terraform permissions to bond-bedrock-user
# Run this with an account that has IAM permissions

USER_NAME="bond-bedrock-user"
POLICY_NAME="TerraformInfrastructurePolicy"

echo "Adding Terraform infrastructure policy to user: $USER_NAME"

aws iam put-user-policy \
  --user-name $USER_NAME \
  --policy-name $POLICY_NAME \
  --policy-document file://iam-policy-for-terraform.json

if [ $? -eq 0 ]; then
  echo "✅ Policy added successfully!"
  echo "You can now run: terraform apply -var-file=environments/minimal.tfvars"
else
  echo "❌ Failed to add policy. You may need to:"
  echo "1. Log into AWS Console with root/admin account"
  echo "2. Manually add the policy from iam-policy-for-terraform.json"
fi