# S3 Connectivity Issue Analysis and Fix

## Problem Description

The Bond AI application deployed via App Runner in existing VPC is experiencing timeout errors when attempting to connect to S3. The backend service fails after Okta authentication with the following error:

```
urllib3.exceptions.ConnectTimeoutError: Connection to bond-bedrock-files-eea42686090e4a1ebcb82b36abf98c40.s3.us-west-2.amazonaws.com timed out. (connect timeout=60)
```

## Root Cause Analysis

### Current Network Configuration
1. **App Runner VPC Egress Mode**: Backend service uses `egress_type = "VPC"` in `backend.tf:74-76`
2. **Private Subnets**: App Runner VPC connector routes traffic through private subnets (identified by `map-public-ip-on-launch = false`)
3. **Missing Connectivity**: No VPC endpoints or NAT Gateway configured for external AWS service access

### Why S3 Fails
- App Runner routes ALL traffic through VPC connector into private subnets
- Private subnets have no internet gateway or NAT gateway routes
- No VPC endpoints exist for AWS services (S3, Secrets Manager, Bedrock)
- Traffic to `*.s3.us-west-2.amazonaws.com` has no valid route

### Why Okta Works (Initially)
- Okta authentication may use different network timeouts
- Initial requests might succeed before the S3 dependency is triggered
- The failure occurs ~3 minutes after auth when S3 access is attempted

## Proposed Solution: VPC Endpoints

### Why VPC Endpoints Solve This
1. **Private AWS Network**: VPC endpoints route traffic through AWS's private backbone
2. **No Internet Required**: Eliminates need for NAT Gateway or internet access
3. **Security**: Traffic never leaves AWS network
4. **Cost Effective**: S3 gateway endpoint is free, interface endpoints ~$7/month each

## CONSERVATIVE MINIMAL FIX (RECOMMENDED)

Based on the error logs, the primary issue is S3 connectivity. The application successfully:
- Reads Okta configuration (Secrets Manager may work via different path)
- Initializes Bedrock providers
- Only fails on S3 connection timeout

**Conservative Approach**: Fix S3 first, add other endpoints only if needed after testing.

### Minimal Implementation - S3 Only

**Files to change:**

### 1. Create New File: `vpc-endpoints.tf`
```hcl
# VPC Endpoint for S3 (Gateway type - FREE, no security groups needed)
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = data.aws_vpc.existing.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = data.aws_route_tables.private.ids

  tags = {
    Name = "${var.project_name}-${var.environment}-s3-endpoint"
  }
}
```

### 2. Update `data-sources.tf`
Add this data source (needed for S3 gateway endpoint):
```hcl
# Get route tables for private subnets (needed for S3 gateway endpoint)
data "aws_route_tables" "private" {
  vpc_id = data.aws_vpc.existing.id

  filter {
    name   = "association.subnet-id"
    values = data.aws_subnets.private.ids
  }
}
```

**That's it!** These 2 changes should fix the S3 timeout issue.

### Why This Minimal Fix Works
- **S3 Gateway Endpoint**: Routes S3 traffic through AWS private network
- **No Security Groups**: Gateway endpoints don't need security group rules
- **No Cost**: S3 gateway endpoints are completely free
- **Automatic Routes**: Gateway endpoints automatically update route tables

---

## FULL IMPLEMENTATION (if minimal fix needs expansion)

If after testing the minimal fix you need Secrets Manager or Bedrock endpoints:

### Additional VPC Endpoints (add to vpc-endpoints.tf)
```hcl
# VPC Endpoint for Secrets Manager (Interface type)
resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id              = data.aws_vpc.existing.id
  service_name        = "com.amazonaws.${var.aws_region}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = local.app_runner_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = {
    Name = "${var.project_name}-${var.environment}-secretsmanager-endpoint"
  }
}

# VPC Endpoint for Bedrock (Interface type)
resource "aws_vpc_endpoint" "bedrock" {
  vpc_id              = data.aws_vpc.existing.id
  service_name        = "com.amazonaws.${var.aws_region}.bedrock-runtime"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = local.app_runner_subnet_ids
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = {
    Name = "${var.project_name}-${var.environment}-bedrock-endpoint"
  }
}
```

### Security Group for Interface Endpoints (add to security.tf)
```hcl
# Security Group for VPC Interface Endpoints
resource "aws_security_group" "vpc_endpoints" {
  name_prefix = "${var.project_name}-${var.environment}-vpc-endpoints-"
  description = "Security group for VPC interface endpoints"
  vpc_id      = data.aws_vpc.existing.id

  ingress {
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.app_runner.id]
    description     = "HTTPS from App Runner"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-vpc-endpoints-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}
```

## Alternative Solutions Considered

### Option 2: Switch to DEFAULT Egress Mode
**Change in `backend.tf`:**
```hcl
# Remove or comment out network_configuration block entirely
# network_configuration {
#   egress_configuration {
#     egress_type       = "VPC"
#     vpc_connector_arn = aws_apprunner_vpc_connector.backend.arn
#   }
# }
```
**Pros**: Simple, immediate fix
**Cons**: Less secure (traffic goes over internet), loses VPC network isolation

### Option 3: Add NAT Gateway (Not Recommended)
Would require creating NAT Gateway, Elastic IP, and updating route tables.
**Pros**: Full internet access
**Cons**: Expensive (~$32/month), less secure, more complex

## Expected Results After Fix

1. **S3 Connectivity**: Backend will successfully connect to S3 bucket
2. **Secrets Manager**: Database credential retrieval will work
3. **Bedrock**: AI service calls will function properly
4. **Security**: All traffic stays within AWS private network
5. **Cost**: Minimal additional cost (~$14/month for interface endpoints)

## Testing Plan

After implementation:
1. Deploy Terraform changes: `terraform apply`
2. Test health endpoint: `curl https://BACKEND_URL/health`
3. Test full authentication flow through frontend
4. Verify S3 operations work without timeouts
5. Check CloudWatch logs for successful AWS service calls

## Rollback Plan

If issues occur:
1. Remove VPC endpoint resources from Terraform
2. Switch to DEFAULT egress mode temporarily
3. Investigate and fix any routing issues
4. Re-implement VPC endpoints with corrections