# ============================================================================
# Post-Deployment Configuration Updates
# ============================================================================
# This file handles updates to services after they are deployed, such as
# updating CORS settings and redirect URIs with the actual service URLs.

# Update backend with frontend URL after both services are deployed
# This dynamically gets service URLs to avoid hard dependencies
resource "null_resource" "update_backend_config" {
  # No hard dependencies - this will be run in Phase 4 after services exist

  # Trigger update on each apply
  triggers = {
    always_run = timestamp()
  }

  # Update backend's runtime environment variables with the frontend URL
  provisioner "local-exec" {
    command = <<-EOT
      echo "Getting service URLs..."

      # Get backend and frontend URLs from AWS
      BACKEND_URL=$(aws apprunner list-services --region ${var.aws_region} \
        --query "ServiceSummaryList[?ServiceName=='${var.project_name}-${var.environment}-backend'].ServiceUrl" \
        --output text)

      FRONTEND_URL=$(aws apprunner list-services --region ${var.aws_region} \
        --query "ServiceSummaryList[?ServiceName=='${var.project_name}-${var.environment}-frontend'].ServiceUrl" \
        --output text)

      if [ -z "$BACKEND_URL" ] || [ -z "$FRONTEND_URL" ]; then
        echo "Error: Backend or Frontend service not found. Please ensure Phases 2 and 3 have completed."
        exit 1
      fi

      echo "Backend URL: https://$BACKEND_URL"
      echo "Frontend URL: https://$FRONTEND_URL"

      echo "Updating backend service with frontend URL and proper CORS..."

      # Get the backend service ARN
      SERVICE_ARN=$(aws apprunner list-services --region ${var.aws_region} \
        --query "ServiceSummaryList[?ServiceName=='${var.project_name}-${var.environment}-backend'].ServiceArn" \
        --output text)

      # Update the service with new environment variables including correct frontend URL
      aws apprunner update-service \
        --service-arn "$SERVICE_ARN" \
        --region ${var.aws_region} \
        --source-configuration '{
          "ImageRepository": {
            "ImageIdentifier": "${aws_ecr_repository.backend.repository_url}:latest",
            "ImageRepositoryType": "ECR",
            "ImageConfiguration": {
              "Port": "8000",
              "RuntimeEnvironmentVariables": {
                "AWS_REGION": "${var.aws_region}",
                "BOND_PROVIDER_CLASS": "bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider",
                "DATABASE_SECRET_ARN": "${aws_secretsmanager_secret.db_credentials.arn}",
                "S3_BUCKET_NAME": "${aws_s3_bucket.uploads.id}",
                "JWT_SECRET_KEY": "${random_password.jwt_secret.result}",
                "BEDROCK_AGENT_ROLE_ARN": "arn:aws:iam::119684128788:role/BondAIBedrockAgentRole",
                "METADATA_DB_URL": "postgresql://bondadmin:${random_password.db_password.result}@${aws_db_instance.main.address}:5432/bondai",
                "OAUTH2_ENABLED_PROVIDERS": "${var.oauth2_providers}",
                "OKTA_DOMAIN": "${var.okta_domain}",
                "OKTA_CLIENT_ID": "${var.okta_client_id}",
                "OKTA_CLIENT_SECRET": "${jsondecode(data.aws_secretsmanager_secret_version.okta_secret.secret_string)["client_secret"]}",
                "OKTA_REDIRECT_URI": "https://'$BACKEND_URL'/auth/okta/callback",
                "OKTA_SCOPES": "${var.okta_scopes}",
                "JWT_REDIRECT_URI": "https://'$FRONTEND_URL'",
                "CORS_ALLOWED_ORIGINS": "https://'$FRONTEND_URL',http://localhost:3000,http://localhost:5000",
                "FRONTEND_URL": "https://'$FRONTEND_URL'"
              }
            }
          },
          "AutoDeploymentsEnabled": true
        }'

      echo "Waiting for backend service to update..."
      sleep 30

      # Check service status
      aws apprunner describe-service \
        --service-arn "$SERVICE_ARN" \
        --region ${var.aws_region} \
        --query "Service.Status" \
        --output text

      echo "Backend configuration updated successfully!"
      echo "CORS now allows: https://$FRONTEND_URL"
      echo "Okta redirect URI: https://$BACKEND_URL/auth/okta/callback"
      echo "JWT redirect URI: https://$FRONTEND_URL"
    EOT
  }
}

# Output to confirm post-deployment configuration
output "post_deployment_status" {
  value = "Run 'make deploy-phase4' to update backend with frontend URL for CORS"
  description = "Reminder to run post-deployment configuration"
}
