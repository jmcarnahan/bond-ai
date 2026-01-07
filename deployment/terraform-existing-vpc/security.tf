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

# Note: App Runner to RDS access is covered by the "allow all outbound" egress rule above.
# A separate aws_security_group_rule is not needed and causes drift.

# Security Group for VPC Interface Endpoints
resource "aws_security_group" "vpc_endpoints" {
  name_prefix = "${var.project_name}-${var.environment}-vpc-endpoints-"
  description = "Security group for VPC interface endpoints"
  vpc_id      = data.aws_vpc.existing.id

  # Allow HTTPS traffic from App Runner security group
  ingress {
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.app_runner.id]
    description     = "HTTPS from App Runner"
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
    Name = "${var.project_name}-${var.environment}-vpc-endpoints-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}
