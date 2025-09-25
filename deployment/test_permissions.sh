# Set your AWS region
export AWS_REGION=us-east-1  # Change as needed
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

# Check if there are existing security groups you can use
echo "Existing security groups:"
aws ec2 describe-security-groups --region $AWS_REGION \
--query 'SecurityGroups[?GroupName!=`default`].[GroupId,GroupName,Description]' --output table

# Check if there are other VPCs with subnets
echo "All VPCs and their subnet counts:"
aws ec2 describe-vpcs --region $AWS_REGION --query 'Vpcs[*].VpcId' --output text | \
while read vpc; do
    subnet_count=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$vpc" --region $AWS_REGION --query 'length(Subnets)' --output text)
    echo "VPC $vpc has $subnet_count subnets"
done


echo ""
echo "Permission test complete. Address any ✗ items before proceeding."