# ============================================================================
# Microsoft Graph MCP Server - Outputs
# ============================================================================

output "mcp_microsoft_service_url" {
  value       = var.mcp_microsoft_enabled ? "https://${aws_apprunner_service.mcp_microsoft[0].service_url}" : "Not deployed (mcp_microsoft_enabled = false)"
  description = "Microsoft Graph MCP server URL"
}

output "mcp_microsoft_mcp_endpoint" {
  value       = var.mcp_microsoft_enabled ? "https://${aws_apprunner_service.mcp_microsoft[0].service_url}/mcp" : "Not deployed"
  description = "MCP endpoint URL for bond_mcp_config"
}

output "mcp_microsoft_service_arn" {
  value       = var.mcp_microsoft_enabled ? aws_apprunner_service.mcp_microsoft[0].arn : ""
  description = "Microsoft MCP App Runner service ARN"
}

output "mcp_microsoft_ecr_repository" {
  value       = var.mcp_microsoft_enabled ? aws_ecr_repository.mcp_microsoft[0].repository_url : ""
  description = "ECR repository URL for Microsoft MCP image"
}
