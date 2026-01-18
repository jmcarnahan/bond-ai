#!/bin/bash
# =============================================================================
# Maintenance Mode Toggle Script
# =============================================================================
# Toggle maintenance mode for the frontend WAF. When enabled, all traffic to
# the frontend is blocked and users see a maintenance page.
#
# Usage: ./maintenance.sh [on|off|status]
#
# This is INDEPENDENT of application deployments. You can:
#   1. Enable maintenance mode (30 sec)
#   2. Deploy your app as many times as needed
#   3. Disable maintenance mode (30 sec)
#
# The WAF blocks traffic at the edge, so your app deployments don't affect it.
# =============================================================================
set -e

# Configuration (can be overridden via environment variables)
AWS_REGION="${AWS_REGION:-us-west-2}"
PROJECT_NAME="${PROJECT_NAME:-bond-ai}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
TFVARS_FILE="${TFVARS_FILE:-}"  # Required - must be set
WEB_ACL_NAME="${PROJECT_NAME}-${ENVIRONMENT}-frontend-waf"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/../terraform-existing-vpc"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

usage() {
    echo "Maintenance Mode Toggle Script"
    echo ""
    echo "Usage: TFVARS_FILE=<path> $0 [on|off|status]"
    echo ""
    echo "Commands:"
    echo "  on      Enable maintenance mode (users see maintenance page)"
    echo "  off     Disable maintenance mode (users see live app)"
    echo "  status  Check current maintenance mode status"
    echo ""
    echo "Required environment variables (for on/off):"
    echo "  TFVARS_FILE   Path to tfvars file (relative to terraform-existing-vpc/)"
    echo ""
    echo "Optional environment variables:"
    echo "  AWS_REGION    AWS region (default: us-west-2)"
    echo "  PROJECT_NAME  Project name (default: bond-ai)"
    echo "  ENVIRONMENT   Environment name (default: dev)"
    echo ""
    echo "Examples:"
    echo "  TFVARS_FILE=environments/us-west-2-existing-vpc.tfvars $0 on"
    echo "  TFVARS_FILE=environments/us-west-2-existing-vpc.tfvars $0 off"
    echo "  $0 status    # status doesn't require TFVARS_FILE"
    exit 1
}

get_waf_id() {
    aws wafv2 list-web-acls --scope REGIONAL --region "$AWS_REGION" \
        --query "WebACLs[?Name=='${WEB_ACL_NAME}'].Id" --output text 2>/dev/null
}

check_prerequisites() {
    # Check if AWS CLI is available
    if ! command -v aws &> /dev/null; then
        echo -e "${RED}Error: AWS CLI is not installed${NC}"
        exit 1
    fi

    # Check if terraform is available
    if ! command -v terraform &> /dev/null; then
        echo -e "${RED}Error: Terraform is not installed${NC}"
        exit 1
    fi

    # Check if terraform directory exists
    if [ ! -d "$TERRAFORM_DIR" ]; then
        echo -e "${RED}Error: Terraform directory not found: $TERRAFORM_DIR${NC}"
        exit 1
    fi
}

# -----------------------------------------------------------------------------
# Command Functions
# -----------------------------------------------------------------------------

check_status() {
    echo -e "${BLUE}Checking maintenance mode status...${NC}"
    echo "   WAF: ${WEB_ACL_NAME}"
    echo "   Region: ${AWS_REGION}"
    echo ""

    local WEB_ACL_ID=$(get_waf_id)

    if [ -z "$WEB_ACL_ID" ]; then
        echo -e "${RED}WAF '${WEB_ACL_NAME}' not found${NC}"
        echo ""
        echo "Make sure you have deployed the infrastructure with:"
        echo "  cd $TERRAFORM_DIR && terraform apply"
        exit 1
    fi

    # Check maintenance rule action
    local RULE_ACTION=$(aws wafv2 get-web-acl --name "$WEB_ACL_NAME" --scope REGIONAL \
        --id "$WEB_ACL_ID" --region "$AWS_REGION" \
        --query "WebACL.Rules[?Name=='maintenance-mode'].Action" --output json 2>/dev/null)

    if [[ "$RULE_ACTION" == *"Block"* ]]; then
        echo -e "${YELLOW}Maintenance mode: ENABLED${NC}"
        echo ""
        echo "   Users are seeing the maintenance page."
        echo "   Run '$0 off' to disable maintenance mode."
        return 0
    else
        echo -e "${GREEN}Maintenance mode: DISABLED${NC}"
        echo ""
        echo "   Frontend is live and serving traffic."
        echo "   Run '$0 on' to enable maintenance mode."
        return 1
    fi
}

check_tfvars() {
    if [ -z "$TFVARS_FILE" ]; then
        echo -e "${RED}Error: TFVARS_FILE environment variable is required${NC}"
        echo ""
        echo "Example:"
        echo "  TFVARS_FILE=environments/us-west-2-existing-vpc.tfvars $0 $1"
        exit 1
    fi

    if [ ! -f "$TERRAFORM_DIR/$TFVARS_FILE" ]; then
        echo -e "${RED}Error: TFVARS_FILE not found: $TERRAFORM_DIR/$TFVARS_FILE${NC}"
        exit 1
    fi
}

enable_maintenance() {
    check_tfvars "on"

    echo -e "${YELLOW}Enabling maintenance mode...${NC}"
    echo "   WAF: ${WEB_ACL_NAME}"
    echo "   Region: ${AWS_REGION}"
    echo "   Config: ${TFVARS_FILE}"
    echo ""

    cd "$TERRAFORM_DIR"

    # Only update the WAF resource - doesn't affect app deployment
    terraform apply \
        -var-file="$TFVARS_FILE" \
        -var="waf_maintenance_mode=true" \
        -auto-approve \
        -target=aws_wafv2_web_acl.frontend

    echo ""
    echo -e "${GREEN}Maintenance mode ENABLED${NC}"
    echo ""
    echo "   Users will now see the maintenance page."
    echo "   You can safely deploy your application."
    echo ""
    echo "   When ready to go live, run: TFVARS_FILE=$TFVARS_FILE $0 off"
}

disable_maintenance() {
    check_tfvars "off"

    echo -e "${YELLOW}Disabling maintenance mode...${NC}"
    echo "   WAF: ${WEB_ACL_NAME}"
    echo "   Region: ${AWS_REGION}"
    echo "   Config: ${TFVARS_FILE}"
    echo ""

    cd "$TERRAFORM_DIR"

    # Only update the WAF resource - doesn't affect app deployment
    terraform apply \
        -var-file="$TFVARS_FILE" \
        -var="waf_maintenance_mode=false" \
        -auto-approve \
        -target=aws_wafv2_web_acl.frontend

    echo ""
    echo -e "${GREEN}Maintenance mode DISABLED${NC}"
    echo ""
    echo "   Frontend is now live and serving traffic!"
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

check_prerequisites

case "${1:-}" in
    on)
        enable_maintenance
        ;;
    off)
        disable_maintenance
        ;;
    status)
        check_status
        ;;
    *)
        usage
        ;;
esac
