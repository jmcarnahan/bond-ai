# App Runner Backend Service

# App Runner VPC Connector for database access
resource "aws_apprunner_vpc_connector" "backend" {
  vpc_connector_name = "${var.project_name}-${var.environment}-connector"
  subnets            = local.app_runner_subnet_ids
  security_groups    = [aws_security_group.app_runner.id]

  tags = {
    Name = "${var.project_name}-${var.environment}-vpc-connector"
  }
}

# App Runner Auto Scaling Configuration
resource "aws_apprunner_auto_scaling_configuration_version" "backend" {
  auto_scaling_configuration_name = "${var.project_name}-${var.environment}-backend-autoscaling"

  min_size = 1
  max_size = var.environment == "prod" ? 10 : 2

  tags = {
    Name = "${var.project_name}-${var.environment}-backend-autoscaling"
  }
}

# App Runner Service
resource "aws_apprunner_service" "backend" {
  service_name = "${var.project_name}-${var.environment}-backend"

  source_configuration {
    authentication_configuration {
      access_role_arn = aws_iam_role.app_runner_ecr_access.arn
    }

    image_repository {
      image_identifier      = "${aws_ecr_repository.backend.repository_url}:latest"
      image_repository_type = "ECR"

      image_configuration {
        port = "8000"

        runtime_environment_variables = {
          AWS_REGION             = var.aws_region
          BOND_PROVIDER_CLASS    = "bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider"
          DATABASE_SECRET_ARN    = aws_secretsmanager_secret.db_credentials.arn
          S3_BUCKET_NAME         = aws_s3_bucket.uploads.id
          JWT_SECRET_KEY         = random_password.jwt_secret.result
          BEDROCK_AGENT_ROLE_ARN = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/BondAIBedrockAgentRole"
          BEDROCK_DEFAULT_MODEL  = var.bedrock_default_model
          METADATA_DB_URL        = "postgresql://bondadmin:${random_password.db_password.result}@${local.database_endpoint}:5432/bondai?sslmode=require"

          # Okta OAuth Configuration
          OAUTH2_ENABLED_PROVIDERS = var.oauth2_providers
          OKTA_DOMAIN              = var.okta_domain
          OKTA_CLIENT_ID           = var.okta_client_id
          OKTA_CLIENT_SECRET       = jsondecode(data.aws_secretsmanager_secret_version.okta_secret.secret_string)["client_secret"]
          # Okta redirect URI - will be set to the actual backend URL after deployment
          # We can't reference self here, so using a placeholder that you'll need to update in Okta
          OKTA_REDIRECT_URI = var.okta_redirect_uri != "" ? var.okta_redirect_uri : "https://BACKEND_URL_PLACEHOLDER/auth/okta/callback"
          OKTA_SCOPES       = var.okta_scopes

          # AWS Cognito OAuth Configuration (only if configured)
          # Note: Add "cognito" to oauth2_providers variable to enable
          COGNITO_DOMAIN       = var.cognito_domain
          COGNITO_CLIENT_ID    = var.cognito_client_id
          COGNITO_SECRET_NAME  = var.cognito_secret_name
          COGNITO_REDIRECT_URI = var.cognito_redirect_uri != "" ? var.cognito_redirect_uri : (var.cognito_domain != "" ? "https://BACKEND_URL_PLACEHOLDER/auth/cognito/callback" : "")
          COGNITO_SCOPES       = var.cognito_scopes
          COGNITO_REGION       = var.cognito_region

          # JWT redirect URI for frontend - uses variable to avoid circular dependency
          JWT_REDIRECT_URI = var.jwt_redirect_uri != "" ? var.jwt_redirect_uri : "*"

          # CORS configuration - uses variable to allow post-deployment tightening
          CORS_ALLOWED_ORIGINS = var.cors_allowed_origins

          # Allowed redirect domains for OAuth callbacks (security)
          # Localhost and *.awsapprunner.com are always allowed by default
          ALLOWED_REDIRECT_DOMAINS = var.allowed_redirect_domains

          # Knowledge Base configuration (only set when KB is enabled)
          BEDROCK_KNOWLEDGE_BASE_ID = try(aws_bedrockagent_knowledge_base.main[0].id, "")
          BEDROCK_KB_DATA_SOURCE_ID = try(aws_bedrockagent_data_source.s3[0].data_source_id, "")
          BEDROCK_KB_S3_PREFIX      = var.enable_knowledge_base ? "knowledge-base/" : ""

          # MCP configuration (only set when provided)
          BOND_MCP_CONFIG = var.bond_mcp_config

          # Admin configuration (prefer ADMIN_USERS for multiple admins)
          ADMIN_USERS = var.admin_users
          ADMIN_EMAIL = var.admin_email  # Legacy fallback for backward compatibility
        }
      }
    }
  }

  # Network configuration with VPC connector
  network_configuration {
    egress_configuration {
      egress_type       = "VPC"
      vpc_connector_arn = aws_apprunner_vpc_connector.backend.arn
    }
  }

  instance_configuration {
    cpu               = "0.5 vCPU"
    memory            = "1 GB"
    instance_role_arn = aws_iam_role.app_runner_instance.arn
  }

  auto_scaling_configuration_arn = aws_apprunner_auto_scaling_configuration_version.backend.arn

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/health"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-backend"
  }

  depends_on = [
    null_resource.build_backend_image,
    aws_secretsmanager_secret_version.db_credentials
  ]
  # Note: Database dependency handled via local.database_endpoint
}

# Wait for App Runner backend to reach RUNNING status before dependent resources proceed
# This prevents race conditions where WAF/other resources try to update while deploying
resource "null_resource" "wait_for_backend_ready" {
  depends_on = [aws_apprunner_service.backend]

  triggers = {
    # Re-trigger when the backend service changes
    service_arn = aws_apprunner_service.backend.arn
  }

  provisioner "local-exec" {
    command = <<-EOT
      echo "Waiting for App Runner backend service to be ready..."
      SERVICE_ARN="${aws_apprunner_service.backend.arn}"
      MAX_ATTEMPTS=30
      ATTEMPT=0

      while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
        STATUS=$(aws apprunner describe-service \
          --service-arn "$SERVICE_ARN" \
          --region ${var.aws_region} \
          --query 'Service.Status' \
          --output text 2>/dev/null || echo "UNKNOWN")

        if [ "$STATUS" = "RUNNING" ]; then
          echo "✓ Backend service is ready (status: $STATUS)"
          exit 0
        fi

        echo "Backend status: $STATUS (attempt $((ATTEMPT+1))/$MAX_ATTEMPTS)"
        ATTEMPT=$((ATTEMPT+1))
        sleep 10
      done

      echo "Warning: Backend service did not reach RUNNING state within timeout"
      exit 0  # Don't fail the deployment, just warn
    EOT
  }
}
