# Shared backend configuration (environment variables) + App Runner VPC connector.
# The App Runner compute path is retired (the platform runs on EKS consume
# mode — see eks-kubernetes.tf); this file keeps only what is still live.

locals {

  # ==========================================================================
  # Shared environment variables for all compute platforms
  # Used by App Runner (backend.tf) and ECS Express (ecs-express.tf)
  # Same pattern as local.backend_shared_policy_statements in iam.tf
  # ==========================================================================
  backend_env_vars = {
    AWS_REGION                = var.aws_region
    BOND_PROVIDER_CLASS       = "bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider"
    DATABASE_SECRET_ARN       = aws_secretsmanager_secret.db_credentials.arn
    S3_BUCKET_NAME            = aws_s3_bucket.uploads.id
    BEDROCK_S3_BUCKET         = aws_s3_bucket.uploads.id
    BEDROCK_AGENT_ROLE_ARN    = aws_iam_role.bedrock_agent.arn
    BEDROCK_DEFAULT_MODEL     = var.bedrock_default_model
    BEDROCK_SELECTABLE_MODELS = var.bedrock_selectable_models

    # App config secret (JWT key, OAuth client IDs/secrets read at runtime)
    APP_CONFIG_SECRET_NAME = aws_secretsmanager_secret.app_config.name

    # Okta OAuth Configuration
    OAUTH2_ENABLED_PROVIDERS = var.oauth2_providers
    OKTA_DOMAIN              = var.okta_domain
    OKTA_SECRET_NAME         = var.okta_secret_name
    OKTA_REDIRECT_URI        = var.okta_redirect_uri != "" ? var.okta_redirect_uri : "https://BACKEND_URL_PLACEHOLDER/auth/okta/callback"
    OKTA_SCOPES              = var.okta_scopes

    # AWS Cognito OAuth Configuration (only if configured)
    COGNITO_DOMAIN       = var.cognito_domain
    COGNITO_SECRET_NAME  = var.cognito_secret_name
    COGNITO_REDIRECT_URI = var.cognito_redirect_uri != "" ? var.cognito_redirect_uri : (var.cognito_domain != "" ? "https://BACKEND_URL_PLACEHOLDER/auth/cognito/callback" : "")
    COGNITO_SCOPES       = var.cognito_scopes
    COGNITO_REGION       = var.cognito_region

    # JWT redirect URI for frontend - same origin now (root of the service)
    JWT_REDIRECT_URI = var.jwt_redirect_uri != "" ? var.jwt_redirect_uri : "*"

    # CORS configuration - keep for local dev compatibility
    CORS_ALLOWED_ORIGINS = var.cors_allowed_origins

    # Allowed redirect domains for OAuth callbacks (security)
    ALLOWED_REDIRECT_DOMAINS = var.allowed_redirect_domains

    # Knowledge Base configuration (only set when KB is enabled)
    BEDROCK_KNOWLEDGE_BASE_ID = try(aws_bedrockagent_knowledge_base.main[0].id, "")
    BEDROCK_KB_DATA_SOURCE_ID = try(aws_bedrockagent_data_source.s3[0].data_source_id, "")
    BEDROCK_KB_S3_PREFIX      = var.enable_knowledge_base ? "knowledge-base/" : ""

    # Admin configuration (prefer ADMIN_USERS for multiple admins)
    ADMIN_USERS = var.admin_users
    ADMIN_EMAIL = var.admin_email # Legacy fallback for backward compatibility

    # Email validation: allow all authenticated IdP users (T-O6)
    ALLOW_ALL_EMAILS       = var.allow_all_emails
    SCHEDULED_JOBS_ENABLED = var.scheduled_jobs_enabled

    # Cookie security: "true" in production (HTTPS), "false" for local dev (HTTP)
    COOKIE_SECURE = "true"

    # Bedrock Guardrails
    BEDROCK_GUARDRAIL_ID      = var.enable_guardrails ? aws_bedrock_guardrail.main[0].guardrail_id : ""
    BEDROCK_GUARDRAIL_VERSION = var.enable_guardrails ? (var.bedrock_guardrail_version != "" ? var.bedrock_guardrail_version : aws_bedrock_guardrail_version.main[0].version) : ""

    # bond-mcps managed-MCP discovery + RFC 8693 token exchange (empty = both
    # features disabled; see docs/PLATFORM-CONTRACT.md "Auth seam")
    BOND_MCPS_DISCOVERY_URL = var.bond_mcps_discovery_url
    BOND_MCPS_AS_BASE_URL   = var.bond_mcps_as_base_url
  }
}

# App Runner VPC Connector for database access.
# KEPT deliberately (2026-08-31) even though no App Runner services exist:
# the bond-ai-dev-connector and its security group are referenced by the
# Aurora/RDS/KB security-group ingress rules, and external MCP deployments
# historically used it. Removing it means touching live database security
# groups — do that as its own reviewed change, not as dead-code cleanup.
resource "aws_apprunner_vpc_connector" "backend" {
  vpc_connector_name = "${var.project_name}-${var.environment}-connector"
  subnets            = local.app_runner_subnet_ids
  security_groups    = [aws_security_group.app_runner.id]

  tags = {
    Name = "${var.project_name}-${var.environment}-vpc-connector"
  }
}
