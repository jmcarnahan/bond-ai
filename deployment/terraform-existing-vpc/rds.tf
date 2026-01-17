# RDS Database configuration for existing VPC
# Only created when use_aurora = false

# DB Subnet Group using existing subnets
resource "aws_db_subnet_group" "main" {
  count = var.use_aurora ? 0 : 1

  name       = "${var.project_name}-${var.environment}-db-subnet"
  subnet_ids = local.rds_subnet_ids

  tags = {
    Name = "${var.project_name}-${var.environment}-db-subnet-group"
  }
}

# RDS Instance
resource "aws_db_instance" "main" {
  count = var.use_aurora ? 0 : 1

  identifier = "${var.project_name}-${var.environment}-db"

  # Engine
  engine         = "postgres"
  engine_version = "15.12"

  # Instance
  instance_class = var.db_instance_class

  # Storage
  allocated_storage = var.db_allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  # Database
  db_name  = "bondai"
  username = "bondadmin"
  password = random_password.db_password.result
  port     = 5432

  # Network - Using existing VPC subnets
  db_subnet_group_name   = aws_db_subnet_group.main[0].name
  vpc_security_group_ids = [aws_security_group.rds[0].id]
  publicly_accessible    = false # Keep in private subnets

  # Backup
  backup_retention_period = var.environment == "prod" ? 7 : 1
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:00-sun:05:00"

  # Final snapshot
  skip_final_snapshot       = var.environment != "prod"
  final_snapshot_identifier = var.environment == "prod" ? "${var.project_name}-${var.environment}-final-${formatdate("YYYYMMDD-hhmm", timestamp())}" : null

  # Deletion protection for prod only
  deletion_protection = var.environment == "prod"

  # Performance Insights
  performance_insights_enabled          = var.environment == "prod"
  performance_insights_retention_period = var.environment == "prod" ? 7 : 0

  tags = {
    Name = "${var.project_name}-${var.environment}-db"
  }
}
