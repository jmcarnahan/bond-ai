# Output values

output "vpc_id" {
  value = data.aws_vpc.existing.id
  description = "ID of the existing VPC being used"
}

output "database_endpoint" {
  value = aws_db_instance.main.endpoint
  sensitive = true
  description = "RDS database endpoint"
}

output "database_secret_arn" {
  value = aws_secretsmanager_secret.db_credentials.arn
  description = "ARN of the database credentials secret"
}

output "database_secret_name" {
  value = aws_secretsmanager_secret.db_credentials.name
  description = "Name of the database credentials secret"
}

output "database_security_group_id" {
  value = aws_security_group.rds.id
  description = "Security group ID for RDS"
}

output "s3_bucket_name" {
  value = aws_s3_bucket.uploads.id
  description = "Name of the S3 uploads bucket"
}

output "ecr_backend_repository_url" {
  value = aws_ecr_repository.backend.repository_url
  description = "URL of the backend ECR repository"
}

output "ecr_frontend_repository_url" {
  value = aws_ecr_repository.frontend.repository_url
  description = "URL of the frontend ECR repository"
}

output "app_runner_vpc_connector_arn" {
  value = aws_apprunner_vpc_connector.backend.arn
  description = "ARN of the App Runner VPC connector"
}

output "app_runner_service_url" {
  value = "https://${aws_apprunner_service.backend.service_url}"
  description = "Backend App Runner service URL"
}

output "frontend_app_runner_service_url" {
  value = "https://${aws_apprunner_service.frontend.service_url}"
  description = "Frontend App Runner service URL (auto-generated)"
}

output "frontend_url" {
  value = local.use_custom_domain ? "https://${local.frontend_fqdn}" : "https://${aws_apprunner_service.frontend.service_url}"
  description = "Frontend application URL (stable with custom domain)"
}

output "jwt_secret" {
  value       = random_password.jwt_secret.result
  sensitive   = true
  description = "JWT secret key for authentication"
}


output "deployment_instructions" {
  value = <<-EOT

    Deployment Complete!

    Backend URL: https://${aws_apprunner_service.backend.service_url}
    Frontend URL: ${local.use_custom_domain ? "https://${local.frontend_fqdn}" : "https://${aws_apprunner_service.frontend.service_url}"}

    Custom Domain: ${local.use_custom_domain ? local.frontend_fqdn : "Not configured - using auto-generated URL"}
    ${local.use_custom_domain ? "\n    ⚠️  SSL CERTIFICATE WARNING:\n    When accessing the frontend via custom domain, you'll see a certificate warning\n    because the SSL cert is for *.awsapprunner.com, not ${local.frontend_fqdn}.\n    This is expected. Accept the warning once and your browser will remember.\n" : ""}
    Next Steps:
    1. Update Okta application with callback URL:
       https://${aws_apprunner_service.backend.service_url}/auth/okta/callback

    2. Test the deployment:
       curl https://${aws_apprunner_service.backend.service_url}/health

    3. Access the application:
       ${local.use_custom_domain ? "https://${local.frontend_fqdn}" : "https://${aws_apprunner_service.frontend.service_url}"}
       ${local.use_custom_domain ? "(Accept the SSL certificate warning on first access)" : ""}
  EOT
  description = "Post-deployment instructions"
}