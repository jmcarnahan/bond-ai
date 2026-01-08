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

  tags = {
    Name = "${var.project_name}-${var.environment}-aurora-params"
  }
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

  name       = "${var.project_name}-${var.environment}-aurora-subnet"
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

  engine             = "aurora-postgresql"
  engine_mode        = "provisioned"
  engine_version     = "15.12"

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
