# App Runner Frontend Service

# App Runner Auto Scaling Configuration for Frontend
resource "aws_apprunner_auto_scaling_configuration_version" "frontend" {
  auto_scaling_configuration_name = "${var.project_name}-${var.environment}-frontend-autoscaling"
  
  min_size = 1
  max_size = var.environment == "prod" ? 10 : 2
  
  tags = {
    Name = "${var.project_name}-${var.environment}-frontend-autoscaling"
  }
}

# App Runner Service for Frontend
resource "aws_apprunner_service" "frontend" {
  service_name = "${var.project_name}-${var.environment}-frontend"

  source_configuration {
    authentication_configuration {
      access_role_arn = aws_iam_role.app_runner_ecr_access.arn
    }
    
    image_repository {
      image_identifier      = "${aws_ecr_repository.frontend.repository_url}:latest"
      image_repository_type = "ECR"
      
      image_configuration {
        port = "8080"
        
        runtime_environment_variables = {
          # API URL is already baked into the Docker image during build
          # This is just for reference/override if needed
          API_BASE_URL = "https://${aws_apprunner_service.backend.service_url}"
        }
      }
    }
    
    # Auto deploy when image updates
    auto_deployments_enabled = false
  }

  instance_configuration {
    cpu               = "0.25 vCPU"
    memory            = "0.5 GB"
    instance_role_arn = aws_iam_role.frontend_apprunner_instance.arn
  }

  auto_scaling_configuration_arn = aws_apprunner_auto_scaling_configuration_version.frontend.arn

  health_check_configuration {
    protocol            = "HTTP"
    path               = "/"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-frontend"
  }

  depends_on = [
    null_resource.build_frontend_image,
    aws_apprunner_service.backend  # Ensure backend exists first
  ]
  
  # Lifecycle rules to prevent accidental recreation
  lifecycle {
    create_before_destroy = false
    ignore_changes = [
      source_configuration[0].image_repository[0].image_configuration[0].runtime_environment_variables["API_BASE_URL"]
    ]
  }
}