# Bond AI App Runner Deployment Debugging Session Summary

**Date**: September 17, 2025
**Issue**: App Runner service fails health checks consistently after 9-10 minutes during deployment
**Context**: Deployment works in another AWS account with existing VPC, but fails in this specific VPC

## 🔍 What We've Tried and Learned

### 1. Initial Problem Identification
- **Symptom**: Terraform deployment fails with "App Runner Service CREATE_FAILED" after ~10 minutes
- **Error Pattern**: Health check fails on `HTTP /health port 8000`
- **Key Insight**: Application starts successfully (confirmed via logs), but health checks timeout

### 2. Application-Level Investigation ✅
**Status: CONFIRMED WORKING**

- ✅ **Health endpoint exists**: `/health` returns `{"status": "healthy"}`
- ✅ **Application startup successful**: Logs show BedrockProvider initialization, database connection, all components ready in ~4-5 seconds
- ✅ **Database connectivity working**: PostgreSQL connection established successfully
- ✅ **Container configuration correct**: Dockerfile uses `--host 0.0.0.0 --port 8000`

**Application logs from successful startup:**
```
[2025-09-17 20:53:36] INFO - Using provider class: bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider
[2025-09-17 20:53:40] INFO - Created all Bedrock metadata tables
[2025-09-17 20:53:40] INFO - Initialized BedrockMetadata with message storage
```

### 3. Infrastructure Fixes Applied ✅

#### 3.1 Subnet Configuration (FIXED)
- **Problem**: App Runner detected "public subnets" due to direct IGW routes
- **Solution**: Enhanced `data-sources.tf` to filter out subnets with direct IGW routes
- **Implementation**:
```hcl
subnets_with_igw_routes = flatten([
  for rt_id, rt in data.aws_route_table.each : [
    for assoc in rt.associations : assoc.subnet_id
    if assoc.subnet_id != null && length([
      for route in rt.routes : route.gateway_id
      if route.gateway_id != null && startswith(route.gateway_id, "igw-") && route.cidr_block == "0.0.0.0/0"
    ]) > 0
  ]
])
```

#### 3.2 RDS Subnet Group Error (FIXED)
- **Problem**: `subnet-018084036d2aa635d` in use by RDS but being removed
- **Solution**: Include existing RDS subnets in addition to truly private subnets
- **Implementation**:
```hcl
rds_subnet_ids = distinct(concat(
  ["subnet-018084036d2aa635d", "subnet-014b5d076741106ff"], # Existing RDS subnets
  local.truly_private_subnets
))
```

#### 3.3 Health Check Configuration (IMPROVED)
- **Problem**: 5-second timeout too short for app initialization
- **Solution**: Increased timeout and failure thresholds
- **Implementation**:
```hcl
health_check_configuration {
  protocol            = "HTTP"
  path               = "/health"
  interval            = 10
  timeout             = 10      # Increased from 5
  healthy_threshold   = 1
  unhealthy_threshold = 10      # Increased from 5
}
```

#### 3.4 Security Group Ingress Rule (ADDED)
- **Problem**: App Runner security group had no ingress rules for health checks
- **Solution**: Added ingress rule for port 8000 from VPC CIDR
- **Implementation**:
```hcl
ingress {
  from_port   = 8000
  to_port     = 8000
  protocol    = "tcp"
  cidr_blocks = [data.aws_vpc.existing.cidr_block]  # 10.6.28.0/23
  description = "Allow HTTP for health checks"
}
```

### 4. Deployment Attempts and Results

#### Attempt 1: Original Configuration
- **Result**: FAILED - "Public subnet ids detected"
- **Duration**: Immediate failure
- **Fix Applied**: Subnet filtering logic

#### Attempt 2: After Subnet Fix
- **Result**: FAILED - RDS subnet group error + App Runner CREATE_FAILED
- **Duration**: ~9 minutes
- **Issues**: Subnet still in use by RDS, health check timeout

#### Attempt 3: After RDS + Health Check Fixes
- **Result**: FAILED - App Runner CREATE_FAILED
- **Duration**: ~9.5 minutes
- **Issue**: Health check still failing despite increased timeouts

#### Attempt 4: After Security Group Fix
- **Result**: FAILED - App Runner CREATE_FAILED
- **Duration**: ~6 minutes (faster failure)
- **Issue**: Health check still failing even with ingress rules

## 🎯 Current Status and Key Findings

### What's Working ✅
1. **Application**: Starts correctly, connects to database, health endpoint responds
2. **Subnet Selection**: Terraform correctly identifies 8 truly private subnets
3. **Basic Infrastructure**: VPC connector, RDS, ECR, security groups all deploy successfully
4. **Image Building**: Backend Docker image builds and pushes to ECR successfully

### What's Still Failing ❌
1. **App Runner Health Checks**: Consistently fail after 6-10 minutes
2. **Root Cause**: Unknown networking issue specific to this VPC

### Critical Insight 🔑
**This deployment works in another AWS account with an existing VPC**, which means:
- The application code is correct
- The Terraform configuration logic is sound
- **The issue is VPC-specific networking configuration**

### Selected Subnets (Terraform Logic)
Our filtering identifies these 8 subnets as "truly private":
```
subnet-0374d7b91b2054239
subnet-0584def4d6ffbe9a5
subnet-014b5d076741106ff
subnet-0b8e4e5c74e60d524
subnet-0dfffe14f39009eeb
subnet-0917dfc1af7e6f812
subnet-050691e25d4a7681e
subnet-02085799b52b1e750
```

## 🔬 Diagnostic Tools Created

### 1. Enhanced VPC Test Script ✅
**File**: `deployment/test-apprunner-connectivity.sh`
**Purpose**: Deep dive into the specific subnets and networking paths App Runner uses
**Features**:
- Tests each Terraform-selected subnet individually
- Validates subnet filtering logic
- Checks NACLs, security groups, route tables
- Tests NAT Gateway connectivity
- DNS resolution validation

## 📋 Complete Next Steps Plan

### Phase 1: Run Diagnostic Script (IMMEDIATE)
1. **Make script executable**: `chmod +x deployment/test-apprunner-connectivity.sh`
2. **Run diagnostic**: `./deployment/test-apprunner-connectivity.sh`
3. **Analyze results**: Focus on any failed tests or warnings
4. **Compare with working VPC**: If possible, run same script on working account's VPC

### Phase 2: Network Deep Dive (IF DIAGNOSTICS SHOW ISSUES)
1. **NACL Analysis**: Check if custom NACLs are blocking port 8000 traffic
2. **Route Table Verification**: Ensure all selected subnets route to NAT Gateways correctly
3. **Security Group Testing**: Verify ingress rules work in practice
4. **DNS Resolution**: Test VPC DNS configuration

### Phase 3: Minimal Container Test (ISOLATION TESTING)
1. **Create simple test container**:
   ```dockerfile
   FROM nginx:alpine
   COPY <<EOF /usr/share/nginx/html/health
   {"status": "healthy"}
   EOF
   EXPOSE 8000
   CMD ["nginx", "-g", "daemon off;"]
   ```
2. **Deploy via App Runner**: Use same VPC connector and subnets
3. **Test health checks**: See if even basic container fails
4. **Compare results**: Isolate if it's application vs networking

### Phase 4: Alternative Approaches (IF STILL FAILING)
1. **Try different subnets**: Manually select specific subnets instead of filtering logic
2. **Simplify security groups**: Use broader CIDR ranges or different ingress rules
3. **Test without VPC connector**: Deploy App Runner without VPC to isolate VPC issues
4. **Use EC2 testing**: Launch EC2 in same subnets to test connectivity patterns

### Phase 5: Expert Consultation (IF ALL ELSE FAILS)
1. **AWS Support Case**: Provide detailed diagnostics and working vs non-working comparison
2. **Network Architecture Review**: Have AWS review the specific VPC configuration
3. **App Runner Team**: Consult with App Runner product team about VPC connector issues

## 🗂️ Files Modified in This Session

### Configuration Changes
1. **`data-sources.tf`**: Enhanced subnet filtering logic, RDS subnet inclusion
2. **`security.tf`**: Added ingress rule for port 8000 health checks
3. **`backend.tf`**: Increased health check timeout and failure thresholds
4. **`environments/mosaic-devqa.tfvars`**: Updated to use Sonnet 4 model

### New Tools Created
1. **`test-apprunner-connectivity.sh`**: Comprehensive VPC diagnostic script

## 🎲 Current Deployment State

**Last Terraform Apply**: In progress (likely failed by now)
**App Runner Services**: Any failed services have been cleaned up
**VPC Resources**: RDS, security groups, VPC connector all exist and configured
**Next Command**: `terraform apply -var-file=environments/mosaic-devqa.tfvars` after running diagnostics

## 🔍 Key Questions for Next Session

1. **What does the diagnostic script reveal?** Are there obvious networking issues?
2. **Do we need to test a minimal container?** Is it application-specific or networking?
3. **Should we try different subnets?** Maybe our filtering logic is too restrictive?
4. **Is there a VPC configuration difference?** Compare with working account if possible

## 📞 Handoff Notes

**Environment**: `deployment/terraform-existing-vpc/`
**Target VPC**: `vpc-08acfe7cf84c026c7` (10.6.28.0/23) in us-west-2
**AWS Account**: 767397995923
**Branch**: Current working directory state

**Critical Context**: The application itself works fine - this is a VPC networking issue preventing App Runner health checks from reaching the container. The diagnostic script should reveal the specific networking component that's failing.