# =============================================================================
# EKS Cluster + Managed Node Group
# All resources gated by var.enable_eks (default: false)
# =============================================================================

locals {
  eks_cluster_name = "${var.project_name}-${var.environment}-eks"

  # -------------------------------------------------------------------------
  # Create vs. Consume mode
  # -------------------------------------------------------------------------
  # Consume mode: bond-ai deploys onto an existing (bond-mcps-owned) cluster
  # named var.eks_existing_cluster_name and joins the shared ALB. It does NOT
  # create the cluster, node group, or LB controller (see PLATFORM-CONTRACT.md).
  # Create mode (default): bond-ai provisions its own cluster as before.
  eks_consume_mode = var.eks_existing_cluster_name != ""
  eks_create       = var.enable_eks && !local.eks_consume_mode

  # The cluster name to use for provider auth, kubeconfig, and ALB lookups.
  eks_cluster_name_effective = local.eks_consume_mode ? var.eks_existing_cluster_name : local.eks_cluster_name

  # Node security group: created cluster's module output, or the pinned SG of the
  # consumed cluster (bond-mcps output). Used by aurora/security/knowledge-base
  # ingress rules.
  eks_node_security_group_id = local.eks_create ? (
    module.eks[0].node_security_group_id
  ) : var.eks_external_node_security_group_id

  # OIDC provider (IRSA trust). Created cluster exposes it via the module; the
  # consumed cluster's provider is looked up by its issuer URL.
  eks_oidc_provider_arn = local.eks_create ? module.eks[0].oidc_provider_arn : (
    var.enable_eks ? data.aws_iam_openid_connect_provider.consumed[0].arn : ""
  )
  eks_oidc_provider = local.eks_create ? module.eks[0].oidc_provider : (
    var.enable_eks ? replace(data.aws_iam_openid_connect_provider.consumed[0].url, "https://", "") : ""
  )

  # Use the shared-ALB Ingress (bond-platform IngressGroup) instead of a
  # self-managed NLB/TargetGroupBinding. Defaults ON in consume mode (the shared
  # cluster's only ingress path is the bond-mcps-owned ALB); create mode can opt
  # in via var.eks_use_ingress for testing.
  eks_use_ingress = var.enable_eks && (local.eks_consume_mode || var.eks_use_ingress)
}

# =============================================================================
# Consumed-cluster data sources (consume mode only)
# =============================================================================

data "aws_eks_cluster" "consumed" {
  count = var.enable_eks && local.eks_consume_mode ? 1 : 0
  name  = var.eks_existing_cluster_name
}

data "aws_eks_cluster_auth" "consumed" {
  count = var.enable_eks && local.eks_consume_mode ? 1 : 0
  name  = var.eks_existing_cluster_name
}

# Look up the consumed cluster's IAM OIDC provider by its issuer URL so the pod
# IRSA role can trust the correct provider ARN.
data "aws_iam_openid_connect_provider" "consumed" {
  count = var.enable_eks && local.eks_consume_mode ? 1 : 0
  url   = data.aws_eks_cluster.consumed[0].identity[0].oidc[0].issuer
}

# =============================================================================
# KMS Key for EKS Secrets Envelope Encryption
# =============================================================================

resource "aws_kms_key" "eks" {
  count = local.eks_create ? 1 : 0

  description             = "KMS key for EKS secrets envelope encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name = "${var.project_name}-${var.environment}-eks-kms"
  }
}

resource "aws_kms_alias" "eks" {
  count = local.eks_create ? 1 : 0

  name          = "alias/${var.project_name}-${var.environment}-eks"
  target_key_id = aws_kms_key.eks[0].key_id
}

# =============================================================================
# EKS Cluster
# =============================================================================

module "eks" {
  count = local.eks_create ? 1 : 0

  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.0"

  name               = local.eks_cluster_name
  kubernetes_version = var.eks_kubernetes_version

  # Networking — reuse same private subnets as App Runner VPC connector
  vpc_id     = data.aws_vpc.existing.id
  subnet_ids = local.app_runner_subnet_ids

  # Endpoint access — public needed for Terraform/kubectl from outside VPC
  endpoint_public_access       = true
  endpoint_private_access      = true
  endpoint_public_access_cidrs = var.eks_cluster_endpoint_public_access_cidrs

  # Grant admin to whoever runs Terraform (EKS access entries API)
  enable_cluster_creator_admin_permissions = true

  # Control plane logging
  enabled_log_types = ["api", "audit", "authenticator"]

  # EKS managed addons
  addons = {
    metrics-server = {
      most_recent = true
    }
  }

  # Secrets envelope encryption
  encryption_config = {
    provider_key_arn = aws_kms_key.eks[0].arn
    resources        = ["secrets"]
  }

  # Node security group rules
  node_security_group_additional_rules = {
    ingress_nodeport = {
      description = "Health checks and traffic from VPC (NodePort range)"
      protocol    = "tcp"
      from_port   = 30000
      to_port     = 32767
      type        = "ingress"
      cidr_blocks = [data.aws_vpc.existing.cidr_block]
    }
    ingress_app = {
      description = "App traffic from VPC to pods on port 8080"
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
      # The golden AMI is AL2-based (CIS hardened) and needs the AL2 bootstrap script,
      # not the AL2023 NodeConfig YAML format. We set ami_type to CUSTOM and point
      # user_data_template_path to the AL2 template to satisfy v21's requirement.
      ami_id                         = var.eks_custom_ami_id != "" ? var.eks_custom_ami_id : null
      ami_type                       = var.eks_custom_ami_id != "" ? "CUSTOM" : "AL2023_x86_64_STANDARD"
      enable_bootstrap_user_data     = var.eks_custom_ami_id != "" ? true : false
      use_latest_ami_release_version = var.eks_custom_ami_id != "" ? false : true
      user_data_template_path        = var.eks_custom_ami_id != "" ? "${path.module}/templates/al2_user_data.tpl" : null

      # Force node group updates through even if pod eviction fails (e.g. PDB deadlock).
      # Without this, rolling updates fail after ~30 min with PodEvictionFailure.
      force_update_version = true
      update_config = {
        max_unavailable = 1
      }

      # v21 changed default from true to false — keep enabled for prod observability
      enable_monitoring = true

      # Additional tags for SCP/tag policy compliance
      tags = var.eks_node_tags
    }
  }

  tags = {
    Name = local.eks_cluster_name
  }
}

# =============================================================================
# Kubernetes / Helm Provider (authenticated via EKS cluster)
#
# Four modes, resolved into local.eks_provider_host / local.eks_provider_ca:
# 1. create  (enable_eks=true, no existing name)  → module.eks outputs
# 2. consume (enable_eks=true, existing name set) → data.aws_eks_cluster.consumed
# 3. teardown (enable_eks=false, cluster exists)  → external data source lookup
# 4. gone    (enable_eks=false, cluster removed)  → dummy localhost (no-op)
#
# The exec block authenticates by cluster name (with an empty-token fallback so
# provider config never hard-fails when the cluster is absent). This works in
# every mode because local.eks_cluster_name_effective resolves to the right name.
# =============================================================================

# Teardown/steady-state probe (create/consume use the AWS data sources above).
data "external" "eks_endpoint" {
  count = var.enable_eks ? 0 : 1
  program = ["bash", "-c", <<-EOF
    EP=$(aws eks describe-cluster --name "${local.eks_cluster_name_effective}" --region "${var.aws_region}" --query 'cluster.endpoint' --output text 2>/dev/null || echo "")
    CA=$(aws eks describe-cluster --name "${local.eks_cluster_name_effective}" --region "${var.aws_region}" --query 'cluster.certificateAuthority.data' --output text 2>/dev/null || echo "")
    if [ -n "$EP" ] && [ "$EP" != "None" ]; then
      printf '{"endpoint":"%s","ca":"%s"}' "$EP" "$CA"
    else
      printf '{"endpoint":"https://localhost","ca":""}'
    fi
  EOF
  ]
}

locals {
  eks_provider_host = local.eks_create ? module.eks[0].cluster_endpoint : (
    local.eks_consume_mode ? data.aws_eks_cluster.consumed[0].endpoint : (
      data.external.eks_endpoint[0].result.endpoint
    )
  )
  eks_provider_ca = local.eks_create ? base64decode(module.eks[0].cluster_certificate_authority_data) : (
    local.eks_consume_mode ? base64decode(data.aws_eks_cluster.consumed[0].certificate_authority[0].data) : (
      data.external.eks_endpoint[0].result.ca != "" ? base64decode(data.external.eks_endpoint[0].result.ca) : ""
    )
  )
}

provider "kubernetes" {
  host                   = local.eks_provider_host
  cluster_ca_certificate = local.eks_provider_ca
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "bash"
    args = ["-c",
      "aws eks get-token --cluster-name '${local.eks_cluster_name_effective}' --region '${var.aws_region}' 2>/dev/null || echo '{\"kind\":\"ExecCredential\",\"apiVersion\":\"client.authentication.k8s.io/v1beta1\",\"status\":{\"token\":\"\"}}'"
    ]
  }
}

provider "helm" {
  kubernetes {
    host                   = local.eks_provider_host
    cluster_ca_certificate = local.eks_provider_ca
    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "bash"
      args = ["-c",
        "aws eks get-token --cluster-name '${local.eks_cluster_name_effective}' --region '${var.aws_region}' 2>/dev/null || echo '{\"kind\":\"ExecCredential\",\"apiVersion\":\"client.authentication.k8s.io/v1beta1\",\"status\":{\"token\":\"\"}}'"
      ]
    }
  }
}

# =============================================================================
# Subnet Tagging (required for internal load balancers to discover subnets)
# EKS is always private — only tag private subnets for internal-elb.
# Tags are additive and do not affect App Runner.
# =============================================================================

resource "aws_ec2_tag" "eks_private_subnet_cluster" {
  # Create mode only — in consume mode bond-mcps owns the cluster and its subnet tags.
  for_each    = local.eks_create ? toset(local.app_runner_subnet_ids) : toset([])
  resource_id = each.value
  key         = "kubernetes.io/cluster/${local.eks_cluster_name}"
  value       = "shared"
}

resource "aws_ec2_tag" "eks_private_subnet_internal_elb" {
  for_each    = local.eks_create ? toset(local.app_runner_subnet_ids) : toset([])
  resource_id = each.value
  key         = "kubernetes.io/role/internal-elb"
  value       = "1"
}
