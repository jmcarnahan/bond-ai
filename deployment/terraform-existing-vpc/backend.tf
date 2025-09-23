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
          AWS_REGION = var.aws_region
          BOND_PROVIDER_CLASS = "bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider"
          DATABASE_SECRET_ARN = aws_secretsmanager_secret.db_credentials.arn
          S3_BUCKET_NAME = aws_s3_bucket.uploads.id
          JWT_SECRET_KEY = random_password.jwt_secret.result
          BEDROCK_AGENT_ROLE_ARN = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/BondAIBedrockAgentRole"
          BEDROCK_DEFAULT_MODEL = var.bedrock_default_model
          METADATA_DB_URL = "postgresql://bondadmin:${random_password.db_password.result}@${aws_db_instance.main.address}:5432/bondai"
          
          # Okta OAuth Configuration
          OAUTH2_ENABLED_PROVIDERS = var.oauth2_providers
          OKTA_DOMAIN = var.okta_domain
          OKTA_CLIENT_ID = var.okta_client_id
          OKTA_CLIENT_SECRET = jsondecode(data.aws_secretsmanager_secret_version.okta_secret.secret_string)["client_secret"]
          # Okta redirect URI - will be dynamically set after deployment
          OKTA_REDIRECT_URI = "https://PENDING_BACKEND_URL/auth/okta/callback"  # Will be set in post-deployment update
          OKTA_SCOPES = var.okta_scopes
          
          # JWT redirect URI for frontend - using wildcard initially
          JWT_REDIRECT_URI = "*"  # Will be updated post-deployment
          
          # CORS configuration - permissive initially, will be tightened post-deployment
          CORS_ALLOWED_ORIGINS = "*"  # Wildcard CORS for initial deployment
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
    cpu               = "0.25 vCPU"
    memory            = "0.5 GB"
    instance_role_arn = aws_iam_role.app_runner_instance.arn
  }

  auto_scaling_configuration_arn = aws_apprunner_auto_scaling_configuration_version.backend.arn

  health_check_configuration {
    protocol            = "HTTP"
    path               = "/health"
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
    aws_db_instance.main,
    aws_secretsmanager_secret_version.db_credentials
  ]
}