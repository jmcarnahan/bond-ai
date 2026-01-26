# AWS Bedrock Knowledge Base Infrastructure
# Uses Aurora PostgreSQL Serverless v2 with pgvector as vector store
# Deployed alongside existing RDS - dedicated cluster for KB vectors only
#
# References:
# - https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.VectorDB.html
# - https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-setup.html

# =============================================================================
# Variables
# =============================================================================

variable "enable_knowledge_base" {
  description = "Whether to create Knowledge Base infrastructure"
  type        = bool
  default     = true
}

variable "knowledge_base_embedding_model" {
  description = "Embedding model for Knowledge Base"
  type        = string
  default     = "amazon.titan-embed-text-v2:0"
}

variable "aurora_min_capacity" {
  description = "Minimum Aurora Serverless v2 capacity (0.5 = minimum)"
  type        = number
  default     = 0.5
}

variable "aurora_max_capacity" {
  description = "Maximum Aurora Serverless v2 capacity"
  type        = number
  default     = 2
}

# =============================================================================
# Locals
# =============================================================================

locals {
  kb_enabled = var.enable_knowledge_base
  kb_name    = "${var.project_name}-${var.environment}-kb"
  kb_prefix  = "knowledge-base/"

  # Vector dimensions for Titan Embed v2 (1024 is default, also supports 512, 256)
  vector_dimension = 1024

  # Aurora KB database settings
  aurora_kb_database = "bedrockdb"
  aurora_kb_schema   = "bedrock_integration"
  aurora_kb_table    = "bedrock_kb"
  aurora_kb_username = "postgres" # Use master user (init script + Bedrock KB access)
}

# =============================================================================
# Security Group for Aurora KB
# =============================================================================

resource "aws_security_group" "aurora_kb" {
  count = local.kb_enabled ? 1 : 0

  name_prefix = "${var.project_name}-${var.environment}-aurora-kb-"
  description = "Security group for Aurora PostgreSQL Knowledge Base cluster"
  vpc_id      = data.aws_vpc.existing.id

  # Allow PostgreSQL from App Runner security group
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app_runner.id]
    description     = "PostgreSQL from App Runner"
  }

  # Allow PostgreSQL from Bedrock (uses AWS PrivateLink internally)
  # Bedrock accesses via Data API, which goes through AWS internal network
  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.existing.cidr_block]
    description = "PostgreSQL from VPC (for Bedrock Data API)"
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
    Name = "${var.project_name}-${var.environment}-aurora-kb-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# =============================================================================
# Aurora Serverless v2 Cluster for Knowledge Base
# =============================================================================

# DB Subnet Group (reuse existing private subnets)
resource "aws_db_subnet_group" "aurora_kb" {
  count = local.kb_enabled ? 1 : 0

  name        = "${var.project_name}-${var.environment}-aurora-kb-subnet-group-v2"
  description = "Subnet group for Aurora KB cluster"
  subnet_ids  = local.rds_subnet_ids

  tags = {
    Name = "${var.project_name}-${var.environment}-aurora-kb-subnet-group"
  }
}

# Random password for Aurora KB
resource "random_password" "aurora_kb_password" {
  count = local.kb_enabled ? 1 : 0

  length  = 32
  special = false
}

# Store Aurora KB credentials in Secrets Manager (required for Bedrock KB)
resource "aws_secretsmanager_secret" "aurora_kb_credentials" {
  count = local.kb_enabled ? 1 : 0

  name_prefix = "${var.project_name}-${var.environment}-aurora-kb-"
  description = "Aurora KB credentials for Bedrock Knowledge Base"

  tags = {
    Name = "${var.project_name}-${var.environment}-aurora-kb-secret"
  }
}

resource "aws_secretsmanager_secret_version" "aurora_kb_credentials" {
  count = local.kb_enabled ? 1 : 0

  secret_id = aws_secretsmanager_secret.aurora_kb_credentials[0].id
  secret_string = jsonencode({
    username = local.aurora_kb_username
    password = random_password.aurora_kb_password[0].result
  })
}

# Aurora Serverless v2 Cluster
resource "aws_rds_cluster" "aurora_kb" {
  count = local.kb_enabled ? 1 : 0

  cluster_identifier = "${var.project_name}-${var.environment}-aurora-kb"
  engine             = "aurora-postgresql"
  engine_mode        = "provisioned"
  engine_version     = "15.12"
  database_name      = local.aurora_kb_database
  master_username    = "postgres"
  master_password    = random_password.aurora_kb_password[0].result

  db_subnet_group_name   = aws_db_subnet_group.aurora_kb[0].name
  vpc_security_group_ids = [aws_security_group.aurora_kb[0].id]

  # Enable Data API (required for Bedrock KB)
  enable_http_endpoint = true

  # Serverless v2 configuration
  serverlessv2_scaling_configuration {
    min_capacity = var.aurora_min_capacity
    max_capacity = var.aurora_max_capacity
  }

  # Storage encryption
  storage_encrypted = true

  # Backup settings
  backup_retention_period = 7
  preferred_backup_window = "03:00-04:00"

  # Skip final snapshot for dev (change for prod)
  skip_final_snapshot       = var.environment != "prod"
  final_snapshot_identifier = var.environment == "prod" ? "${var.project_name}-${var.environment}-aurora-kb-final" : null

  # Enable IAM authentication
  iam_database_authentication_enabled = true

  tags = {
    Name = "${var.project_name}-${var.environment}-aurora-kb"
  }
}

# Aurora Serverless v2 Instance
resource "aws_rds_cluster_instance" "aurora_kb" {
  count = local.kb_enabled ? 1 : 0

  identifier         = "${var.project_name}-${var.environment}-aurora-kb-instance"
  cluster_identifier = aws_rds_cluster.aurora_kb[0].id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.aurora_kb[0].engine
  engine_version     = aws_rds_cluster.aurora_kb[0].engine_version

  # Performance Insights (optional, helpful for debugging)
  performance_insights_enabled = var.environment == "prod"

  tags = {
    Name = "${var.project_name}-${var.environment}-aurora-kb-instance"
  }
}

# =============================================================================
# Initialize Aurora with pgvector extension and Bedrock schema
# Uses RDS Data API to execute SQL
# =============================================================================

# Wait for cluster to be available
resource "time_sleep" "wait_for_aurora" {
  count = local.kb_enabled ? 1 : 0

  depends_on      = [aws_rds_cluster_instance.aurora_kb]
  create_duration = "60s"
}

# Initialize database with pgvector extension and schema
resource "null_resource" "init_aurora_kb" {
  count = local.kb_enabled ? 1 : 0

  triggers = {
    cluster_id = aws_rds_cluster.aurora_kb[0].id
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      set -e

      echo "Initializing Aurora KB with pgvector extension..."

      CLUSTER_ARN="${aws_rds_cluster.aurora_kb[0].arn}"
      SECRET_ARN="${aws_secretsmanager_secret.aurora_kb_credentials[0].arn}"
      DATABASE="${local.aurora_kb_database}"
      REGION="${var.aws_region}"

      # Enable pgvector extension
      echo "Enabling pgvector extension..."
      aws rds-data execute-statement \
        --resource-arn "$CLUSTER_ARN" \
        --secret-arn "$SECRET_ARN" \
        --database "$DATABASE" \
        --sql "CREATE EXTENSION IF NOT EXISTS vector;" \
        --region "$REGION"

      # Create schema for Bedrock
      echo "Creating Bedrock schema..."
      aws rds-data execute-statement \
        --resource-arn "$CLUSTER_ARN" \
        --secret-arn "$SECRET_ARN" \
        --database "$DATABASE" \
        --sql "CREATE SCHEMA IF NOT EXISTS ${local.aurora_kb_schema};" \
        --region "$REGION"

      # Create the knowledge base table with metadata columns for filtering
      # agent_id column is required for multi-tenant filtering
      echo "Creating KB table with vector column and metadata columns..."
      aws rds-data execute-statement \
        --resource-arn "$CLUSTER_ARN" \
        --secret-arn "$SECRET_ARN" \
        --database "$DATABASE" \
        --sql "CREATE TABLE IF NOT EXISTS ${local.aurora_kb_schema}.${local.aurora_kb_table} (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          embedding vector(${local.vector_dimension}),
          chunks text,
          metadata json,
          agent_id varchar(255),
          file_id varchar(255),
          file_name varchar(500)
        );" \
        --region "$REGION"

      # Create index on agent_id for faster filtering
      echo "Creating agent_id index..."
      aws rds-data execute-statement \
        --resource-arn "$CLUSTER_ARN" \
        --secret-arn "$SECRET_ARN" \
        --database "$DATABASE" \
        --sql "CREATE INDEX IF NOT EXISTS ${local.aurora_kb_table}_agent_id_idx ON ${local.aurora_kb_schema}.${local.aurora_kb_table} (agent_id);" \
        --region "$REGION"

      # Create GIN index on chunks for text search (required by Bedrock KB)
      echo "Creating chunks text index..."
      aws rds-data execute-statement \
        --resource-arn "$CLUSTER_ARN" \
        --secret-arn "$SECRET_ARN" \
        --database "$DATABASE" \
        --sql "CREATE INDEX IF NOT EXISTS ${local.aurora_kb_table}_chunks_idx ON ${local.aurora_kb_schema}.${local.aurora_kb_table} USING gin (to_tsvector('english', chunks));" \
        --region "$REGION"

      # Create HNSW index for vector search (pgvector 0.5+)
      echo "Creating HNSW index..."
      aws rds-data execute-statement \
        --resource-arn "$CLUSTER_ARN" \
        --secret-arn "$SECRET_ARN" \
        --database "$DATABASE" \
        --sql "CREATE INDEX IF NOT EXISTS ${local.aurora_kb_table}_embedding_idx ON ${local.aurora_kb_schema}.${local.aurora_kb_table} USING hnsw (embedding vector_cosine_ops) WITH (ef_construction=256);" \
        --region "$REGION"

      echo "Aurora KB initialization complete!"
    EOT
  }

  depends_on = [time_sleep.wait_for_aurora]
}

# =============================================================================
# IAM Role for Bedrock Knowledge Base
# =============================================================================

resource "aws_iam_role" "bedrock_kb_role" {
  count = local.kb_enabled ? 1 : 0

  name = "${var.project_name}-${var.environment}-bedrock-kb-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "bedrock.amazonaws.com"
        }
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-${var.environment}-bedrock-kb-role"
  }
}

resource "aws_iam_role_policy" "bedrock_kb_policy" {
  count = local.kb_enabled ? 1 : 0

  name = "${var.project_name}-${var.environment}-bedrock-kb-policy"
  role = aws_iam_role.bedrock_kb_role[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # S3 access for knowledge base documents
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.uploads.arn,
          "${aws_s3_bucket.uploads.arn}/${local.kb_prefix}*"
        ]
      },
      # RDS Data API access for Aurora
      {
        Effect = "Allow"
        Action = [
          "rds-data:ExecuteStatement",
          "rds-data:BatchExecuteStatement"
        ]
        Resource = [aws_rds_cluster.aurora_kb[0].arn]
      },
      # RDS describe access (required for Bedrock KB to validate Aurora)
      {
        Effect = "Allow"
        Action = [
          "rds:DescribeDBClusters"
        ]
        Resource = [aws_rds_cluster.aurora_kb[0].arn]
      },
      # Secrets Manager access for Aurora credentials
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [aws_secretsmanager_secret.aurora_kb_credentials[0].arn]
      },
      # Bedrock embedding model access
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.knowledge_base_embedding_model}"
      }
    ]
  })
}

# =============================================================================
# Bedrock Knowledge Base
# =============================================================================

resource "aws_bedrockagent_knowledge_base" "main" {
  count = local.kb_enabled ? 1 : 0

  name     = local.kb_name
  role_arn = aws_iam_role.bedrock_kb_role[0].arn

  knowledge_base_configuration {
    type = "VECTOR"
    vector_knowledge_base_configuration {
      embedding_model_arn = "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.knowledge_base_embedding_model}"
    }
  }

  storage_configuration {
    type = "RDS"
    rds_configuration {
      resource_arn           = aws_rds_cluster.aurora_kb[0].arn
      credentials_secret_arn = aws_secretsmanager_secret.aurora_kb_credentials[0].arn
      database_name          = local.aurora_kb_database
      table_name             = "${local.aurora_kb_schema}.${local.aurora_kb_table}"
      field_mapping {
        primary_key_field = "id"
        vector_field      = "embedding"
        text_field        = "chunks"
        metadata_field    = "metadata"
      }
    }
  }

  tags = {
    Name = local.kb_name
  }

  depends_on = [
    null_resource.init_aurora_kb,
    aws_iam_role_policy.bedrock_kb_policy
  ]
}

# =============================================================================
# S3 Data Source for Knowledge Base
# =============================================================================

resource "aws_bedrockagent_data_source" "s3" {
  count = local.kb_enabled ? 1 : 0

  name              = "${var.project_name}-${var.environment}-kb-s3-source"
  knowledge_base_id = aws_bedrockagent_knowledge_base.main[0].id

  data_source_configuration {
    type = "S3"
    s3_configuration {
      bucket_arn         = aws_s3_bucket.uploads.arn
      inclusion_prefixes = [local.kb_prefix]
    }
  }

  vector_ingestion_configuration {
    chunking_configuration {
      chunking_strategy = "FIXED_SIZE"
      fixed_size_chunking_configuration {
        max_tokens         = 300
        overlap_percentage = 20
      }
    }
    # Note: Metadata from .metadata.json sidecar files is automatically ingested
    # No special parsing configuration needed - Bedrock KB handles this by default
  }
}

# =============================================================================
# IAM Permissions for App Runner to use Knowledge Base
# =============================================================================

resource "aws_iam_role_policy" "app_runner_knowledge_base" {
  count = local.kb_enabled ? 1 : 0

  name = "${var.project_name}-${var.environment}-apprunner-kb-policy"
  role = aws_iam_role.app_runner_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Knowledge Base retrieval
      {
        Effect = "Allow"
        Action = [
          "bedrock:Retrieve",
          "bedrock:RetrieveAndGenerate"
        ]
        Resource = [aws_bedrockagent_knowledge_base.main[0].arn]
      },
      # Ingestion job management
      {
        Effect = "Allow"
        Action = [
          "bedrock:StartIngestionJob",
          "bedrock:GetIngestionJob",
          "bedrock:ListIngestionJobs"
        ]
        Resource = ["${aws_bedrockagent_knowledge_base.main[0].arn}/datasource/*"]
      },
      # Pass role permission for KB role
      {
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = [aws_iam_role.bedrock_kb_role[0].arn]
      }
    ]
  })
}

# =============================================================================
# Outputs
# =============================================================================

output "knowledge_base_id" {
  value       = local.kb_enabled ? aws_bedrockagent_knowledge_base.main[0].id : null
  description = "Bedrock Knowledge Base ID"
}

output "knowledge_base_data_source_id" {
  value       = local.kb_enabled ? aws_bedrockagent_data_source.s3[0].data_source_id : null
  description = "Bedrock Knowledge Base Data Source ID"
}

output "knowledge_base_s3_prefix" {
  value       = local.kb_enabled ? local.kb_prefix : null
  description = "S3 prefix for Knowledge Base documents"
}

output "knowledge_base_role_arn" {
  value       = local.kb_enabled ? aws_iam_role.bedrock_kb_role[0].arn : null
  description = "ARN of the Bedrock Knowledge Base IAM role"
}

output "aurora_kb_cluster_endpoint" {
  value       = local.kb_enabled ? aws_rds_cluster.aurora_kb[0].endpoint : null
  description = "Aurora KB cluster endpoint"
  sensitive   = true
}

output "aurora_kb_cluster_arn" {
  value       = local.kb_enabled ? aws_rds_cluster.aurora_kb[0].arn : null
  description = "Aurora KB cluster ARN"
}

output "aurora_kb_secret_arn" {
  value       = local.kb_enabled ? aws_secretsmanager_secret.aurora_kb_credentials[0].arn : null
  description = "Aurora KB credentials secret ARN"
}
