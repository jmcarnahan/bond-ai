# KMS Keys for encryption at rest
# Used by Aurora clusters and S3 buckets

# =============================================================================
# KMS Key for RDS/Aurora Encryption
# =============================================================================

resource "aws_kms_key" "rds" {
  description             = "KMS key for RDS/Aurora encryption - ${var.project_name}-${var.environment}"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name = "${var.project_name}-${var.environment}-rds-kms"
  }
}

resource "aws_kms_alias" "rds" {
  name          = "alias/${var.project_name}-${var.environment}-rds"
  target_key_id = aws_kms_key.rds.key_id
}

# =============================================================================
# KMS Key for S3 Encryption
# =============================================================================

resource "aws_kms_key" "s3" {
  description             = "KMS key for S3 encryption - ${var.project_name}-${var.environment}"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name = "${var.project_name}-${var.environment}-s3-kms"
  }
}

resource "aws_kms_alias" "s3" {
  name          = "alias/${var.project_name}-${var.environment}-s3"
  target_key_id = aws_kms_key.s3.key_id
}
