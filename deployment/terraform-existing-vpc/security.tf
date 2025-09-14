# Security Groups for existing VPC deployment

# Security Group for RDS
resource "aws_security_group" "rds" {
  name_prefix = "${var.project_name}-${var.environment}-rds-"
  description = "Security group for RDS database"
  vpc_id      = data.aws_vpc.existing.id

  # Allow PostgreSQL from App Runner security group
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app_runner.id]
    description     = "PostgreSQL from App Runner"
  }

  # Allow all outbound
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-rds-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Security Group for App Runner VPC Connector
resource "aws_security_group" "app_runner" {
  name_prefix = "${var.project_name}-${var.environment}-apprunner-"
  description = "Security group for App Runner VPC connector"
  vpc_id      = data.aws_vpc.existing.id

  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-apprunner-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Add rule to allow App Runner to access RDS
resource "aws_security_group_rule" "app_runner_to_rds" {
  type                     = "egress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.rds.id
  security_group_id        = aws_security_group.app_runner.id
  description              = "Allow App Runner to access RDS"
}