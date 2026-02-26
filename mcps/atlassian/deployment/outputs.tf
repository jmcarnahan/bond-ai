# ============================================================================
# Atlassian MCP Server - Outputs
# ============================================================================

output "mcp_atlassian_service_url" {
  value       = var.mcp_atlassian_v2_enabled ? "https://${aws_apprunner_service.mcp_atlassian[0].service_url}" : "Not deployed (mcp_atlassian_v2_enabled = false)"
  description = "Atlassian MCP server URL"
}

output "mcp_atlassian_mcp_endpoint" {
  value       = var.mcp_atlassian_v2_enabled ? "https://${aws_apprunner_service.mcp_atlassian[0].service_url}/mcp" : "Not deployed"
  description = "MCP endpoint URL for bond_mcp_config"
}

output "mcp_atlassian_service_arn" {
  value       = var.mcp_atlassian_v2_enabled ? aws_apprunner_service.mcp_atlassian[0].arn : ""
  description = "Atlassian MCP App Runner service ARN"
}

output "mcp_atlassian_ecr_repository" {
  value       = var.mcp_atlassian_v2_enabled ? aws_ecr_repository.mcp_atlassian[0].repository_url : ""
  description = "ECR repository URL for Atlassian MCP image"
}
