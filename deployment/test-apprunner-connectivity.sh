#!/bin/bash

# Enhanced App Runner VPC Connectivity Diagnostic Script
# Focuses on specific subnets and networking paths that App Runner uses
# Usage: ./test-apprunner-connectivity.sh

set -e

# Configuration
VPC_ID="${VPC_ID:-vpc-08acfe7cf84c026c7}"
AWS_REGION="${AWS_REGION:-us-west-2}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Specific subnets our Terraform selects as "truly private"
TERRAFORM_SELECTED_SUBNETS=(
    "subnet-0374d7b91b2054239"
    "subnet-0584def4d6ffbe9a5"
    "subnet-014b5d076741106ff"
    "subnet-0b8e4e5c74e60d524"
    "subnet-0dfffe14f39009eeb"
    "subnet-0917dfc1af7e6f812"
    "subnet-050691e25d4a7681e"
    "subnet-02085799b52b1e750"
)

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Test counters
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

print_info() {
    echo -e "${BLUE}ℹ${NC}  $1"
}

print_section() {
    echo -e "\n${PURPLE}========================================${NC}"
    echo -e "${PURPLE}$1${NC}"
    echo -e "${PURPLE}========================================${NC}"
}

print_subsection() {
    echo -e "\n${BLUE}$1${NC}"
    echo "----------------------------------------"
}

# Get VPC details
get_vpc_details() {
    VPC_INFO=$(aws ec2 describe-vpcs --vpc-ids $VPC_ID --region $AWS_REGION 2>&1)
    if [ $? -eq 0 ]; then
        VPC_CIDR=$(echo "$VPC_INFO" | jq -r '.Vpcs[0].CidrBlock')
        VPC_NAME=$(aws ec2 describe-tags --filters "Name=resource-id,Values=$VPC_ID" "Name=key,Values=Name" --region $AWS_REGION --query 'Tags[0].Value' --output text 2>/dev/null || echo "unnamed")
    else
        echo -e "${RED}Error: Cannot access VPC $VPC_ID${NC}"
        exit 1
    fi
}

print_section "App Runner VPC Connectivity Diagnostics"
echo ""
echo "Target VPC: $VPC_ID"
echo "AWS Region: $AWS_REGION"
echo "AWS Account: $AWS_ACCOUNT_ID"

get_vpc_details
echo "VPC CIDR: $VPC_CIDR"
echo "VPC Name: $VPC_NAME"
echo ""
echo "Testing $(echo ${TERRAFORM_SELECTED_SUBNETS[@]} | wc -w) Terraform-selected subnets"

# Phase 1: Validate Subnet Selection Logic
print_section "Phase 1: Subnet Selection Logic Validation"

print_subsection "1.1 Verify Subnets Don't Have Direct IGW Routes"

for subnet in "${TERRAFORM_SELECTED_SUBNETS[@]}"; do
    echo "Testing subnet: $subnet"

    # Check if subnet exists
    SUBNET_INFO=$(aws ec2 describe-subnets --subnet-ids $subnet --region $AWS_REGION 2>&1)
    if [ $? -ne 0 ]; then
        print_result 1 "Subnet $subnet does not exist or is not accessible"
        continue
    fi

    # Get subnet details
    AZ=$(echo "$SUBNET_INFO" | jq -r '.Subnets[0].AvailabilityZone')
    SUBNET_CIDR=$(echo "$SUBNET_INFO" | jq -r '.Subnets[0].CidrBlock')
    MAP_PUBLIC_IP=$(echo "$SUBNET_INFO" | jq -r '.Subnets[0].MapPublicIpOnLaunch')

    print_info "  AZ: $AZ, CIDR: $SUBNET_CIDR, MapPublicIP: $MAP_PUBLIC_IP"

    # Check route table for direct IGW routes
    ROUTE_TABLES=$(aws ec2 describe-route-tables --filters "Name=association.subnet-id,Values=$subnet" --region $AWS_REGION --query 'RouteTables[0].Routes[?GatewayId && starts_with(GatewayId, `igw`)].[DestinationCidrBlock,GatewayId]' --output json 2>/dev/null)

    if [ $? -eq 0 ]; then
        IGW_ROUTES=$(echo "$ROUTE_TABLES" | jq 'length')
        if [ "$IGW_ROUTES" -gt 0 ]; then
            print_result 1 "  Has direct IGW routes (should be filtered out!)"
            echo "$ROUTE_TABLES" | jq -r '.[] | "    - \(.[0]) -> \(.[1])"'
        else
            print_result 0 "  No direct IGW routes (correctly filtered)"
        fi
    else
        print_warning "  Could not check route table for $subnet"
    fi

    # Check for NAT Gateway routes
    NAT_ROUTES=$(aws ec2 describe-route-tables --filters "Name=association.subnet-id,Values=$subnet" --region $AWS_REGION --query 'RouteTables[0].Routes[?GatewayId && starts_with(GatewayId, `nat`)].[DestinationCidrBlock,GatewayId]' --output json 2>/dev/null)

    if [ $? -eq 0 ]; then
        NAT_ROUTE_COUNT=$(echo "$NAT_ROUTES" | jq 'length')
        if [ "$NAT_ROUTE_COUNT" -gt 0 ]; then
            print_result 0 "  Has NAT Gateway routes (good for App Runner)"
            echo "$NAT_ROUTES" | jq -r '.[] | "    - \(.[0]) -> \(.[1])"'
        else
            print_result 1 "  No NAT Gateway routes found (App Runner needs internet access)"
        fi
    fi
    echo ""
done

print_subsection "1.2 Test NAT Gateway Connectivity"

# Test if we can reach the internet through NAT gateways
print_info "Testing internet connectivity through NAT Gateways..."

# Get NAT Gateways in the VPC
NAT_GWS=$(aws ec2 describe-nat-gateways --filter "Name=vpc-id,Values=$VPC_ID" "Name=state,Values=available" --region $AWS_REGION --query 'NatGateways[*].[NatGatewayId,SubnetId,State]' --output json)

if [ $? -eq 0 ]; then
    NAT_COUNT=$(echo "$NAT_GWS" | jq 'length')
    print_info "Found $NAT_COUNT NAT Gateway(s) in VPC"

    if [ $NAT_COUNT -gt 0 ]; then
        echo "$NAT_GWS" | jq -r '.[] | "  - \(.[0]) in \(.[1]) (\(.[2]))"'
        print_result 0 "NAT Gateways are available"
    else
        print_result 1 "No NAT Gateways found - App Runner needs internet access"
    fi
else
    print_warning "Could not check NAT Gateways"
fi

# Phase 2: Network ACLs Check
print_section "Phase 2: Network Access Control Lists (NACLs)"

print_subsection "2.1 Check NACLs on Selected Subnets"

for subnet in "${TERRAFORM_SELECTED_SUBNETS[@]}"; do
    echo "Checking NACLs for subnet: $subnet"

    # Get NACL associated with subnet
    NACL_ASSOC=$(aws ec2 describe-network-acls --filters "Name=association.subnet-id,Values=$subnet" --region $AWS_REGION --query 'NetworkAcls[0].[NetworkAclId,IsDefault]' --output json 2>/dev/null)

    if [ $? -eq 0 ]; then
        NACL_ID=$(echo "$NACL_ASSOC" | jq -r '.[0]')
        IS_DEFAULT=$(echo "$NACL_ASSOC" | jq -r '.[1]')

        print_info "  NACL: $NACL_ID (default: $IS_DEFAULT)"

        if [ "$IS_DEFAULT" == "true" ]; then
            print_result 0 "  Using default NACL (usually permissive)"
        else
            print_warning "  Using custom NACL - checking rules..."

            # Check for rules that might block HTTP traffic on port 8000
            NACL_RULES=$(aws ec2 describe-network-acls --network-acl-ids $NACL_ID --region $AWS_REGION --query 'NetworkAcls[0].Entries[?RuleAction==`deny` && (PortRange.From<=`8000` && PortRange.To>=`8000`)].[RuleNumber,Protocol,RuleAction,PortRange,CidrBlock]' --output json 2>/dev/null)

            if [ $? -eq 0 ]; then
                BLOCKING_RULES=$(echo "$NACL_RULES" | jq 'length')
                if [ $BLOCKING_RULES -gt 0 ]; then
                    print_result 1 "  Found DENY rules that might block port 8000"
                    echo "$NACL_RULES" | jq -r '.[] | "    Rule \(.[0]): \(.[1]) \(.[2]) \(.[3]) \(.[4])"'
                else
                    print_result 0 "  No obvious blocking rules for port 8000"
                fi
            fi
        fi
    else
        print_warning "  Could not check NACL for $subnet"
    fi
    echo ""
done

# Phase 3: Security Group Validation
print_section "Phase 3: Security Group Deep Testing"

print_subsection "3.1 Analyze Current App Runner Security Group"

# Find our App Runner security group
APP_RUNNER_SG=$(aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$VPC_ID" "Name=description,Values=*App Runner*" --region $AWS_REGION --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null)

if [ "$APP_RUNNER_SG" != "None" ] && [ ! -z "$APP_RUNNER_SG" ]; then
    print_result 0 "Found App Runner security group: $APP_RUNNER_SG"

    # Check ingress rules
    INGRESS_RULES=$(aws ec2 describe-security-groups --group-ids $APP_RUNNER_SG --region $AWS_REGION --query 'SecurityGroups[0].IpPermissions[?FromPort==`8000`].[FromPort,ToPort,IpProtocol,IpRanges[0].CidrIp]' --output json 2>/dev/null)

    if [ $? -eq 0 ]; then
        INGRESS_COUNT=$(echo "$INGRESS_RULES" | jq 'length')
        if [ $INGRESS_COUNT -gt 0 ]; then
            print_result 0 "Found ingress rules for port 8000"
            echo "$INGRESS_RULES" | jq -r '.[] | "  Port \(.[0])-\(.[1]) \(.[2]) from \(.[3])"'

            # Verify the CIDR matches our VPC
            RULE_CIDR=$(echo "$INGRESS_RULES" | jq -r '.[0][3]')
            if [ "$RULE_CIDR" == "$VPC_CIDR" ]; then
                print_result 0 "CIDR matches VPC CIDR ($VPC_CIDR)"
            else
                print_warning "CIDR mismatch: rule has $RULE_CIDR, VPC has $VPC_CIDR"
            fi
        else
            print_result 1 "No ingress rules found for port 8000"
        fi
    fi

    # Check egress rules
    EGRESS_RULES=$(aws ec2 describe-security-groups --group-ids $APP_RUNNER_SG --region $AWS_REGION --query 'SecurityGroups[0].IpPermissionsEgress' --output json 2>/dev/null)
    EGRESS_COUNT=$(echo "$EGRESS_RULES" | jq 'length')
    print_info "Found $EGRESS_COUNT egress rule(s)"

else
    print_result 1 "Could not find App Runner security group"
fi

print_subsection "3.2 Test Security Group Rules in Practice"

# Create a test security group to validate our understanding
TEST_SG_NAME="test-apprunner-connectivity-$$"
print_info "Creating test security group: $TEST_SG_NAME"

TEST_SG=$(aws ec2 create-security-group --group-name $TEST_SG_NAME --description "Test SG for App Runner connectivity debugging" --vpc-id $VPC_ID --region $AWS_REGION --query 'GroupId' --output text 2>&1)

if [ $? -eq 0 ]; then
    print_result 0 "Created test security group: $TEST_SG"

    # Add the same ingress rule we have for App Runner
    aws ec2 authorize-security-group-ingress --group-id $TEST_SG --protocol tcp --port 8000 --cidr $VPC_CIDR --region $AWS_REGION 2>&1 > /dev/null
    if [ $? -eq 0 ]; then
        print_result 0 "Successfully added ingress rule for port 8000"
    else
        print_result 1 "Failed to add ingress rule"
    fi

    # Clean up test security group
    aws ec2 delete-security-group --group-id $TEST_SG --region $AWS_REGION 2>&1 > /dev/null
    print_info "Cleaned up test security group"
else
    print_result 1 "Could not create test security group"
fi

# Phase 4: DNS Resolution Testing
print_section "Phase 4: DNS Resolution Testing"

print_subsection "4.1 VPC DNS Configuration"

# Check VPC DNS attributes
DNS_SUPPORT=$(aws ec2 describe-vpc-attribute --vpc-id $VPC_ID --attribute enableDnsSupport --region $AWS_REGION --query 'EnableDnsSupport.Value' --output text 2>/dev/null)
DNS_HOSTNAMES=$(aws ec2 describe-vpc-attribute --vpc-id $VPC_ID --attribute enableDnsHostnames --region $AWS_REGION --query 'EnableDnsHostnames.Value' --output text 2>/dev/null)

if [ "$DNS_SUPPORT" == "true" ] && [ "$DNS_HOSTNAMES" == "true" ]; then
    print_result 0 "VPC DNS configuration is correct (Support: $DNS_SUPPORT, Hostnames: $DNS_HOSTNAMES)"
else
    print_result 1 "VPC DNS configuration issue (Support: $DNS_SUPPORT, Hostnames: $DNS_HOSTNAMES)"
fi

# Phase 5: Detailed Route Analysis
print_section "Phase 5: Route Table Deep Analysis"

print_subsection "5.1 Analyze Routes for Each Selected Subnet"

for subnet in "${TERRAFORM_SELECTED_SUBNETS[@]}"; do
    echo "Analyzing routes for subnet: $subnet"

    # Get all route tables associated with this subnet
    ROUTE_TABLE_ID=$(aws ec2 describe-route-tables --filters "Name=association.subnet-id,Values=$subnet" --region $AWS_REGION --query 'RouteTables[0].RouteTableId' --output text 2>/dev/null)

    if [ "$ROUTE_TABLE_ID" != "None" ] && [ ! -z "$ROUTE_TABLE_ID" ]; then
        print_info "  Route Table: $ROUTE_TABLE_ID"

        # Get all routes
        ALL_ROUTES=$(aws ec2 describe-route-tables --route-table-ids $ROUTE_TABLE_ID --region $AWS_REGION --query 'RouteTables[0].Routes[].[DestinationCidrBlock,GatewayId,InstanceId,NatGatewayId,NetworkInterfaceId,VpcPeeringConnectionId,State]' --output json 2>/dev/null)

        echo "    Routes:"
        echo "$ALL_ROUTES" | jq -r '.[] | "      \(.[0]) -> \(if .[1] != null then .[1] elif .[3] != null then .[3] elif .[2] != null then .[2] elif .[4] != null then .[4] elif .[5] != null then .[5] else "local" end) (\(.[6]))"'

        # Check for default route to NAT Gateway
        DEFAULT_NAT=$(echo "$ALL_ROUTES" | jq -r '.[] | select(.[0] == "0.0.0.0/0" and .[3] != null) | .[3]')
        if [ ! -z "$DEFAULT_NAT" ] && [ "$DEFAULT_NAT" != "null" ]; then
            print_result 0 "  Has default route through NAT Gateway: $DEFAULT_NAT"
        else
            print_result 1 "  Missing default route through NAT Gateway"
        fi

    else
        print_warning "  Could not find route table for $subnet"
    fi
    echo ""
done

# Summary and Recommendations
print_section "Summary and Recommendations"

echo ""
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo -e "Warnings: ${YELLOW}$WARNINGS${NC}"
echo ""

if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "${RED}❌ CONNECTIVITY ISSUES FOUND${NC}"
    echo ""
    echo "Critical issues that could prevent App Runner health checks:"
    echo "- Review the failed tests above"
    echo "- Focus on routing, security groups, and NACLs"
    echo ""
    echo "Next steps:"
    echo "1. Fix any subnet routing issues (ensure NAT Gateway routes exist)"
    echo "2. Verify security group ingress rules allow port 8000 from VPC CIDR"
    echo "3. Check for custom NACLs that might block traffic"
    echo "4. Consider deploying a minimal test container to isolate the issue"
else
    echo -e "${GREEN}✅ NO OBVIOUS CONNECTIVITY ISSUES FOUND${NC}"
    echo ""
    echo "The VPC networking appears configured correctly for App Runner."
    echo "The health check failure might be due to:"
    echo "1. Application startup timing issues"
    echo "2. App Runner service configuration"
    echo "3. Container image or application code issues"
    echo ""
    echo "Next steps:"
    echo "1. Deploy a minimal test container to verify App Runner can work"
    echo "2. Check application logs for startup errors"
    echo "3. Verify the health check endpoint responds correctly"
fi

echo ""
echo "Report generated: $(date)"
echo "VPC tested: $VPC_NAME ($VPC_ID) in region $AWS_REGION"