# Validation resource to ensure the combined service is created and running
resource "null_resource" "validate_deployment" {
  count = var.enable_apprunner ? 1 : 0

  triggers = {
    backend_url = local.backend_url
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      echo ""
      echo "========================================="
      echo "Validating Deployment"
      echo "========================================="

      SERVICE_URL="${local.backend_url}"
      IS_PRIVATE="${var.backend_is_private}"

      echo "Service URL: https://$SERVICE_URL"
      if [ "$IS_PRIVATE" = "true" ]; then
        echo "Access: PRIVATE (VPN required)"
      fi
      echo ""

      # Check health (skip if private — not reachable from this machine without VPN)
      if [ "$IS_PRIVATE" = "true" ]; then
        echo "Skipping health check (private service — use VPN to test)"
      else
        echo "Checking backend health..."
        BACKEND_RESPONSE=$(curl -s -o /dev/null -w "%%{http_code}" "https://$SERVICE_URL/health" || echo "000")

        if [ "$BACKEND_RESPONSE" = "200" ] || [ "$BACKEND_RESPONSE" = "503" ]; then
          echo "✓ Backend is accessible (HTTP $BACKEND_RESPONSE)"
        else
          echo "⚠️ Backend returned HTTP $BACKEND_RESPONSE"
          echo "  This may be normal during initial deployment"
        fi

        echo "Checking frontend..."
        FRONTEND_RESPONSE=$(curl -s -o /dev/null -w "%%{http_code}" "https://$SERVICE_URL/" || echo "000")

        if [ "$FRONTEND_RESPONSE" = "200" ]; then
          echo "✓ Frontend is accessible (HTTP $FRONTEND_RESPONSE)"
        else
          echo "⚠️ Frontend returned HTTP $FRONTEND_RESPONSE"
          echo "  This may be normal during initial deployment"
        fi
      fi

      # List App Runner services to confirm
      echo ""
      echo "Confirming App Runner services in AWS..."
      aws apprunner list-services \
        --region ${var.aws_region} \
        --query 'ServiceSummaryList[?ServiceName==`${var.project_name}-${var.environment}-backend`].[ServiceName, Status, ServiceUrl]' \
        --output table

      echo ""
      echo "========================================="
      echo "Deployment Validation Complete"
      echo "========================================="
      echo ""
      echo "Next steps:"
      echo "1. Wait 2-3 minutes for service to fully stabilize"
      if [ "$IS_PRIVATE" = "true" ]; then
        echo "2. Connect to VPN, then test: curl https://$SERVICE_URL/health"
        echo "3. Connect to VPN, then access: https://$SERVICE_URL"
      else
        echo "2. Test backend: curl https://$SERVICE_URL/health"
        echo "3. Access frontend: https://$SERVICE_URL"
      fi
      echo "4. Check OAuth callback URL is set to: https://$SERVICE_URL/auth/okta/callback"
      echo ""
    EOT
  }

  depends_on = [
    null_resource.wait_for_backend_ready
  ]
}

moved {
  from = null_resource.validate_deployment
  to   = null_resource.validate_deployment[0]
}

# =============================================================================
# ECS Express Deployment Validation
# =============================================================================

resource "null_resource" "validate_ecs_express_deployment" {
  count = var.enable_ecs_express ? 1 : 0

  triggers = {
    service_arn = aws_ecs_express_gateway_service.backend[0].service_arn
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      echo ""
      echo "========================================="
      echo "Validating ECS Express Deployment"
      echo "========================================="

      SERVICE_URL="${local.ecs_express_backend_url}"
      REGION="${var.aws_region}"
      VPC_ID="${data.aws_vpc.existing.id}"
      SERVICE_NAME="${var.project_name}-${var.environment}-backend"
      CONFIGURE_ALB="${var.ecs_express_configure_alb}"

      echo "Service Endpoint: $SERVICE_URL"
      echo ""

      # --- Discover ALB via CLI (works on first deploy before configure_alb is set) ---
      echo "Discovering ALB..."
      ALB_ARN=""
      ALL_ALBS=$(aws elbv2 describe-load-balancers \
        --region "$REGION" \
        --query "LoadBalancers[?VpcId=='$VPC_ID' && Type=='application'].[LoadBalancerArn]" \
        --output json 2>/dev/null || echo "[]")

      for ARN in $(echo "$ALL_ALBS" | jq -r '.[][] // empty'); do
        TAGS=$(aws elbv2 describe-tags \
          --resource-arns "$ARN" \
          --region "$REGION" \
          --query "TagDescriptions[0].Tags" \
          --output json 2>/dev/null || echo "[]")

        MATCH=$(echo "$TAGS" | jq -r --arg svc "$SERVICE_NAME" \
          '[.[] | select(.Value == $svc or (.Value | contains($svc)))] | length')

        if [ "$MATCH" -gt "0" ]; then
          ALB_ARN="$ARN"
          break
        fi
      done

      if [ -n "$ALB_ARN" ]; then
        echo "ALB ARN: $ALB_ARN"

        # Set idle timeout to 300s (matches nginx proxy_read_timeout)
        echo "Setting ALB idle timeout to 300s..."
        aws elbv2 modify-load-balancer-attributes \
          --load-balancer-arn "$ALB_ARN" \
          --attributes Key=idle_timeout.timeout_seconds,Value=300 \
          --region "$REGION" \
          --output text 2>/dev/null || echo "  Warning: could not set timeout"

        TIMEOUT=$(aws elbv2 describe-load-balancer-attributes \
          --load-balancer-arn "$ALB_ARN" \
          --region "$REGION" \
          --query "Attributes[?Key=='idle_timeout.timeout_seconds'].Value | [0]" \
          --output text 2>/dev/null || echo "unknown")
        echo "ALB idle timeout: $${TIMEOUT}s"
      else
        echo "ALB: not yet discovered (may still be provisioning)"
      fi
      echo ""

      # --- Health checks ---
      if [ -z "$SERVICE_URL" ] || [ "$SERVICE_URL" = "pending" ]; then
        echo "Service endpoint not yet available — skipping health check"
      else
        echo "Checking backend health..."
        BACKEND_RESPONSE=$(curl -s -o /dev/null -w "%%{http_code}" "https://$SERVICE_URL/health" 2>/dev/null || echo "000")

        if [ "$BACKEND_RESPONSE" = "200" ] || [ "$BACKEND_RESPONSE" = "503" ]; then
          echo "Backend is accessible (HTTP $BACKEND_RESPONSE)"
        else
          echo "Backend returned HTTP $BACKEND_RESPONSE"
          echo "  This may be normal during initial deployment"
        fi

        echo "Checking frontend..."
        FRONTEND_RESPONSE=$(curl -s -o /dev/null -w "%%{http_code}" "https://$SERVICE_URL/" 2>/dev/null || echo "000")

        if [ "$FRONTEND_RESPONSE" = "200" ]; then
          echo "Frontend is accessible (HTTP $FRONTEND_RESPONSE)"
        else
          echo "Frontend returned HTTP $FRONTEND_RESPONSE"
          echo "  This may be normal during initial deployment"
        fi
      fi

      echo ""
      echo "========================================="
      echo "ECS Express Validation Complete"
      echo "========================================="
      echo ""
      if [ "$CONFIGURE_ALB" = "true" ]; then
        echo "Next steps:"
        echo "1. Test: curl https://$SERVICE_URL/health"
        echo "2. Test streaming: send a long agent request and verify it exceeds 2 minutes"
        echo "3. When ready to cut over domain: set primary_platform = \"ecs_express\""
      else
        echo "Next steps:"
        echo "1. Test: curl https://$SERVICE_URL/health"
        echo "2. Set ecs_express_configure_alb = true and re-apply for WAF + timeout"
        echo "3. Test streaming beyond 2 minutes"
        echo "4. When ready: set primary_platform = \"ecs_express\""
      fi
      echo ""
    EOT
  }

  depends_on = [
    aws_ecs_express_gateway_service.backend,
  ]
}
