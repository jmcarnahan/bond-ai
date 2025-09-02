# Frontend App Runner Service Configuration

# ECR Repository for Frontend
resource "aws_ecr_repository" "frontend" {
  name                 = "${var.project_name}-${var.environment}-frontend"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = false
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-frontend"
  }
}

# ECR Repository Policy for Frontend
resource "aws_ecr_repository_policy" "frontend" {
  repository = aws_ecr_repository.frontend.name

  policy = jsonencode({
    Version = "2008-10-17"
    Statement = [
      {
        Sid    = "AllowAppRunnerAccess"
        Effect = "Allow"
        Principal = {
          Service = "build.apprunner.amazonaws.com"
        }
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
      }
    ]
  })
}

# IAM Role for Frontend App Runner
resource "aws_iam_role" "frontend_apprunner_instance" {
  name = "${var.project_name}-${var.environment}-frontend-apprunner-instance"

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
    Name = "${var.project_name}-${var.environment}-frontend"
  }
}

# App Runner Service for Frontend
resource "aws_apprunner_service" "frontend" {
  service_name = "${var.project_name}-${var.environment}-frontend"

  source_configuration {
    image_repository {
      image_identifier      = "${aws_ecr_repository.frontend.repository_url}:latest"
      image_repository_type = "ECR"

      image_configuration {
        port = "8080"
        
        # Runtime environment variables
        runtime_environment_variables = {
          NGINX_PORT = "8080"
        }
      }
    }

    authentication_configuration {
      access_role_arn = aws_iam_role.app_runner_ecr_access.arn
    }

    auto_deployments_enabled = false
  }

  instance_configuration {
    cpu               = "0.25 vCPU"
    memory            = "0.5 GB"
    instance_role_arn = aws_iam_role.frontend_apprunner_instance.arn
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-frontend"
  }

  depends_on = [
    aws_ecr_repository_policy.frontend,
    null_resource.build_frontend_image  # Wait for Docker image to be built and pushed
  ]
}

# Outputs for Frontend
output "frontend_ecr_repository_url" {
  value = aws_ecr_repository.frontend.repository_url
}

output "frontend_app_runner_service_url" {
  value = "https://${aws_apprunner_service.frontend.service_url}"
}

output "frontend_build_command" {
  value = <<-EOT
    # Build and push frontend container
    # Note: The API_BASE_URL is passed as a build argument
    
    aws ecr get-login-password --region ${var.aws_region} | \
      docker login --username AWS --password-stdin ${aws_ecr_repository.frontend.repository_url}
    
    docker buildx build --platform linux/amd64 \
      --build-arg API_BASE_URL=https://${aws_apprunner_service.backend.service_url} \
      --build-arg ENABLE_AGENTS=true \
      -t ${aws_ecr_repository.frontend.repository_url}:latest \
      -f deployment/Dockerfile.frontend --push .
  EOT
}