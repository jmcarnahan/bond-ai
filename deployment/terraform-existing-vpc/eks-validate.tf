# =============================================================================
# EKS Post-Deploy Validation
# Runs kubectl commands to verify the deployment after apply.
# All resources gated by var.enable_eks (default: false)
# =============================================================================

resource "null_resource" "validate_eks_deployment" {
  count = var.enable_eks ? 1 : 0

  triggers = {
    deployment_id = kubernetes_deployment.backend[0].spec[0].template[0].spec[0].container[0].image
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
      echo "--- ALB Endpoint ---"
      ALB_HOST="${var.eks_alb_dns_name}"
      if [ -z "$ALB_HOST" ]; then
        TG_ARN=$(kubectl get targetgroupbinding -n bond-ai bond-ai-backend \
          -o jsonpath='{.spec.targetGroupARN}' 2>/dev/null || echo "")
        if [ -n "$TG_ARN" ] && [ "$TG_ARN" != "pending" ]; then
          ALB_ARN=$(aws elbv2 describe-target-groups \
            --target-group-arns "$TG_ARN" \
            --region ${var.aws_region} \
            --query 'TargetGroups[0].LoadBalancerArns[0]' \
            --output text 2>/dev/null || echo "")
          if [ -n "$ALB_ARN" ] && [ "$ALB_ARN" != "None" ]; then
            ALB_HOST=$(aws elbv2 describe-load-balancers \
              --load-balancer-arns "$ALB_ARN" \
              --region ${var.aws_region} \
              --query 'LoadBalancers[0].DNSName' \
              --output text 2>/dev/null || echo "pending")
          fi
        fi
        ALB_HOST=$${ALB_HOST:-pending}
      fi
      echo "ALB: $ALB_HOST"

      echo ""
      echo "--- TargetGroupBinding Status ---"
      kubectl get targetgroupbinding -n bond-ai 2>/dev/null || echo "No TargetGroupBinding found"

      echo ""
      echo "--- HPA Status ---"
      kubectl get hpa -n bond-ai 2>/dev/null || echo "No HPA found"

      echo ""
      echo "--- TLS Check ---"
      if [ -n "$ALB_HOST" ] && [ "$ALB_HOST" != "pending" ]; then
        # Verify TLS listener is active on port 443
        timeout 5 openssl s_client -connect "$ALB_HOST:443" -servername "$ALB_HOST" </dev/null 2>/dev/null | head -5 || \
          echo "Warning: TLS handshake failed or timed out"
      else
        echo "Skipped (no ALB hostname yet)"
      fi

      echo ""
      echo "--- LB Controller Status ---"
      kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller -o wide 2>/dev/null || \
        echo "Warning: AWS Load Balancer Controller not found"

      echo ""
      echo "========================================"
      echo "EKS validation complete."
      echo "EKS service is PRIVATE (internal ALB) — use VPN to access."
      if [ -n "$ALB_HOST" ] && [ "$ALB_HOST" != "pending" ]; then
        echo "Test from VPN: curl -f https://$ALB_HOST/health"
        if [ -n "${var.eks_custom_domain_name}" ]; then
          echo "Custom domain: https://${var.eks_custom_domain_name}"
        fi
      fi
      echo "========================================"
    EOT
  }

  depends_on = [
    kubernetes_deployment.backend,
    kubernetes_service.backend,
    kubernetes_manifest.target_group_binding,
  ]
}
