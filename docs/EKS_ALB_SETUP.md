# EKS + ALB Setup Guide

This document describes the architecture and manual setup steps required to run
Bond AI on EKS in environments where an **org-level SCP (Service Control Policy)
blocks the AWS Load Balancer Controller from creating Application Load Balancers
automatically**.

---

## Architecture

```
User (VPN/ZPA) ──► Corporate ZTNA Connector ──► Internal ALB (port 443/HTTPS)
                                                      │  TLS terminated here
                                                      │  cert: ACM imported cert
                                                      ▼
                                               TargetGroupBinding
                                               (LB Controller syncs pod IPs)
                                                      │
                                                      ▼
                                               EKS Pods (port 8080)
```

**Key components:**

| Component | Managed by | Notes |
|-----------|-----------|-------|
| ALB | Cloud/infra team | SCP may block Terraform/LB controller from creating it |
| TLS certificate | Cert team (imported to ACM) | Must be **RSA-2048**; RSA-4096 is rejected by NLB but works on ALB |
| Target group | Cloud/infra team | IP type, HTTP port 8080 |
| TargetGroupBinding | Terraform (LB Controller) | Keeps pod IPs registered automatically |
| CNAME / DNS | Network/DNS team | Points custom domain → ALB DNS name |
| ZPA App Segment | ZPA admin team | Must use subnets with Transit Gateway routing |

---

## Pre-requisites

### 1. ACM Certificate

**RSA-2048 and RSA-4096 both work** on ALB HTTPS listeners. If you ever need
to fall back to an NLB, only RSA-2048 is supported (NLB TLS listeners reject
RSA-4096). Recommend RSA-2048 for maximum flexibility.

To verify key size on an existing cert:

```bash
aws acm get-certificate --certificate-arn <arn> \
  --query Certificate --output text | \
  openssl x509 -noout -text | grep "Public-Key"
```

Import (or re-import) the cert:
```bash
aws acm import-certificate \
  --certificate fileb://cert.pem \
  --private-key fileb://key.pem \
  --certificate-chain fileb://chain.pem \
  --region <region>
```

### 2. VPC Subnet Selection — CRITICAL

The ALB **must** be placed in subnets that have a **Transit Gateway route** for
corporate network ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).
Without the TGW route, ZTNA/VPN connectors cannot reach the ALB even if security
groups are open.

Verify a subnet has the required routes:
```bash
aws ec2 describe-route-tables \
  --filters "Name=association.subnet-id,Values=<subnet-id>" \
  --query 'RouteTables[0].Routes[*].{Dest:DestinationCidrBlock,ViaTGW:TransitGatewayId}'
```

Look for a route matching `10.0.0.0/8` (or the corporate range) via a
`TransitGatewayId`. If absent, the ALB will be unreachable from VPN.

Use the **same subnets** configured in `app_runner_subnet_ids` in the tfvars
(the "internal-green" subnets) — these are already known to have TGW routing.

### 3. ALB Configuration

Create an internal Application Load Balancer with:

| Setting | Value |
|---------|-------|
| Type | Application |
| Scheme | **Internal** |
| Subnets | internal-green subnets (see above) |
| Security Group | Allow HTTPS 443 inbound from VPC CIDR + ZPA connector CIDRs |

### 4. Target Group

Create a target group attached to the ALB:

| Setting | Value |
|---------|-------|
| Target type | **IP** (not Instance) |
| Protocol | HTTP |
| Port | 8080 |
| Health check path | `/health` |
| Health check protocol | HTTP |

> **Do not manually register targets.** Leave the target group empty — the
> `TargetGroupBinding` Kubernetes resource (managed by Terraform) will register
> pod IPs automatically and keep them in sync as pods restart or scale.

### 5. HTTPS Listener

Add a listener to the ALB:

| Setting | Value |
|---------|-------|
| Protocol | HTTPS |
| Port | 443 |
| Default action | Forward to target group above |
| SSL/TLS certificate | ACM cert ARN |
| Security policy | `ELBSecurityPolicy-TLS13-1-2-2021-06` (standard TLS 1.3 + 1.2) |

> Avoid post-quantum policies (e.g., `*-PQ-*`) unless all clients in your
> environment support ML-KEM/Kyber. Most TLS clients (browsers, curl) do not
> yet support post-quantum TLS as of 2026.

### 6. DNS / CNAME

Ask the DNS team to create a CNAME:
```
<custom-domain>  CNAME  <alb-dns-name>.elb.<region>.amazonaws.com
```

### 7. ZPA / ZTNA App Segment

Ask the ZPA admin to create an Application Segment for the custom domain:
- **Domain**: `<custom-domain>:443 TCP`
- **App Connector Group**: must be a connector group with network access to the
  ALB's subnets (i.e., the subnets have TGW routing as described above)

---

## Terraform Configuration

After the cloud team creates the ALB and target group, update `environments/<env>.tfvars`:

```hcl
# ACM certificate ARN (RSA-2048, imported by cert team)
eks_acm_certificate_arn = "arn:aws:acm:<region>:<account>:certificate/<id>"

# Custom domain (DNS team creates CNAME pointing here)
eks_custom_domain_name = "<custom-domain>"

# ALB created by cloud team (SCP blocks LB controller from creating ALBs)
eks_target_group_arn = "arn:aws:elasticloadbalancing:<region>:<account>:targetgroup/<name>/<id>"
eks_alb_dns_name     = "<internal-alb-dns>.elb.<region>.amazonaws.com"

# Include ALB hostname and custom domain in CORS and redirect domains
allowed_redirect_domains = "<apprunner-domain>,<alb-dns-name>,<custom-domain>"
cors_allowed_origins     = "https://<apprunner-domain>,https://<alb-dns-name>,https://<custom-domain>"
```

Then run:
```bash
terraform apply -var-file=environments/<env>.tfvars
```

Terraform will create the `TargetGroupBinding` Kubernetes resource, which causes
the AWS Load Balancer Controller to register pod IPs into the target group.

---

## Verification

```bash
# 1. Pods are registered in target group
aws elbv2 describe-target-health --target-group-arn <tg-arn> \
  --query 'TargetHealthDescriptions[*].{IP:Target.Id,Health:TargetHealth.State}'

# 2. HTTPS works through ALB
curl -f https://<custom-domain>/health

# 3. Cert is attached
aws elbv2 describe-listeners --load-balancer-arn <alb-arn> \
  --query 'Listeners[0].Certificates'

# 4. TargetGroupBinding is reconciled
kubectl get targetgroupbinding -n bond-ai

# 5. Run full smoke test
poetry run python deployment/terraform-existing-vpc/scripts/smoke_test_deployment.py \
  --env <env> --region <region> --test-eks \
  --eks-alb-hostname <alb-dns-name>
```

---

## Troubleshooting

### Connection reset during TLS handshake

**Symptom**: `curl: (35) Recv failure: Connection reset by peer`

**Likely causes (in order):**
1. **Wrong subnets** — ALB is in subnets without TGW routing. Verify with the
   route table check above. Move ALB to subnets that have the TGW route.
2. **ZPA connector not configured** — Check ZPA connection logs for
   `No configured App Connector` against the application. Add a connector group
   with network access to the ALB subnets.
3. **Security group blocking** — Verify ALB SG allows inbound 443 from the VPC
   CIDR and ZPA connector CIDRs.
4. **Post-quantum TLS policy** — If using a `*-PQ-*` SSL policy, the client
   must support ML-KEM. Switch to `ELBSecurityPolicy-TLS13-1-2-2021-06`.

> **Diagnostic tip**: Test from inside the cluster first to isolate
> network/VPN issues from ALB configuration issues:
> ```bash
> kubectl exec -n bond-ai deployment/bond-ai-backend -- \
>   python3 -c "
> import urllib.request, ssl
> ctx = ssl.create_default_context()
> ctx.check_hostname = False
> ctx.verify_mode = ssl.CERT_NONE
> r = urllib.request.urlopen('https://<alb-dns>/health', context=ctx, timeout=5)
> print(r.status, r.read())
> "
> ```
> If this works but external access fails, the problem is network/VPN routing,
> not the ALB configuration.

### Target group shows unhealthy targets

- Verify pods are running: `kubectl get pods -n bond-ai`
- Verify ALB is in the same VPC as the pods
- Verify the ALB security group allows egress to port 8080 in the VPC CIDR
- Verify node security group allows inbound port 8080 from the VPC CIDR

### TargetGroupBinding not registering pods

- Verify LB Controller is running: `kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller`
- Check LB Controller logs: `kubectl logs -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller`
- Verify the IRSA role has `elasticloadbalancing:RegisterTargets` permission

---

## Why ALB instead of NLB

NLB TLS listeners reject **RSA-4096** certificates with `UnsupportedCertificate`.
ALB HTTPS listeners use software-based TLS termination and support RSA-4096.
If your certificate is RSA-4096, use ALB. NLB requires RSA-2048 or smaller.
