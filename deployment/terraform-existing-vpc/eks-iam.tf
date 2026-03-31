# =============================================================================
# EKS Pod IAM Role (IRSA — IAM Roles for Service Accounts)
# Uses the same shared policy as App Runner instance role to prevent drift.
# All resources gated by var.enable_eks (default: false)
# =============================================================================

# OIDC provider is auto-created by the EKS module.
# We create a pod role that trusts the specific service account via WebIdentity.

resource "aws_iam_role" "eks_pod" {
  count = var.enable_eks ? 1 : 0

  name = "${var.project_name}-${var.environment}-eks-pod-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = module.eks[0].oidc_provider_arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${module.eks[0].oidc_provider}:sub" = "system:serviceaccount:bond-ai:bond-ai-backend"
            "${module.eks[0].oidc_provider}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-${var.environment}-eks-pod-role"
  }
}

# Pod role uses shared policy statements + its own PassRole
resource "aws_iam_role_policy" "eks_pod" {
  count = var.enable_eks ? 1 : 0

  name = "${var.project_name}-${var.environment}-eks-pod-policy"
  role = aws_iam_role.eks_pod[0].id

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
          aws_iam_role.eks_pod[0].arn,
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
