# Simplified Main Terraform Configuration for Bond AI Infrastructure
# Start with essentials, add complexity later

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Environment = var.environment
      Project     = var.project_name
      ManagedBy   = "Terraform"
    }
  }
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Simple VPC with just the basics
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.project_name}-${var.environment}-vpc"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-${var.environment}-igw"
  }
}

# Elastic IP for NAT Gateway
resource "aws_eip" "nat" {
  domain = "vpc"
  
  tags = {
    Name = "${var.project_name}-${var.environment}-nat-eip"
  }
  
  depends_on = [aws_internet_gateway.main]
}

# NAT Gateway (placed in first public subnet)
resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id
  
  tags = {
    Name = "${var.project_name}-${var.environment}-nat"
  }
  
  depends_on = [aws_internet_gateway.main]
}

# Route table for private subnets (database subnets will use NAT)
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
  
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }
  
  tags = {
    Name = "${var.project_name}-${var.environment}-private-rt"
  }
}

# Associate database subnets with private route table
resource "aws_route_table_association" "database" {
  count = length(aws_subnet.database)
  
  subnet_id      = aws_subnet.database[count.index].id
  route_table_id = aws_route_table.private.id
}

# Public Subnets (2 for high availability)
resource "aws_subnet" "public" {
  count = 2

  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-${var.environment}-public-${count.index + 1}"
  }
}

# Database Subnets (2 required for RDS subnet group)
resource "aws_subnet" "database" {
  count = 2

  vpc_id            = aws_vpc.main.id
  cidr_block        = var.database_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name = "${var.project_name}-${var.environment}-database-${count.index + 1}"
  }
}

# Simple Route Table for Public Subnets
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-public-rt"
  }
}

# Associate Public Subnets with Route Table
resource "aws_route_table_association" "public" {
  count = length(aws_subnet.public)

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# DB Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-${var.environment}-db-subnet"
  subnet_ids = aws_subnet.database[*].id

  tags = {
    Name = "${var.project_name}-${var.environment}-db-subnet-group"
  }
}

# Security Group for RDS
resource "aws_security_group" "rds" {
  name_prefix = "${var.project_name}-${var.environment}-rds-"
  description = "Security group for RDS database"
  vpc_id      = aws_vpc.main.id

  # Allow PostgreSQL from VPC
  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "PostgreSQL from VPC"
  }

  # Allow all outbound
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-rds-sg"
  }
}

# Random password for RDS
resource "random_password" "db_password" {
  length  = 32
  special = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# Random JWT secret key
resource "random_password" "jwt_secret" {
  length  = 64
  special = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# Get Okta client secret from Secrets Manager
data "aws_secretsmanager_secret" "okta_secret" {
  name = var.okta_secret_name
}

data "aws_secretsmanager_secret_version" "okta_secret" {
  secret_id = data.aws_secretsmanager_secret.okta_secret.id
}

# Store credentials in Secrets Manager
resource "aws_secretsmanager_secret" "db_credentials" {
  name_prefix = "${var.project_name}-${var.environment}-db-"
  description = "RDS credentials for ${var.project_name} ${var.environment}"
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = "bondadmin"
    password = random_password.db_password.result
    engine   = "postgres"
    host     = aws_db_instance.main.address
    port     = 5432
    dbname   = "bondai"
  })
}

# Simple RDS Instance
resource "aws_db_instance" "main" {
  identifier = "${var.project_name}-${var.environment}-db"

  # Engine
  engine         = "postgres"
  engine_version = "15.7"
  
  # Instance
  instance_class = var.db_instance_class
  
  # Storage
  allocated_storage     = var.db_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  
  # Database
  db_name  = "bondai"
  username = "bondadmin"
  password = random_password.db_password.result
  port     = 5432
  
  # Network
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false
  
  # Backup (simplified)
  backup_retention_period = var.environment == "prod" ? 7 : 1
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"
  
  # Final snapshot
  skip_final_snapshot       = var.environment != "prod"
  final_snapshot_identifier = var.environment == "prod" ? "${var.project_name}-${var.environment}-final-${formatdate("YYYYMMDD-hhmm", timestamp())}" : null
  
  # Deletion protection for prod only
  deletion_protection = var.environment == "prod"
  
  tags = {
    Name = "${var.project_name}-${var.environment}-db"
  }
}

# S3 Bucket for file uploads
resource "aws_s3_bucket" "uploads" {
  bucket = "${var.project_name}-${var.environment}-uploads-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${var.project_name}-${var.environment}-uploads"
  }
}

# S3 Bucket Versioning
resource "aws_s3_bucket_versioning" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  
  versioning_configuration {
    status = var.environment == "prod" ? "Enabled" : "Suspended"
  }
}

# S3 Bucket Server-Side Encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# S3 Bucket Public Access Block
resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 Bucket CORS Configuration
resource "aws_s3_bucket_cors_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST", "DELETE", "HEAD"]
    allowed_origins = ["*"]  # Update with your App Runner URL later
    expose_headers  = ["ETag", "x-amz-server-side-encryption", "x-amz-request-id", "x-amz-id-2"]
    max_age_seconds = 3000
  }
}

# ECR Repository for Docker images
resource "aws_ecr_repository" "backend" {
  name = "${var.project_name}-${var.environment}-backend"
  
  image_tag_mutability = "MUTABLE"
  
  image_scanning_configuration {
    scan_on_push = true
  }
  
  tags = {
    Name = "${var.project_name}-${var.environment}-backend-ecr"
  }
}

# ECR Lifecycle Policy to keep only recent images
resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name
  
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus     = "any"
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# ECR Repository Policy to allow App Runner access
resource "aws_ecr_repository_policy" "backend" {
  repository = aws_ecr_repository.backend.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowAppRunnerPull"
        Effect = "Allow"
        Principal = {
          Service = "build.apprunner.amazonaws.com"
        }
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:DescribeImages",
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability"
        ]
      }
    ]
  })
}

# App Runner VPC Connector for database access (use private subnets)
resource "aws_apprunner_vpc_connector" "backend" {
  vpc_connector_name = "${var.project_name}-${var.environment}-connector"
  subnets            = aws_subnet.database[*].id  # Use private subnets for VPC connector
  security_groups    = [aws_security_group.app_runner.id]

  tags = {
    Name = "${var.project_name}-${var.environment}-vpc-connector"
  }
}

# Security Group for VPC Endpoints
resource "aws_security_group" "vpc_endpoints" {
  name_prefix = "${var.project_name}-${var.environment}-vpce-"
  description = "Security group for VPC Endpoints"
  vpc_id      = aws_vpc.main.id

  # Allow HTTPS from VPC
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.main.cidr_block]
  }

  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-vpce-sg"
  }
}

# VPC Gateway Endpoint for S3 (free, no ENI required)
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  
  # Associate with private route table
  route_table_ids = [aws_route_table.private.id]
  
  tags = {
    Name = "${var.project_name}-${var.environment}-s3-endpoint"
  }
}

# VPC Interface Endpoint for Bedrock Runtime
resource "aws_vpc_endpoint" "bedrock_runtime" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.bedrock-runtime"
  vpc_endpoint_type   = "Interface"
  
  # Place in database subnets (private subnets)
  subnet_ids          = aws_subnet.database[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  
  # Enable private DNS
  private_dns_enabled = true
  
  tags = {
    Name = "${var.project_name}-${var.environment}-bedrock-runtime-endpoint"
  }
}

# VPC Interface Endpoint for Bedrock (for model management)
resource "aws_vpc_endpoint" "bedrock" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.bedrock"
  vpc_endpoint_type   = "Interface"
  
  # Place in database subnets (private subnets)
  subnet_ids          = aws_subnet.database[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  
  # Enable private DNS
  private_dns_enabled = true
  
  tags = {
    Name = "${var.project_name}-${var.environment}-bedrock-endpoint"
  }
}

# Security Group for App Runner
resource "aws_security_group" "app_runner" {
  name_prefix = "${var.project_name}-${var.environment}-apprunner-"
  description = "Security group for App Runner service"
  vpc_id      = aws_vpc.main.id

  # Allow all outbound
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-apprunner-sg"
  }
}

# IAM Role for App Runner
resource "aws_iam_role" "app_runner_instance" {
  name = "${var.project_name}-${var.environment}-apprunner-instance-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = [
            "tasks.apprunner.amazonaws.com",
            "bedrock.amazonaws.com"
          ]
        }
      }
    ]
  })
}

# Attach AmazonBedrockFullAccess managed policy to App Runner instance role
resource "aws_iam_role_policy_attachment" "app_runner_bedrock_full_access" {
  role       = aws_iam_role.app_runner_instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonBedrockFullAccess"
}

# Add S3 Full Access (matching BondAIBedrockAgentRole)
resource "aws_iam_role_policy_attachment" "app_runner_s3_full_access" {
  role       = aws_iam_role.app_runner_instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

# Add CloudWatch Events Full Access (matching BondAIBedrockAgentRole)
resource "aws_iam_role_policy_attachment" "app_runner_cloudwatch_events" {
  role       = aws_iam_role.app_runner_instance.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchEventsFullAccess"
}

# Add OpenSearch Service Full Access (matching BondAIBedrockAgentRole)
resource "aws_iam_role_policy_attachment" "app_runner_opensearch" {
  role       = aws_iam_role.app_runner_instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonOpenSearchServiceFullAccess"
}

# Add PassRole policy for Bedrock Agent (critical for InvokeAgent)
resource "aws_iam_role_policy" "app_runner_pass_role" {
  name = "BondAIBedrockAgentRolePassRole"
  role = aws_iam_role.app_runner_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "iam:PassRole"
        Resource = aws_iam_role.app_runner_instance.arn
        Condition = {
          StringEquals = {
            "iam:PassedToService" = "bedrock.amazonaws.com"
          }
        }
      }
    ]
  })
}

# IAM Policy for App Runner to access AWS services
resource "aws_iam_role_policy" "app_runner_instance" {
  name = "${var.project_name}-${var.environment}-apprunner-policy"
  role = aws_iam_role.app_runner_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_secretsmanager_secret.db_credentials.arn,
          data.aws_secretsmanager_secret.okta_secret.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.uploads.arn,
          "${aws_s3_bucket.uploads.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:CreateBucket",
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetBucketLocation",
          "s3:GetBucketVersioning",
          "s3:PutBucketVersioning"
        ]
        Resource = [
          "arn:aws:s3:::bond-bedrock-files-*",
          "arn:aws:s3:::bond-bedrock-files-*/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          # Foundation Model Permissions
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
          "bedrock:ListFoundationModels",
          "bedrock:GetFoundationModel",
          "bedrock:ListProvisionedModelThroughputs",
          "bedrock:ListCustomModels",
          "bedrock:GetCustomModel",
          "bedrock:CreateModelCustomizationJob",
          "bedrock:GetModelCustomizationJob",
          "bedrock:ListModelCustomizationJobs",
          "bedrock:StopModelCustomizationJob",
          "bedrock:CreateProvisionedModelThroughput",
          "bedrock:UpdateProvisionedModelThroughput",
          "bedrock:GetProvisionedModelThroughput",
          "bedrock:DeleteProvisionedModelThroughput",
          # Model Evaluation
          "bedrock:CreateEvaluationJob",
          "bedrock:GetEvaluationJob",
          "bedrock:ListEvaluationJobs",
          "bedrock:StopEvaluationJob",
          # Guardrails
          "bedrock:CreateGuardrail",
          "bedrock:UpdateGuardrail",
          "bedrock:GetGuardrail",
          "bedrock:ListGuardrails",
          "bedrock:DeleteGuardrail",
          "bedrock:CreateGuardrailVersion",
          "bedrock:GetGuardrailVersion",
          "bedrock:ListGuardrailVersions",
          # Model Access
          "bedrock:PutFoundationModelEntitlement",
          "bedrock:GetFoundationModelAvailability"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          # Bedrock Agent Permissions
          "bedrock:CreateAgent",
          "bedrock:UpdateAgent",
          "bedrock:GetAgent",
          "bedrock:ListAgents",
          "bedrock:DeleteAgent",
          "bedrock:CreateAgentAlias",
          "bedrock:UpdateAgentAlias",
          "bedrock:GetAgentAlias",
          "bedrock:ListAgentAliases",
          "bedrock:DeleteAgentAlias",
          "bedrock:CreateAgentActionGroup",
          "bedrock:UpdateAgentActionGroup",
          "bedrock:GetAgentActionGroup",
          "bedrock:ListAgentActionGroups",
          "bedrock:DeleteAgentActionGroup",
          "bedrock:PrepareAgent",
          "bedrock:GetAgentVersion",
          "bedrock:ListAgentVersions",
          "bedrock:DeleteAgentVersion",
          "bedrock:UpdateAgentPrompt",
          "bedrock:GetAgentPrompt",
          # Knowledge Base Permissions
          "bedrock:CreateKnowledgeBase",
          "bedrock:UpdateKnowledgeBase",
          "bedrock:GetKnowledgeBase",
          "bedrock:ListKnowledgeBases",
          "bedrock:DeleteKnowledgeBase",
          "bedrock:AssociateAgentKnowledgeBase",
          "bedrock:DisassociateAgentKnowledgeBase",
          "bedrock:ListAgentKnowledgeBases",
          "bedrock:CreateDataSource",
          "bedrock:UpdateDataSource",
          "bedrock:GetDataSource",
          "bedrock:ListDataSources",
          "bedrock:DeleteDataSource",
          "bedrock:StartIngestionJob",
          "bedrock:GetIngestionJob",
          "bedrock:ListIngestionJobs",
          # Query and Retrieval
          "bedrock:QueryKnowledgeBase",
          "bedrock:Retrieve",
          "bedrock:RetrieveAndGenerate",
          # Legacy bedrock-agent permissions (for backwards compatibility)
          "bedrock-agent:*"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          # Agent Runtime Permissions
          "bedrock:InvokeAgent",
          "bedrock-runtime:InvokeAgent",
          "bedrock-runtime:InvokeModel",
          "bedrock-runtime:InvokeModelWithResponseStream",
          "bedrock-agent-runtime:*",
          # Additional permissions for agent execution
          "bedrock:TagResource",
          "bedrock:UntagResource",
          "bedrock:ListTagsForResource",
          "bedrock:GetFoundationModelAvailability"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = aws_iam_role.app_runner_instance.arn
      },
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = "arn:aws:iam::119684128788:role/BondAIBedrockAgentRole"
        Condition = {
          StringEquals = {
            "iam:PassedToService" = "bedrock.amazonaws.com"
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          # AWS Marketplace for model subscriptions
          "aws-marketplace:Subscribe",
          "aws-marketplace:Unsubscribe",
          "aws-marketplace:ViewSubscriptions",
          # Additional IAM permissions for service-linked roles
          "iam:CreateServiceLinkedRole"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "iam:AWSServiceName" = [
              "bedrock.amazonaws.com"
            ]
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"
      }
    ]
  })
}

# App Runner Access Role for ECR
resource "aws_iam_role" "app_runner_ecr_access" {
  name = "${var.project_name}-${var.environment}-apprunner-ecr-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "build.apprunner.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "app_runner_ecr_access" {
  role       = aws_iam_role.app_runner_ecr_access.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

# IAM Role for Bedrock Agents - REMOVED
# We now use the app_runner_instance role for both App Runner and Bedrock agents
# resource "aws_iam_role" "bedrock_agent" {
#   name = var.bedrock_agent_role_name
#
#   assume_role_policy = jsonencode({
#     Version = "2012-10-17"
#     Statement = [
#       {
#         Effect = "Allow"
#         Principal = {
#           Service = "bedrock.amazonaws.com"
#         }
#         Action = "sts:AssumeRole"
#       }
#     ]
#   })
# }

# Attach necessary policies to Bedrock Agent Role - REMOVED
# resource "aws_iam_role_policy_attachment" "bedrock_agent_s3" {
#   role       = aws_iam_role.bedrock_agent.name
#   policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
# }
#
# resource "aws_iam_role_policy_attachment" "bedrock_agent_bedrock" {
#   role       = aws_iam_role.bedrock_agent.name
#   policy_arn = "arn:aws:iam::aws:policy/AmazonBedrockFullAccess"
# }
#
# # Inline policy for Bedrock Agent with cross-region inference support
# resource "aws_iam_role_policy" "bedrock_agent_cross_region" {
#   name = "bedrock-cross-region-inference"
#   role = aws_iam_role.bedrock_agent.id

#
#   policy = jsonencode({
#     Version = "2012-10-17"
#     Statement = [
#       {
#         Effect = "Allow"
#         Action = [
#           "bedrock:InvokeModel",
#           "bedrock:InvokeModelWithResponseStream"
#         ]
#         Resource = [
#           "arn:aws:bedrock:*:*:inference-profile/*",
#           "arn:aws:bedrock:*::foundation-model/*",
#           "arn:aws:bedrock:*:*:provisioned-model/*"
#         ]
#       },
#       {
#         Effect = "Allow"
#         Action = [
#           "logs:CreateLogGroup",
#           "logs:CreateLogStream",
#           "logs:PutLogEvents"
#         ]
#         Resource = "arn:aws:logs:*:*:*"
#       }
#     ]
#   })
# }

# App Runner Service
resource "aws_apprunner_service" "backend" {
  service_name = "${var.project_name}-${var.environment}-backend"

  source_configuration {
    authentication_configuration {
      access_role_arn = aws_iam_role.app_runner_ecr_access.arn
    }
    
    image_repository {
      image_identifier      = "${aws_ecr_repository.backend.repository_url}:latest"
      image_repository_type = "ECR"
      
      image_configuration {
        port = "8000"
        
        runtime_environment_variables = {
          AWS_REGION = var.aws_region
          BOND_PROVIDER_CLASS = "bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider"
          DATABASE_SECRET_ARN = aws_secretsmanager_secret.db_credentials.arn
          S3_BUCKET_NAME = aws_s3_bucket.uploads.id
          JWT_SECRET_KEY = random_password.jwt_secret.result
          # Use the dedicated Bedrock agent role that works correctly
          # The App Runner role has issues when invoking agents from App Runner context
          BEDROCK_AGENT_ROLE_ARN = "arn:aws:iam::119684128788:role/BondAIBedrockAgentRole"
          # Using PostgreSQL with VPC connector
          METADATA_DB_URL = "postgresql://bondadmin:${random_password.db_password.result}@${aws_db_instance.main.address}:5432/bondai"
          
          # Okta OAuth Configuration
          OAUTH2_ENABLED_PROVIDERS = var.oauth2_providers
          OKTA_DOMAIN = var.okta_domain
          OKTA_CLIENT_ID = var.okta_client_id
          OKTA_CLIENT_SECRET = jsondecode(data.aws_secretsmanager_secret_version.okta_secret.secret_string)["client_secret"]
          # Use variable for redirect URI - set per environment or leave empty for dynamic Host header
          OKTA_REDIRECT_URI = var.okta_redirect_uri
          OKTA_SCOPES = var.okta_scopes
          
          # JWT redirect URI for frontend - where to redirect after successful auth
          JWT_REDIRECT_URI = var.jwt_redirect_uri
          
          # CORS configuration
          CORS_ALLOWED_ORIGINS = var.cors_allowed_origins
        }
      }
    }
  }

  # Re-enabling VPC connector with proper NAT and VPC endpoints
  network_configuration {
    egress_configuration {
      egress_type       = "VPC"
      vpc_connector_arn = aws_apprunner_vpc_connector.backend.arn
    }
  }

  instance_configuration {
    cpu               = "0.25 vCPU"
    memory            = "0.5 GB"
    instance_role_arn = aws_iam_role.app_runner_instance.arn
  }

  auto_scaling_configuration_arn = aws_apprunner_auto_scaling_configuration_version.backend.arn

  health_check_configuration {
    protocol            = "HTTP"
    path               = "/health"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-backend"
  }

  depends_on = [
    null_resource.build_backend_image  # Wait for Docker image to be built and pushed
  ]
}

resource "aws_apprunner_auto_scaling_configuration_version" "backend" {
  auto_scaling_configuration_name = "${var.project_name}-${var.environment}-backend-autoscaling"
  
  min_size = 1
  max_size = var.environment == "prod" ? 10 : 2
  
  tags = {
    Name = "${var.project_name}-${var.environment}-backend-autoscaling"
  }
}

# Outputs
output "vpc_id" {
  value = aws_vpc.main.id
}

output "database_endpoint" {
  value = aws_db_instance.main.endpoint
  sensitive = true
}

output "database_secret_arn" {
  value = aws_secretsmanager_secret.db_credentials.arn
}

output "database_secret_name" {
  value = aws_secretsmanager_secret.db_credentials.name
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "database_security_group_id" {
  value = aws_security_group.rds.id
}

output "s3_bucket_name" {
  value = aws_s3_bucket.uploads.id
}

output "s3_bucket_arn" {
  value = aws_s3_bucket.uploads.arn
}

output "ecr_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "ecr_repository_name" {
  value = aws_ecr_repository.backend.name
}

output "app_runner_vpc_connector_arn" {
  value = aws_apprunner_vpc_connector.backend.arn
}

output "app_runner_service_url" {
  value = "https://${aws_apprunner_service.backend.service_url}"
}

output "quick_test" {
  value = <<-EOT
    
    Database deployed! Test with:
    
    1. Get credentials:
       aws secretsmanager get-secret-value --secret-id ${aws_secretsmanager_secret.db_credentials.name} --query SecretString --output text | jq .
    
    2. Test connection:
       python ../scripts/test_database_deployment.py --env ${var.environment}
  EOT
}
# ============================================================================
# Outputs
# ============================================================================
# Note: SSM Parameter Store resources removed - not being used by the application
# Configuration is handled via environment variables and post-deployment updates

output "jwt_secret" {
  value       = random_password.jwt_secret.result
  sensitive   = true
  description = "JWT secret key for authentication (use 'terraform output -raw jwt_secret' to retrieve)"
}
