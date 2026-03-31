# =============================================================================
# EKS Post-Deploy Validation
# Runs kubectl commands to verify the deployment after apply.
# All resources gated by var.enable_eks (default: false)
# =============================================================================

resource "null_resource" "validate_eks_deployment" {
  count = var.enable_eks ? 1 : 0

  triggers = {
    deployment_id = kubernetes_deployment.backend[0].metadata[0].resource_version
  }

  provisioner "local-exec" {
    command = <<-EOT
      echo "========================================"
      echo "Validating EKS deployment..."
      echo "========================================"

      # Configure kubectl
      aws eks update-kubeconfig \
        --name ${module.eks[0].cluster_name} \
        --region ${var.aws_region} 2>/dev/null

      echo ""
      echo "--- Pod Status ---"
      kubectl get pods -n bond-ai -l app=bond-ai-backend -o wide 2>/dev/null || \
        echo "Warning: kubectl not available or not configured"

      echo ""
      echo "--- Service Status ---"
      kubectl get svc -n bond-ai bond-ai-backend -o wide 2>/dev/null || \
        echo "Warning: could not get service status"

      echo ""
      echo "--- NLB Hostname ---"
      NLB_HOST=$(kubectl get svc -n bond-ai bond-ai-backend \
        -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "pending")
      echo "NLB: $NLB_HOST"

      echo ""
      echo "--- HPA Status ---"
      kubectl get hpa -n bond-ai 2>/dev/null || echo "No HPA found"

      echo ""
      echo "========================================"
      echo "EKS validation complete."
      echo "EKS service is PRIVATE (internal NLB) — use VPN to access."
      if [ -n "$NLB_HOST" ] && [ "$NLB_HOST" != "pending" ]; then
        echo "Test from VPN: curl -ksf https://$NLB_HOST/health"
      fi
      echo "========================================"
    EOT
  }

  depends_on = [
    kubernetes_deployment.backend,
    kubernetes_service.backend
  ]
}
