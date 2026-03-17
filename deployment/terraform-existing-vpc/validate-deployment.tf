# Validation resource to ensure the combined service is created and running
resource "null_resource" "validate_deployment" {
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
    null_resource.wait_for_backend_ready  # Wait for service to finish deploying
  ]
}
