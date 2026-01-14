# IAM Roles and Policies

# Data source for MCP Atlassian OAuth secret (for backend access)
data "aws_secretsmanager_secret" "mcp_atlassian_oauth_backend" {
  count = var.mcp_atlassian_enabled ? 1 : 0
  name  = var.mcp_atlassian_oauth_secret_name
}

# IAM Role for App Runner Instance
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

# Attach AmazonBedrockFullAccess managed policy
resource "aws_iam_role_policy_attachment" "app_runner_bedrock_full_access" {
  role       = aws_iam_role.app_runner_instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonBedrockFullAccess"
}

# Add S3 Full Access
resource "aws_iam_role_policy_attachment" "app_runner_s3_full_access" {
  role       = aws_iam_role.app_runner_instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
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
        Resource = concat(
          [
            aws_secretsmanager_secret.db_credentials.arn,
            data.aws_secretsmanager_secret.okta_secret.arn
          ],
          var.mcp_atlassian_enabled ? [
            data.aws_secretsmanager_secret.mcp_atlassian_oauth_backend[0].arn
          ] : [],
          # Add Databricks secret access
          ["arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:bond-ai-dev-databricks-secret-*"]
        )
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
          "iam:PassRole"
        ]
        Resource = [
          aws_iam_role.app_runner_instance.arn,
          "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/BondAIBedrockAgentRole"
        ]
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

# IAM Role for Frontend App Runner
resource "aws_iam_role" "frontend_apprunner_instance" {
  name = "${var.project_name}-${var.environment}-frontend-apprunner-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "tasks.apprunner.amazonaws.com"
        }
      }
    ]
  })
}
