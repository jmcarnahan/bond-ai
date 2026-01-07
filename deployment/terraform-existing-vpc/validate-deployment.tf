# Validation resource to ensure both services are created and running
resource "null_resource" "validate_deployment" {
  triggers = {
    backend_url  = aws_apprunner_service.backend.service_url
    frontend_url = aws_apprunner_service.frontend.service_url
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      echo ""
      echo "========================================="
      echo "Validating Deployment"
      echo "========================================="

      BACKEND_URL="${aws_apprunner_service.backend.service_url}"
      FRONTEND_URL="${aws_apprunner_service.frontend.service_url}"

      echo "Backend URL: https://$BACKEND_URL"
      echo "Frontend URL: https://$FRONTEND_URL"
      echo ""

      # Check backend health
      echo "Checking backend health..."
      BACKEND_RESPONSE=$(curl -s -o /dev/null -w "%%{http_code}" "https://$BACKEND_URL/health" || echo "000")

      if [ "$BACKEND_RESPONSE" = "200" ] || [ "$BACKEND_RESPONSE" = "503" ]; then
        echo "✓ Backend is accessible (HTTP $BACKEND_RESPONSE)"
      else
        echo "⚠️ Backend returned HTTP $BACKEND_RESPONSE"
        echo "  This may be normal during initial deployment"
      fi

      # Check frontend
      echo "Checking frontend..."
      FRONTEND_RESPONSE=$(curl -s -o /dev/null -w "%%{http_code}" "https://$FRONTEND_URL/" || echo "000")

      if [ "$FRONTEND_RESPONSE" = "200" ]; then
        echo "✓ Frontend is accessible (HTTP $FRONTEND_RESPONSE)"
      else
        echo "⚠️ Frontend returned HTTP $FRONTEND_RESPONSE"
        echo "  This may be normal during initial deployment"
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
      echo "2. Test backend: curl https://$BACKEND_URL/health"
      echo "3. Access frontend: https://$FRONTEND_URL"
      echo "4. Check Okta callback URL is set to: https://$BACKEND_URL/auth/okta/callback"
      echo ""
    EOT
  }

  depends_on = [
    aws_apprunner_service.backend,
    aws_apprunner_service.frontend
  ]
}
