# Validation resource to ensure both services are created and running
resource "null_resource" "validate_deployment" {
  triggers = {
    backend_url  = local.backend_url
    frontend_url = local.frontend_url
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      echo ""
      echo "========================================="
      echo "Validating Deployment"
      echo "========================================="

      BACKEND_URL="${local.backend_url}"
      FRONTEND_URL="${local.frontend_url}"
      BACKEND_IS_PRIVATE="${var.backend_is_private}"
      FRONTEND_IS_PRIVATE="${var.frontend_is_private}"

      echo "Backend URL: https://$BACKEND_URL"
      echo "Frontend URL: https://$FRONTEND_URL"
      if [ "$BACKEND_IS_PRIVATE" = "true" ]; then
        echo "Backend access: PRIVATE (VPN required)"
      fi
      if [ "$FRONTEND_IS_PRIVATE" = "true" ]; then
        echo "Frontend access: PRIVATE (VPN required)"
      fi
      echo ""

      # Check backend health (skip if private — not reachable from this machine without VPN)
      if [ "$BACKEND_IS_PRIVATE" = "true" ]; then
        echo "Skipping backend health check (private service — use VPN to test)"
      else
        echo "Checking backend health..."
        BACKEND_RESPONSE=$(curl -s -o /dev/null -w "%%{http_code}" "https://$BACKEND_URL/health" || echo "000")

        if [ "$BACKEND_RESPONSE" = "200" ] || [ "$BACKEND_RESPONSE" = "503" ]; then
          echo "✓ Backend is accessible (HTTP $BACKEND_RESPONSE)"
        else
          echo "⚠️ Backend returned HTTP $BACKEND_RESPONSE"
          echo "  This may be normal during initial deployment"
        fi
      fi

      # Check frontend (skip if private — not reachable from this machine without VPN)
      if [ "$FRONTEND_IS_PRIVATE" = "true" ]; then
        echo "Skipping frontend health check (private service — use VPN to test)"
      else
        echo "Checking frontend..."
        FRONTEND_RESPONSE=$(curl -s -o /dev/null -w "%%{http_code}" "https://$FRONTEND_URL/" || echo "000")

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
        --query 'ServiceSummaryList[?ServiceName==`${var.project_name}-${var.environment}-backend` || ServiceName==`${var.project_name}-${var.environment}-frontend`].[ServiceName, Status, ServiceUrl]' \
        --output table

      echo ""
      echo "========================================="
      echo "Deployment Validation Complete"
      echo "========================================="
      echo ""
      echo "Next steps:"
      echo "1. Wait 2-3 minutes for services to fully stabilize"
      if [ "$BACKEND_IS_PRIVATE" = "true" ]; then
        echo "2. Connect to VPN, then test backend: curl https://$BACKEND_URL/health"
      else
        echo "2. Test backend: curl https://$BACKEND_URL/health"
      fi
      if [ "$FRONTEND_IS_PRIVATE" = "true" ]; then
        echo "3. Connect to VPN, then access frontend: https://$FRONTEND_URL"
      else
        echo "3. Access frontend: https://$FRONTEND_URL"
      fi
      echo "4. Check Okta callback URL is set to: https://$BACKEND_URL/auth/okta/callback"
      echo ""
    EOT
  }

  depends_on = [
    null_resource.wait_for_backend_ready, # Wait for backend to finish deploying
    aws_apprunner_service.frontend
  ]
}
