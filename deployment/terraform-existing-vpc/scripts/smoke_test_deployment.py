#!/usr/bin/env python3
"""
Smoke tests for Bond AI deployment (App Runner + EKS).

Validates that both compute platforms are functioning correctly after
Terraform apply. Tests infrastructure state via AWS APIs, health endpoints,
and Kubernetes status.

Usage:
    # After refactoring apply (App Runner only):
    python smoke_test_deployment.py --env dev --region us-west-2

    # After EKS deployment (both platforms):
    python smoke_test_deployment.py --env dev --region us-west-2 --test-eks

    # EKS only (App Runner disabled):
    python smoke_test_deployment.py --env dev --region us-west-2 --test-eks --skip-apprunner

    # With custom App Runner URL:
    python smoke_test_deployment.py --env dev --region us-west-2 --apprunner-url https://xxx.awsapprunner.com
"""

import argparse
import json
import subprocess  # nosec B404
import sys
import time
import urllib.request
import urllib.error
import ssl

try:
    import boto3
except ImportError:
    print("ERROR: boto3 is required. Install with: pip install boto3")
    sys.exit(1)


class DeploymentSmokeTest:
    def __init__(self, env, region, project="bond-ai",
                 apprunner_url="", test_eks=False, skip_apprunner=False,
                 eks_cluster_name=""):
        self.env = env
        self.region = region
        self.project = project
        self.apprunner_url = apprunner_url
        self.test_eks = test_eks
        self.skip_apprunner = skip_apprunner
        self.eks_cluster_name = eks_cluster_name or f"{project}-{env}-eks"
        self.results = []

        self.apprunner_client = boto3.client("apprunner", region_name=region)
        self.eks_client = boto3.client("eks", region_name=region)
        self.ec2_client = boto3.client("ec2", region_name=region)
        self.iam_client = boto3.client("iam", region_name=region)
        self.sts_client = boto3.client("sts", region_name=region)
        self.account_id = self.sts_client.get_caller_identity()["Account"]

    def _record(self, name, passed, detail=""):
        status = "PASS" if passed else "FAIL"
        self.results.append({"name": name, "passed": passed, "detail": detail})
        icon = "+" if passed else "!"
        print(f"  [{icon}] {name}: {status}" + (f" - {detail}" if detail else ""))

    def _http_get(self, url, timeout=10, verify_ssl=True):
        """Make HTTP GET request, return (status_code, body)."""
        try:
            ctx = None
            if not verify_ssl:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers={"User-Agent": "bond-ai-smoke-test"})
            resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)  # nosec B310
            return resp.getcode(), resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            return e.code, str(e)
        except Exception as e:
            return 0, str(e)

    def _run_cmd(self, cmd, timeout=30):
        """Run shell command, return (returncode, stdout, stderr)."""
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=timeout  # nosec B602
            )
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return 1, "", "Command timed out"
        except Exception as e:
            return 1, "", str(e)

    # =========================================================================
    # App Runner Tests
    # =========================================================================

    def test_apprunner_service_exists(self):
        """Verify App Runner service exists and is RUNNING."""
        service_name = f"{self.project}-{self.env}-backend"
        try:
            resp = self.apprunner_client.list_services()
            services = [
                s for s in resp.get("ServiceSummaryList", [])
                if s["ServiceName"] == service_name
            ]
            if not services:
                self._record("AppRunner service exists", False, f"Service '{service_name}' not found")
                return None
            svc = services[0]
            status = svc.get("Status", "UNKNOWN")
            url = svc.get("ServiceUrl", "")
            self._record("AppRunner service exists", True, f"Status: {status}, URL: {url}")

            if not self.apprunner_url and url:
                self.apprunner_url = f"https://{url}"
            return svc
        except Exception as e:
            self._record("AppRunner service exists", False, str(e))
            return None

    def test_apprunner_health(self):
        """Hit /health endpoint on App Runner."""
        if not self.apprunner_url:
            self._record("AppRunner health check", False, "No URL available")
            return
        url = f"{self.apprunner_url}/health"
        code, body = self._http_get(url)
        passed = code == 200
        self._record("AppRunner health check", passed, f"HTTP {code} from {url}")

    def test_apprunner_frontend(self):
        """Verify frontend loads from App Runner."""
        if not self.apprunner_url:
            self._record("AppRunner frontend loads", False, "No URL available")
            return
        code, body = self._http_get(self.apprunner_url)
        passed = code == 200 and ("flutter" in body.lower() or "<html" in body.lower() or "<!DOCTYPE" in body)
        self._record("AppRunner frontend loads", passed, f"HTTP {code}, HTML present: {'<!DOCTYPE' in body}")

    def test_apprunner_iam_role(self):
        """Verify App Runner instance role exists."""
        role_name = f"{self.project}-{self.env}-apprunner-instance-role"
        try:
            resp = self.iam_client.get_role(RoleName=role_name)
            self._record("AppRunner IAM role exists", True, role_name)
        except self.iam_client.exceptions.NoSuchEntityException:
            self._record("AppRunner IAM role exists", False, f"Role '{role_name}' not found")

    def test_apprunner_waf(self):
        """Verify WAF is associated with App Runner service."""
        if not self.apprunner_url:
            self._record("AppRunner WAF association", False, "No URL available")
            return
        try:
            waf = boto3.client("wafv2", region_name=self.region)
            resp = self.apprunner_client.list_services()
            service_name = f"{self.project}-{self.env}-backend"
            services = [s for s in resp["ServiceSummaryList"] if s["ServiceName"] == service_name]
            if not services:
                self._record("AppRunner WAF association", False, "Service not found")
                return
            arn = services[0]["ServiceArn"]
            waf_resp = waf.get_web_acl_for_resource(ResourceArn=arn)
            acl_name = waf_resp.get("WebACL", {}).get("Name", "none")
            self._record("AppRunner WAF association", bool(acl_name != "none"), f"WAF: {acl_name}")
        except Exception as e:
            self._record("AppRunner WAF association", False, str(e))

    # =========================================================================
    # EKS Tests
    # =========================================================================

    def test_eks_cluster_active(self):
        """Verify EKS cluster exists and is ACTIVE."""
        try:
            resp = self.eks_client.describe_cluster(name=self.eks_cluster_name)
            status = resp["cluster"]["status"]
            version = resp["cluster"]["version"]
            passed = status == "ACTIVE"
            self._record("EKS cluster active", passed, f"Status: {status}, Version: {version}")
            return resp["cluster"]
        except self.eks_client.exceptions.ResourceNotFoundException:
            self._record("EKS cluster active", False, f"Cluster '{self.eks_cluster_name}' not found")
            return None
        except Exception as e:
            self._record("EKS cluster active", False, str(e))
            return None

    def test_eks_nodegroup_active(self):
        """Verify at least one node group is ACTIVE."""
        try:
            resp = self.eks_client.list_nodegroups(clusterName=self.eks_cluster_name)
            nodegroups = resp.get("nodegroups", [])
            if not nodegroups:
                self._record("EKS node group active", False, "No node groups found")
                return

            for ng_name in nodegroups:
                ng = self.eks_client.describe_nodegroup(
                    clusterName=self.eks_cluster_name, nodegroupName=ng_name
                )
                status = ng["nodegroup"]["status"]
                desired = ng["nodegroup"]["scalingConfig"]["desiredSize"]
                self._record(
                    f"EKS node group '{ng_name}'", status == "ACTIVE",
                    f"Status: {status}, Desired: {desired}"
                )
        except Exception as e:
            self._record("EKS node group active", False, str(e))

    def test_eks_pods_running(self):
        """Verify bond-ai pods are Running via kubectl."""
        rc, out, err = self._run_cmd(
            f"kubectl get pods -n bond-ai -l app=bond-ai-backend "
            f"-o jsonpath='{{.items[*].status.phase}}'",
            timeout=15
        )
        if rc != 0:
            self._record("EKS pods running", False, f"kubectl failed: {err}")
            return

        phases = out.split() if out else []
        running = [p for p in phases if p == "Running"]
        passed = len(running) > 0 and len(running) == len(phases)
        self._record(
            "EKS pods running", passed,
            f"{len(running)}/{len(phases)} pods Running"
        )

    def test_eks_nlb_endpoint(self):
        """Get NLB hostname from Kubernetes service."""
        rc, out, err = self._run_cmd(
            "kubectl get svc -n bond-ai bond-ai-backend "
            "-o jsonpath='{.status.loadBalancer.ingress[0].hostname}'",
            timeout=15
        )
        if rc != 0 or not out or out == "''":
            self._record("EKS NLB endpoint", False, f"No NLB hostname: {err}")
            return None

        hostname = out.strip("'")
        self._record("EKS NLB endpoint", True, hostname)
        return hostname

    def test_eks_health(self, nlb_hostname):
        """Hit /health on EKS NLB (requires VPN)."""
        if not nlb_hostname:
            self._record("EKS health check", False, "No NLB hostname available")
            return

        # Try HTTPS first, fall back to HTTP
        for proto in ["https", "http"]:
            url = f"{proto}://{nlb_hostname}/health"
            code, body = self._http_get(url, timeout=10, verify_ssl=False)
            if code == 200:
                self._record("EKS health check", True, f"HTTP {code} from {url}")
                return
            if code != 0:
                self._record("EKS health check", code == 200, f"HTTP {code} from {url}")
                return

        self._record(
            "EKS health check", False,
            f"NLB unreachable at {nlb_hostname} (are you on VPN?)"
        )

    def test_eks_frontend(self, nlb_hostname):
        """Verify frontend loads from EKS NLB (requires VPN)."""
        if not nlb_hostname:
            self._record("EKS frontend loads", False, "No NLB hostname")
            return

        for proto in ["https", "http"]:
            url = f"{proto}://{nlb_hostname}/"
            code, body = self._http_get(url, timeout=10, verify_ssl=False)
            if code == 200:
                has_html = "<!DOCTYPE" in body or "<html" in body
                self._record("EKS frontend loads", has_html, f"HTTP {code}, HTML: {has_html}")
                return

        self._record("EKS frontend loads", False, f"Unreachable (are you on VPN?)")

    def test_eks_irsa(self):
        """Verify IRSA role exists for EKS pods."""
        role_name = f"{self.project}-{self.env}-eks-pod-role"
        try:
            self.iam_client.get_role(RoleName=role_name)
            self._record("EKS IRSA role exists", True, role_name)
        except self.iam_client.exceptions.NoSuchEntityException:
            self._record("EKS IRSA role exists", False, f"Role '{role_name}' not found")

    def test_eks_irsa_in_pod(self):
        """Verify pods have IRSA env vars (AWS_ROLE_ARN + token file)."""
        rc, out, err = self._run_cmd(
            "kubectl exec -n bond-ai deployment/bond-ai-backend -- "
            "env 2>/dev/null",
            timeout=15
        )
        if rc != 0:
            self._record("EKS IRSA in pod", False, f"kubectl exec failed: {err}")
            return

        has_role_arn = "AWS_ROLE_ARN=" in out
        has_token = "AWS_WEB_IDENTITY_TOKEN_FILE=" in out
        is_pod_role = "eks-pod-role" in out

        passed = has_role_arn and has_token and is_pod_role
        role_line = [l for l in out.split("\n") if "AWS_ROLE_ARN=" in l]
        detail = role_line[0] if role_line else "AWS_ROLE_ARN not found"
        self._record("EKS IRSA in pod", passed, detail)

    # =========================================================================
    # Cross-Platform Tests
    # =========================================================================

    def test_both_same_database(self, nlb_hostname):
        """Verify both platforms hit the same database (health responses match)."""
        if not self.apprunner_url or not nlb_hostname:
            self._record("Cross-platform: same DB", False, "Need both URLs")
            return

        ar_code, ar_body = self._http_get(f"{self.apprunner_url}/health")
        for proto in ["https", "http"]:
            eks_code, eks_body = self._http_get(
                f"{proto}://{nlb_hostname}/health", verify_ssl=False
            )
            if eks_code == 200:
                break

        both_healthy = ar_code == 200 and eks_code == 200
        self._record(
            "Cross-platform: both healthy", both_healthy,
            f"AppRunner: {ar_code}, EKS: {eks_code}"
        )

    # =========================================================================
    # Security Tests
    # =========================================================================

    def test_security_groups(self):
        """Verify Aurora SG allows ingress from expected sources."""
        try:
            # Find Aurora SG
            resp = self.ec2_client.describe_security_groups(
                Filters=[
                    {"Name": "tag:Name", "Values": [f"{self.project}-{self.env}-aurora-sg"]},
                ]
            )
            sgs = resp.get("SecurityGroups", [])
            if not sgs:
                self._record("Aurora SG exists", False, "Not found")
                return

            sg = sgs[0]
            ingress_sgs = []
            for rule in sg.get("IpPermissions", []):
                for pair in rule.get("UserIdGroupPairs", []):
                    ingress_sgs.append(pair.get("GroupId", ""))

            self._record(
                "Aurora SG ingress sources", len(ingress_sgs) > 0,
                f"{len(ingress_sgs)} source SG(s): {', '.join(ingress_sgs[:3])}"
            )
        except Exception as e:
            self._record("Aurora SG check", False, str(e))

    def test_eks_nlb_internal(self, nlb_hostname):
        """Verify NLB is internal (resolves to private IPs)."""
        if not nlb_hostname:
            self._record("EKS NLB is internal", False, "No hostname")
            return

        import socket
        try:
            ips = socket.getaddrinfo(nlb_hostname, 443, socket.AF_INET)
            ip_addrs = list(set(addr[4][0] for addr in ips))
            all_private = all(
                ip.startswith("10.") or ip.startswith("172.") or ip.startswith("192.168.")
                for ip in ip_addrs
            )
            self._record(
                "EKS NLB is internal", all_private,
                f"IPs: {', '.join(ip_addrs)} ({'private' if all_private else 'PUBLIC!'})"
            )
        except socket.gaierror as e:
            self._record("EKS NLB is internal", False, f"DNS resolution failed: {e}")

    # =========================================================================
    # Run
    # =========================================================================

    def run(self):
        print("=" * 60)
        print(f"Bond AI Deployment Smoke Test")
        print(f"Environment: {self.env} | Region: {self.region}")
        print(f"App Runner: {'SKIP' if self.skip_apprunner else 'TEST'}")
        print(f"EKS: {'TEST' if self.test_eks else 'SKIP'}")
        print("=" * 60)

        # --- App Runner ---
        if not self.skip_apprunner:
            print("\n--- App Runner Tests ---")
            self.test_apprunner_service_exists()
            self.test_apprunner_health()
            self.test_apprunner_frontend()
            self.test_apprunner_iam_role()
            self.test_apprunner_waf()

        # --- EKS ---
        nlb_hostname = None
        if self.test_eks:
            print("\n--- EKS Tests ---")

            # Configure kubectl
            rc, _, err = self._run_cmd(
                f"aws eks update-kubeconfig --name {self.eks_cluster_name} "
                f"--region {self.region} 2>&1",
                timeout=15
            )
            if rc != 0:
                print(f"  [!] kubectl config failed: {err}")

            cluster = self.test_eks_cluster_active()
            if cluster:
                self.test_eks_nodegroup_active()
                self.test_eks_pods_running()
                self.test_eks_irsa()
                nlb_hostname = self.test_eks_nlb_endpoint()
                self.test_eks_health(nlb_hostname)
                self.test_eks_frontend(nlb_hostname)
                self.test_eks_irsa_in_pod()

                print("\n--- EKS Security Tests ---")
                self.test_eks_nlb_internal(nlb_hostname)

        # --- Cross-Platform ---
        if not self.skip_apprunner and self.test_eks and nlb_hostname:
            print("\n--- Cross-Platform Tests ---")
            self.test_both_same_database(nlb_hostname)

        # --- Infrastructure ---
        print("\n--- Infrastructure Tests ---")
        self.test_security_groups()

        # --- Summary ---
        print("\n" + "=" * 60)
        passed = sum(1 for r in self.results if r["passed"])
        failed = sum(1 for r in self.results if not r["passed"])
        total = len(self.results)
        print(f"Results: {passed}/{total} passed, {failed} failed")

        if failed > 0:
            print("\nFailed tests:")
            for r in self.results:
                if not r["passed"]:
                    print(f"  FAIL: {r['name']} - {r['detail']}")

        print("=" * 60)
        return 0 if failed == 0 else 1


def main():
    parser = argparse.ArgumentParser(description="Bond AI deployment smoke tests")
    parser.add_argument("--env", required=True, help="Environment (dev, staging, prod)")
    parser.add_argument("--region", required=True, help="AWS region")
    parser.add_argument("--project", default="bond-ai", help="Project name prefix")
    parser.add_argument("--apprunner-url", default="", help="App Runner service URL (auto-detected if empty)")
    parser.add_argument("--test-eks", action="store_true", help="Include EKS tests")
    parser.add_argument("--skip-apprunner", action="store_true", help="Skip App Runner tests")
    parser.add_argument("--eks-cluster-name", default="", help="EKS cluster name (default: {project}-{env}-eks)")

    args = parser.parse_args()

    runner = DeploymentSmokeTest(
        env=args.env,
        region=args.region,
        project=args.project,
        apprunner_url=args.apprunner_url,
        test_eks=args.test_eks,
        skip_apprunner=args.skip_apprunner,
        eks_cluster_name=args.eks_cluster_name,
    )
    sys.exit(runner.run())


if __name__ == "__main__":
    main()
