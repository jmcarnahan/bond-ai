# Output values

output "vpc_id" {
  value       = data.aws_vpc.existing.id
  description = "ID of the existing VPC being used"
}

output "database_endpoint" {
  value       = local.database_endpoint
  sensitive   = true
  description = "Database endpoint (RDS or Aurora depending on use_aurora)"
}

output "database_secret_arn" {
  value       = aws_secretsmanager_secret.db_credentials.arn
  description = "ARN of the database credentials secret"
}

output "database_secret_name" {
  value       = aws_secretsmanager_secret.db_credentials.name
  description = "Name of the database credentials secret"
}

output "database_security_group_id" {
  value       = var.use_aurora ? aws_security_group.aurora[0].id : aws_security_group.rds[0].id
  description = "Security group ID for database"
}

output "aurora_reader_endpoint" {
  value       = var.use_aurora ? aws_rds_cluster.aurora[0].reader_endpoint : null
  description = "Aurora cluster reader endpoint (null if using RDS)"
  sensitive   = true
}

output "use_aurora" {
  value       = var.use_aurora
  description = "Whether Aurora is being used instead of RDS"
}

output "s3_bucket_name" {
  value       = aws_s3_bucket.uploads.id
  description = "Name of the S3 uploads bucket"
}

output "ecr_backend_repository_url" {
  value       = aws_ecr_repository.backend.repository_url
  description = "URL of the backend ECR repository"
}

# =============================================================================
# App Runner leftovers still shared with external MCP deployments
# =============================================================================

output "app_runner_vpc_connector_arn" {
  value       = aws_apprunner_vpc_connector.backend.arn
  description = "ARN of the App Runner VPC connector (kept for external MCP deployments)"
}

output "jwt_secret" {
  value       = random_password.jwt_secret.result
  sensitive   = true
  description = "JWT secret key for authentication"
}

output "app_config_secret_name" {
  value       = aws_secretsmanager_secret.app_config.name
  description = "Name of the app config secret in Secrets Manager"
}

output "app_config_secret_arn" {
  value       = aws_secretsmanager_secret.app_config.arn
  description = "ARN of the app config secret in Secrets Manager"
}

# Outputs for reuse by other projects (e.g., sbel)
output "private_subnet_ids" {
  value       = data.aws_subnets.private.ids
  description = "Private subnet IDs in the VPC"
}

output "app_runner_security_group_id" {
  value       = aws_security_group.app_runner.id
  description = "Security group ID for the App Runner VPC connector (kept; referenced by DB security-group ingress rules)"
}

locals {
  # Safe version for output interpolation (never null)
  eks_url_display = local.eks_service_url != "" ? "${local.eks_service_protocol}://${local.eks_service_url}" : "DISABLED"
}

output "deployment_instructions" {
  value       = <<-EOT

    Deployment Complete!
    EKS:          ${var.enable_eks ? "${local.eks_url_display} (PRIVATE — VPN required)" : "DISABLED"}
    Primary:      ${var.primary_platform}
  EOT
  description = "Post-deployment instructions"
}

# Databricks CDC Outputs
output "aurora_replication_secret_arn" {
  value       = var.use_aurora ? aws_secretsmanager_secret.aurora_replication_credentials[0].arn : null
  description = "ARN of replication credentials secret for Databricks CDC"
}

output "aurora_replication_secret_name" {
  value       = var.use_aurora ? aws_secretsmanager_secret.aurora_replication_credentials[0].name : null
  description = "Name of replication credentials secret for Databricks CDC"
}

output "aurora_cluster_resource_id" {
  value       = var.use_aurora ? aws_rds_cluster.aurora[0].cluster_resource_id : null
  description = "Aurora cluster resource ID for IAM database authentication"
}

# =============================================================================
# EKS Outputs (conditional on enable_eks)
# =============================================================================

output "eks_cluster_name" {
  value       = var.enable_eks ? local.eks_cluster_name_effective : null
  description = "EKS cluster name (null if EKS disabled)"
}

output "eks_cluster_endpoint" {
  value       = var.enable_eks ? local.eks_provider_host : null
  description = "EKS cluster API endpoint (null if EKS disabled)"
}

output "eks_url" {
  value       = var.enable_eks ? "${local.eks_service_protocol}://${local.eks_service_url}" : null
  description = "EKS service URL — private, requires VPN (null if EKS disabled)"
}

# Deprecated: kept for backward compatibility with downstream consumers
output "eks_nlb_url" {
  value       = var.enable_eks ? "${local.eks_service_protocol}://${local.eks_service_url}" : null
  description = "Deprecated — use eks_url instead"
}

output "eks_alb_dns_name" {
  value       = var.enable_eks && var.eks_alb_dns_name != "" ? var.eks_alb_dns_name : null
  description = "Externally-managed ALB DNS name for EKS (null if not configured)"
}

output "eks_custom_domain_url" {
  value       = var.enable_eks && var.eks_custom_domain_name != "" ? "${local.eks_service_protocol}://${var.eks_custom_domain_name}" : null
  description = "EKS custom domain URL (null if not configured or EKS disabled)"
}

output "eks_kubectl_config" {
  value       = var.enable_eks ? "aws eks update-kubeconfig --name ${local.eks_cluster_name_effective} --region ${var.aws_region}" : null
  description = "Command to configure kubectl for EKS cluster (null if EKS disabled)"
}

# =============================================================================
# Platform Status
# =============================================================================

output "enable_eks" {
  value       = var.enable_eks
  description = "Whether EKS is enabled"
}

output "primary_platform" {
  value       = var.primary_platform
  description = "Which platform serves the custom domain"
}

# =============================================================================
# Deploy status (consumed by `make deploy-status`)
# =============================================================================

output "deployed_image_tag" {
  value       = local.combined_image_tag
  description = "Content-hash tag of the combined image this configuration deploys"
}

output "deployed_image_uri" {
  value       = "${aws_ecr_repository.backend.repository_url}:${local.combined_image_tag}"
  description = "Full ECR image URI this configuration deploys (compare against the running pod)"
}
