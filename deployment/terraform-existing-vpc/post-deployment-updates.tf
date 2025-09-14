# Post-deployment configuration updates
# This updates ONLY the environment variables without recreating the service

resource "null_resource" "update_backend_cors" {
  triggers = {
    frontend_url = aws_apprunner_service.frontend.service_url
    backend_url  = aws_apprunner_service.backend.service_url
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      echo "========================================="
      echo "Post-deployment configuration update"
      echo "========================================="
      
      # Get the service URLs
      BACKEND_URL="${aws_apprunner_service.backend.service_url}"
      FRONTEND_URL="${aws_apprunner_service.frontend.service_url}"
      BACKEND_ARN="${aws_apprunner_service.backend.arn}"
      
      echo "Backend URL: https://$BACKEND_URL"
      echo "Frontend URL: https://$FRONTEND_URL"
      
      # Wait for both services to be running
      echo "Checking service status..."
      
      for i in {1..30}; do
        BACKEND_STATUS=$(aws apprunner describe-service \
          --service-arn "$BACKEND_ARN" \
          --region ${var.aws_region} \
          --query 'Service.Status' \
          --output text)
        
        if [ "$BACKEND_STATUS" = "RUNNING" ]; then
          echo "✓ Backend service is running"
          break
        else
          echo "  Backend status: $BACKEND_STATUS (attempt $i/30)"
          if [ "$i" -eq 30 ]; then
            echo "✗ Backend service failed to reach RUNNING state"
            exit 1
          fi
          sleep 10
        fi
      done
      
      # Create the update configuration
      # IMPORTANT: We only update the environment variables that need the frontend URL
      # We keep the same image to avoid service recreation
      cat > /tmp/backend-env-update.json <<EOF
{
  "ImageRepository": {
    "ImageIdentifier": "${aws_ecr_repository.backend.repository_url}:latest",
    "ImageConfiguration": {
      "Port": "8000",
      "RuntimeEnvironmentVariables": {
        "AWS_REGION": "${var.aws_region}",
        "BOND_PROVIDER_CLASS": "bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider",
        "DATABASE_SECRET_ARN": "${aws_secretsmanager_secret.db_credentials.arn}",
        "S3_BUCKET_NAME": "${aws_s3_bucket.uploads.id}",
        "JWT_SECRET_KEY": "${random_password.jwt_secret.result}",
        "BEDROCK_AGENT_ROLE_ARN": "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/BondAIBedrockAgentRole",
        "BEDROCK_DEFAULT_MODEL": "${var.bedrock_default_model}",
        "METADATA_DB_URL": "postgresql://bondadmin:${random_password.db_password.result}@${aws_db_instance.main.address}:5432/bondai",
        "OAUTH2_ENABLED_PROVIDERS": "${var.oauth2_providers}",
        "OKTA_DOMAIN": "${var.okta_domain}",
        "OKTA_CLIENT_ID": "${var.okta_client_id}",
        "OKTA_CLIENT_SECRET": "${jsondecode(data.aws_secretsmanager_secret_version.okta_secret.secret_string)["client_secret"]}",
        "OKTA_REDIRECT_URI": "https://$BACKEND_URL/auth/okta/callback",
        "OKTA_SCOPES": "${var.okta_scopes}",
        "JWT_REDIRECT_URI": "https://$FRONTEND_URL",
        "CORS_ALLOWED_ORIGINS": "${var.cors_allowed_origins},https://$FRONTEND_URL"
      }
    },
    "ImageRepositoryType": "ECR"
  }
}
EOF
      
      echo "Updating backend with frontend URL for CORS and JWT redirect..."
      
      # Perform the update
      UPDATE_OUTPUT=$(aws apprunner update-service \
        --service-arn "$BACKEND_ARN" \
        --source-configuration file:///tmp/backend-env-update.json \
        --region ${var.aws_region} 2>&1)
      
      UPDATE_STATUS=$?
      
      if [ $UPDATE_STATUS -eq 0 ]; then
        echo "✓ Update command executed successfully"
        
        # Extract the new service URL from the update response
        NEW_SERVICE_URL=$(echo "$UPDATE_OUTPUT" | jq -r '.Service.ServiceUrl // empty')
        
        if [ -n "$NEW_SERVICE_URL" ] && [ "$NEW_SERVICE_URL" != "$BACKEND_URL" ]; then
          echo "⚠️ WARNING: Backend URL changed from https://$BACKEND_URL to https://$NEW_SERVICE_URL"
          echo "This will break the frontend configuration!"
          # We don't exit here, but log the warning
        fi
        
        # Wait for the update to complete
        echo "Waiting for backend service update to complete..."
        for i in {1..60}; do
          STATUS=$(aws apprunner describe-service \
            --service-arn "$BACKEND_ARN" \
            --region ${var.aws_region} \
            --query 'Service.Status' \
            --output text)
          
          if [ "$STATUS" = "RUNNING" ]; then
            FINAL_URL=$(aws apprunner describe-service \
              --service-arn "$BACKEND_ARN" \
              --region ${var.aws_region} \
              --query 'Service.ServiceUrl' \
              --output text)
            
            echo "✓ Backend service is running"
            echo "  Final backend URL: https://$FINAL_URL"
            
            if [ "$FINAL_URL" != "$BACKEND_URL" ]; then
              echo ""
              echo "⚠️ CRITICAL WARNING ⚠️"
              echo "Backend URL has changed during update!"
              echo "Original: https://$BACKEND_URL"
              echo "New: https://$FINAL_URL"
              echo "Frontend may need to be rebuilt with the new backend URL"
            else
              echo "✓ Backend URL remains stable at https://$BACKEND_URL"
            fi
            break
          elif [ "$STATUS" = "OPERATION_IN_PROGRESS" ]; then
            echo "  Update in progress... (attempt $i/60)"
          else
            echo "  Service status: $STATUS (attempt $i/60)"
          fi
          
          if [ "$i" -eq 60 ]; then
            echo "✗ Timeout waiting for service update"
            exit 1
          fi
          
          sleep 10
        done
        
        echo ""
        echo "✓ Post-deployment configuration complete"
        echo "  Backend CORS now includes: https://$FRONTEND_URL"
        echo "  JWT redirect URI set to: https://$FRONTEND_URL"
        
      else
        echo "✗ Failed to update backend configuration"
        echo "Error output: $UPDATE_OUTPUT"
        exit 1
      fi
      
      # Clean up
      rm -f /tmp/backend-env-update.json
    EOT
  }

  depends_on = [
    aws_apprunner_service.backend,
    aws_apprunner_service.frontend
  ]
  
  # Prevent this from running on destroy
  lifecycle {
    create_before_destroy = false
  }
}

# Output to confirm post-deployment status
output "post_deployment_update_status" {
  value = "Backend CORS and JWT redirect updated with frontend URL"
  depends_on = [null_resource.update_backend_cors]
}