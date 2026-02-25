# ============================================================================
# GitHub MCP Server - Outputs
# ============================================================================

output "mcp_github_service_url" {
  value       = var.mcp_github_enabled ? "https://${aws_apprunner_service.mcp_github[0].service_url}" : "Not deployed (mcp_github_enabled = false)"
  description = "GitHub MCP server URL"
}

output "mcp_github_mcp_endpoint" {
  value       = var.mcp_github_enabled ? "https://${aws_apprunner_service.mcp_github[0].service_url}/mcp" : "Not deployed"
  description = "MCP endpoint URL for bond_mcp_config"
}

output "mcp_github_service_arn" {
  value       = var.mcp_github_enabled ? aws_apprunner_service.mcp_github[0].arn : ""
  description = "GitHub MCP App Runner service ARN"
}

output "mcp_github_ecr_repository" {
  value       = var.mcp_github_enabled ? aws_ecr_repository.mcp_github[0].repository_url : ""
  description = "ECR repository URL for GitHub MCP image"
}
