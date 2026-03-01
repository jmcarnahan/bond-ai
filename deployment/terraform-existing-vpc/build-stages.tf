# ============================================================================
# Build Stages Configuration
# ============================================================================
# This file defines the proper build order for Docker images to ensure
# dependencies are met before services are deployed.

# Content-hash image tags — deterministic from file hashes so immutable ECR repos
# get a new tag only when source actually changes.
locals {
  # force_rebuild is folded into each tag so that a forced rebuild produces a
  # distinct tag, avoiding ImageTagAlreadyExistsException on immutable repos.
  backend_image_tag = substr(md5(join("", [
    filemd5("${path.module}/../Dockerfile.backend"),
    filemd5("${path.module}/../../requirements.txt"),
    md5(join("", [
      for f in fileset("${path.module}/../../bondable", "**/*.py") :
      filemd5("${path.module}/../../bondable/${f}")
    ])),
    var.force_rebuild,
  ])), 0, 12)

  frontend_image_tag = substr(md5(join("", [
    filemd5("${path.module}/../Dockerfile.frontend"),
    filemd5("${path.module}/../../flutterui/pubspec.lock"),
    filemd5("${path.module}/../../flutterui/web/index.html"),
    md5(join("", [
      for f in fileset("${path.module}/../../flutterui/lib", "**/*.dart") :
      filemd5("${path.module}/../../flutterui/lib/${f}")
    ])),
    filemd5("${path.module}/../Dockerfile.maintenance"),
    filemd5("${path.module}/../maintenance/index.html"),
    var.maintenance_mode ? "maintenance" : "normal",
    var.maintenance_message,
    var.backend_service_url,
    var.theme_config_path,
    var.force_rebuild,
  ])), 0, 12)
}

# Stage 1: Build backend Docker image (independent of other services)
resource "null_resource" "build_backend_image" {
  depends_on = [
    aws_ecr_repository.backend,
    aws_ecr_repository_policy.backend
  ]

  triggers = {
    # Rebuild when content hash changes (covers code, deps, Dockerfile, force_rebuild)
    image_tag = local.backend_image_tag
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e  # Exit on error
      echo "Building backend Docker image (tag: ${local.backend_image_tag})..."

      # Verify Docker is running
      if ! docker info > /dev/null 2>&1; then
        echo "Error: Docker daemon is not running"
        exit 1
      fi

      # Login to ECR (use base registry URL, not repo-specific URL)
      ECR_REGISTRY="${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com"
      echo "Authenticating with ECR at $ECR_REGISTRY..."

      # Clear ALL existing credentials to prevent Keychain conflicts on macOS
      # (docker logout + security delete ensures no stale Keychain entries)
      docker logout $ECR_REGISTRY 2>/dev/null || true
      if [[ "$OSTYPE" == "darwin"* ]]; then
        while security delete-internet-password -s "$ECR_REGISTRY" 2>/dev/null; do :; done
      fi

      aws ecr get-login-password --region ${var.aws_region} | \
        docker login --username AWS --password-stdin $ECR_REGISTRY

      # Verify Dockerfile exists
      if [ ! -f "deployment/Dockerfile.backend" ]; then
        echo "Error: deployment/Dockerfile.backend not found"
        exit 1
      fi

      # Build and push backend
      echo "Building and pushing backend image..."
      docker buildx build --platform linux/amd64 \
        -t ${aws_ecr_repository.backend.repository_url}:${local.backend_image_tag} \
        -f deployment/Dockerfile.backend --push .

      # Verify image was pushed
      aws ecr describe-images \
        --repository-name ${aws_ecr_repository.backend.name} \
        --region ${var.aws_region} \
        --image-ids imageTag=${local.backend_image_tag} > /dev/null 2>&1

      if [ $? -eq 0 ]; then
        echo "✓ Backend image built and pushed successfully (tag: ${local.backend_image_tag})"
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
# Supports maintenance_mode to deploy a lightweight maintenance page instead
resource "null_resource" "build_frontend_image" {
  depends_on = [
    aws_ecr_repository.frontend,
    aws_ecr_repository_policy.frontend
    # Backend dependency removed - using var.backend_service_url from tfvars
  ]

  triggers = {
    # Rebuild when content hash changes (covers code, deps, Dockerfile, config, force_rebuild)
    image_tag = local.frontend_image_tag
  }

  # Add lifecycle to ensure this completes before proceeding
  lifecycle {
    create_before_destroy = false
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e  # Exit on error

      # Verify Docker is running
      if ! docker info > /dev/null 2>&1; then
        echo "Error: Docker daemon is not running"
        exit 1
      fi

      # Login to ECR (use base registry URL, not repo-specific URL)
      ECR_REGISTRY="${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com"
      echo "Authenticating with ECR at $ECR_REGISTRY..."

      # Clear ALL existing credentials to prevent Keychain conflicts on macOS
      # (docker logout + security delete ensures no stale Keychain entries)
      docker logout $ECR_REGISTRY 2>/dev/null || true
      if [[ "$OSTYPE" == "darwin"* ]]; then
        while security delete-internet-password -s "$ECR_REGISTRY" 2>/dev/null; do :; done
      fi

      aws ecr get-login-password --region ${var.aws_region} | \
        docker login --username AWS --password-stdin $ECR_REGISTRY

      # Check if maintenance mode is enabled
      if [ "${var.maintenance_mode}" = "true" ]; then
        echo "========================================="
        echo "MAINTENANCE MODE ENABLED"
        echo "Building lightweight maintenance page..."
        echo "========================================="

        # Derive paths from theme config
        THEME_CONFIG="flutterui/${var.theme_config_path}"
        THEME_CSS="$${THEME_CONFIG%.json}.css"

        # Verify theme config exists
        if [ ! -f "$THEME_CONFIG" ]; then
          echo "Error: Theme config not found at $THEME_CONFIG"
          exit 1
        fi

        # Verify CSS file exists (should be generated by theme generator)
        if [ ! -f "$THEME_CSS" ]; then
          echo "Error: Theme CSS not found at $THEME_CSS"
          echo "Run: cd flutterui && dart run tool/generate_theme.dart -c ${var.theme_config_path}"
          exit 1
        fi

        # Extract values from JSON using jq
        THEME_NAME=$(jq -r '.themeName' "$THEME_CONFIG")
        LOGO_PATH=$(jq -r '.logoPath' "$THEME_CONFIG")

        echo "Theme: $THEME_NAME"
        echo "Logo: $LOGO_PATH"
        echo "Message: ${var.maintenance_message}"

        # Prepare build context
        TEMP_DIR=$(mktemp -d)
        echo "Using temporary build directory: $TEMP_DIR"

        cp deployment/maintenance/index.html "$TEMP_DIR/"
        cp "$THEME_CSS" "$TEMP_DIR/maintenance_theme.css"
        cp deployment/Dockerfile.maintenance "$TEMP_DIR/Dockerfile"

        # Copy logo if it exists
        if [ -f "flutterui/assets/$LOGO_PATH" ]; then
          cp "flutterui/assets/$LOGO_PATH" "$TEMP_DIR/logo.png"
        else
          # Create a placeholder 1x1 transparent PNG if logo doesn't exist
          echo "Warning: Logo not found at flutterui/assets/$LOGO_PATH, using placeholder"
          printf '\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82' > "$TEMP_DIR/logo.png"
        fi

        # Build and push maintenance image
        cd "$TEMP_DIR"
        docker buildx build --platform linux/amd64 \
          --build-arg "MAINTENANCE_MESSAGE=${var.maintenance_message}" \
          --build-arg "THEME_NAME=$THEME_NAME" \
          -t ${aws_ecr_repository.frontend.repository_url}:${local.frontend_image_tag} \
          --push .

        cd - > /dev/null
        rm -rf "$TEMP_DIR"

        # Verify image was pushed
        aws ecr describe-images \
          --repository-name ${aws_ecr_repository.frontend.name} \
          --region ${var.aws_region} \
          --image-ids imageTag=${local.frontend_image_tag} > /dev/null 2>&1

        if [ $? -eq 0 ]; then
          echo "========================================="
          echo "✓ Maintenance page deployed successfully!"
          echo "  Theme: $THEME_NAME"
          echo "  Message: ${var.maintenance_message}"
          echo "========================================="
        else
          echo "Error: Failed to verify maintenance image in ECR"
          exit 1
        fi

      else
        # Normal frontend build (existing logic)
        echo "Building frontend locally and packaging in Docker..."

        # Get backend URL from tfvars (static - no waiting needed)
        BACKEND_URL="${var.backend_service_url}"

        if [ -z "$BACKEND_URL" ]; then
          echo "Error: backend_service_url not set in tfvars."
          echo "For first deployment, set backend_service_url in your tfvars file."
          echo "Get the URL after backend deploys: terraform output backend_app_runner_service_url"
          exit 1
        fi

        # Require https:// prefix and normalize by removing it for internal use
        if ! echo "$BACKEND_URL" | grep -qE '^https://'; then
          echo "Error: backend_service_url must start with 'https://'. Current value: $BACKEND_URL"
          echo "Update your tfvars file. Example: backend_service_url = \"https://xxx.us-west-2.awsapprunner.com\""
          exit 1
        fi
        BACKEND_URL="$${BACKEND_URL#https://}"

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

        # Build and push Docker image with pre-built Flutter app
        echo "Building Docker image with pre-built Flutter app..."
        cd "$TEMP_BUILD_DIR"
        docker buildx build --platform linux/amd64 \
          -t ${aws_ecr_repository.frontend.repository_url}:${local.frontend_image_tag} \
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
          --image-ids imageTag=${local.frontend_image_tag} > /dev/null 2>&1

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
      fi
    EOT

    working_dir = "${path.module}/../.."
  }

  provisioner "local-exec" {
    when    = destroy
    command = "echo 'Frontend Docker image will remain in ECR for potential reuse'"
  }
}
