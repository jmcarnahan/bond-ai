# ============================================================================
# MCP Atlassian Server Deployment
# ============================================================================
# This file deploys an MCP Atlassian server to AWS App Runner as a private
# VPC-only service. The ghcr.io image is mirrored to ECR since App Runner
# doesn't support GitHub Container Registry directly.
#
# Usage:
#   1. Store OAuth client secret in AWS Secrets Manager:
#      aws secretsmanager create-secret \
#        --name bond-ai-dev-mcp-atlassian-oauth \
#        --secret-string '{"client_secret":"YOUR_SECRET"}' \
#        --region us-east-1
#
#   2. Create tfvars file based on environments/mcp-atlassian.example.tfvars
#
#   3. Deploy with:
#      terraform apply -var-file=environments/example.tfvars \
#                      -var-file=environments/mcp-atlassian.example.tfvars
# ============================================================================

# -----------------------------------------------------------------------------
# Variables (self-contained - no changes to variables.tf required)
# -----------------------------------------------------------------------------

variable "mcp_atlassian_enabled" {
  description = "Enable MCP Atlassian deployment"
  type        = bool
  default     = false
}

variable "mcp_atlassian_oauth_cloud_id" {
  description = "Atlassian Cloud ID (required when enabled)"
  type        = string
  default     = ""
}

variable "mcp_atlassian_oauth_client_id" {
  description = "Atlassian OAuth app client ID (required when enabled)"
  type        = string
  default     = ""
}

variable "mcp_atlassian_oauth_secret_name" {
  description = "AWS Secrets Manager secret name containing OAuth client_secret (required when enabled)"
  type        = string
  default     = ""
}

variable "mcp_atlassian_oauth_scopes" {
  description = "OAuth scopes for Atlassian APIs"
  type        = string
  default     = "read:jira-user read:jira-work write:jira-work read:confluence-space.summary write:confluence-content offline_access"
}

variable "mcp_atlassian_logging_level" {
  description = "MCP server logging level"
  type        = string
  default     = "INFO"
}

variable "mcp_atlassian_cpu" {
  description = "CPU allocation for MCP Atlassian service"
  type        = string
  default     = "0.25 vCPU"
}

variable "mcp_atlassian_memory" {
  description = "Memory allocation for MCP Atlassian service"
  type        = string
  default     = "0.5 GB"
}

# -----------------------------------------------------------------------------
# Locals - Computed values
# -----------------------------------------------------------------------------

locals {
  # Only deploy if enabled and required variables are set
  mcp_atlassian_can_deploy = (
    var.mcp_atlassian_enabled &&
    var.mcp_atlassian_oauth_cloud_id != "" &&
    var.mcp_atlassian_oauth_client_id != "" &&
    var.mcp_atlassian_oauth_secret_name != ""
  )

  # Compute Atlassian API URLs from cloud_id
  mcp_atlassian_jira_url       = "https://api.atlassian.com/ex/jira/${var.mcp_atlassian_oauth_cloud_id}"
  mcp_atlassian_confluence_url = "https://api.atlassian.com/ex/confluence/${var.mcp_atlassian_oauth_cloud_id}"
}

# -----------------------------------------------------------------------------
# Data Source: Retrieve OAuth Secret from AWS Secrets Manager
# -----------------------------------------------------------------------------

data "aws_secretsmanager_secret" "mcp_atlassian_oauth" {
  count = local.mcp_atlassian_can_deploy ? 1 : 0
  name  = var.mcp_atlassian_oauth_secret_name
}

data "aws_secretsmanager_secret_version" "mcp_atlassian_oauth" {
  count     = local.mcp_atlassian_can_deploy ? 1 : 0
  secret_id = data.aws_secretsmanager_secret.mcp_atlassian_oauth[0].id
}

# -----------------------------------------------------------------------------
# ECR Repository for MCP Atlassian Image
# -----------------------------------------------------------------------------

resource "aws_ecr_repository" "mcp_atlassian" {
  count = local.mcp_atlassian_can_deploy ? 1 : 0
  name  = "${var.project_name}-${var.environment}-mcp-atlassian"

  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-mcp-atlassian"
  }
}

# ECR Lifecycle Policy - keep last 5 images
resource "aws_ecr_lifecycle_policy" "mcp_atlassian" {
  count      = local.mcp_atlassian_can_deploy ? 1 : 0
  repository = aws_ecr_repository.mcp_atlassian[0].name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 5 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# ECR Repository Policy - allow App Runner to pull
resource "aws_ecr_repository_policy" "mcp_atlassian" {
  count      = local.mcp_atlassian_can_deploy ? 1 : 0
  repository = aws_ecr_repository.mcp_atlassian[0].name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowAppRunnerPull"
        Effect = "Allow"
        Principal = {
          Service = "build.apprunner.amazonaws.com"
        }
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:DescribeImages",
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability"
        ]
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# Image Mirroring - Pull from ghcr.io and push to ECR
# -----------------------------------------------------------------------------

resource "null_resource" "mirror_mcp_atlassian_image" {
  count = local.mcp_atlassian_can_deploy ? 1 : 0

  depends_on = [
    aws_ecr_repository.mcp_atlassian,
    aws_ecr_repository_policy.mcp_atlassian
  ]

  triggers = {
    always_run = timestamp()
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      echo "Mirroring MCP Atlassian image from ghcr.io to ECR..."

      # Verify Docker is running
      if ! docker info > /dev/null 2>&1; then
        echo "Error: Docker daemon is not running"
        exit 1
      fi

      # Login to ECR
      echo "Authenticating with ECR..."
      aws ecr get-login-password --region ${var.aws_region} | \
        docker login --username AWS --password-stdin ${aws_ecr_repository.mcp_atlassian[0].repository_url}

      # Pull from ghcr.io
      echo "Pulling image from ghcr.io/sooperset/mcp-atlassian:latest..."
      docker pull ghcr.io/sooperset/mcp-atlassian:latest

      # Tag for ECR
      echo "Tagging image for ECR..."
      docker tag ghcr.io/sooperset/mcp-atlassian:latest \
        ${aws_ecr_repository.mcp_atlassian[0].repository_url}:latest

      # Push to ECR
      echo "Pushing image to ECR..."
      docker push ${aws_ecr_repository.mcp_atlassian[0].repository_url}:latest

      # Verify image was pushed
      aws ecr describe-images \
        --repository-name ${aws_ecr_repository.mcp_atlassian[0].name} \
        --region ${var.aws_region} \
        --image-ids imageTag=latest > /dev/null 2>&1

      if [ $? -eq 0 ]; then
        echo "✓ MCP Atlassian image mirrored to ECR successfully"
      else
        echo "Error: Failed to verify image in ECR"
        exit 1
      fi
    EOT

    working_dir = "${path.module}/../.."
  }
}

# -----------------------------------------------------------------------------
# IAM Role for MCP Atlassian Instance
# -----------------------------------------------------------------------------

resource "aws_iam_role" "mcp_atlassian_instance" {
  count = local.mcp_atlassian_can_deploy ? 1 : 0
  name  = "${var.project_name}-${var.environment}-mcp-atlassian-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "tasks.apprunner.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-${var.environment}-mcp-atlassian-role"
  }
}

resource "aws_iam_role_policy" "mcp_atlassian_instance" {
  count = local.mcp_atlassian_can_deploy ? 1 : 0
  name  = "${var.project_name}-${var.environment}-mcp-atlassian-policy"
  role  = aws_iam_role.mcp_atlassian_instance[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          data.aws_secretsmanager_secret.mcp_atlassian_oauth[0].arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# App Runner Auto Scaling Configuration
# -----------------------------------------------------------------------------

resource "aws_apprunner_auto_scaling_configuration_version" "mcp_atlassian" {
  count                           = local.mcp_atlassian_can_deploy ? 1 : 0
  auto_scaling_configuration_name = "${var.project_name}-${var.environment}-mcp-atlassian-autoscaling"

  min_size = 1
  max_size = 2

  tags = {
    Name = "${var.project_name}-${var.environment}-mcp-atlassian-autoscaling"
  }
}

# -----------------------------------------------------------------------------
# App Runner Service for MCP Atlassian (Private - VPC Only)
# -----------------------------------------------------------------------------

resource "aws_apprunner_service" "mcp_atlassian" {
  count        = local.mcp_atlassian_can_deploy ? 1 : 0
  service_name = "${var.project_name}-${var.environment}-mcp-atlassian"

  source_configuration {
    authentication_configuration {
      access_role_arn = aws_iam_role.app_runner_ecr_access.arn
    }

    image_repository {
      image_identifier      = "${aws_ecr_repository.mcp_atlassian[0].repository_url}:latest"
      image_repository_type = "ECR"

      image_configuration {
        port = "8000"

        runtime_environment_variables = {
          # Atlassian API URLs - computed from cloud_id
          JIRA_URL       = local.mcp_atlassian_jira_url
          CONFLUENCE_URL = local.mcp_atlassian_confluence_url

          # OAuth Configuration
          ATLASSIAN_OAUTH_CLIENT_ID = var.mcp_atlassian_oauth_client_id
          ATLASSIAN_OAUTH_CLIENT_SECRET = jsondecode(
            data.aws_secretsmanager_secret_version.mcp_atlassian_oauth[0].secret_string
          )["client_secret"]
          ATLASSIAN_OAUTH_REDIRECT_URI = "https://${aws_apprunner_service.backend.service_url}/connections/atlassian/callback"
          ATLASSIAN_OAUTH_SCOPE        = var.mcp_atlassian_oauth_scopes
          ATLASSIAN_OAUTH_CLOUD_ID     = var.mcp_atlassian_oauth_cloud_id

          # Logging
          MCP_LOGGING_LEVEL = var.mcp_atlassian_logging_level
        }
      }
    }

    auto_deployments_enabled = false
  }

  # Network configuration - Private with VPC egress
  network_configuration {
    ingress_configuration {
      is_publicly_accessible = false
    }

    egress_configuration {
      egress_type       = "VPC"
      vpc_connector_arn = aws_apprunner_vpc_connector.backend.arn
    }
  }

  instance_configuration {
    cpu               = var.mcp_atlassian_cpu
    memory            = var.mcp_atlassian_memory
    instance_role_arn = aws_iam_role.mcp_atlassian_instance[0].arn
  }

  auto_scaling_configuration_arn = aws_apprunner_auto_scaling_configuration_version.mcp_atlassian[0].arn

  health_check_configuration {
    protocol            = "TCP"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-mcp-atlassian"
    Type = "MCP-Server"
  }

  depends_on = [
    null_resource.mirror_mcp_atlassian_image,
    aws_apprunner_service.backend
  ]
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "mcp_atlassian_service_url" {
  value       = local.mcp_atlassian_can_deploy ? "https://${aws_apprunner_service.mcp_atlassian[0].service_url}" : "Not deployed (mcp_atlassian_enabled = false)"
  description = "MCP Atlassian server URL (private - VPC access only)"
}

output "mcp_atlassian_service_arn" {
  value       = local.mcp_atlassian_can_deploy ? aws_apprunner_service.mcp_atlassian[0].arn : ""
  description = "MCP Atlassian App Runner service ARN"
}

output "mcp_atlassian_mcp_endpoint" {
  value       = local.mcp_atlassian_can_deploy ? "https://${aws_apprunner_service.mcp_atlassian[0].service_url}/mcp" : "Not deployed"
  description = "MCP endpoint URL for client configuration"
}

output "mcp_atlassian_ecr_repository" {
  value       = local.mcp_atlassian_can_deploy ? aws_ecr_repository.mcp_atlassian[0].repository_url : ""
  description = "ECR repository URL for MCP Atlassian image"
}
