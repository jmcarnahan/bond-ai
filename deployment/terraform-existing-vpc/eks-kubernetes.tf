# =============================================================================
# Kubernetes Resources for Bond AI on EKS
# All resources gated by var.enable_eks (default: false)
# Uses the same combined Docker image as App Runner.
# =============================================================================

# =============================================================================
# Namespace
# =============================================================================

resource "kubernetes_namespace" "bond_ai" {
  count = var.enable_eks ? 1 : 0

  metadata {
    name = "bond-ai"
  }

  depends_on = [module.eks]
}

# =============================================================================
# Service Account (IRSA-annotated)
# =============================================================================

resource "kubernetes_service_account" "backend" {
  count = var.enable_eks ? 1 : 0

  metadata {
    name      = "bond-ai-backend"
    namespace = kubernetes_namespace.bond_ai[0].metadata[0].name
    annotations = {
      "eks.amazonaws.com/role-arn" = aws_iam_role.eks_pod[0].arn
    }
  }

  depends_on = [kubernetes_namespace.bond_ai]
}

# =============================================================================
# ConfigMap — Non-sensitive environment variables
# Mirrors the App Runner runtime_environment_variables from backend.tf
# =============================================================================

resource "kubernetes_config_map" "backend" {
  count = var.enable_eks ? 1 : 0

  metadata {
    name      = "bond-ai-backend-config"
    namespace = kubernetes_namespace.bond_ai[0].metadata[0].name
  }

  data = {
    AWS_REGION             = var.aws_region
    BOND_PROVIDER_CLASS    = "bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider"
    S3_BUCKET_NAME         = aws_s3_bucket.uploads.id
    BEDROCK_AGENT_ROLE_ARN = aws_iam_role.bedrock_agent.arn
    BEDROCK_DEFAULT_MODEL      = var.bedrock_default_model
    BEDROCK_SELECTABLE_MODELS  = var.bedrock_selectable_models

    # OAuth Configuration — uses EKS-specific URL for redirects (not App Runner)
    # Precedence: eks_custom_domain_name > eks_oauth_base_url > wildcard fallback
    OAUTH2_ENABLED_PROVIDERS = var.oauth2_providers
    OKTA_DOMAIN              = var.okta_domain
    OKTA_SECRET_NAME         = var.okta_secret_name
    OKTA_REDIRECT_URI        = local.eks_oauth_base_url != "" ? "${local.eks_oauth_base_url}/auth/okta/callback" : "*"
    OKTA_SCOPES              = var.okta_scopes

    # Cognito OAuth (only if configured) — uses EKS URL
    COGNITO_DOMAIN       = var.cognito_domain
    COGNITO_SECRET_NAME  = var.cognito_secret_name
    COGNITO_REDIRECT_URI = var.cognito_domain != "" ? (local.eks_oauth_base_url != "" ? "${local.eks_oauth_base_url}/auth/cognito/callback" : "*") : ""
    COGNITO_SCOPES       = var.cognito_scopes
    COGNITO_REGION       = var.cognito_region

    # JWT redirect URI — EKS frontend URL (where to go after login)
    JWT_REDIRECT_URI = local.eks_oauth_base_url != "" ? local.eks_oauth_base_url : "*"

    # CORS — include both App Runner and EKS origins
    CORS_ALLOWED_ORIGINS = join(",", distinct(compact(concat(
      split(",", var.cors_allowed_origins),
      local.eks_oauth_base_url != "" ? [local.eks_oauth_base_url] : []
    ))))

    # Allowed redirect domains for OAuth callbacks
    ALLOWED_REDIRECT_DOMAINS = join(",", distinct(compact(concat(
      split(",", var.allowed_redirect_domains),
      var.eks_custom_domain_name != "" ? [var.eks_custom_domain_name] : [],
      var.eks_oauth_base_url != "" ? [replace(replace(trimsuffix(var.eks_oauth_base_url, "/"), "https://", ""), "http://", "")] : []
    ))))

    # Knowledge Base configuration
    BEDROCK_KNOWLEDGE_BASE_ID = try(aws_bedrockagent_knowledge_base.main[0].id, "")
    BEDROCK_KB_DATA_SOURCE_ID = try(aws_bedrockagent_data_source.s3[0].data_source_id, "")
    BEDROCK_KB_S3_PREFIX      = var.enable_knowledge_base ? "knowledge-base/" : ""

    # Admin configuration
    ADMIN_USERS = var.admin_users
    ADMIN_EMAIL = var.admin_email

    # Email validation
    ALLOW_ALL_EMAILS       = var.allow_all_emails
    SCHEDULED_JOBS_ENABLED = "false"  # Only App Runner runs the scheduler

    # Cookie security
    COOKIE_SECURE = "true"

    # Bedrock Guardrails
    BEDROCK_GUARDRAIL_ID      = var.enable_guardrails ? aws_bedrock_guardrail.main[0].guardrail_id : ""
    BEDROCK_GUARDRAIL_VERSION = var.enable_guardrails ? (var.bedrock_guardrail_version != "" ? var.bedrock_guardrail_version : aws_bedrock_guardrail_version.main[0].version) : ""
  }

  depends_on = [kubernetes_namespace.bond_ai]
}

# =============================================================================
# Secret — Sensitive environment variables (secret ARNs/names)
# =============================================================================

resource "kubernetes_secret" "backend" {
  count = var.enable_eks ? 1 : 0

  metadata {
    name      = "bond-ai-backend-secrets"
    namespace = kubernetes_namespace.bond_ai[0].metadata[0].name
  }

  data = {
    DATABASE_SECRET_ARN    = aws_secretsmanager_secret.db_credentials.arn
    APP_CONFIG_SECRET_NAME = aws_secretsmanager_secret.app_config.name
  }

  depends_on = [kubernetes_namespace.bond_ai]
}

# =============================================================================
# Deployment — Same combined image as App Runner
# =============================================================================

resource "kubernetes_deployment" "backend" {
  count = var.enable_eks ? 1 : 0

  metadata {
    name      = "bond-ai-backend"
    namespace = kubernetes_namespace.bond_ai[0].metadata[0].name
    labels = {
      app = "bond-ai-backend"
    }
  }

  spec {
    replicas = var.eks_node_desired_count

    selector {
      match_labels = {
        app = "bond-ai-backend"
      }
    }

    template {
      metadata {
        labels = {
          app = "bond-ai-backend"
        }
      }

      spec {
        service_account_name = kubernetes_service_account.backend[0].metadata[0].name

        container {
          name  = "bond-ai"
          image = "${aws_ecr_repository.backend.repository_url}:${local.combined_image_tag}"
          port {
            container_port = 8080
          }

          security_context {
            allow_privilege_escalation = false

            capabilities {
              drop = ["ALL"]
              # CHOWN: nginx chowns /var/lib/nginx/* to www-data (uid 33) at startup
              # DAC_OVERRIDE: nginx reads config files owned by root
              # SETGID/SETUID: nginx master drops to www-data for worker processes
              add  = ["CHOWN", "DAC_OVERRIDE", "SETGID", "SETUID"]
            }
          }

          env_from {
            config_map_ref {
              name = kubernetes_config_map.backend[0].metadata[0].name
            }
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.backend[0].metadata[0].name
            }
          }

          resources {
            requests = {
              cpu    = "500m"
              memory = "1Gi"
            }
            limits = {
              cpu    = "1000m"
              memory = "2Gi"
            }
          }

          liveness_probe {
            http_get {
              path = "/health"
              port = 8080
            }
            initial_delay_seconds = 30
            period_seconds        = 10
            failure_threshold     = 5
          }

          readiness_probe {
            http_get {
              path = "/health"
              port = 8080
            }
            initial_delay_seconds = 15
            period_seconds        = 10
            failure_threshold     = 3
          }
        }
      }
    }
  }

  depends_on = [
    kubernetes_namespace.bond_ai,
    kubernetes_service_account.backend,
    null_resource.build_combined_image
  ]
}

# =============================================================================
# Service
#
# Two modes based on whether an externally-managed ALB target group is provided:
#
# 1. eks_target_group_arn set (ALB via TargetGroupBinding):
#    type = ClusterIP — no cloud load balancer created; the AWS Load Balancer
#    Controller keeps pod IPs registered in the external target group directly.
#
# 2. eks_target_group_arn empty (fallback — self-managed load balancer):
#    type = LoadBalancer with AWS Load Balancer Controller annotations to create
#    an internal NLB (IP target mode). Requires ALB creation to NOT be blocked
#    by SCP, or use a policy that allows NLB creation via the LB Controller.
# =============================================================================

locals {
  eks_use_external_alb = var.eks_target_group_arn != ""
}

resource "kubernetes_service" "backend" {
  count = var.enable_eks ? 1 : 0

  metadata {
    name      = "bond-ai-backend"
    namespace = kubernetes_namespace.bond_ai[0].metadata[0].name
    annotations = local.eks_use_external_alb ? {} : merge(
      {
        "service.beta.kubernetes.io/aws-load-balancer-type"            = "external"
        "service.beta.kubernetes.io/aws-load-balancer-nlb-target-type" = "ip"
        "service.beta.kubernetes.io/aws-load-balancer-scheme"          = "internal"
        "service.beta.kubernetes.io/aws-load-balancer-subnets"         = join(",", local.app_runner_subnet_ids)
      },
      local.eks_has_tls ? {
        "service.beta.kubernetes.io/aws-load-balancer-ssl-cert"              = local.eks_cert_arn
        "service.beta.kubernetes.io/aws-load-balancer-ssl-ports"             = "443"
        "service.beta.kubernetes.io/aws-load-balancer-ssl-negotiation-policy" = "ELBSecurityPolicy-TLS13-1-2-2021-06"
      } : {}
    )
  }

  spec {
    selector = {
      app = "bond-ai-backend"
    }

    type = local.eks_use_external_alb ? "ClusterIP" : "LoadBalancer"

    port {
      port        = local.eks_use_external_alb ? 8080 : (local.eks_has_tls ? 443 : 80)
      target_port = 8080
      protocol    = "TCP"
    }
  }

  depends_on = [kubernetes_deployment.backend]
}

# =============================================================================
# TargetGroupBinding — Wires pod IPs into the externally-managed ALB target group.
# The LB Controller watches Service endpoints and keeps the target group in sync
# as pods restart or scale. Requires eks_target_group_arn to be set.
# =============================================================================

resource "kubernetes_manifest" "target_group_binding" {
  count = var.enable_eks && var.eks_target_group_arn != "" ? 1 : 0

  manifest = {
    apiVersion = "elbv2.k8s.aws/v1beta1"
    kind       = "TargetGroupBinding"
    metadata = {
      name      = "bond-ai-backend"
      namespace = kubernetes_namespace.bond_ai[0].metadata[0].name
    }
    spec = {
      serviceRef = {
        name = kubernetes_service.backend[0].metadata[0].name
        port = 8080
      }
      targetGroupARN = var.eks_target_group_arn
    }
  }

  depends_on = [helm_release.lb_controller, kubernetes_service.backend]
}

# =============================================================================
# Horizontal Pod Autoscaler
# =============================================================================

resource "kubernetes_horizontal_pod_autoscaler_v2" "backend" {
  count = var.enable_eks ? 1 : 0

  metadata {
    name      = "bond-ai-backend"
    namespace = kubernetes_namespace.bond_ai[0].metadata[0].name
  }

  spec {
    scale_target_ref {
      api_version = "apps/v1"
      kind        = "Deployment"
      name        = kubernetes_deployment.backend[0].metadata[0].name
    }

    min_replicas = 1
    max_replicas = var.environment == "prod" ? 10 : 2

    metric {
      type = "Resource"
      resource {
        name = "cpu"
        target {
          type                = "Utilization"
          average_utilization = 70
        }
      }
    }
  }

  depends_on = [kubernetes_deployment.backend]
}

# =============================================================================
# NetworkPolicy — NOT IMPLEMENTED (requires CNI change)
#
# AWS VPC CNI (default EKS CNI) does NOT enforce Kubernetes NetworkPolicy.
# Creating a NetworkPolicy resource would exist in etcd but have zero effect
# on traffic. Enforcement requires installing Calico or Cilium as a CNI addon.
#
# Future work: Install Calico/Cilium, then add NetworkPolicy restricting:
#   - Ingress: port 8080 only (from ALB)
#   - Egress: DNS (53), HTTPS (443), PostgreSQL (5432)
#   - Note: 443 egress must be unrestricted (OAuth providers + MCP servers have dynamic IPs)
# =============================================================================

# =============================================================================
# Pod Disruption Budget — Ensure at least 1 pod during updates
# =============================================================================

resource "kubernetes_pod_disruption_budget_v1" "backend" {
  count = var.enable_eks ? 1 : 0

  metadata {
    name      = "bond-ai-backend"
    namespace = kubernetes_namespace.bond_ai[0].metadata[0].name
  }

  spec {
    max_unavailable = "1"

    selector {
      match_labels = {
        app = "bond-ai-backend"
      }
    }
  }

  depends_on = [kubernetes_deployment.backend]
}
