# ============================================================================
# Build Stages Configuration
# ============================================================================
# This file defines the proper build order for Docker images to ensure
# dependencies are met before services are deployed.

# Stage 1: Build backend Docker image (independent of other services)
resource "null_resource" "build_backend_image" {
  depends_on = [
    aws_ecr_repository.backend,
    aws_ecr_repository_policy.backend
  ]

  triggers = {
    always_run = timestamp() # Force rebuild on each apply
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e  # Exit on error
      echo "Building backend Docker image..."

      # Verify Docker is running
      if ! docker info > /dev/null 2>&1; then
        echo "Error: Docker daemon is not running"
        exit 1
      fi

      # Login to ECR
      echo "Authenticating with ECR..."
      aws ecr get-login-password --region ${var.aws_region} | \
        docker login --username AWS --password-stdin ${aws_ecr_repository.backend.repository_url}

      # Verify Dockerfile exists
      if [ ! -f "deployment/Dockerfile.backend" ]; then
        echo "Error: deployment/Dockerfile.backend not found"
        exit 1
      fi

      # Build and push backend
      echo "Building and pushing backend image..."
      docker buildx build --platform linux/amd64 \
        -t ${aws_ecr_repository.backend.repository_url}:latest \
        -f deployment/Dockerfile.backend --push .

      # Verify image was pushed
      aws ecr describe-images \
        --repository-name ${aws_ecr_repository.backend.name} \
        --region ${var.aws_region} \
        --image-ids imageTag=latest > /dev/null 2>&1

      if [ $? -eq 0 ]; then
        echo "✓ Backend image built and pushed successfully"
      else
        echo "Error: Failed to verify backend image in ECR"
        exit 1
      fi
    EOT

    working_dir = "${path.module}/../.."
  }

  provisioner "local-exec" {
    when    = destroy
    command = "echo 'Backend Docker image will remain in ECR for potential reuse'"
  }
}

# Stage 2: Build frontend Docker image
# This dynamically gets the backend URL from the deployed service
# to avoid creating a hard dependency that causes issues with phased deployment
resource "null_resource" "build_frontend_image" {
  depends_on = [
    aws_ecr_repository.frontend,
    aws_ecr_repository_policy.frontend
  ]

  triggers = {
    always_run  = timestamp() # Force rebuild on each apply
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e  # Exit on error
      echo "Getting backend URL from deployed service..."

      # Verify Docker is running
      if ! docker info > /dev/null 2>&1; then
        echo "Error: Docker daemon is not running"
        exit 1
      fi

      # Get backend URL from AWS
      BACKEND_URL=$(aws apprunner list-services --region ${var.aws_region} \
        --query "ServiceSummaryList[?ServiceName=='${var.project_name}-${var.environment}-backend'].ServiceUrl" \
        --output text)

      if [ -z "$BACKEND_URL" ]; then
        echo "Error: Backend service not found. Please ensure backend deployment has completed successfully."
        echo "Looking for service: ${var.project_name}-${var.environment}-backend"
        echo "Available services:"
        aws apprunner list-services --region ${var.aws_region} \
          --query "ServiceSummaryList[].ServiceName" --output text
        exit 1
      fi

      echo "Building frontend with backend URL: https://$BACKEND_URL"

      # Login to ECR
      echo "Authenticating with ECR..."
      aws ecr get-login-password --region ${var.aws_region} | \
        docker login --username AWS --password-stdin ${aws_ecr_repository.frontend.repository_url}

      # Verify Dockerfile exists
      if [ ! -f "deployment/Dockerfile.frontend" ]; then
        echo "Error: deployment/Dockerfile.frontend not found"
        exit 1
      fi

      # Build and push frontend with the backend URL
      echo "Building and pushing frontend image..."
      docker buildx build --platform linux/amd64 \
        --build-arg API_BASE_URL=https://$BACKEND_URL \
        --build-arg ENABLE_AGENTS=true \
        -t ${aws_ecr_repository.frontend.repository_url}:latest \
        -f deployment/Dockerfile.frontend --push .

      # Verify image was pushed
      aws ecr describe-images \
        --repository-name ${aws_ecr_repository.frontend.name} \
        --region ${var.aws_region} \
        --image-ids imageTag=latest > /dev/null 2>&1

      if [ $? -eq 0 ]; then
        echo "✓ Frontend image built and pushed successfully with API_BASE_URL: https://$BACKEND_URL"
      else
        echo "Error: Failed to verify frontend image in ECR"
        exit 1
      fi
    EOT

    working_dir = "${path.module}/../.."
  }

  provisioner "local-exec" {
    when    = destroy
    command = "echo 'Frontend Docker image will remain in ECR for potential reuse'"
  }
}
