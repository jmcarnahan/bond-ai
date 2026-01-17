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

output "ecr_frontend_repository_url" {
  value       = aws_ecr_repository.frontend.repository_url
  description = "URL of the frontend ECR repository"
}

output "app_runner_vpc_connector_arn" {
  value       = aws_apprunner_vpc_connector.backend.arn
  description = "ARN of the App Runner VPC connector"
}

output "app_runner_service_url" {
  value       = "https://${aws_apprunner_service.backend.service_url}"
  description = "Backend App Runner service URL"
}

output "frontend_app_runner_service_url" {
  value       = "https://${aws_apprunner_service.frontend.service_url}"
  description = "Frontend App Runner service URL (auto-generated)"
}

output "jwt_secret" {
  value       = random_password.jwt_secret.result
  sensitive   = true
  description = "JWT secret key for authentication"
}

# Outputs for reuse by other projects (e.g., sbel)
output "private_subnet_ids" {
  value       = data.aws_subnets.private.ids
  description = "Private subnet IDs in the VPC"
}

output "app_runner_ecr_access_role_arn" {
  value       = aws_iam_role.app_runner_ecr_access.arn
  description = "ARN of the IAM role for App Runner ECR access"
}

output "app_runner_security_group_id" {
  value       = aws_security_group.app_runner.id
  description = "Security group ID for App Runner VPC connector"
}

output "deployment_instructions" {
  value       = <<-EOT

    Deployment Complete!

    Backend URL: https://${aws_apprunner_service.backend.service_url}
    Frontend URL: https://${aws_apprunner_service.frontend.service_url}

    Next Steps:
    1. Update Okta application with callback URL:
       https://${aws_apprunner_service.backend.service_url}/auth/okta/callback

    2. Test the deployment:
       curl https://${aws_apprunner_service.backend.service_url}/health

    3. Access the application:
       https://${aws_apprunner_service.frontend.service_url}
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

# Custom Domain Outputs
output "custom_domain_url" {
  description = "Custom domain URL for frontend (null if not configured)"
  value       = var.custom_domain_name != "" ? "https://${var.custom_domain_name}" : null
}

output "custom_domain_status" {
  description = "Custom domain certificate status (null if not configured)"
  value       = var.custom_domain_name != "" ? aws_apprunner_custom_domain_association.frontend[0].status : null
}

output "custom_domain_nameservers" {
  description = "Route 53 nameservers for custom domain (null if not configured)"
  value       = var.custom_domain_name != "" ? data.aws_route53_zone.frontend[0].name_servers : null
}
