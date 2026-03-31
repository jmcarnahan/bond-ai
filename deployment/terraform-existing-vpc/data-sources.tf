# Data sources for existing VPC resources

data "aws_vpc" "existing" {
  id = var.existing_vpc_id
}

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.existing.id]
  }

  # Filter for private subnets (no public IP assignment)
  filter {
    name   = "map-public-ip-on-launch"
    values = ["false"]
  }
}

# Get details for each subnet
data "aws_subnet" "private" {
  for_each = toset(data.aws_subnets.private.ids)
  id       = each.value
}

# Get route tables
data "aws_route_tables" "private" {
  vpc_id = data.aws_vpc.existing.id

  filter {
    name   = "association.subnet-id"
    values = data.aws_subnets.private.ids
  }
}

# Get the main route table for the VPC (many subnets use this by default)
data "aws_route_table" "main" {
  vpc_id = data.aws_vpc.existing.id

  filter {
    name   = "association.main"
    values = ["true"]
  }
}

# Get availability zones from subnets
locals {
  availability_zones = distinct([for s in data.aws_subnet.private : s.availability_zone])

  # Select subnets for RDS (need at least 2 in different AZs)
  # Use explicitly provided subnet IDs if available, otherwise auto-detect
  rds_subnet_ids = length(var.rds_subnet_ids) > 0 ? var.rds_subnet_ids : [
    for az in slice(local.availability_zones, 0, min(2, length(local.availability_zones))) :
    [for s in data.aws_subnet.private : s.id if s.availability_zone == az][0]
  ]

  # Select subnets for App Runner VPC connector
  # Use explicitly provided subnet IDs if available, otherwise auto-detect
  app_runner_subnet_ids = length(var.app_runner_subnet_ids) > 0 ? var.app_runner_subnet_ids : slice(data.aws_subnets.private.ids, 0, min(3, length(data.aws_subnets.private.ids)))

  # Select subnets for VPC endpoints (need different AZs for interface endpoints)
  vpc_endpoint_subnet_ids = [
    for az in slice(local.availability_zones, 0, min(2, length(local.availability_zones))) :
    [for s in data.aws_subnet.private : s.id if s.availability_zone == az][0]
  ]

  # True if ANY App Runner service is private — drives shared infra (VPC endpoint)
  # Includes standalone private MCP services deployed outside this module
  any_service_private = var.backend_is_private || var.has_private_mcp_services
}

# Validate at least one compute platform is enabled
check "at_least_one_platform" {
  assert {
    condition     = var.enable_apprunner || var.enable_eks
    error_message = "At least one of enable_apprunner or enable_eks must be true."
  }
}

# Note: These data sources are informational only - not used in resource creation
# They help validate the VPC has required networking components
