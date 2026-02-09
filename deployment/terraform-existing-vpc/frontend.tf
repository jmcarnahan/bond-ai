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

# Wait for App Runner to finish any auto-deployment triggered by the ECR image push.
resource "null_resource" "wait_for_frontend_auto_deploy" {
  depends_on = [null_resource.build_frontend_image]

  triggers = {
    build_id = null_resource.build_frontend_image.id
  }

  provisioner "local-exec" {
    command = <<-EOT
      echo "Waiting for App Runner frontend to finish any auto-deployment..."
      SERVICE_NAME="bond-ai-${var.environment}-frontend"

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
          echo "✓ Frontend service is RUNNING — safe to proceed with Terraform update."
          exit 0
        fi

        echo "Frontend status: $STATUS (attempt $((ATTEMPT+1))/$MAX_ATTEMPTS, waiting 10s...)"
        ATTEMPT=$((ATTEMPT+1))
        sleep 10
      done

      echo "Warning: Frontend did not reach RUNNING within timeout. Proceeding anyway."
      exit 0
    EOT
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
          # API URL is baked into Docker image during build via --dart-define
          # This env var is for reference only (Flutter doesn't read runtime env vars)
          API_BASE_URL = var.backend_service_url != "" ? var.backend_service_url : "https://PLACEHOLDER"
        }
      }
    }

    # Auto deploy when image updates in ECR
    auto_deployments_enabled = true
  }

  instance_configuration {
    cpu               = "0.25 vCPU"
    memory            = "0.5 GB"
    instance_role_arn = aws_iam_role.frontend_apprunner_instance.arn
  }

  auto_scaling_configuration_arn = aws_apprunner_auto_scaling_configuration_version.frontend.arn

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
    null_resource.wait_for_frontend_auto_deploy
    # Backend dependency removed - using var.backend_service_url from tfvars
  ]

  # Lifecycle rules to prevent accidental recreation
  lifecycle {
    create_before_destroy = false
    ignore_changes = [
      source_configuration[0].image_repository[0].image_configuration[0].runtime_environment_variables["API_BASE_URL"]
    ]
  }
}
