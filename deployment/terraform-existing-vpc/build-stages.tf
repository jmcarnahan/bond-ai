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
# This needs to happen after backend is deployed to get the URL
resource "null_resource" "build_frontend_image" {
  depends_on = [
    aws_ecr_repository.frontend,
    aws_ecr_repository_policy.frontend,
    aws_apprunner_service.backend  # Frontend needs backend URL
  ]
  
  triggers = {
    always_run  = timestamp() # Force rebuild on each apply
    backend_url = aws_apprunner_service.backend.service_url
  }
  
  # Add lifecycle to ensure this completes before proceeding
  lifecycle {
    create_before_destroy = false
  }
  
  provisioner "local-exec" {
    command = <<-EOT
      set -e  # Exit on error
      echo "Building frontend Docker image..."
      
      # Verify Docker is running
      if ! docker info > /dev/null 2>&1; then
        echo "Error: Docker daemon is not running"
        exit 1
      fi
      
      # Get backend URL and wait for it to be fully operational
      BACKEND_URL="${aws_apprunner_service.backend.service_url}"
      
      if [ -z "$BACKEND_URL" ]; then
        echo "Error: Backend URL is empty. Backend service may not be deployed."
        exit 1
      fi
      
      echo "Backend URL: https://$BACKEND_URL"
      echo "Verifying backend is operational before building frontend..."
      
      # Wait for backend to be accessible
      for i in {1..30}; do
        if curl -s -o /dev/null -w "%%{http_code}" "https://$BACKEND_URL/health" | grep -q "200\|503"; then
          echo "✓ Backend is responding at https://$BACKEND_URL"
          break
        else
          echo "  Waiting for backend to be accessible (attempt $i/30)..."
          if [ "$i" -eq 30 ]; then
            echo "⚠️ Warning: Backend may not be fully operational yet"
            echo "  Continuing with frontend build anyway..."
          fi
          sleep 10
        fi
      done
      
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
        echo ""
        echo "Frontend image is ready for deployment."
        echo "The frontend App Runner service will be created next."
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