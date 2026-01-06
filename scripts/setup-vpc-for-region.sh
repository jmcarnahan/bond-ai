#!/bin/bash

# setup-vpc-for-region.sh
# Creates a complete VPC in any specified AWS region for Bond AI deployment
# Usage: ./setup-vpc-for-region.sh [region]
# Example: ./setup-vpc-for-region.sh us-west-2

set -e

# Get region from command line argument or environment variable
if [ -n "$1" ]; then
    AWS_REGION="$1"
elif [ -n "$AWS_REGION" ]; then
    AWS_REGION="$AWS_REGION"
else
    echo "Error: AWS region not specified"
    echo "Usage: $0 <aws-region>"
    echo "Example: $0 us-west-2"
    echo "Or set AWS_REGION environment variable"
    exit 1
fi

# Configuration
VPC_CIDR="10.0.0.0/16"
PROJECT_NAME="bond-ai"
ENVIRONMENT="dev"
TIMESTAMP=$(date +%Y%m%d%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Verify AWS CLI is configured
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo -e "${RED}Error: AWS CLI is not configured or credentials are invalid${NC}"
    exit 1
fi

# Verify region is valid
if ! aws ec2 describe-regions --region-names $AWS_REGION > /dev/null 2>&1; then
    echo -e "${RED}Error: Invalid AWS region: $AWS_REGION${NC}"
    exit 1
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Bond AI VPC Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}This script will create in region ${GREEN}$AWS_REGION${YELLOW}:${NC}"
echo "  - VPC with CIDR ${VPC_CIDR}"
echo "  - 2 private subnets in different AZs (for RDS)"
echo "  - 2 public subnets (for NAT Gateways)"
echo "  - Internet Gateway"
echo "  - NAT Gateways (one per AZ for high availability)"
echo "  - Route tables and associations"
echo "  - Security group for VPC endpoints"
echo ""
echo -e "${YELLOW}Region: ${GREEN}$AWS_REGION${NC}"
echo -e "${YELLOW}Account: $(aws sts get-caller-identity --query Account --output text)${NC}"
echo ""

# Confirm before proceeding
read -p "Do you want to proceed? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo -e "${RED}Setup cancelled.${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}Starting VPC setup in $AWS_REGION...${NC}"

# Create VPC
echo -e "${BLUE}Creating VPC...${NC}"
VPC_ID=$(aws ec2 create-vpc \
    --cidr-block $VPC_CIDR \
    --region $AWS_REGION \
    --tag-specifications "ResourceType=vpc,Tags=[{Key=Name,Value=${PROJECT_NAME}-${ENVIRONMENT}-vpc},{Key=Project,Value=${PROJECT_NAME}},{Key=Environment,Value=${ENVIRONMENT}},{Key=ManagedBy,Value=setup-script},{Key=CreatedAt,Value=${TIMESTAMP}},{Key=Region,Value=${AWS_REGION}}]" \
    --query 'Vpc.VpcId' \
    --output text)

echo "  VPC created: $VPC_ID"

# Enable DNS hostnames
aws ec2 modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-hostnames --region $AWS_REGION
aws ec2 modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-support --region $AWS_REGION
echo "  DNS hostnames and support enabled"

# Get availability zones (use first 2 available zones)
echo -e "\n${BLUE}Getting availability zones...${NC}"
AZ1=$(aws ec2 describe-availability-zones --region $AWS_REGION --filters "Name=state,Values=available" --query 'AvailabilityZones[0].ZoneName' --output text)
AZ2=$(aws ec2 describe-availability-zones --region $AWS_REGION --filters "Name=state,Values=available" --query 'AvailabilityZones[1].ZoneName' --output text)

if [ "$AZ1" == "None" ] || [ "$AZ2" == "None" ]; then
    echo -e "${RED}Error: Unable to find at least 2 availability zones in $AWS_REGION${NC}"
    # Clean up VPC
    aws ec2 delete-vpc --vpc-id $VPC_ID --region $AWS_REGION 2>/dev/null
    exit 1
fi

echo "  Using AZs: $AZ1, $AZ2"

# Create Internet Gateway
echo -e "\n${BLUE}Creating Internet Gateway...${NC}"
IGW_ID=$(aws ec2 create-internet-gateway \
    --region $AWS_REGION \
    --tag-specifications "ResourceType=internet-gateway,Tags=[{Key=Name,Value=${PROJECT_NAME}-${ENVIRONMENT}-igw},{Key=Project,Value=${PROJECT_NAME}},{Key=Environment,Value=${ENVIRONMENT}}]" \
    --query 'InternetGateway.InternetGatewayId' \
    --output text)

aws ec2 attach-internet-gateway --vpc-id $VPC_ID --internet-gateway-id $IGW_ID --region $AWS_REGION
echo "  Internet Gateway created and attached: $IGW_ID"

# Create subnets
echo -e "\n${BLUE}Creating subnets...${NC}"

# Public subnet 1 (for NAT Gateway)
PUBLIC_SUBNET_1=$(aws ec2 create-subnet \
    --vpc-id $VPC_ID \
    --cidr-block "10.0.1.0/24" \
    --availability-zone $AZ1 \
    --region $AWS_REGION \
    --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=${PROJECT_NAME}-${ENVIRONMENT}-public-1},{Key=Type,Value=public},{Key=Project,Value=${PROJECT_NAME}},{Key=Environment,Value=${ENVIRONMENT}}]" \
    --query 'Subnet.SubnetId' \
    --output text)
echo "  Public subnet 1 created: $PUBLIC_SUBNET_1 (10.0.1.0/24) in $AZ1"

# Public subnet 2 (for NAT Gateway)
PUBLIC_SUBNET_2=$(aws ec2 create-subnet \
    --vpc-id $VPC_ID \
    --cidr-block "10.0.2.0/24" \
    --availability-zone $AZ2 \
    --region $AWS_REGION \
    --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=${PROJECT_NAME}-${ENVIRONMENT}-public-2},{Key=Type,Value=public},{Key=Project,Value=${PROJECT_NAME}},{Key=Environment,Value=${ENVIRONMENT}}]" \
    --query 'Subnet.SubnetId' \
    --output text)
echo "  Public subnet 2 created: $PUBLIC_SUBNET_2 (10.0.2.0/24) in $AZ2"

# Private subnet 1 (for RDS and App Runner)
PRIVATE_SUBNET_1=$(aws ec2 create-subnet \
    --vpc-id $VPC_ID \
    --cidr-block "10.0.10.0/24" \
    --availability-zone $AZ1 \
    --region $AWS_REGION \
    --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=${PROJECT_NAME}-${ENVIRONMENT}-private-1},{Key=Type,Value=private},{Key=Project,Value=${PROJECT_NAME}},{Key=Environment,Value=${ENVIRONMENT}}]" \
    --query 'Subnet.SubnetId' \
    --output text)
echo "  Private subnet 1 created: $PRIVATE_SUBNET_1 (10.0.10.0/24) in $AZ1"

# Private subnet 2 (for RDS and App Runner)
PRIVATE_SUBNET_2=$(aws ec2 create-subnet \
    --vpc-id $VPC_ID \
    --cidr-block "10.0.11.0/24" \
    --availability-zone $AZ2 \
    --region $AWS_REGION \
    --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=${PROJECT_NAME}-${ENVIRONMENT}-private-2},{Key=Type,Value=private},{Key=Project,Value=${PROJECT_NAME}},{Key=Environment,Value=${ENVIRONMENT}}]" \
    --query 'Subnet.SubnetId' \
    --output text)
echo "  Private subnet 2 created: $PRIVATE_SUBNET_2 (10.0.11.0/24) in $AZ2"

# Enable auto-assign public IP for public subnets
aws ec2 modify-subnet-attribute --subnet-id $PUBLIC_SUBNET_1 --map-public-ip-on-launch --region $AWS_REGION
aws ec2 modify-subnet-attribute --subnet-id $PUBLIC_SUBNET_2 --map-public-ip-on-launch --region $AWS_REGION
echo "  Auto-assign public IP enabled for public subnets"

# Create Elastic IPs for NAT Gateways
echo -e "\n${BLUE}Creating Elastic IPs for NAT Gateways...${NC}"
EIP_1=$(aws ec2 allocate-address --domain vpc --region $AWS_REGION --query 'AllocationId' --output text)
EIP_2=$(aws ec2 allocate-address --domain vpc --region $AWS_REGION --query 'AllocationId' --output text)
echo "  Elastic IPs allocated: $EIP_1, $EIP_2"

# Create NAT Gateways
echo -e "\n${BLUE}Creating NAT Gateways...${NC}"
NAT_GW_1=$(aws ec2 create-nat-gateway \
    --subnet-id $PUBLIC_SUBNET_1 \
    --allocation-id $EIP_1 \
    --region $AWS_REGION \
    --query 'NatGateway.NatGatewayId' \
    --output text)
echo "  NAT Gateway 1 created: $NAT_GW_1"

# Tag NAT Gateway 1 after creation
aws ec2 create-tags --resources $NAT_GW_1 --tags "Key=Name,Value=${PROJECT_NAME}-${ENVIRONMENT}-nat-1" "Key=Project,Value=${PROJECT_NAME}" "Key=Environment,Value=${ENVIRONMENT}" --region $AWS_REGION

NAT_GW_2=$(aws ec2 create-nat-gateway \
    --subnet-id $PUBLIC_SUBNET_2 \
    --allocation-id $EIP_2 \
    --region $AWS_REGION \
    --query 'NatGateway.NatGatewayId' \
    --output text)
echo "  NAT Gateway 2 created: $NAT_GW_2"

# Tag NAT Gateway 2 after creation
aws ec2 create-tags --resources $NAT_GW_2 --tags "Key=Name,Value=${PROJECT_NAME}-${ENVIRONMENT}-nat-2" "Key=Project,Value=${PROJECT_NAME}" "Key=Environment,Value=${ENVIRONMENT}" --region $AWS_REGION

# Wait for NAT Gateways to be available
echo -e "\n${YELLOW}Waiting for NAT Gateways to become available (this may take 2-3 minutes)...${NC}"
aws ec2 wait nat-gateway-available --nat-gateway-ids $NAT_GW_1 --region $AWS_REGION
aws ec2 wait nat-gateway-available --nat-gateway-ids $NAT_GW_2 --region $AWS_REGION
echo -e "${GREEN}NAT Gateways are available${NC}"

# Create route tables
echo -e "\n${BLUE}Creating route tables...${NC}"

# Public route table
PUBLIC_RT=$(aws ec2 create-route-table \
    --vpc-id $VPC_ID \
    --region $AWS_REGION \
    --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=${PROJECT_NAME}-${ENVIRONMENT}-public-rt},{Key=Type,Value=public},{Key=Project,Value=${PROJECT_NAME}},{Key=Environment,Value=${ENVIRONMENT}}]" \
    --query 'RouteTable.RouteTableId' \
    --output text)
echo "  Public route table created: $PUBLIC_RT"

# Add route to Internet Gateway
aws ec2 create-route \
    --route-table-id $PUBLIC_RT \
    --destination-cidr-block 0.0.0.0/0 \
    --gateway-id $IGW_ID \
    --region $AWS_REGION > /dev/null
echo "  Route to Internet Gateway added"

# Private route table 1
PRIVATE_RT_1=$(aws ec2 create-route-table \
    --vpc-id $VPC_ID \
    --region $AWS_REGION \
    --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=${PROJECT_NAME}-${ENVIRONMENT}-private-rt-1},{Key=Type,Value=private},{Key=Project,Value=${PROJECT_NAME}},{Key=Environment,Value=${ENVIRONMENT}}]" \
    --query 'RouteTable.RouteTableId' \
    --output text)
echo "  Private route table 1 created: $PRIVATE_RT_1"

# Add route to NAT Gateway 1
aws ec2 create-route \
    --route-table-id $PRIVATE_RT_1 \
    --destination-cidr-block 0.0.0.0/0 \
    --nat-gateway-id $NAT_GW_1 \
    --region $AWS_REGION > /dev/null
echo "  Route to NAT Gateway 1 added"

# Private route table 2
PRIVATE_RT_2=$(aws ec2 create-route-table \
    --vpc-id $VPC_ID \
    --region $AWS_REGION \
    --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=${PROJECT_NAME}-${ENVIRONMENT}-private-rt-2},{Key=Type,Value=private},{Key=Project,Value=${PROJECT_NAME}},{Key=Environment,Value=${ENVIRONMENT}}]" \
    --query 'RouteTable.RouteTableId' \
    --output text)
echo "  Private route table 2 created: $PRIVATE_RT_2"

# Add route to NAT Gateway 2
aws ec2 create-route \
    --route-table-id $PRIVATE_RT_2 \
    --destination-cidr-block 0.0.0.0/0 \
    --nat-gateway-id $NAT_GW_2 \
    --region $AWS_REGION > /dev/null
echo "  Route to NAT Gateway 2 added"

# Associate route tables with subnets
echo -e "\n${BLUE}Associating route tables with subnets...${NC}"
aws ec2 associate-route-table --subnet-id $PUBLIC_SUBNET_1 --route-table-id $PUBLIC_RT --region $AWS_REGION > /dev/null
aws ec2 associate-route-table --subnet-id $PUBLIC_SUBNET_2 --route-table-id $PUBLIC_RT --region $AWS_REGION > /dev/null
aws ec2 associate-route-table --subnet-id $PRIVATE_SUBNET_1 --route-table-id $PRIVATE_RT_1 --region $AWS_REGION > /dev/null
aws ec2 associate-route-table --subnet-id $PRIVATE_SUBNET_2 --route-table-id $PRIVATE_RT_2 --region $AWS_REGION > /dev/null
echo "  Route tables associated"

# Create security group for VPC endpoints (optional but recommended)
echo -e "\n${BLUE}Creating security group for VPC endpoints...${NC}"
SG_ID=$(aws ec2 create-security-group \
    --group-name "${PROJECT_NAME}-${ENVIRONMENT}-vpc-endpoints" \
    --description "Security group for VPC endpoints" \
    --vpc-id $VPC_ID \
    --region $AWS_REGION \
    --tag-specifications "ResourceType=security-group,Tags=[{Key=Name,Value=${PROJECT_NAME}-${ENVIRONMENT}-vpc-endpoints},{Key=Project,Value=${PROJECT_NAME}},{Key=Environment,Value=${ENVIRONMENT}}]" \
    --query 'GroupId' \
    --output text)

# Add rule to allow HTTPS traffic from VPC
aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 443 \
    --cidr $VPC_CIDR \
    --region $AWS_REGION > /dev/null
echo "  Security group created: $SG_ID"

# Output summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}VPC Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}VPC Details:${NC}"
echo "  VPC ID: ${GREEN}$VPC_ID${NC}"
echo "  VPC CIDR: $VPC_CIDR"
echo "  Region: ${GREEN}$AWS_REGION${NC}"
echo ""
echo -e "${BLUE}Subnets:${NC}"
echo "  Public Subnet 1:  $PUBLIC_SUBNET_1 (10.0.1.0/24) - $AZ1"
echo "  Public Subnet 2:  $PUBLIC_SUBNET_2 (10.0.2.0/24) - $AZ2"
echo "  Private Subnet 1: $PRIVATE_SUBNET_1 (10.0.10.0/24) - $AZ1"
echo "  Private Subnet 2: $PRIVATE_SUBNET_2 (10.0.11.0/24) - $AZ2"
echo ""
echo -e "${BLUE}NAT Gateways:${NC}"
echo "  NAT Gateway 1: $NAT_GW_1"
echo "  NAT Gateway 2: $NAT_GW_2"
echo ""
echo -e "${BLUE}Route Tables:${NC}"
echo "  Public:  $PUBLIC_RT"
echo "  Private 1: $PRIVATE_RT_1"
echo "  Private 2: $PRIVATE_RT_2"
echo ""

# Save configuration to file
CONFIG_FILE="vpc-config-${AWS_REGION}-${TIMESTAMP}.txt"
cat > $CONFIG_FILE <<EOF
# VPC Configuration for Bond AI
# Created: $(date)
# Region: $AWS_REGION

VPC_ID=$VPC_ID
VPC_CIDR=$VPC_CIDR
AWS_REGION=$AWS_REGION

# Subnets
PUBLIC_SUBNET_1=$PUBLIC_SUBNET_1
PUBLIC_SUBNET_2=$PUBLIC_SUBNET_2
PRIVATE_SUBNET_1=$PRIVATE_SUBNET_1
PRIVATE_SUBNET_2=$PRIVATE_SUBNET_2

# NAT Gateways
NAT_GW_1=$NAT_GW_1
NAT_GW_2=$NAT_GW_2

# Route Tables
PUBLIC_RT=$PUBLIC_RT
PRIVATE_RT_1=$PRIVATE_RT_1
PRIVATE_RT_2=$PRIVATE_RT_2

# Other Resources
IGW_ID=$IGW_ID
SG_ID=$SG_ID
EIP_1=$EIP_1
EIP_2=$EIP_2
EOF

echo -e "${GREEN}Configuration saved to: $CONFIG_FILE${NC}"
echo ""
echo -e "${YELLOW}IMPORTANT: Save the VPC ID for your terraform configuration:${NC}"
echo -e "${GREEN}$VPC_ID${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Run the verification script:"
echo "   ${GREEN}VPC_ID=$VPC_ID AWS_REGION=$AWS_REGION ./deployment/test-vpc-availability.sh${NC}"
echo ""
echo "2. Update terraform configuration:"
echo "   Edit terraform-existing-vpc/environments/${AWS_REGION}-existing-vpc.tfvars"
echo "   Set: existing_vpc_id = \"$VPC_ID\""
echo "   Set: aws_region = \"$AWS_REGION\""
echo ""
echo "3. To delete this VPC later:"
echo "   ${GREEN}./deployment/cleanup-vpc-for-region.sh $VPC_ID $AWS_REGION${NC}"
echo ""
