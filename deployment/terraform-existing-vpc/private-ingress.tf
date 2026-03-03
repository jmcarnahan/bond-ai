# ============================================================================
# Private App Runner Ingress
# ============================================================================
# Shared VPC endpoint + per-service VPC Ingress Connections for private
# App Runner services. One `apprunner.requests` VPC endpoint per VPC handles
# all private services; each service gets its own ingress connection resource.
#
# Controlled by `local.any_service_private` (shared infra) and per-service
# variables like `var.backend_is_private`.
# ============================================================================

# -----------------------------------------------------------------------------
# Security Group for App Runner Requests VPC Endpoint
# -----------------------------------------------------------------------------
# Separate from aws_security_group.vpc_endpoints which only allows traffic
# from the App Runner VPC connector SG. This SG allows HTTPS from the entire
# VPC CIDR so that VPN clients (e.g. Tailscale subnet router) can reach
# private App Runner services through the VPC endpoint.

resource "aws_security_group" "apprunner_requests_endpoint" {
  count = local.any_service_private ? 1 : 0

  name_prefix = "${var.project_name}-${var.environment}-apprunner-requests-"
  description = "Security group for App Runner requests VPC endpoint (private ingress)"
  vpc_id      = data.aws_vpc.existing.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.existing.cidr_block]
    description = "HTTPS from VPC (VPN clients and internal services)"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [data.aws_vpc.existing.cidr_block]
    description = "Allow outbound within VPC"
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-apprunner-requests-endpoint"
  }
}

# -----------------------------------------------------------------------------
# VPC Interface Endpoint for App Runner Requests
# -----------------------------------------------------------------------------
# One per VPC — shared by all private App Runner services.

resource "aws_vpc_endpoint" "apprunner_requests" {
  count = local.any_service_private ? 1 : 0

  vpc_id              = data.aws_vpc.existing.id
  service_name        = "com.amazonaws.${var.aws_region}.apprunner.requests"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = false

  subnet_ids         = local.vpc_endpoint_subnet_ids
  security_group_ids = [aws_security_group.apprunner_requests_endpoint[0].id]

  tags = {
    Name = "${var.project_name}-${var.environment}-apprunner-requests"
  }
}

# -----------------------------------------------------------------------------
# Dependency Bridge
# -----------------------------------------------------------------------------
# Ensures the VPC endpoint is fully provisioned before any App Runner service
# is switched to private. Without this, Terraform could set
# is_publicly_accessible = false before the endpoint exists, causing errors.

resource "null_resource" "private_ingress_ready" {
  count = local.any_service_private ? 1 : 0

  triggers = {
    vpc_endpoint_id = aws_vpc_endpoint.apprunner_requests[0].id
  }
}

# -----------------------------------------------------------------------------
# VPC Ingress Connection — Backend
# -----------------------------------------------------------------------------
# Per-service resource that links a private App Runner service to the shared
# VPC endpoint. Provides the private domain name used to reach the service.

resource "aws_apprunner_vpc_ingress_connection" "backend" {
  count = var.backend_is_private ? 1 : 0

  name        = "${var.project_name}-${var.environment}-backend-ingress"
  service_arn = aws_apprunner_service.backend.arn

  ingress_vpc_configuration {
    vpc_id          = data.aws_vpc.existing.id
    vpc_endpoint_id = aws_vpc_endpoint.apprunner_requests[0].id
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-backend-ingress"
  }

  depends_on = [null_resource.wait_for_backend_ready]
}

# -----------------------------------------------------------------------------
# VPC Ingress Connection — Frontend
# -----------------------------------------------------------------------------
# Per-service resource that links a private App Runner service to the shared
# VPC endpoint. Provides the private domain name used to reach the service.

resource "aws_apprunner_vpc_ingress_connection" "frontend" {
  count = var.frontend_is_private ? 1 : 0

  name        = "${var.project_name}-${var.environment}-frontend-ingress"
  service_arn = aws_apprunner_service.frontend.arn

  ingress_vpc_configuration {
    vpc_id          = data.aws_vpc.existing.id
    vpc_endpoint_id = aws_vpc_endpoint.apprunner_requests[0].id
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-frontend-ingress"
  }
}
