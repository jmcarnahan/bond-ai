# App Runner Combined Service (Backend + Frontend)
# All App Runner resources gated by var.enable_apprunner (default: true)

locals {
  # When private, service_url is null — use VPC Ingress Connection domain instead
  backend_url = var.enable_apprunner ? (
    var.backend_is_private ? aws_apprunner_vpc_ingress_connection.backend[0].domain_name : aws_apprunner_service.backend[0].service_url
  ) : null
}

# App Runner VPC Connector for database access
# Always created — shared by backend and MCP services (including external deployments)
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
  count = var.enable_apprunner ? 1 : 0

  auto_scaling_configuration_name = "${var.project_name}-${var.environment}-backend-autoscaling"

  min_size = 1
  max_size = var.environment == "prod" ? 10 : 2

  tags = {
    Name = "${var.project_name}-${var.environment}-backend-autoscaling"
  }
}

# State migration: moved blocks for adding count to existing resources
moved {
  from = aws_apprunner_vpc_connector.backend[0]
  to   = aws_apprunner_vpc_connector.backend
}

moved {
  from = aws_apprunner_auto_scaling_configuration_version.backend
  to   = aws_apprunner_auto_scaling_configuration_version.backend[0]
}

# Wait for App Runner to finish any auto-deployment triggered by the ECR image push.
# App Runner auto-deploys when it detects a new :latest image, which races with
# Terraform's UpdateService call. This resource polls until the service is RUNNING.
resource "null_resource" "wait_for_backend_auto_deploy" {
  count = var.enable_apprunner ? 1 : 0

  depends_on = [null_resource.build_combined_image]

  triggers = {
    build_id = null_resource.build_combined_image.id
  }

  provisioner "local-exec" {
    command = <<-EOT
      echo "Waiting for App Runner backend to finish any auto-deployment..."
      SERVICE_NAME="bond-ai-${var.environment}-backend"

      # Find the service ARN
      SERVICE_ARN=$(aws apprunner list-services \
        --region ${var.aws_region} \
        --query "ServiceSummaryList[?ServiceName=='$SERVICE_NAME'].ServiceArn" \
        --output text 2>/dev/null || echo "")

      if [ -z "$SERVICE_ARN" ] || [ "$SERVICE_ARN" = "None" ]; then
        echo "Service not found yet (first deploy) — skipping wait."
        exit 0
      fi

      # Give App Runner a moment to detect the new image
      sleep 15

      MAX_ATTEMPTS=60
      ATTEMPT=0

      while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
        STATUS=$(aws apprunner describe-service \
          --service-arn "$SERVICE_ARN" \
          --region ${var.aws_region} \
          --query 'Service.Status' \
          --output text 2>/dev/null || echo "UNKNOWN")

        if [ "$STATUS" = "RUNNING" ]; then
          echo "✓ Backend service is RUNNING — safe to proceed with Terraform update."
          exit 0
        fi

        echo "Backend status: $STATUS (attempt $((ATTEMPT+1))/$MAX_ATTEMPTS, waiting 10s...)"
        ATTEMPT=$((ATTEMPT+1))
        sleep 10
      done

      echo "Warning: Backend did not reach RUNNING within timeout. Proceeding anyway."
      exit 0
    EOT
  }
}

# App Runner Service (combined frontend + backend)
resource "aws_apprunner_service" "backend" {
  count = var.enable_apprunner ? 1 : 0

  service_name = "${var.project_name}-${var.environment}-backend"

  source_configuration {
    authentication_configuration {
      access_role_arn = aws_iam_role.app_runner_ecr_access[0].arn
    }

    image_repository {
      image_identifier      = "${aws_ecr_repository.backend.repository_url}:${local.combined_image_tag}"
      image_repository_type = "ECR"

      image_configuration {
        port = "8080"

        runtime_environment_variables = {
          AWS_REGION             = var.aws_region
          BOND_PROVIDER_CLASS    = "bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider"
          DATABASE_SECRET_ARN    = aws_secretsmanager_secret.db_credentials.arn
          S3_BUCKET_NAME         = aws_s3_bucket.uploads.id
          BEDROCK_AGENT_ROLE_ARN = aws_iam_role.bedrock_agent.arn
          BEDROCK_DEFAULT_MODEL      = var.bedrock_default_model
          BEDROCK_SELECTABLE_MODELS  = var.bedrock_selectable_models

          # App config secret (JWT key, OAuth client IDs/secrets read at runtime)
          APP_CONFIG_SECRET_NAME = aws_secretsmanager_secret.app_config.name

          # Okta OAuth Configuration
          OAUTH2_ENABLED_PROVIDERS = var.oauth2_providers
          OKTA_DOMAIN              = var.okta_domain
          OKTA_SECRET_NAME         = var.okta_secret_name
          OKTA_REDIRECT_URI = var.okta_redirect_uri != "" ? var.okta_redirect_uri : "https://BACKEND_URL_PLACEHOLDER/auth/okta/callback"
          OKTA_SCOPES       = var.okta_scopes

          # AWS Cognito OAuth Configuration (only if configured)
          COGNITO_DOMAIN       = var.cognito_domain
          COGNITO_SECRET_NAME  = var.cognito_secret_name
          COGNITO_REDIRECT_URI = var.cognito_redirect_uri != "" ? var.cognito_redirect_uri : (var.cognito_domain != "" ? "https://BACKEND_URL_PLACEHOLDER/auth/cognito/callback" : "")
          COGNITO_SCOPES       = var.cognito_scopes
          COGNITO_REGION       = var.cognito_region

          # JWT redirect URI for frontend - same origin now (root of the service)
          JWT_REDIRECT_URI = var.jwt_redirect_uri != "" ? var.jwt_redirect_uri : "*"

          # CORS configuration - keep for local dev compatibility
          CORS_ALLOWED_ORIGINS = var.cors_allowed_origins

          # Allowed redirect domains for OAuth callbacks (security)
          # Localhost and *.awsapprunner.com are always allowed by default
          ALLOWED_REDIRECT_DOMAINS = var.allowed_redirect_domains

          # Knowledge Base configuration (only set when KB is enabled)
          BEDROCK_KNOWLEDGE_BASE_ID = try(aws_bedrockagent_knowledge_base.main[0].id, "")
          BEDROCK_KB_DATA_SOURCE_ID = try(aws_bedrockagent_data_source.s3[0].data_source_id, "")
          BEDROCK_KB_S3_PREFIX      = var.enable_knowledge_base ? "knowledge-base/" : ""

          # Admin configuration (prefer ADMIN_USERS for multiple admins)
          ADMIN_USERS = var.admin_users
          ADMIN_EMAIL = var.admin_email  # Legacy fallback for backward compatibility

          # Email validation: allow all authenticated IdP users (T-O6)
          # Set to "true" when IdP app assignment controls access (e.g., Okta groups)
          # Set to "false" and configure *_VALID_EMAILS to restrict by email list
          ALLOW_ALL_EMAILS = var.allow_all_emails

          # Cookie security: "true" in production (HTTPS), "false" for local dev (HTTP)
          COOKIE_SECURE = "true"
        }
      }
    }
  }

  # Network configuration with VPC connector
  network_configuration {
    ingress_configuration {
      is_publicly_accessible = var.backend_is_private ? false : true
    }

    egress_configuration {
      egress_type       = "VPC"
      vpc_connector_arn = aws_apprunner_vpc_connector.backend.arn
    }
  }

  instance_configuration {
    cpu               = "1 vCPU"
    memory            = "2 GB"
    instance_role_arn = aws_iam_role.app_runner_instance[0].arn
  }

  auto_scaling_configuration_arn = aws_apprunner_auto_scaling_configuration_version.backend[0].arn

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
    null_resource.wait_for_backend_auto_deploy,
    aws_secretsmanager_secret_version.db_credentials,
    null_resource.private_ingress_ready  # VPC endpoint must exist before going private
  ]
  # Note: Database dependency handled via local.database_endpoint
}

moved {
  from = aws_apprunner_service.backend
  to   = aws_apprunner_service.backend[0]
}

# Wait for App Runner backend to reach RUNNING status before dependent resources proceed
# This prevents race conditions where WAF/other resources try to update while deploying
resource "null_resource" "wait_for_backend_ready" {
  count = var.enable_apprunner ? 1 : 0

  depends_on = [aws_apprunner_service.backend]

  triggers = {
    # Re-trigger when the backend service changes
    service_arn = aws_apprunner_service.backend[0].arn
  }

  provisioner "local-exec" {
    command = <<-EOT
      echo "Waiting for App Runner backend service to be ready..."
      SERVICE_ARN="${aws_apprunner_service.backend[0].arn}"
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

moved {
  from = null_resource.wait_for_backend_auto_deploy
  to   = null_resource.wait_for_backend_auto_deploy[0]
}

moved {
  from = null_resource.wait_for_backend_ready
  to   = null_resource.wait_for_backend_ready[0]
}
