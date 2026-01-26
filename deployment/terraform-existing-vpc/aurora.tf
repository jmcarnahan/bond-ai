# Aurora Serverless v2 PostgreSQL Cluster
# Enabled when var.use_aurora = true
#
# This file provides an alternative to RDS for the main database.
# Toggle with: use_aurora = true in your tfvars file.

# =============================================================================
# Locals
# =============================================================================

locals {
  # Use Aurora endpoint when enabled, otherwise RDS
  database_endpoint = var.use_aurora ? (
    aws_rds_cluster.aurora[0].endpoint
    ) : (
    aws_db_instance.main[0].address
  )
}

# =============================================================================
# Cluster Parameter Group for SSL
# =============================================================================

resource "aws_rds_cluster_parameter_group" "aurora" {
  count = var.use_aurora ? 1 : 0

  name        = "${var.project_name}-${var.environment}-aurora-params"
  family      = "aurora-postgresql15"
  description = "Aurora PostgreSQL cluster parameter group with SSL enforcement"

  parameter {
    name         = "rds.force_ssl"
    value        = "1"
    apply_method = "pending-reboot"
  }

  parameter {
    name         = "ssl_min_protocol_version"
    value        = "TLSv1.2"
    apply_method = "pending-reboot"
  }

  # Logical Replication for Databricks CDC (requires cluster reboot)
  parameter {
    name         = "rds.logical_replication"
    value        = "1"
    apply_method = "pending-reboot"
  }

  # Replication slot configuration
  parameter {
    name         = "max_replication_slots"
    value        = "5"
    apply_method = "pending-reboot"
  }

  parameter {
    name         = "max_wal_senders"
    value        = "5"
    apply_method = "pending-reboot"
  }

  parameter {
    name         = "max_slot_wal_keep_size"
    value        = "10240" # 10GB in MB - prevents WAL bloat
    apply_method = "pending-reboot"
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-aurora-params"
  }
}

# =============================================================================
# Replication User Credentials
# =============================================================================

# Password for Databricks replication user
resource "random_password" "aurora_replication_password" {
  count   = var.use_aurora ? 1 : 0
  length  = 32
  special = false
}

# =============================================================================
# Security Group for Aurora
# =============================================================================

resource "aws_security_group" "aurora" {
  count = var.use_aurora ? 1 : 0

  name_prefix = "${var.project_name}-${var.environment}-aurora-"
  description = "Security group for Aurora PostgreSQL cluster"
  vpc_id      = data.aws_vpc.existing.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app_runner.id]
    description     = "PostgreSQL from App Runner"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-aurora-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# =============================================================================
# DB Subnet Group for Aurora
# =============================================================================

resource "aws_db_subnet_group" "aurora" {
  count = var.use_aurora ? 1 : 0

  name       = "${var.project_name}-${var.environment}-aurora-subnet-v2"
  subnet_ids = local.rds_subnet_ids

  tags = {
    Name = "${var.project_name}-${var.environment}-aurora-subnet-group"
  }
}

# =============================================================================
# Aurora Cluster
# =============================================================================

resource "aws_rds_cluster" "aurora" {
  count = var.use_aurora ? 1 : 0

  cluster_identifier = "${var.project_name}-${var.environment}-aurora"

  engine         = "aurora-postgresql"
  engine_mode    = "provisioned"
  engine_version = "15.12"

  database_name   = "bondai"
  master_username = "bondadmin"
  master_password = random_password.db_password.result
  port            = 5432

  db_subnet_group_name            = aws_db_subnet_group.aurora[0].name
  db_cluster_parameter_group_name = aws_rds_cluster_parameter_group.aurora[0].name
  vpc_security_group_ids          = [aws_security_group.aurora[0].id]

  serverlessv2_scaling_configuration {
    min_capacity = var.aurora_main_min_capacity
    max_capacity = var.aurora_main_max_capacity
  }

  storage_encrypted = true

  # Enable Data API for Query Editor access
  enable_http_endpoint = true

  backup_retention_period = var.environment == "prod" ? 7 : 1
  preferred_backup_window = "03:00-04:00"

  skip_final_snapshot       = var.environment != "prod"
  final_snapshot_identifier = var.environment == "prod" ? "${var.project_name}-${var.environment}-aurora-final" : null

  deletion_protection = var.environment == "prod"

  tags = {
    Name = "${var.project_name}-${var.environment}-aurora"
  }
}

# =============================================================================
# Aurora Instance (Serverless v2)
# =============================================================================

resource "aws_rds_cluster_instance" "aurora" {
  count = var.use_aurora ? 1 : 0

  identifier         = "${var.project_name}-${var.environment}-aurora-instance"
  cluster_identifier = aws_rds_cluster.aurora[0].id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.aurora[0].engine
  engine_version     = aws_rds_cluster.aurora[0].engine_version

  performance_insights_enabled = var.environment == "prod"

  tags = {
    Name = "${var.project_name}-${var.environment}-aurora-instance"
  }
}

# =============================================================================
# Secrets Manager for Replication Credentials
# =============================================================================

# Store replication credentials for Databricks CDC
resource "aws_secretsmanager_secret" "aurora_replication_credentials" {
  count = var.use_aurora ? 1 : 0

  name_prefix = "${var.project_name}-${var.environment}-aurora-replication-"
  description = "Aurora PostgreSQL replication credentials for Databricks CDC"

  tags = {
    Name    = "${var.project_name}-${var.environment}-aurora-replication-creds"
    Purpose = "Databricks-CDC"
  }
}

resource "aws_secretsmanager_secret_version" "aurora_replication_credentials" {
  count = var.use_aurora ? 1 : 0

  secret_id = aws_secretsmanager_secret.aurora_replication_credentials[0].id
  secret_string = jsonencode({
    username         = "databricks_replication"
    password         = random_password.aurora_replication_password[0].result
    host             = aws_rds_cluster.aurora[0].endpoint
    port             = 5432
    dbname           = "bondai"
    slot_name        = "databricks_lakeflow_slot"
    publication_name = "databricks_publication"
  })
}
