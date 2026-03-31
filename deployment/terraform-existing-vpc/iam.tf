# IAM Roles and Policies

# Data source for MCP Atlassian OAuth secret (for backend access)
data "aws_secretsmanager_secret" "mcp_atlassian_oauth_backend" {
  count = var.mcp_atlassian_enabled ? 1 : 0
  name  = var.mcp_atlassian_oauth_secret_name
}

# IAM Role for App Runner Instance
resource "aws_iam_role" "app_runner_instance" {
  count = var.enable_apprunner ? 1 : 0

  name = "${var.project_name}-${var.environment}-apprunner-instance-role"

  # SA-8: Added SourceAccount condition to prevent confused deputy attacks.
  # Uses SourceAccount (not SourceArn) because the App Runner service ARN
  # isn't known at role creation time (circular dependency).
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
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })
}

# =============================================================================
# Shared Backend Policy Statements
# Used by both App Runner instance role and EKS pod role (IRSA) to ensure
# identical permissions across compute platforms. PassRole is excluded here
# because each role needs to reference its own ARN (avoiding circular deps).
# =============================================================================

locals {
  backend_shared_policy_statements = [
    {
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue"
      ]
      Resource = concat(
        [
          aws_secretsmanager_secret.db_credentials.arn,
          data.aws_secretsmanager_secret.okta_secret.arn,
          aws_secretsmanager_secret.app_config.arn
        ],
        var.mcp_atlassian_enabled ? [
          data.aws_secretsmanager_secret.mcp_atlassian_oauth_backend[0].arn
        ] : [],
        # Add Databricks secret access
        ["arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}-${var.environment}-databricks-secret-*"],
        # Add Microsoft MCP secret access
        ["arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}-${var.environment}-microsoft-mcp-secret-*"]
      )
    },
    {
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:HeadBucket",
        "s3:CreateBucket"
      ]
      Resource = [
        aws_s3_bucket.uploads.arn,
        "${aws_s3_bucket.uploads.arn}/*",
        "arn:aws:s3:::bond-bedrock-files-*"
      ]
    },
    {
      Effect = "Allow"
      Action = [
        "bedrock:*",
        "bedrock-agent:*",
        "bedrock-runtime:*",
        "bedrock-agent-runtime:*"
      ]
      Resource = "*"
    },
    {
      Effect = "Allow"
      Action = [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ]
      Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"
    },
    {
      Effect = "Allow"
      Action = [
        "kms:Decrypt",
        "kms:GenerateDataKey"
      ]
      Resource = [aws_kms_key.s3.arn, aws_kms_key.secrets.arn]
    }
  ]
}

# T33: Removed AmazonBedrockFullAccess and AmazonS3FullAccess managed policies.
# The inline policy below already provides scoped access:
# - S3: GetObject/PutObject/DeleteObject/ListBucket on the specific uploads bucket only
# - Bedrock: bedrock:*/bedrock-agent:*/bedrock-runtime:*/bedrock-agent-runtime:* on *
# Removing the managed policies eliminates wildcard S3 access to all buckets.

# IAM Policy for App Runner to access AWS services
resource "aws_iam_role_policy" "app_runner_instance" {
  count = var.enable_apprunner ? 1 : 0

  name = "${var.project_name}-${var.environment}-apprunner-policy"
  role = aws_iam_role.app_runner_instance[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(local.backend_shared_policy_statements, [
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = [
          aws_iam_role.app_runner_instance[0].arn,
          aws_iam_role.bedrock_agent.arn
        ]
        Condition = {
          StringEquals = {
            "iam:PassedToService" = "bedrock.amazonaws.com"
          }
        }
      }
    ])
  })
}

moved {
  from = aws_iam_role.app_runner_instance
  to   = aws_iam_role.app_runner_instance[0]
}

moved {
  from = aws_iam_role_policy.app_runner_instance
  to   = aws_iam_role_policy.app_runner_instance[0]
}

# App Runner Access Role for ECR
resource "aws_iam_role" "app_runner_ecr_access" {
  count = var.enable_apprunner ? 1 : 0

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
  count = var.enable_apprunner ? 1 : 0

  role       = aws_iam_role.app_runner_ecr_access[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

# KMS decrypt for pulling images from CMK-encrypted ECR repos
resource "aws_iam_role_policy" "app_runner_ecr_kms" {
  count = var.enable_apprunner ? 1 : 0

  name = "${var.project_name}-${var.environment}-apprunner-ecr-kms"
  role = aws_iam_role.app_runner_ecr_access[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = [aws_kms_key.secrets.arn]
      }
    ]
  })
}

moved {
  from = aws_iam_role.app_runner_ecr_access
  to   = aws_iam_role.app_runner_ecr_access[0]
}

moved {
  from = aws_iam_role_policy_attachment.app_runner_ecr_access
  to   = aws_iam_role_policy_attachment.app_runner_ecr_access[0]
}

moved {
  from = aws_iam_role_policy.app_runner_ecr_kms
  to   = aws_iam_role_policy.app_runner_ecr_kms[0]
}

# =============================================================================
# Bedrock Agent Role
# This role is assumed by AWS Bedrock when executing agents.
# =============================================================================

resource "aws_iam_role" "bedrock_agent" {
  name = var.bedrock_agent_role_name

  # SA-8: Added SourceAccount condition to prevent confused deputy attacks.
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "bedrock.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })
}

# T33 NOTE: The Bedrock agent role retains managed policies because AWS Bedrock's
# internal operations (knowledge base ingestion, OpenSearch indexing, S3 data source
# access) require broad permissions that are opaque to the application layer.
# Scoping these down risks breaking Bedrock agent functionality. Review with
# IAM Access Analyzer once operational patterns are established.

# Managed policy: AmazonBedrockFullAccess (required for agent orchestration)
resource "aws_iam_role_policy_attachment" "bedrock_agent_bedrock_full_access" {
  role       = aws_iam_role.bedrock_agent.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonBedrockFullAccess"
}

# Managed policy: AmazonS3FullAccess (required for knowledge base data sources)
resource "aws_iam_role_policy_attachment" "bedrock_agent_s3_full_access" {
  role       = aws_iam_role.bedrock_agent.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

# Managed policy: CloudWatchEventsFullAccess (required for Bedrock scheduling)
resource "aws_iam_role_policy_attachment" "bedrock_agent_cloudwatch_events" {
  role       = aws_iam_role.bedrock_agent.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchEventsFullAccess"
}

# Managed policy: AmazonOpenSearchServiceFullAccess (required for KB vector store)
resource "aws_iam_role_policy_attachment" "bedrock_agent_opensearch_full_access" {
  role       = aws_iam_role.bedrock_agent.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonOpenSearchServiceFullAccess"
}

# Inline policy: Allow role to pass itself to Bedrock
resource "aws_iam_role_policy" "bedrock_agent_pass_role" {
  name = "BondAIBedrockAgentRolePassRole"
  role = aws_iam_role.bedrock_agent.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = aws_iam_role.bedrock_agent.arn
        Condition = {
          StringEquals = {
            "iam:PassedToService" = "bedrock.amazonaws.com"
          }
        }
      }
    ]
  })
}
