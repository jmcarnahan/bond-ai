# Bond AI Phased Deployment Makefile
# This ensures proper deployment order and dependency management

.PHONY: help deploy deploy-phase1 deploy-phase2 deploy-phase3 deploy-phase4 validate-phase1 validate-phase2 validate-phase3 destroy init plan

# Default environment file
ENV_FILE ?= environments/minimal-us-east-2.tfvars
AWS_REGION ?= us-east-2
AWS_ACCOUNT ?= 119684128788

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)Bond AI Phased Deployment Commands$(NC)"
	@echo "===================================="
	@echo ""
	@echo "$(GREEN)Main Commands:$(NC)"
	@echo "  make init        - Initialize Terraform (run first time)"
	@echo "  make deploy      - Deploy everything in proper order"
	@echo "  make destroy     - Destroy all infrastructure"
	@echo ""
	@echo "$(YELLOW)Phased Deployment (for troubleshooting):$(NC)"
	@echo "  make deploy-phase1 - Infrastructure (VPC, RDS, S3, ECR, IAM)"
	@echo "  make deploy-phase2 - Backend (build Docker, deploy service)"
	@echo "  make deploy-phase3 - Frontend (build Docker with backend URL, deploy)"
	@echo "  make deploy-phase4 - Post-deployment (CORS, redirects)"
	@echo ""
	@echo "$(BLUE)Validation Commands:$(NC)"
	@echo "  make validate    - Run all validations"
	@echo "  make status      - Check service status"
	@echo "  make outputs     - Show deployment outputs"

# ============================================================================
# Primary Commands
# ============================================================================

init: ## Initialize Terraform (run this first time)
	@echo "$(GREEN)Initializing Terraform...$(NC)"
	cd terraform && terraform init
	@echo "$(GREEN)Terraform initialized!$(NC)"

deploy: init ## Deploy everything in proper order
	@echo "$(BLUE)========================================$(NC)"
	@echo "$(BLUE)Starting Bond AI Phased Deployment$(NC)"
	@echo "$(BLUE)========================================$(NC)"
	@$(MAKE) deploy-phase1
	@$(MAKE) validate-phase1
	@$(MAKE) deploy-phase2
	@$(MAKE) validate-phase2
	@$(MAKE) deploy-phase3
	@$(MAKE) validate-phase3
	@$(MAKE) deploy-phase4
	@echo "$(GREEN)========================================$(NC)"
	@echo "$(GREEN)✅ Deployment Complete!$(NC)"
	@echo "$(GREEN)========================================$(NC)"
	@$(MAKE) outputs
	@echo ""
	@echo "$(YELLOW)⚠️  MANUAL STEP REQUIRED:$(NC)"
	@echo "$(YELLOW)=========================$(NC)"
	@echo "Please update your Okta application with the backend callback URL:"
	@echo ""
	@BACKEND_URL=$$(cd terraform && terraform output -raw app_runner_service_url 2>/dev/null) && \
		echo "  1. Go to: https://trial-9457917.okta.com/admin/app/oidc_client/instance/0oas1uz67oWaTK8iP697#tab-general" && \
		echo "  2. Add to 'Sign-in redirect URIs':" && \
		echo "     $(GREEN)https://$$BACKEND_URL/auth/okta/callback$(NC)" && \
		echo "  3. Click 'Save'" && \
		echo ""
	@echo "Once this is done, OAuth login will work correctly!"

# ============================================================================
# Phase 1: Infrastructure
# ============================================================================

deploy-phase1: ## Deploy infrastructure (VPC, RDS, S3, ECR, IAM)
	@echo ""
	@echo "$(BLUE)📦 Phase 1: Deploying Infrastructure...$(NC)"
	@echo "----------------------------------------"
	cd terraform && terraform apply -var-file=$(ENV_FILE) \
		-target=aws_vpc.main \
		-target=aws_subnet.public \
		-target=aws_subnet.database \
		-target=aws_internet_gateway.main \
		-target=aws_eip.nat \
		-target=aws_nat_gateway.main \
		-target=aws_route_table.public \
		-target=aws_route_table.private \
		-target=aws_route_table_association.public \
		-target=aws_route_table_association.database \
		-target=aws_security_group.app_runner \
		-target=aws_security_group.rds \
		-target=aws_security_group.vpc_endpoints \
		-target=aws_db_subnet_group.main \
		-target=aws_db_instance.main \
		-target=aws_secretsmanager_secret.db_credentials \
		-target=aws_secretsmanager_secret_version.db_credentials \
		-target=aws_s3_bucket.uploads \
		-target=aws_s3_bucket_public_access_block.uploads \
		-target=aws_s3_bucket_versioning.uploads \
		-target=aws_s3_bucket_server_side_encryption_configuration.uploads \
		-target=aws_s3_bucket_cors_configuration.uploads \
		-target=aws_ecr_repository.backend \
		-target=aws_ecr_repository.frontend \
		-target=aws_ecr_repository_policy.frontend \
		-target=aws_iam_role.app_runner_instance \
		-target=aws_iam_role_policy.app_runner_instance \
		-target=aws_iam_role.app_runner_ecr_access \
		-target=aws_iam_role_policy_attachment.app_runner_ecr_access \
		-target=aws_iam_role.frontend_apprunner_instance \
		-target=aws_apprunner_vpc_connector.backend \
		-target=aws_apprunner_auto_scaling_configuration_version.backend \
		-target=random_password.db_password \
		-target=random_password.jwt_secret \
		-target=data.aws_secretsmanager_secret.okta_secret \
		-target=data.aws_secretsmanager_secret_version.okta_secret \
		-target=aws_vpc_endpoint.s3 \
		-target=aws_vpc_endpoint.bedrock \
		-target=aws_vpc_endpoint.bedrock_runtime \
		-auto-approve
	@echo "$(GREEN)✅ Phase 1 Complete: Infrastructure deployed$(NC)"

validate-phase1: ## Validate Phase 1 deployment
	@echo "$(YELLOW)🔍 Validating Phase 1...$(NC)"
	@aws ecr describe-repositories --repository-names bond-ai-dev-backend bond-ai-dev-frontend --region $(AWS_REGION) >/dev/null 2>&1 && \
		echo "$(GREEN)  ✓ ECR repositories created$(NC)" || \
		echo "$(RED)  ✗ ECR repositories missing$(NC)"
	@aws rds describe-db-instances --db-instance-identifier bond-ai-dev-db --region $(AWS_REGION) >/dev/null 2>&1 && \
		echo "$(GREEN)  ✓ RDS database created$(NC)" || \
		echo "$(RED)  ✗ RDS database missing$(NC)"
	@aws s3api head-bucket --bucket bond-ai-dev-uploads-$(AWS_ACCOUNT) --region $(AWS_REGION) 2>/dev/null && \
		echo "$(GREEN)  ✓ S3 bucket created$(NC)" || \
		echo "$(RED)  ✗ S3 bucket missing$(NC)"

# ============================================================================
# Phase 2: Backend Service
# ============================================================================

deploy-phase2: ## Deploy backend (Docker build + AppRunner service)
	@echo ""
	@echo "$(BLUE)🚀 Phase 2: Deploying Backend Service...$(NC)"
	@echo "----------------------------------------"
	cd terraform && terraform apply -var-file=$(ENV_FILE) \
		-target=null_resource.build_backend_image \
		-target=aws_apprunner_service.backend \
		-auto-approve
	@echo "$(GREEN)✅ Phase 2 Complete: Backend deployed$(NC)"

validate-phase2: ## Validate Phase 2 deployment
	@echo "$(YELLOW)🔍 Validating Phase 2...$(NC)"
	@BACKEND_URL=$$(cd terraform && terraform output -raw app_runner_service_url 2>/dev/null) && \
		curl -sf $$BACKEND_URL/health >/dev/null && \
		echo "$(GREEN)  ✓ Backend health check passed$(NC)" || \
		echo "$(RED)  ✗ Backend health check failed$(NC)"
	@echo "$(GREEN)  Backend URL: $$(cd terraform && terraform output -raw app_runner_service_url 2>/dev/null)$(NC)"

# ============================================================================
# Phase 3: Frontend Service
# ============================================================================

deploy-phase3: ## Deploy frontend (Docker build with backend URL + AppRunner service)
	@echo ""
	@echo "$(BLUE)🎨 Phase 3: Deploying Frontend Service...$(NC)"
	@echo "----------------------------------------"
	cd terraform && terraform apply -var-file=$(ENV_FILE) \
		-target=null_resource.build_frontend_image \
		-target=aws_apprunner_service.frontend \
		-auto-approve
	@echo "$(GREEN)✅ Phase 3 Complete: Frontend deployed$(NC)"

validate-phase3: ## Validate Phase 3 deployment
	@echo "$(YELLOW)🔍 Validating Phase 3...$(NC)"
	@FRONTEND_URL=$$(cd terraform && terraform output -raw frontend_app_runner_service_url 2>/dev/null) && \
		curl -sf $$FRONTEND_URL >/dev/null && \
		echo "$(GREEN)  ✓ Frontend is accessible$(NC)" || \
		echo "$(RED)  ✗ Frontend is not accessible$(NC)"
	@echo "$(GREEN)  Frontend URL: $$(cd terraform && terraform output -raw frontend_app_runner_service_url 2>/dev/null)$(NC)"

# ============================================================================
# Phase 4: Post-Deployment Configuration
# ============================================================================

deploy-phase4: ## Update backend with CORS and redirect URLs
	@echo ""
	@echo "$(BLUE)⚙️  Phase 4: Post-Deployment Configuration...$(NC)"
	@echo "----------------------------------------"
	cd terraform && terraform apply -var-file=$(ENV_FILE) \
		-target=null_resource.update_backend_config \
		-auto-approve
	@echo "$(GREEN)✅ Phase 4 Complete: Configuration updated$(NC)"

# ============================================================================
# Validation & Status Commands
# ============================================================================

validate: ## Run all validations
	@echo "$(BLUE)Running Full Validation...$(NC)"
	@$(MAKE) validate-phase1
	@$(MAKE) validate-phase2
	@$(MAKE) validate-phase3
	@echo ""
	@echo "$(YELLOW)🔍 Validating CORS Configuration...$(NC)"
	@BACKEND_URL=$$(cd terraform && terraform output -raw app_runner_service_url 2>/dev/null) && \
	FRONTEND_URL=$$(cd terraform && terraform output -raw frontend_app_runner_service_url 2>/dev/null) && \
	curl -X OPTIONS $$BACKEND_URL/providers \
		-H "Origin: $$FRONTEND_URL" \
		-H "Access-Control-Request-Method: GET" \
		-I 2>/dev/null | grep -q "access-control-allow-origin" && \
		echo "$(GREEN)  ✓ CORS is properly configured$(NC)" || \
		echo "$(RED)  ✗ CORS configuration needs attention$(NC)"

status: ## Check deployment status
	@echo "$(GREEN)Checking deployment status...$(NC)"
	@aws apprunner list-services --region $(AWS_REGION) \
		--query "ServiceSummaryList[?contains(ServiceName, 'bond-ai')].{Name:ServiceName,Status:Status}" \
		--output table

outputs: ## Show Terraform outputs (URLs, etc.)
	@echo "$(GREEN)Deployment Information:$(NC)"
	@echo "======================="
	@cd terraform && terraform output | grep -E "backend|frontend|post_deployment"
	@echo ""
	@echo "$(YELLOW)⚠️  Remember: Manual Okta configuration required!$(NC)"
	@BACKEND_URL=$$(cd terraform && terraform output -raw app_runner_service_url 2>/dev/null) && \
		echo "Add https://$$BACKEND_URL/auth/okta/callback to Okta redirect URIs"

# ============================================================================
# Maintenance Commands
# ============================================================================

plan: ## Review deployment plan
	@echo "$(YELLOW)Planning deployment...$(NC)"
	cd terraform && terraform plan -var-file=$(ENV_FILE)

destroy: ## Destroy all infrastructure (CAREFUL!)
	@echo "$(RED)WARNING: This will destroy all infrastructure!$(NC)"
	@read -p "Are you sure? Type 'yes' to continue: " confirm && \
	if [ "$$confirm" = "yes" ]; then \
		cd terraform && terraform destroy -var-file=$(ENV_FILE) -auto-approve; \
		echo "$(RED)Infrastructure destroyed!$(NC)"; \
	else \
		echo "$(YELLOW)Destroy cancelled.$(NC)"; \
	fi

# ============================================================================
# Troubleshooting Commands
# ============================================================================

logs-backend: ## Tail backend logs
	@echo "$(GREEN)Tailing backend logs...$(NC)"
	aws logs tail /aws/apprunner/bond-ai-dev-backend --follow --region $(AWS_REGION)

logs-frontend: ## Tail frontend logs
	@echo "$(GREEN)Tailing frontend logs...$(NC)"
	aws logs tail /aws/apprunner/bond-ai-dev-frontend --follow --region $(AWS_REGION)

test-cors: ## Test CORS configuration
	@BACKEND_URL=$$(cd terraform && terraform output -raw app_runner_service_url 2>/dev/null) && \
	FRONTEND_URL=$$(cd terraform && terraform output -raw frontend_app_runner_service_url 2>/dev/null) && \
	echo "Testing CORS from $$FRONTEND_URL to $$BACKEND_URL" && \
	curl -X OPTIONS $$BACKEND_URL/providers \
		-H "Origin: $$FRONTEND_URL" \
		-H "Access-Control-Request-Method: GET" -I

# Default target
.DEFAULT_GOAL := help