# Custom Domain Configuration for Frontend
# Requires domain to be registered first via AWS Console
# Note: AWS automatically creates a hosted zone when registering a domain
#
# Usage:
#   - Set custom_domain_name = "yourdomain.com" to enable
#   - Leave custom_domain_name = "" (default) to skip custom domain setup

locals {
  custom_domain_enabled = var.custom_domain_name != ""
  # Use hosted_zone_name if provided, otherwise fall back to custom_domain_name (for root domains)
  hosted_zone_name = var.hosted_zone_name != "" ? var.hosted_zone_name : var.custom_domain_name
}

# Use the existing Route 53 Hosted Zone (created automatically during domain registration)
data "aws_route53_zone" "frontend" {
  count = local.custom_domain_enabled ? 1 : 0
  name  = local.hosted_zone_name
}

# Get App Runner Hosted Zone ID for this region
data "aws_apprunner_hosted_zone_id" "main" {
  count  = local.custom_domain_enabled ? 1 : 0
  region = var.aws_region
}

# Associate custom domain with App Runner service
resource "aws_apprunner_custom_domain_association" "frontend" {
  count                = local.custom_domain_enabled ? 1 : 0
  domain_name          = var.custom_domain_name
  service_arn          = aws_apprunner_service.frontend.arn
  enable_www_subdomain = var.enable_www_subdomain
}

# Certificate validation CNAME records
# App Runner requires these records for ACM certificate validation
# Using null_resource to create records via AWS CLI after association is established
# This avoids the Terraform "count depends on resource attributes" limitation
resource "null_resource" "cert_validation_records" {
  count = local.custom_domain_enabled ? 1 : 0

  triggers = {
    domain_association = aws_apprunner_custom_domain_association.frontend[0].id
    zone_id            = data.aws_route53_zone.frontend[0].zone_id
  }

  provisioner "local-exec" {
    command = <<-EOT
      # Wait for the association to be fully created
      sleep 5

      # Get the certificate validation records from the association
      RECORDS=$(aws apprunner describe-custom-domains \
        --service-arn "${aws_apprunner_service.frontend.arn}" \
        --region "${var.aws_region}" \
        --query "CustomDomains[?DomainName=='${var.custom_domain_name}'].CertificateValidationRecords[]" \
        --output json)

      # Create each validation record in Route 53
      echo "$RECORDS" | jq -c '.[]' | while read -r record; do
        NAME=$(echo "$record" | jq -r '.Name')
        VALUE=$(echo "$record" | jq -r '.Value')
        TYPE=$(echo "$record" | jq -r '.Type')

        echo "Creating validation record: $NAME -> $VALUE"

        aws route53 change-resource-record-sets \
          --hosted-zone-id "${data.aws_route53_zone.frontend[0].zone_id}" \
          --change-batch '{
            "Changes": [{
              "Action": "UPSERT",
              "ResourceRecordSet": {
                "Name": "'"$NAME"'",
                "Type": "'"$TYPE"'",
                "TTL": 300,
                "ResourceRecords": [{"Value": "'"$VALUE"'"}]
              }
            }]
          }'
      done

      echo "Certificate validation records created successfully"
    EOT
  }

  depends_on = [aws_apprunner_custom_domain_association.frontend]
}

# Alias A record pointing to App Runner
resource "aws_route53_record" "frontend_alias" {
  count   = local.custom_domain_enabled ? 1 : 0
  zone_id = data.aws_route53_zone.frontend[0].zone_id
  name    = var.custom_domain_name
  type    = "A"

  alias {
    name                   = aws_apprunner_service.frontend.service_url
    zone_id                = data.aws_apprunner_hosted_zone_id.main[0].id
    evaluate_target_health = true
  }
}

# Optional: www subdomain alias
resource "aws_route53_record" "frontend_www_alias" {
  count   = local.custom_domain_enabled && var.enable_www_subdomain ? 1 : 0
  zone_id = data.aws_route53_zone.frontend[0].zone_id
  name    = "www.${var.custom_domain_name}"
  type    = "A"

  alias {
    name                   = aws_apprunner_service.frontend.service_url
    zone_id                = data.aws_apprunner_hosted_zone_id.main[0].id
    evaluate_target_health = true
  }
}
