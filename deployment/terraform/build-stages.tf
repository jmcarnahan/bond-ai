# ============================================================================
# Build Stages Configuration
# ============================================================================
# This file defines the proper build order for Docker images to ensure
# dependencies are met before services are deployed.

# Stage 1: Build backend Docker image (independent of other services)
resource "null_resource" "build_backend_image" {
  depends_on = [
    aws_ecr_repository.backend
  ]
  
  triggers = {
    always_run = timestamp() # Force rebuild on each apply
  }
  
  provisioner "local-exec" {
    command = <<-EOT
      echo "Building backend Docker image..."
      
      # Login to ECR
      aws ecr get-login-password --region ${var.aws_region} | \
        docker login --username AWS --password-stdin ${aws_ecr_repository.backend.repository_url}
      
      # Build and push backend
      docker buildx build --platform linux/amd64 \
        -t ${aws_ecr_repository.backend.repository_url}:latest \
        -f deployment/Dockerfile.backend --push .
      
      echo "Backend image built and pushed successfully"
    EOT
    
    working_dir = "${path.module}/../.."
  }
}

# Stage 2: Build frontend Docker image 
# This dynamically gets the backend URL from the deployed service
# to avoid creating a hard dependency that causes issues with phased deployment
resource "null_resource" "build_frontend_image" {
  depends_on = [
    aws_ecr_repository.frontend
  ]
  
  triggers = {
    always_run  = timestamp() # Force rebuild on each apply
  }
  
  provisioner "local-exec" {
    command = <<-EOT
      echo "Getting backend URL from deployed service..."
      
      # Get backend URL from AWS
      BACKEND_URL=$(aws apprunner list-services --region ${var.aws_region} \
        --query "ServiceSummaryList[?ServiceName=='${var.project_name}-${var.environment}-backend'].ServiceUrl" \
        --output text)
      
      if [ -z "$BACKEND_URL" ]; then
        echo "Error: Backend service not found. Please ensure Phase 2 (backend deployment) has completed successfully."
        exit 1
      fi
      
      echo "Building frontend with backend URL: https://$BACKEND_URL"
      
      # Login to ECR
      aws ecr get-login-password --region ${var.aws_region} | \
        docker login --username AWS --password-stdin ${aws_ecr_repository.frontend.repository_url}
      
      # Build and push frontend with the backend URL
      docker buildx build --platform linux/amd64 \
        --build-arg API_BASE_URL=https://$BACKEND_URL \
        --build-arg ENABLE_AGENTS=true \
        -t ${aws_ecr_repository.frontend.repository_url}:latest \
        -f deployment/Dockerfile.frontend --push .
      
      echo "Frontend image built and pushed with API_BASE_URL: https://$BACKEND_URL"
    EOT
    
    working_dir = "${path.module}/../.."
  }
}