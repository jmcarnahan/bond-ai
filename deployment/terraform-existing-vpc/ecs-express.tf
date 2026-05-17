# =============================================================================
# ECS Express Mode Service (Backend + Frontend)
# All resources gated by var.enable_ecs_express (default: false)
#
# ECS Express Mode auto-provisions an ALB, target groups, security groups,
# and auto-scaling policies. Uses the same combined Docker image as App Runner.
#
# Key benefit: No 2-minute timeout — ALB idle timeout configurable up to 4000s
# (set to 300s to match nginx proxy_read_timeout in nginx-combined.conf).
# =============================================================================

locals {
  # Service endpoint URL from the ECS Express ingress path
  ecs_express_backend_url = var.enable_ecs_express ? (
    try(aws_ecs_express_gateway_service.backend[0].ingress_paths[0].endpoint, "pending")
  ) : ""
}

# =============================================================================
# CloudWatch Log Group
# =============================================================================

resource "aws_cloudwatch_log_group" "ecs_express" {
  count = var.enable_ecs_express ? 1 : 0

  name              = "/ecs/${var.project_name}-${var.environment}-backend"
  retention_in_days = 30

  tags = {
    Name = "${var.project_name}-${var.environment}-ecs-express-logs"
  }
}

# =============================================================================
# ECS Express Gateway Service
# =============================================================================

resource "aws_ecs_express_gateway_service" "backend" {
  count = var.enable_ecs_express ? 1 : 0

  service_name            = "${var.project_name}-${var.environment}-pub-backend"
  health_check_path       = "/health"
  execution_role_arn      = aws_iam_role.ecs_express_execution[0].arn
  infrastructure_role_arn = aws_iam_role.ecs_express_infrastructure[0].arn
  task_role_arn           = aws_iam_role.ecs_express_task[0].arn

  # Match current App Runner instance size: 1 vCPU, 2 GB
  cpu    = "1024"
  memory = "2048"

  primary_container {
    image          = "${aws_ecr_repository.backend.repository_url}:${local.combined_image_tag}"
    container_port = 8080

    aws_logs_configuration {
      log_group         = aws_cloudwatch_log_group.ecs_express[0].name
      log_stream_prefix = "backend"
    }

    # Environment variables — same as App Runner (shared via local.backend_env_vars)
    dynamic "environment" {
      for_each = local.backend_env_vars
      content {
        name  = environment.key
        value = environment.value
      }
    }
  }

  network_configuration {
    subnets         = local.ecs_express_subnet_ids
    security_groups = [aws_security_group.app_runner.id]
  }

  scaling_target {
    min_task_count            = 1
    max_task_count            = var.environment == "prod" ? 10 : 2
    auto_scaling_metric       = "AVERAGE_CPU"
    auto_scaling_target_value = 70
  }

  # Wait for deployment to complete before Terraform proceeds.
  # Ensures ALB, DNS, and tasks are fully ready for validation.
  wait_for_steady_state = true

  # ECS Express auto-creates and injects its own ALB security group into
  # network_configuration.security_groups. This causes a provider bug where
  # Terraform sees a mismatch between planned (1 SG) and actual (2 SGs).
  # Ignoring this field prevents the inconsistent result error.
  lifecycle {
    ignore_changes = [network_configuration]
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-ecs-express-backend"
  }

  depends_on = [
    null_resource.build_combined_image,
    aws_secretsmanager_secret_version.db_credentials,
  ]

  timeouts {
    create = "30m"
    update = "30m"
    delete = "20m"
  }
}

# =============================================================================
# ALB Configuration (Phase 2 — after first deploy)
#
# ECS Express auto-creates an ALB. On the first deploy, we discover and
# configure it via CLI in the validation script. For Terraform-managed
# resources (WAF, Route53), set ecs_express_configure_alb = true on the
# second apply after verifying the service is running.
#
# Key benefit: ALB idle timeout set to 300s (matches nginx proxy_read_timeout).
# This is the primary improvement over App Runner's 2-minute enforced timeout.
# =============================================================================

# Look up the auto-created ALB — only after ecs_express_configure_alb is enabled
data "aws_lb" "ecs_express" {
  count = var.enable_ecs_express && var.ecs_express_configure_alb ? 1 : 0

  # ECS Express shares ALBs across services in the same VPC.
  # The Name tag reflects whichever service created the ALB first.
  # Filter on AmazonECSManaged only since there's one shared ALB per VPC.
  tags = {
    "AmazonECSManaged" = "true"
  }
}

locals {
  ecs_express_alb_arn      = var.enable_ecs_express && var.ecs_express_configure_alb ? data.aws_lb.ecs_express[0].arn : ""
  ecs_express_alb_dns_name = var.enable_ecs_express && var.ecs_express_configure_alb ? data.aws_lb.ecs_express[0].dns_name : ""
  ecs_express_alb_zone_id  = var.enable_ecs_express && var.ecs_express_configure_alb ? data.aws_lb.ecs_express[0].zone_id : ""
  ecs_express_alb_found    = local.ecs_express_alb_arn != ""
}

# Set ALB idle timeout to 300s on every apply to prevent drift.
# ECS Express updates can reset the timeout to the default 60s.
resource "null_resource" "ecs_express_alb_timeout" {
  count = var.enable_ecs_express && var.ecs_express_configure_alb ? 1 : 0

  triggers = {
    # Re-run on every apply to ensure timeout stays at 300s
    always_run = timestamp()
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      ALB_ARN="${data.aws_lb.ecs_express[0].arn}"

      CURRENT=$(aws elbv2 describe-load-balancer-attributes \
        --load-balancer-arn "$ALB_ARN" \
        --region ${var.aws_region} \
        --query "Attributes[?Key=='idle_timeout.timeout_seconds'].Value | [0]" \
        --output text 2>/dev/null || echo "unknown")

      if [ "$CURRENT" = "300" ]; then
        echo "ALB idle timeout already 300s — no change needed"
      else
        echo "ALB idle timeout is $${CURRENT}s — setting to 300s..."
        aws elbv2 modify-load-balancer-attributes \
          --load-balancer-arn "$ALB_ARN" \
          --attributes Key=idle_timeout.timeout_seconds,Value=300 \
          --region ${var.aws_region} \
          --output text
        echo "ALB idle timeout set to 300s (matches nginx proxy_read_timeout)"
      fi
    EOT
  }
}
