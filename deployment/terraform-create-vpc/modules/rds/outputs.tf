output "db_instance_id" {
  description = "ID of the RDS instance"
  value       = aws_db_instance.main.id
}

output "db_instance_arn" {
  description = "ARN of the RDS instance"
  value       = aws_db_instance.main.arn
}

output "db_instance_endpoint" {
  description = "Connection endpoint for the RDS instance"
  value       = aws_db_instance.main.endpoint
}

output "db_instance_address" {
  description = "Address of the RDS instance"
  value       = aws_db_instance.main.address
}

output "db_instance_port" {
  description = "Port of the RDS instance"
  value       = aws_db_instance.main.port
}

output "db_name" {
  description = "Name of the default database"
  value       = aws_db_instance.main.db_name
}

output "db_username" {
  description = "Master username for the database"
  value       = aws_db_instance.main.username
  sensitive   = true
}

output "db_security_group_id" {
  description = "ID of the security group for RDS"
  value       = aws_security_group.rds.id
}

output "db_subnet_group_name" {
  description = "Name of the DB subnet group"
  value       = aws_db_subnet_group.main.name
}

output "db_parameter_group_name" {
  description = "Name of the DB parameter group"
  value       = aws_db_parameter_group.main.name
}

output "db_credentials_secret_arn" {
  description = "ARN of the Secrets Manager secret containing database credentials"
  value       = aws_secretsmanager_secret.db_credentials.arn
}

output "db_credentials_secret_name" {
  description = "Name of the Secrets Manager secret containing database credentials"
  value       = aws_secretsmanager_secret.db_credentials.name
}

output "db_kms_key_id" {
  description = "ID of the KMS key used for encryption"
  value       = var.db_storage_encrypted ? aws_kms_key.rds[0].id : null
}

output "db_kms_key_arn" {
  description = "ARN of the KMS key used for encryption"
  value       = var.db_storage_encrypted ? aws_kms_key.rds[0].arn : null
}

output "db_cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group for RDS logs"
  value       = length(var.db_enabled_cloudwatch_logs_exports) > 0 ? aws_cloudwatch_log_group.rds[0].name : null
}

output "db_monitoring_role_arn" {
  description = "ARN of the IAM role for enhanced monitoring"
  value       = var.db_monitoring_interval > 0 ? aws_iam_role.enhanced_monitoring[0].arn : null
}

output "db_connection_string" {
  description = "PostgreSQL connection string (without password)"
  value       = "postgresql://${aws_db_instance.main.username}@${aws_db_instance.main.address}:${aws_db_instance.main.port}/${aws_db_instance.main.db_name}"
  sensitive   = true
}