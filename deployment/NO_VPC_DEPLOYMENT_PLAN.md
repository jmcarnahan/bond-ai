# Bond AI No-VPC Deployment Plan

## Overview
This document outlines the complete plan for deploying Bond AI without creating a new VPC. Instead, we'll use the AWS default VPC with a publicly accessible RDS instance secured by strict security groups.

## Key Architecture Changes

### Current VPC-Based Architecture
- Creates custom VPC with CIDR 10.0.0.0/16
- Private subnets for RDS
- Public subnets for NAT Gateway
- VPC endpoints for S3 and Bedrock
- App Runner with VPC Connector
- Monthly NAT Gateway cost: ~$45

### New No-VPC Architecture
- Uses AWS default VPC (exists in every account)
- RDS with public endpoint in default subnets
- App Runner in DEFAULT mode (no VPC connector)
- Security groups restrict RDS access to App Runner only
- No NAT Gateway costs
- Simpler networking model

## Prerequisites

### Required AWS Permissions
The following IAM permissions are required for deployment:
- EC2: Security groups, describe VPCs/Subnets
- RDS: Create/manage database instances and subnet groups
- App Runner: Create/manage services
- ECR: Create/manage repositories
- IAM: Create/manage roles and policies
- Secrets Manager: Create/manage secrets
- S3: Create/manage buckets

## Step 1: Test AWS Permissions

Run these commands to verify you have the necessary permissions in your target AWS account:

```bash
# Set your AWS region
export AWS_REGION=us-east-2  # Change as needed
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "Testing permissions for account: $AWS_ACCOUNT_ID in region: $AWS_REGION"

# Test 1: Check default VPC exists
echo "1. Checking default VPC..."
aws ec2 describe-vpcs --filters "Name=is-default,Values=true" --region $AWS_REGION --query 'Vpcs[0].VpcId' --output text
if [ $? -eq 0 ]; then echo "✓ Default VPC found"; else echo "✗ No default VPC"; fi

# Test 2: List default subnets (need at least 2 for RDS)
echo "2. Checking default subnets..."
SUBNET_COUNT=$(aws ec2 describe-subnets --filters "Name=default-for-az,Values=true" --region $AWS_REGION --query 'length(Subnets)' --output text)
echo "   Found $SUBNET_COUNT default subnets"
if [ $SUBNET_COUNT -ge 2 ]; then echo "✓ Sufficient subnets"; else echo "✗ Need at least 2 subnets"; fi

# Test 3: Test RDS permissions
echo "3. Testing RDS permissions..."
aws rds describe-db-engine-versions --engine postgres --engine-version 15.7 --region $AWS_REGION --max-items 1 > /dev/null 2>&1
if [ $? -eq 0 ]; then echo "✓ RDS permissions OK"; else echo "✗ RDS permissions issue"; fi

# Test 4: Test security group creation
echo "4. Testing security group creation..."
TEST_SG=$(aws ec2 create-security-group --group-name test-bond-ai-sg-$$ --description "Test SG" --region $AWS_REGION --query 'GroupId' --output text 2>/dev/null)
if [ $? -eq 0 ]; then 
    echo "✓ Can create security groups (ID: $TEST_SG)"
    aws ec2 delete-security-group --group-id $TEST_SG --region $AWS_REGION 2>/dev/null
else 
    echo "✗ Cannot create security groups"
fi

# Test 5: Test ECR repository creation
echo "5. Testing ECR permissions..."
aws ecr create-repository --repository-name test-bond-ai-repo-$$ --region $AWS_REGION > /dev/null 2>&1
if [ $? -eq 0 ]; then 
    echo "✓ ECR permissions OK"
    aws ecr delete-repository --repository-name test-bond-ai-repo-$$ --force --region $AWS_REGION > /dev/null 2>&1
else 
    echo "✗ ECR permissions issue"
fi

# Test 6: Test App Runner permissions
echo "6. Testing App Runner permissions..."
aws apprunner list-services --region $AWS_REGION > /dev/null 2>&1
if [ $? -eq 0 ]; then echo "✓ App Runner permissions OK"; else echo "✗ App Runner permissions issue"; fi

# Test 7: Test Secrets Manager
echo "7. Testing Secrets Manager permissions..."
aws secretsmanager create-secret --name test-bond-ai-secret-$$ --secret-string "test" --region $AWS_REGION > /dev/null 2>&1
if [ $? -eq 0 ]; then 
    echo "✓ Secrets Manager permissions OK"
    aws secretsmanager delete-secret --secret-id test-bond-ai-secret-$$ --force-delete-without-recovery --region $AWS_REGION > /dev/null 2>&1
else 
    echo "✗ Secrets Manager permissions issue"
fi

# Test 8: Test S3 permissions
echo "8. Testing S3 permissions..."
TEST_BUCKET="test-bond-ai-bucket-$$-$AWS_ACCOUNT_ID"
aws s3 mb s3://$TEST_BUCKET --region $AWS_REGION > /dev/null 2>&1
if [ $? -eq 0 ]; then 
    echo "✓ S3 permissions OK"
    aws s3 rb s3://$TEST_BUCKET --force > /dev/null 2>&1
else 
    echo "✗ S3 permissions issue"
fi

echo ""
echo "Permission test complete. Address any ✗ items before proceeding."
```

## Step 2: Destroy Existing VPC Deployment (If Any)

If you have an existing VPC-based deployment, destroy it first:

```bash
cd deployment/terraform
terraform destroy -var-file=environments/minimal-us-east-2.tfvars
```

## Step 3: Restructure Deployment Directories

```bash
cd deployment

# Rename existing terraform directory
mv terraform terraform-vpc

# Create new no-vpc directory structure
mkdir -p terraform-no-vpc/environments
mkdir -p terraform-no-vpc/modules
```

## Step 4: Update Main Makefile

The main `deployment/Makefile` will be updated to support deployment type selection:

### Key Changes:
- Interactive prompt for deployment type (VPC vs No-VPC)
- Separate make targets for each deployment type
- Unified commands that work with both deployments

### New Make Commands:
- `make deploy` - Interactive selection of deployment type
- `make deploy-vpc` - Direct VPC deployment
- `make deploy-no-vpc` - Direct no-VPC deployment
- `make destroy` - Interactive selection for destruction
- `make destroy-vpc` - Destroy VPC deployment
- `make destroy-no-vpc` - Destroy no-VPC deployment

## Step 5: Create No-VPC Terraform Configuration

### Key Configuration Files:

#### terraform-no-vpc/main.tf
- Data sources for default VPC and subnets
- RDS with public endpoint
- App Runner without VPC connector
- Security groups with strict IP restrictions

#### terraform-no-vpc/rds-public.tf
```hcl
# Key configuration:
resource "aws_db_instance" "main" {
  publicly_accessible    = true  # Critical for no-VPC
  db_subnet_group_name  = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds_public.id]
  # ... rest of RDS config
}
```

#### terraform-no-vpc/backend.tf
```hcl
# App Runner without VPC connector:
resource "aws_apprunner_service" "backend" {
  # No network_configuration block needed
  # Or use:
  network_configuration {
    egress_configuration {
      egress_type = "DEFAULT"  # No VPC connector
    }
  }
}
```

## Step 6: Security Configuration

### RDS Security Group
```bash
# The security group will:
1. Allow PostgreSQL (5432) only from App Runner service IPs
2. Deny all other inbound traffic
3. Enable SSL/TLS enforcement
4. Use AWS Secrets Manager for credentials
```

### App Runner Security
```bash
# App Runner will:
1. Use IAM roles for AWS service access
2. Store secrets in AWS Secrets Manager
3. Use environment variables for configuration
4. Enable CloudWatch logging
```

## Step 7: Deployment Process

```bash
# 1. Navigate to deployment directory
cd deployment

# 2. Run the deployment (will prompt for type)
make deploy

# 3. Select option 2 for no-VPC deployment
# Enter choice [1-2]: 2

# 4. Monitor the deployment
# The process will:
#   - Initialize Terraform
#   - Create RDS in default VPC with public endpoint
#   - Deploy App Runner services
#   - Configure security groups
#   - Set up post-deployment configurations

# 5. Get deployment outputs
make outputs

# 6. Test the deployment
make test-health
```

## Step 8: Validation

After deployment, validate the setup:

```bash
# 1. Check RDS is publicly accessible but secured
aws rds describe-db-instances --db-instance-identifier bond-ai-dev-db \
  --query 'DBInstances[0].PubliclyAccessible' --output text

# 2. Test App Runner health
curl https://$(terraform output -raw app_runner_service_url)/health

# 3. Verify security group restrictions
aws ec2 describe-security-groups --group-ids $(terraform output -raw rds_security_group_id) \
  --query 'SecurityGroups[0].IpPermissions'

# 4. Test database connectivity from App Runner
make test-backend
```

## Step 9: Application Configuration

No application code changes are required. The application uses the `METADATA_DB_URL` environment variable which is set by Terraform:

```
METADATA_DB_URL=postgresql://bondadmin:PASSWORD@rds-public-endpoint.region.rds.amazonaws.com:5432/bondai
```

## Rollback Plan

If issues arise, rollback to VPC deployment:

```bash
# 1. Destroy no-VPC deployment
cd deployment
make destroy-no-vpc

# 2. Deploy using VPC version
make deploy-vpc

# 3. The terraform-vpc directory remains untouched
# All previous configurations are preserved
```

## Cost Comparison

### VPC Deployment
- NAT Gateway: ~$45/month
- RDS (db.t3.micro): ~$15/month
- App Runner: Variable based on usage
- **Total: ~$60/month + usage**

### No-VPC Deployment
- No NAT Gateway: $0
- RDS (db.t3.micro): ~$15/month
- App Runner: Variable based on usage
- **Total: ~$15/month + usage**

**Monthly Savings: ~$45**

## Security Considerations

### Advantages
- Simpler network topology
- Fewer components to manage
- Same encryption capabilities (TLS/SSL)
- IAM-based access control

### Mitigations for Public RDS
1. **Strict Security Groups**: Only allow App Runner IPs
2. **SSL/TLS Required**: Force encrypted connections
3. **Strong Passwords**: Use AWS Secrets Manager
4. **Monitoring**: Enable CloudWatch and RDS Performance Insights
5. **Backups**: Automated backups enabled
6. **Encryption**: Enable encryption at rest

## Troubleshooting

### Common Issues and Solutions

1. **Default VPC Not Found**
   ```bash
   # Create default VPC if missing
   aws ec2 create-default-vpc --region $AWS_REGION
   ```

2. **Insufficient Subnets**
   - Default VPC should have subnets in all AZs
   - Verify with: `aws ec2 describe-subnets --filters "Name=default-for-az,Values=true"`

3. **RDS Connection Failed**
   - Check security group rules
   - Verify App Runner service is running
   - Ensure SSL/TLS is configured correctly

4. **App Runner Can't Connect to RDS**
   - Verify METADATA_DB_URL environment variable
   - Check RDS is publicly accessible
   - Validate security group allows App Runner IPs

## Next Steps

After successful deployment:

1. **Update Okta Configuration**
   - Add backend callback URL to Okta app
   - Update redirect URIs

2. **Test Authentication Flow**
   - Visit frontend URL
   - Test OAuth login
   - Verify JWT tokens

3. **Monitor Application**
   - Set up CloudWatch alarms
   - Enable RDS Performance Insights
   - Configure log aggregation

4. **Documentation**
   - Update README with new deployment option
   - Document environment-specific configurations
   - Create runbook for operations

## Appendix: File Structure

```
deployment/
├── terraform-vpc/              # Original VPC-based deployment
│   ├── main.tf
│   ├── backend.tf
│   ├── frontend.tf
│   └── environments/
├── terraform-no-vpc/           # New no-VPC deployment
│   ├── main.tf                # Core resources
│   ├── rds-public.tf          # RDS with public endpoint
│   ├── backend.tf             # App Runner backend
│   ├── frontend.tf            # App Runner frontend
│   ├── security.tf            # Security groups
│   ├── variables.tf           # Variable definitions
│   ├── outputs.tf             # Output values
│   └── environments/
│       └── minimal.tfvars     # Environment configuration
├── Makefile                    # Updated with deployment selection
└── NO_VPC_DEPLOYMENT_PLAN.md   # This document
```

## Summary

This no-VPC deployment approach:
- ✅ Eliminates VPC creation requirements
- ✅ Reduces costs by $45/month (no NAT Gateway)
- ✅ Simplifies network architecture
- ✅ Maintains security through strict security groups
- ✅ Requires no application code changes
- ✅ Preserves all application functionality

The implementation maintains backward compatibility with the VPC deployment, allowing easy switching between deployment modes based on requirements.