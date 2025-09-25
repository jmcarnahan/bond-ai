#!/bin/bash

# Bond AI VPC Testing Script
# Tests if an existing VPC can be used for Bond AI deployment
# Usage: ./test-vpc-availability.sh

set -e

# Configuration
VPC_ID="vpc-08acfe7cf84c026c7"
VPC_NAME="tfvpc-us-west-dev-2"
VPC_CIDR="10.6.28.0/23"
AWS_REGION="us-west-2"  # Hard-coded to us-west-2
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Bond AI VPC Availability Test${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Testing VPC: $VPC_NAME ($VPC_ID)"
echo "VPC CIDR: $VPC_CIDR"
echo "AWS Account: $AWS_ACCOUNT_ID"
echo "AWS Region: $AWS_REGION"
echo ""
echo -e "${BLUE}----------------------------------------${NC}"

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0
WARNINGS=0

# Function to print test results
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}✗${NC} $2"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

print_warning() {
    echo -e "${YELLOW}⚠${NC}  $1"
    WARNINGS=$((WARNINGS + 1))
}

# Test 1: Verify VPC exists and is accessible
echo -e "\n${BLUE}1. VPC Accessibility Tests${NC}"
echo "----------------------------------------"

VPC_INFO=$(aws ec2 describe-vpcs --vpc-ids $VPC_ID --region $AWS_REGION 2>&1)
if [ $? -eq 0 ]; then
    print_result 0 "VPC $VPC_ID is accessible"
    
    # Extract VPC details
    VPC_STATE=$(echo "$VPC_INFO" | jq -r '.Vpcs[0].State')
    VPC_ACTUAL_CIDR=$(echo "$VPC_INFO" | jq -r '.Vpcs[0].CidrBlock')
    
    # Get DNS attributes separately (not included in describe-vpcs)
    DNS_SUPPORT_RESULT=$(aws ec2 describe-vpc-attribute --vpc-id $VPC_ID --attribute enableDnsSupport --region $AWS_REGION 2>&1)
    if [ $? -eq 0 ]; then
        DNS_SUPPORT=$(echo "$DNS_SUPPORT_RESULT" | jq -r '.EnableDnsSupport.Value')
    else
        DNS_SUPPORT="unknown"
    fi
    
    DNS_HOSTNAMES_RESULT=$(aws ec2 describe-vpc-attribute --vpc-id $VPC_ID --attribute enableDnsHostnames --region $AWS_REGION 2>&1)
    if [ $? -eq 0 ]; then
        DNS_HOSTNAMES=$(echo "$DNS_HOSTNAMES_RESULT" | jq -r '.EnableDnsHostnames.Value')
    else
        DNS_HOSTNAMES="unknown"
    fi
    
    echo "   - State: $VPC_STATE"
    echo "   - CIDR: $VPC_ACTUAL_CIDR"
    echo "   - DNS Support: $DNS_SUPPORT"
    echo "   - DNS Hostnames: $DNS_HOSTNAMES"
    
    if [ "$VPC_STATE" != "available" ]; then
        print_result 1 "VPC is not in available state"
    else
        print_result 0 "VPC is in available state"
    fi
    
    if [ "$DNS_SUPPORT" != "true" ] || [ "$DNS_HOSTNAMES" != "true" ]; then
        print_warning "DNS support or hostnames not fully enabled (required for RDS)"
    fi
else
    print_result 1 "Cannot access VPC $VPC_ID"
    echo -e "${RED}Error: $VPC_INFO${NC}"
    echo -e "${RED}Cannot continue tests without VPC access${NC}"
    exit 1
fi

# Test 2: Check subnets
echo -e "\n${BLUE}2. Subnet Tests${NC}"
echo "----------------------------------------"

SUBNETS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --region $AWS_REGION --query 'Subnets[*].[SubnetId,AvailabilityZone,CidrBlock,State,MapPublicIpOnLaunch]' --output json 2>&1)
if [ $? -eq 0 ]; then
    SUBNET_COUNT=$(echo "$SUBNETS" | jq 'length')
    print_result 0 "Found $SUBNET_COUNT subnets in VPC"
    
    if [ $SUBNET_COUNT -ge 2 ]; then
        print_result 0 "Sufficient subnets for RDS (need at least 2)"
    else
        print_result 1 "Insufficient subnets for RDS (need at least 2, found $SUBNET_COUNT)"
    fi
    
    # List subnet details and check for private subnets (App Runner best practice)
    PRIVATE_SUBNETS=0
    PUBLIC_SUBNETS=0
    echo "$SUBNETS" | jq -r '.[] | "   - \(.[0]): AZ=\(.[1]), CIDR=\(.[2]), State=\(.[3]), PublicIP=\(.[4])"'
    
    # Count private vs public subnets
    while IFS= read -r subnet; do
        PUBLIC_IP=$(echo "$subnet" | jq -r '.[4]')
        if [ "$PUBLIC_IP" == "true" ]; then
            PUBLIC_SUBNETS=$((PUBLIC_SUBNETS + 1))
        else
            PRIVATE_SUBNETS=$((PRIVATE_SUBNETS + 1))
        fi
    done <<< "$(echo "$SUBNETS" | jq -c '.[]')"
    
    echo "   - Private subnets: $PRIVATE_SUBNETS (recommended for App Runner)"
    echo "   - Public subnets: $PUBLIC_SUBNETS"
    
    if [ $PRIVATE_SUBNETS -gt 0 ]; then
        print_result 0 "Private subnets available (App Runner best practice)"
    else
        print_warning "No private subnets found (App Runner recommends private subnets)"
    fi
    
    # Check for different AZs (required for RDS)
    UNIQUE_AZS=$(echo "$SUBNETS" | jq -r '.[] | .[1]' | sort -u | wc -l)
    if [ $UNIQUE_AZS -ge 2 ]; then
        print_result 0 "Subnets span $UNIQUE_AZS availability zones (good for RDS)"
    else
        print_result 1 "Subnets only in $UNIQUE_AZS AZ (need at least 2 for RDS)"
    fi
    
    # Store subnet IDs for later use
    SUBNET_IDS=$(echo "$SUBNETS" | jq -r '.[] | .[0]' | paste -sd, -)
else
    print_result 1 "Cannot list subnets in VPC"
    echo "   Error: $SUBNETS"
fi

# Test 3: Internet Gateway
echo -e "\n${BLUE}3. Internet Gateway Tests${NC}"
echo "----------------------------------------"

IGW=$(aws ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=$VPC_ID" --region $AWS_REGION --query 'InternetGateways[0].InternetGatewayId' --output text 2>&1)
if [ "$IGW" != "None" ] && [ ! -z "$IGW" ]; then
    print_result 0 "Internet Gateway found: $IGW"
else
    print_result 1 "No Internet Gateway attached to VPC"
    print_warning "App Runner needs internet access"
fi

# Test 4: NAT Gateway
echo -e "\n${BLUE}4. NAT Gateway Tests${NC}"
echo "----------------------------------------"

NAT_GWS=$(aws ec2 describe-nat-gateways --filter "Name=vpc-id,Values=$VPC_ID" "Name=state,Values=available" --region $AWS_REGION --query 'NatGateways[*].NatGatewayId' --output json 2>&1)
if [ $? -eq 0 ]; then
    NAT_COUNT=$(echo "$NAT_GWS" | jq 'length')
    if [ $NAT_COUNT -gt 0 ]; then
        print_result 0 "Found $NAT_COUNT NAT Gateway(s)"
        echo "$NAT_GWS" | jq -r '.[]' | while read nat; do
            echo "   - $nat"
        done
    else
        print_warning "No NAT Gateways found (may be needed for private subnet resources)"
    fi
else
    print_warning "Cannot check NAT Gateways"
fi

# Test 5: Security Group Permissions
echo -e "\n${BLUE}5. Security Group Permission Tests${NC}"
echo "----------------------------------------"

# Try to create a test security group
TEST_SG_NAME="test-bond-ai-sg-$$"
TEST_SG=$(aws ec2 create-security-group --group-name $TEST_SG_NAME --description "Test SG for Bond AI" --vpc-id $VPC_ID --region $AWS_REGION --query 'GroupId' --output text 2>&1)
if [ $? -eq 0 ]; then
    print_result 0 "Can create security groups in VPC (ID: $TEST_SG)"
    
    # Test adding rules
    aws ec2 authorize-security-group-ingress --group-id $TEST_SG --protocol tcp --port 5432 --source-group $TEST_SG --region $AWS_REGION 2>&1 > /dev/null
    if [ $? -eq 0 ]; then
        print_result 0 "Can add security group rules"
    else
        print_result 1 "Cannot add security group rules"
    fi
    
    # Clean up
    aws ec2 delete-security-group --group-id $TEST_SG --region $AWS_REGION 2>&1 > /dev/null
else
    print_result 1 "Cannot create security groups in VPC"
    echo "   Error: $TEST_SG"
fi

# Test 6: RDS Subnet Group
echo -e "\n${BLUE}6. RDS Subnet Group Tests${NC}"
echo "----------------------------------------"

# Check if we can create RDS subnet groups
if [ $SUBNET_COUNT -ge 2 ]; then
    TEST_SUBNET_GROUP="test-bond-ai-subnet-group-$$"
    
    # Get first two subnet IDs
    SUBNET_ID_1=$(echo "$SUBNETS" | jq -r '.[0][0]')
    SUBNET_ID_2=$(echo "$SUBNETS" | jq -r '.[1][0]')
    
    CREATE_SUBNET_GROUP=$(aws rds create-db-subnet-group \
        --db-subnet-group-name $TEST_SUBNET_GROUP \
        --db-subnet-group-description "Test subnet group for Bond AI" \
        --subnet-ids $SUBNET_ID_1 $SUBNET_ID_2 \
        --region $AWS_REGION 2>&1)
    
    if [ $? -eq 0 ]; then
        print_result 0 "Can create RDS subnet groups"
        # Clean up
        aws rds delete-db-subnet-group --db-subnet-group-name $TEST_SUBNET_GROUP --region $AWS_REGION 2>&1 > /dev/null
    else
        print_result 1 "Cannot create RDS subnet groups"
        echo "   Error: $CREATE_SUBNET_GROUP"
    fi
else
    print_warning "Skipping RDS subnet group test (insufficient subnets)"
fi

# Test 7: Route Tables
echo -e "\n${BLUE}7. Route Table Tests${NC}"
echo "----------------------------------------"

ROUTE_TABLES=$(aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$VPC_ID" --region $AWS_REGION --query 'RouteTables[*].RouteTableId' --output json 2>&1)
if [ $? -eq 0 ]; then
    RT_COUNT=$(echo "$ROUTE_TABLES" | jq 'length')
    print_result 0 "Found $RT_COUNT route table(s) in VPC"
    echo "$ROUTE_TABLES" | jq -r '.[]' | while read rt; do
        echo "   - $rt"
    done
else
    print_result 1 "Cannot access route tables"
fi

# Test 8: App Runner VPC Connector capability
echo -e "\n${BLUE}8. App Runner VPC Connector Tests${NC}"
echo "----------------------------------------"

# Check if we can create VPC connectors
VPC_CONNECTOR_TEST=$(aws apprunner list-vpc-connectors --region $AWS_REGION 2>&1)
if [ $? -eq 0 ]; then
    print_result 0 "App Runner VPC connector API is accessible"
    
    # Check if any connectors exist for this VPC
    # Note: We can't easily test creation without actually creating one
    print_warning "Cannot test VPC connector creation without creating actual resources"
else
    print_result 1 "Cannot access App Runner VPC connector API"
fi

# Test 9: Check for existing RDS instances in VPC
echo -e "\n${BLUE}9. Existing Resources Check${NC}"
echo "----------------------------------------"

# Check for existing RDS instances
RDS_INSTANCES=$(aws rds describe-db-instances --region $AWS_REGION --query "DBInstances[?DBSubnetGroup.VpcId=='$VPC_ID'].DBInstanceIdentifier" --output json 2>&1)
if [ $? -eq 0 ]; then
    RDS_COUNT=$(echo "$RDS_INSTANCES" | jq 'length')
    if [ $RDS_COUNT -gt 0 ]; then
        print_warning "Found $RDS_COUNT existing RDS instance(s) in VPC"
        echo "$RDS_INSTANCES" | jq -r '.[]' | while read instance; do
            echo "   - $instance"
        done
    else
        print_result 0 "No existing RDS instances in VPC (clean slate)"
    fi
fi

# Check for existing security groups
EXISTING_SGS=$(aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$VPC_ID" --region $AWS_REGION --query 'SecurityGroups[?GroupName!=`default`].[GroupId,GroupName]' --output json 2>&1)
if [ $? -eq 0 ]; then
    SG_COUNT=$(echo "$EXISTING_SGS" | jq 'length')
    echo "   Found $SG_COUNT non-default security group(s) in VPC"
    if [ $SG_COUNT -gt 0 ]; then
        echo "$EXISTING_SGS" | jq -r '.[] | "   - \(.[0]): \(.[1])"'
    fi
fi

# Test 10: VPC Endpoint Support
echo -e "\n${BLUE}10. VPC Endpoint Tests${NC}"
echo "----------------------------------------"

# Check if VPC endpoints can be created
VPC_ENDPOINTS=$(aws ec2 describe-vpc-endpoints --filters "Name=vpc-id,Values=$VPC_ID" --region $AWS_REGION --query 'VpcEndpoints[*].[VpcEndpointId,ServiceName]' --output json 2>&1)
if [ $? -eq 0 ]; then
    ENDPOINT_COUNT=$(echo "$VPC_ENDPOINTS" | jq 'length')
    if [ $ENDPOINT_COUNT -gt 0 ]; then
        print_result 0 "Found $ENDPOINT_COUNT existing VPC endpoint(s)"
        echo "$VPC_ENDPOINTS" | jq -r '.[] | "   - \(.[0]): \(.[1])"'
    else
        print_result 0 "VPC endpoints accessible (none currently exist)"
    fi
else
    print_warning "Cannot check VPC endpoints"
fi

# Summary
echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo -e "Warnings: ${YELLOW}$WARNINGS${NC}"
echo ""

# Deployment Recommendation
echo -e "${BLUE}Deployment Recommendation:${NC}"
echo "----------------------------------------"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ VPC is SUITABLE for Bond AI deployment${NC}"
    echo ""
    echo "This VPC can be used with the following Terraform configuration:"
    echo ""
    echo "  data \"aws_vpc\" \"existing\" {"
    echo "    id = \"$VPC_ID\""
    echo "  }"
    echo ""
    echo "  data \"aws_subnets\" \"existing\" {"
    echo "    filter {"
    echo "      name   = \"vpc-id\""
    echo "      values = [data.aws_vpc.existing.id]"
    echo "    }"
    echo "  }"
    echo ""
    echo "Next steps:"
    echo "1. Update terraform configuration to use this existing VPC"
    echo "2. Configure RDS to use subnets from this VPC"
    echo "3. Create security groups in this VPC"
    echo "4. Configure App Runner VPC connector to use this VPC"
elif [ $TESTS_FAILED -le 2 ]; then
    echo -e "${YELLOW}⚠ VPC is POSSIBLY SUITABLE with modifications${NC}"
    echo ""
    echo "Issues to address:"
    if [ $SUBNET_COUNT -lt 2 ]; then
        echo "- Need to create additional subnets in different AZs"
    fi
    if [ "$IGW" == "None" ]; then
        echo "- Need to attach an Internet Gateway"
    fi
    echo ""
    echo "Consult with your AWS administrator to resolve these issues."
else
    echo -e "${RED}✗ VPC is NOT SUITABLE for Bond AI deployment${NC}"
    echo ""
    echo "Critical issues found:"
    echo "- Multiple infrastructure components missing or inaccessible"
    echo "- Consider requesting a properly configured VPC from your AWS administrator"
fi

echo ""
echo "Report generated: $(date)"
echo "VPC tested: $VPC_NAME ($VPC_ID) in region $AWS_REGION"