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

output "jwt_secret" {
  value       = random_password.jwt_secret.result
  sensitive   = true
  description = "JWT secret key for authentication"
}

output "deployment_instructions" {
  value = <<-EOT
    
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