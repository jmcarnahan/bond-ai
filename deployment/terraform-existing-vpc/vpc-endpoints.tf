# VPC Endpoints for AWS services

# VPC Endpoint for S3 (Gateway type - FREE, no security groups needed)
# Set create_s3_vpc_endpoint = false in tfvars if your VPC already has an S3 endpoint
# Note: Only one S3 Gateway endpoint is allowed per VPC (AWS limitation)
resource "aws_vpc_endpoint" "s3" {
  count = var.create_s3_vpc_endpoint ? 1 : 0

  vpc_id            = data.aws_vpc.existing.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = concat(data.aws_route_tables.private.ids, [data.aws_route_table.main.id])

  tags = {
    Name = "${var.project_name}-${var.environment}-s3-endpoint"
  }
}

# # VPC Endpoint for Secrets Manager (Interface type)
# resource "aws_vpc_endpoint" "secretsmanager" {
#   vpc_id              = data.aws_vpc.existing.id
#   service_name        = "com.amazonaws.${var.aws_region}.secretsmanager"
#   vpc_endpoint_type   = "Interface"
#   subnet_ids          = local.vpc_endpoint_subnet_ids  # Use subnets in different AZs
#   security_group_ids  = [aws_security_group.vpc_endpoints.id]
#   private_dns_enabled = true

#   tags = {
#     Name = "${var.project_name}-${var.environment}-secretsmanager-endpoint"
#   }
# }

# # VPC Endpoint for Bedrock (Interface type)
# resource "aws_vpc_endpoint" "bedrock" {
#   vpc_id              = data.aws_vpc.existing.id
#   service_name        = "com.amazonaws.${var.aws_region}.bedrock-runtime"
#   vpc_endpoint_type   = "Interface"
#   subnet_ids          = local.vpc_endpoint_subnet_ids  # Use subnets in different AZs
#   security_group_ids  = [aws_security_group.vpc_endpoints.id]
#   private_dns_enabled = true

#   tags = {
#     Name = "${var.project_name}-${var.environment}-bedrock-endpoint"
#   }
# }

# # VPC Endpoint for CloudWatch Logs (Interface type)
# resource "aws_vpc_endpoint" "logs" {
#   vpc_id              = data.aws_vpc.existing.id
#   service_name        = "com.amazonaws.${var.aws_region}.logs"
#   vpc_endpoint_type   = "Interface"
#   subnet_ids          = local.vpc_endpoint_subnet_ids  # Use subnets in different AZs
#   security_group_ids  = [aws_security_group.vpc_endpoints.id]
#   private_dns_enabled = false  # Disabled due to existing conflicting DNS domain

#   tags = {
#     Name = "${var.project_name}-${var.environment}-logs-endpoint"
#   }
# }
