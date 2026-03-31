# =============================================================================
# EKS Cluster + Managed Node Group
# All resources gated by var.enable_eks (default: false)
# =============================================================================

locals {
  eks_cluster_name = "${var.project_name}-${var.environment}-eks"
}

# =============================================================================
# KMS Key for EKS Secrets Envelope Encryption
# =============================================================================

resource "aws_kms_key" "eks" {
  count = var.enable_eks ? 1 : 0

  description             = "KMS key for EKS secrets envelope encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name = "${var.project_name}-${var.environment}-eks-kms"
  }
}

resource "aws_kms_alias" "eks" {
  count = var.enable_eks ? 1 : 0

  name          = "alias/${var.project_name}-${var.environment}-eks"
  target_key_id = aws_kms_key.eks[0].key_id
}

# =============================================================================
# EKS Cluster
# =============================================================================

module "eks" {
  count = var.enable_eks ? 1 : 0

  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.31"

  cluster_name    = local.eks_cluster_name
  cluster_version = var.eks_kubernetes_version

  # Networking — reuse same private subnets as App Runner VPC connector
  vpc_id     = data.aws_vpc.existing.id
  subnet_ids = local.app_runner_subnet_ids

  # Endpoint access — public needed for Terraform/kubectl from outside VPC
  cluster_endpoint_public_access       = true
  cluster_endpoint_private_access      = true
  cluster_endpoint_public_access_cidrs = var.eks_cluster_endpoint_public_access_cidrs

  # Grant admin to whoever runs Terraform (EKS access entries API)
  enable_cluster_creator_admin_permissions = true

  # Control plane logging
  cluster_enabled_log_types = ["api", "audit", "authenticator"]

  # Secrets envelope encryption
  cluster_encryption_config = {
    provider_key_arn = aws_kms_key.eks[0].arn
    resources        = ["secrets"]
  }

  # Node security group rules
  node_security_group_additional_rules = {
    ingress_nlb = {
      description = "NLB health checks and traffic from VPC (NodePort range)"
      protocol    = "tcp"
      from_port   = 30000
      to_port     = 32767
      type        = "ingress"
      cidr_blocks = [data.aws_vpc.existing.cidr_block]
    }
    ingress_app = {
      description = "App traffic from VPC (NLB to pods on port 8080)"
      protocol    = "tcp"
      from_port   = 8080
      to_port     = 8080
      type        = "ingress"
      cidr_blocks = [data.aws_vpc.existing.cidr_block]
    }
    ingress_https = {
      description = "HTTPS from VPC and VPN CIDRs"
      protocol    = "tcp"
      from_port   = 443
      to_port     = 443
      type        = "ingress"
      cidr_blocks = concat([data.aws_vpc.existing.cidr_block], var.eks_additional_ingress_cidrs)
    }
  }

  # Managed node group
  eks_managed_node_groups = {
    default = {
      instance_types = [var.eks_node_instance_type]

      min_size     = var.eks_node_min_count
      max_size     = var.eks_node_max_count
      desired_size = var.eks_node_desired_count

      # Custom AMI support for company-certified images
      ami_id                     = var.eks_custom_ami_id != "" ? var.eks_custom_ami_id : null
      ami_type                   = var.eks_custom_ami_id != "" ? "CUSTOM" : "AL2023_x86_64_STANDARD"
      enable_bootstrap_user_data = var.eks_custom_ami_id != "" ? true : false

      # Additional tags for SCP/tag policy compliance
      tags = var.eks_node_tags
    }
  }

  tags = {
    Name = local.eks_cluster_name
  }
}

# =============================================================================
# Kubernetes Provider (authenticated via EKS cluster)
#
# Three modes:
# 1. enable_eks=true  → uses module.eks outputs (normal operation)
# 2. enable_eks=false, cluster still exists → uses data source lookup (teardown)
# 3. enable_eks=false, cluster gone → dummy values (no K8s resources to manage)
# =============================================================================

data "aws_eks_cluster_auth" "cluster" {
  count = var.enable_eks ? 1 : 0
  name  = module.eks[0].cluster_name
}

# Kubernetes provider authentication.
# When enable_eks=true: uses module.eks outputs directly.
# When enable_eks=false: uses external data source to check if cluster still exists.
#   - Cluster exists (teardown): connects to real cluster, K8s resources destroyed
#   - Cluster gone (steady state): falls back to localhost, no K8s resources to manage
data "external" "eks_endpoint" {
  count   = var.enable_eks ? 0 : 1
  program = ["bash", "-c", <<-EOF
    EP=$(aws eks describe-cluster --name "${local.eks_cluster_name}" --region "${var.aws_region}" --query 'cluster.endpoint' --output text 2>/dev/null || echo "")
    CA=$(aws eks describe-cluster --name "${local.eks_cluster_name}" --region "${var.aws_region}" --query 'cluster.certificateAuthority.data' --output text 2>/dev/null || echo "")
    if [ -n "$EP" ] && [ "$EP" != "None" ]; then
      printf '{"endpoint":"%s","ca":"%s"}' "$EP" "$CA"
    else
      printf '{"endpoint":"https://localhost","ca":""}'
    fi
  EOF
  ]
}

provider "kubernetes" {
  host = var.enable_eks ? module.eks[0].cluster_endpoint : (
    data.external.eks_endpoint[0].result.endpoint
  )
  cluster_ca_certificate = var.enable_eks ? base64decode(module.eks[0].cluster_certificate_authority_data) : (
    data.external.eks_endpoint[0].result.ca != "" ? base64decode(data.external.eks_endpoint[0].result.ca) : ""
  )
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "bash"
    args = ["-c",
      "aws eks get-token --cluster-name '${local.eks_cluster_name}' --region '${var.aws_region}' 2>/dev/null || echo '{\"kind\":\"ExecCredential\",\"apiVersion\":\"client.authentication.k8s.io/v1beta1\",\"status\":{\"token\":\"\"}}'"
    ]
  }
}

# =============================================================================
# Subnet Tagging (required for internal NLB to discover subnets)
# EKS is always private — only tag private subnets for internal-elb.
# Tags are additive and do not affect App Runner.
# =============================================================================

resource "aws_ec2_tag" "eks_private_subnet_cluster" {
  for_each    = var.enable_eks ? toset(local.app_runner_subnet_ids) : toset([])
  resource_id = each.value
  key         = "kubernetes.io/cluster/${local.eks_cluster_name}"
  value       = "shared"
}

resource "aws_ec2_tag" "eks_private_subnet_internal_elb" {
  for_each    = var.enable_eks ? toset(local.app_runner_subnet_ids) : toset([])
  resource_id = each.value
  key         = "kubernetes.io/role/internal-elb"
  value       = "1"
}
