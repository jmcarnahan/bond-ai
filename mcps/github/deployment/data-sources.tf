# Data sources for existing VPC resources

data "aws_caller_identity" "current" {}

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

locals {
  # Select up to 3 private subnets for App Runner VPC connector
  app_runner_subnet_ids = slice(
    data.aws_subnets.private.ids,
    0,
    min(3, length(data.aws_subnets.private.ids))
  )
}
