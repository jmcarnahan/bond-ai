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
    # Force rebuild if explicitly requested
    force_rebuild = var.force_rebuild

    # Rebuild when Python code, dependencies, or Dockerfile changes
    dockerfile_hash   = filemd5("${path.module}/../Dockerfile.backend")
    requirements_hash = filemd5("${path.module}/../../requirements.txt")

    # Hash of all Python files in bondable directory
    bondable_hash = md5(join("", [
      for f in fileset("${path.module}/../../bondable", "**/*.py") :
      filemd5("${path.module}/../../bondable/${f}")
    ]))
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
# Uses var.backend_service_url from tfvars - no backend dependency needed
resource "null_resource" "build_frontend_image" {
  depends_on = [
    aws_ecr_repository.frontend,
    aws_ecr_repository_policy.frontend
    # Backend dependency removed - using var.backend_service_url from tfvars
  ]

  triggers = {
    # Force rebuild if explicitly requested
    force_rebuild = var.force_rebuild

    # Rebuild when Flutter code, dependencies, or Dockerfile changes
    dockerfile_hash = filemd5("${path.module}/../Dockerfile.frontend")
    pubspec_hash    = filemd5("${path.module}/../../flutterui/pubspec.lock")

    # Hash of all Dart source files
    lib_hash = md5(join("", [
      for f in fileset("${path.module}/../../flutterui/lib", "**/*.dart") :
      filemd5("${path.module}/../../flutterui/lib/${f}")
    ]))

    # Backend URL from tfvars (triggers rebuild if config changes)
    backend_url_config = var.backend_service_url
  }

  # Add lifecycle to ensure this completes before proceeding
  lifecycle {
    create_before_destroy = false
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e  # Exit on error
      echo "Building frontend locally and packaging in Docker..."

      # Verify Docker is running
      if ! docker info > /dev/null 2>&1; then
        echo "Error: Docker daemon is not running"
        exit 1
      fi

      # Get backend URL from tfvars (static - no waiting needed)
      BACKEND_URL="${var.backend_service_url}"

      if [ -z "$BACKEND_URL" ]; then
        echo "Error: backend_service_url not set in tfvars."
        echo "For first deployment, set backend_service_url in your tfvars file."
        echo "Get the URL after backend deploys: terraform output backend_app_runner_service_url"
        exit 1
      fi

      # Remove https:// prefix if present (URL may or may not have it)
      BACKEND_URL=$(echo "$BACKEND_URL" | sed 's|^https://||')

      echo "Backend URL: https://$BACKEND_URL (from tfvars)"

      echo "========================================="
      echo "Building Flutter web app locally..."
      echo "========================================="

      # Check if Flutter is installed
      if ! command -v flutter &> /dev/null; then
        echo "Error: Flutter is not installed or not in PATH"
        echo "Please install Flutter: https://flutter.dev/docs/get-started/install"
        exit 1
      fi

      # Build Flutter web app locally (outside Docker)
      cd flutterui

      echo "Enabling Flutter web support..."
      flutter config --enable-web --no-analytics

      echo "Getting Flutter dependencies..."
      flutter pub get

      echo "Building Flutter web app with backend URL: https://$BACKEND_URL"
      flutter build web --release \
        --no-tree-shake-icons \
        --dart-define=API_BASE_URL=https://$BACKEND_URL \
        --dart-define=ENABLE_AGENTS=true

      if [ ! -d "build/web" ]; then
        echo "Error: Flutter build failed - build/web directory not found"
        exit 1
      fi

      echo "✓ Flutter web app built successfully"

      # Go back to project root
      cd ..

      echo "========================================="
      echo "Packaging Flutter app in Docker..."
      echo "========================================="

      # Create temporary directory for Docker build context
      TEMP_BUILD_DIR=$(mktemp -d)
      echo "Using temporary build directory: $TEMP_BUILD_DIR"

      # Copy built Flutter web files to temp directory
      cp -r flutterui/build/web "$TEMP_BUILD_DIR/web"

      # Copy Dockerfile to temp directory
      cp deployment/Dockerfile.frontend "$TEMP_BUILD_DIR/Dockerfile"

      # Login to ECR
      echo "Authenticating with ECR..."
      aws ecr get-login-password --region ${var.aws_region} | \
        docker login --username AWS --password-stdin ${aws_ecr_repository.frontend.repository_url}

      # Build and push Docker image with pre-built Flutter app
      echo "Building Docker image with pre-built Flutter app..."
      cd "$TEMP_BUILD_DIR"
      docker buildx build --platform linux/amd64 \
        -t ${aws_ecr_repository.frontend.repository_url}:latest \
        --push .

      # Go back to original directory
      cd - > /dev/null

      # Clean up temp directory
      rm -rf "$TEMP_BUILD_DIR"
      echo "✓ Cleaned up temporary build directory"

      # Verify image was pushed
      aws ecr describe-images \
        --repository-name ${aws_ecr_repository.frontend.name} \
        --region ${var.aws_region} \
        --image-ids imageTag=latest > /dev/null 2>&1

      if [ $? -eq 0 ]; then
        echo "========================================="
        echo "✓ Frontend image built and pushed successfully!"
        echo "  - Flutter built locally (avoiding TLS issues)"
        echo "  - Packaged in Docker with nginx"
        echo "  - API_BASE_URL: https://$BACKEND_URL"
        echo "========================================="
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
