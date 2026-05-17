# =============================================================================
# ECS Express Mode IAM Roles
# Uses the same shared policy as App Runner instance role to prevent drift.
# All resources gated by var.enable_ecs_express (default: false)
# =============================================================================

# =============================================================================
# Task Role — assumed by the running application container
# Equivalent of App Runner instance role / EKS pod role (IRSA)
# =============================================================================

resource "aws_iam_role" "ecs_express_task" {
  count = var.enable_ecs_express ? 1 : 0

  name = "${var.project_name}-${var.environment}-ecs-express-task-role"

  # Split trust policy: ECS tasks with SourceAccount condition (SA-8),
  # Bedrock without it (Bedrock may not pass SourceAccount when assuming
  # the caller's role during InvokeAgent).
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ECSTasksAssume"
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      },
      {
        Sid    = "BedrockAssume"
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "bedrock.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-${var.environment}-ecs-express-task-role"
  }
}

# Task role uses shared policy statements + its own PassRole
resource "aws_iam_role_policy" "ecs_express_task" {
  count = var.enable_ecs_express ? 1 : 0

  name = "${var.project_name}-${var.environment}-ecs-express-task-policy"
  role = aws_iam_role.ecs_express_task[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(local.backend_shared_policy_statements, [
      {
        Sid    = "PassRole"
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = [
          aws_iam_role.ecs_express_task[0].arn,
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

# =============================================================================
# Execution Role — used by the ECS agent to pull images and write logs
# Equivalent of App Runner ECR access role
# =============================================================================

resource "aws_iam_role" "ecs_express_execution" {
  count = var.enable_ecs_express ? 1 : 0

  name = "${var.project_name}-${var.environment}-ecs-express-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
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
    Name = "${var.project_name}-${var.environment}-ecs-express-execution-role"
  }
}

# Standard ECS task execution policy (ECR pull, CloudWatch logs)
resource "aws_iam_role_policy_attachment" "ecs_express_execution" {
  count = var.enable_ecs_express ? 1 : 0

  role       = aws_iam_role.ecs_express_execution[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# KMS decrypt for pulling images from CMK-encrypted ECR repos
resource "aws_iam_role_policy" "ecs_express_execution_kms" {
  count = var.enable_ecs_express ? 1 : 0

  name = "${var.project_name}-${var.environment}-ecs-express-execution-kms"
  role = aws_iam_role.ecs_express_execution[0].id

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

# =============================================================================
# Infrastructure Role — used by ECS to manage ALB, target groups, auto-scaling
# This is a new role type specific to ECS Express Mode
# =============================================================================

resource "aws_iam_role" "ecs_express_infrastructure" {
  count = var.enable_ecs_express ? 1 : 0

  name = "${var.project_name}-${var.environment}-ecs-express-infra-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs.amazonaws.com"
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
    Name = "${var.project_name}-${var.environment}-ecs-express-infra-role"
  }
}

# Managed policy for Express Mode infrastructure management
resource "aws_iam_role_policy_attachment" "ecs_express_infrastructure" {
  count = var.enable_ecs_express ? 1 : 0

  role       = aws_iam_role.ecs_express_infrastructure[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSInfrastructureRoleforExpressGatewayServices"
}

# CloudWatch Logs permissions — the managed policy doesn't include these,
# but ECS Express needs them to verify/configure log groups during service creation
resource "aws_iam_role_policy" "ecs_express_infrastructure_logs" {
  count = var.enable_ecs_express ? 1 : 0

  name = "${var.project_name}-${var.environment}-ecs-express-infra-logs"
  role = aws_iam_role.ecs_express_infrastructure[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:DescribeLogGroups",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"
      }
    ]
  })
}
