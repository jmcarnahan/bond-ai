#!/bin/bash

# Monitor deployment script for Bond AI
# This script helps track the deployment progress and identify issues

set -e

REGION="us-west-2"
PROJECT="bond-ai"
ENV="dev"

echo "========================================="
echo "Bond AI Deployment Monitor"
echo "Region: $REGION"
echo "========================================="

# Function to check terraform state
check_terraform_state() {
    echo ""
    echo "Checking Terraform state..."
    cd /Users/jcarnahan/projects/bond-ai/deployment/terraform-existing-vpc

    # Count resources
    RESOURCE_COUNT=$(terraform state list 2>/dev/null | wc -l)
    echo "Resources in state: $RESOURCE_COUNT"

    # Check for critical resources
    echo ""
    echo "Critical resources:"

    if terraform state show aws_apprunner_service.backend 2>/dev/null | grep -q "service_url"; then
        BACKEND_URL=$(terraform state show aws_apprunner_service.backend 2>/dev/null | grep "service_url" | awk '{print $3}' | tr -d '"')
        echo "✓ Backend service: https://$BACKEND_URL"
    else
        echo "✗ Backend service: NOT FOUND"
    fi

    if terraform state show aws_apprunner_service.frontend 2>/dev/null | grep -q "service_url"; then
        FRONTEND_URL=$(terraform state show aws_apprunner_service.frontend 2>/dev/null | grep "service_url" | awk '{print $3}' | tr -d '"')
        echo "✓ Frontend service: https://$FRONTEND_URL"
    else
        echo "✗ Frontend service: NOT FOUND"
    fi

    if terraform state show null_resource.build_backend_image 2>/dev/null | grep -q "id"; then
        echo "✓ Backend image build: COMPLETE"
    else
        echo "✗ Backend image build: NOT FOUND"
    fi

    if terraform state show null_resource.build_frontend_image 2>/dev/null | grep -q "id"; then
        echo "✓ Frontend image build: COMPLETE"
    else
        echo "✗ Frontend image build: NOT FOUND"
    fi
}

# Function to check AWS resources
check_aws_resources() {
    echo ""
    echo "Checking AWS App Runner services..."

    # List App Runner services
    aws apprunner list-services \
        --region $REGION \
        --query 'ServiceSummaryList[?contains(ServiceName, `bond-ai`)].[ServiceName, Status, ServiceUrl]' \
        --output table

    echo ""
    echo "Checking ECR repositories..."

    # Check ECR repos
    for REPO in "bond-ai-dev-backend" "bond-ai-dev-frontend"; do
        IMAGE_COUNT=$(aws ecr describe-images \
            --repository-name $REPO \
            --region $REGION \
            --query 'length(imageDetails)' \
            --output text 2>/dev/null || echo "0")

        if [ "$IMAGE_COUNT" -gt 0 ]; then
            echo "✓ ECR repository $REPO: $IMAGE_COUNT image(s)"
        else
            echo "✗ ECR repository $REPO: No images or not found"
        fi
    done
}

# Function to test services
test_services() {
    echo ""
    echo "Testing service endpoints..."

    # Get service URLs from AWS
    BACKEND_URL=$(aws apprunner list-services \
        --region $REGION \
        --query 'ServiceSummaryList[?ServiceName==`bond-ai-dev-backend`].ServiceUrl' \
        --output text 2>/dev/null)

    FRONTEND_URL=$(aws apprunner list-services \
        --region $REGION \
        --query 'ServiceSummaryList[?ServiceName==`bond-ai-dev-frontend`].ServiceUrl' \
        --output text 2>/dev/null)

    if [ -n "$BACKEND_URL" ]; then
        echo ""
        echo "Testing backend at https://$BACKEND_URL/health"
        RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "https://$BACKEND_URL/health" || echo "000")

        if [ "$RESPONSE" = "200" ] || [ "$RESPONSE" = "503" ]; then
            echo "✓ Backend health check: HTTP $RESPONSE"
        else
            echo "✗ Backend health check: HTTP $RESPONSE"
        fi
    else
        echo "✗ Backend URL not found"
    fi

    if [ -n "$FRONTEND_URL" ]; then
        echo ""
        echo "Testing frontend at https://$FRONTEND_URL/"
        RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "https://$FRONTEND_URL/" || echo "000")

        if [ "$RESPONSE" = "200" ]; then
            echo "✓ Frontend: HTTP $RESPONSE"
        else
            echo "✗ Frontend: HTTP $RESPONSE"
        fi
    else
        echo "✗ Frontend URL not found"
    fi
}

# Main monitoring loop
while true; do
    clear
    echo "$(date '+%Y-%m-%d %H:%M:%S')"

    check_terraform_state
    check_aws_resources
    test_services

    echo ""
    echo "========================================="
    echo "Press Ctrl+C to exit, refreshing in 30 seconds..."
    sleep 30
done
