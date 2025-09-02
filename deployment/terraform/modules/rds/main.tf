# RDS PostgreSQL Module for Bond AI

locals {
  common_tags = merge(
    var.tags,
    {
      Environment = var.environment
      Project     = var.project_name
      ManagedBy   = "Terraform"
    }
  )
  
  db_identifier = "${var.project_name}-${var.environment}-db"
}

# Generate random password for database
resource "random_password" "db_password" {
  length  = 32
  special = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# Store database credentials in Secrets Manager
resource "aws_secretsmanager_secret" "db_credentials" {
  name_prefix = "${var.project_name}-${var.environment}-db-credentials-"
  description = "RDS PostgreSQL credentials for ${var.project_name} ${var.environment}"

  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.db_password.result
    engine   = "postgres"
    host     = aws_db_instance.main.address
    port     = var.db_port
    dbname   = var.db_name
    endpoint = aws_db_instance.main.endpoint
  })
}

# Security Group for RDS
resource "aws_security_group" "rds" {
  name_prefix = "${local.db_identifier}-sg-"
  description = "Security group for RDS PostgreSQL instance"
  vpc_id      = var.vpc_id

  tags = merge(
    local.common_tags,
    {
      Name = "${local.db_identifier}-sg"
    }
  )
}

# Security Group Rules
resource "aws_security_group_rule" "rds_ingress_security_groups" {
  count = length(var.allowed_security_group_ids)

  type                     = "ingress"
  from_port                = var.db_port
  to_port                  = var.db_port
  protocol                 = "tcp"
  source_security_group_id = var.allowed_security_group_ids[count.index]
  security_group_id        = aws_security_group.rds.id
  description              = "PostgreSQL access from security group"
}

resource "aws_security_group_rule" "rds_ingress_cidr" {
  count = length(var.allowed_cidr_blocks)

  type              = "ingress"
  from_port         = var.db_port
  to_port           = var.db_port
  protocol          = "tcp"
  cidr_blocks       = [var.allowed_cidr_blocks[count.index]]
  security_group_id = aws_security_group.rds.id
  description       = "PostgreSQL access from CIDR block"
}

resource "aws_security_group_rule" "rds_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.rds.id
  description       = "Allow all outbound traffic"
}

# DB Subnet Group
resource "aws_db_subnet_group" "main" {
  name_prefix = "${local.db_identifier}-subnet-group-"
  description = "Subnet group for ${local.db_identifier}"
  subnet_ids  = var.database_subnet_ids

  tags = merge(
    local.common_tags,
    {
      Name = "${local.db_identifier}-subnet-group"
    }
  )
}

# DB Parameter Group
resource "aws_db_parameter_group" "main" {
  name_prefix = "${local.db_identifier}-params-"
  family      = var.db_parameter_family
  description = "Custom parameter group for ${local.db_identifier}"

  dynamic "parameter" {
    for_each = var.db_parameters
    content {
      name  = parameter.key
      value = parameter.value
    }
  }

  tags = local.common_tags
}

# CloudWatch Log Group for RDS logs
resource "aws_cloudwatch_log_group" "rds" {
  count = length(var.db_enabled_cloudwatch_logs_exports) > 0 ? 1 : 0

  name              = "/aws/rds/instance/${local.db_identifier}/postgresql"
  retention_in_days = 30

  tags = local.common_tags
}

# IAM Role for Enhanced Monitoring
resource "aws_iam_role" "enhanced_monitoring" {
  count = var.db_monitoring_interval > 0 ? 1 : 0

  name_prefix = "${local.db_identifier}-monitoring-role-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "enhanced_monitoring" {
  count = var.db_monitoring_interval > 0 ? 1 : 0

  role       = aws_iam_role.enhanced_monitoring[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# KMS Key for encryption
resource "aws_kms_key" "rds" {
  count = var.db_storage_encrypted ? 1 : 0

  description             = "KMS key for ${local.db_identifier} encryption"
  deletion_window_in_days = 10
  enable_key_rotation     = true

  tags = merge(
    local.common_tags,
    {
      Name = "${local.db_identifier}-kms-key"
    }
  )
}

resource "aws_kms_alias" "rds" {
  count = var.db_storage_encrypted ? 1 : 0

  name          = "alias/${local.db_identifier}"
  target_key_id = aws_kms_key.rds[0].key_id
}

# RDS Instance
resource "aws_db_instance" "main" {
  identifier = local.db_identifier

  # Engine configuration
  engine         = "postgres"
  engine_version = var.db_engine_version

  # Instance configuration
  instance_class = var.db_instance_class

  # Storage configuration
  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_max_allocated_storage
  storage_type          = var.db_storage_type
  storage_encrypted     = var.db_storage_encrypted
  kms_key_id           = var.db_storage_encrypted ? aws_kms_key.rds[0].arn : null
  iops                 = var.db_storage_type == "gp3" || var.db_storage_type == "io1" ? var.db_iops : null
  storage_throughput   = var.db_storage_type == "gp3" ? var.db_storage_throughput : null

  # Database configuration
  db_name  = var.db_name
  username = var.db_username
  password = random_password.db_password.result
  port     = var.db_port

  # Network configuration
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false

  # High Availability
  multi_az = var.db_multi_az

  # Backup configuration
  backup_retention_period   = var.db_backup_retention_period
  backup_window            = var.db_backup_window
  maintenance_window       = var.db_maintenance_window
  copy_tags_to_snapshot    = var.db_copy_tags_to_snapshot
  delete_automated_backups = var.db_delete_automated_backups
  skip_final_snapshot      = var.db_skip_final_snapshot
  final_snapshot_identifier = var.db_skip_final_snapshot ? null : "${local.db_identifier}-final-snapshot-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"

  # Monitoring
  enabled_cloudwatch_logs_exports = var.db_enabled_cloudwatch_logs_exports
  performance_insights_enabled    = var.db_performance_insights_enabled
  performance_insights_retention_period = var.db_performance_insights_enabled ? var.db_performance_insights_retention_period : null
  monitoring_interval = var.db_monitoring_interval
  monitoring_role_arn = var.db_monitoring_interval > 0 ? aws_iam_role.enhanced_monitoring[0].arn : null

  # Parameters
  parameter_group_name = aws_db_parameter_group.main.name

  # Security and maintenance
  deletion_protection          = var.db_deletion_protection
  auto_minor_version_upgrade   = var.db_auto_minor_version_upgrade
  apply_immediately           = var.db_apply_immediately

  tags = merge(
    local.common_tags,
    {
      Name = local.db_identifier
    }
  )

  depends_on = [
    aws_cloudwatch_log_group.rds
  ]
}

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "database_cpu" {
  alarm_name          = "${local.db_identifier}-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors RDS CPU utilization"
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "database_storage" {
  alarm_name          = "${local.db_identifier}-low-storage"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "10737418240" # 10GB in bytes
  alarm_description   = "This metric monitors RDS free storage"
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "database_connections" {
  alarm_name          = "${local.db_identifier}-high-connections"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors RDS connection count"
  treat_missing_data  = "notBreaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }

  tags = local.common_tags
}