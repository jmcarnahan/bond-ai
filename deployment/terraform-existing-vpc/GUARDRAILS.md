# Guardrails Update Guide

How to modify Bedrock Guardrails configuration and keep all environments in sync.

## Prerequisites

- **Terraform AWS provider**: `~> 6.0` (required for `input_action`/`output_action` fields)
- **EKS module**: `~> 21.0` (required for provider v6 compatibility)
- Run `terraform init -upgrade` after pulling these changes to update providers

## Files That Matter

| File | Purpose |
|------|---------|
| `deployment/terraform-existing-vpc/guardrails.tf` | Guardrail definition (topics, word filters, regex, PII, content filters) + `guardrails_mode` variable |
| `deployment/terraform-existing-vpc/scripts/migrate_guardrails.py` | Batch-migrate existing agents to a new guardrail version |
| `.env` | Local dev: `BEDROCK_GUARDRAIL_ID` and `BEDROCK_GUARDRAIL_VERSION` |
| `environments/<env>.tfvars` | Deployed env: `bedrock_guardrail_version` (if pinned), `guardrails_mode` |
| `tests/test_bedrock_guardrails.py` | Direct guardrail API tests (fast, no backend needed) |
| `tests/test_guardrails_smoke.py` | End-to-end tests against running backend |
| `deployment/terraform-existing-vpc/scripts/smoke_test_deployment.py` | Full deployment smoke tests including guardrails |

## Guardrail Mode (`guardrails_mode`)

The `guardrails_mode` variable controls how the guardrail handles detected content. Set it in your environment's tfvars file.

| Mode | Behavior | Use case |
|------|----------|----------|
| `enforce` (default) | Blocks harmful content, returns error messaging | Production — active protection |
| `detect` | Evaluates content and produces trace data, but does **not** block | Diagnosing false positives — users are unaffected while you analyze traces |
| `permissive` | Disables most filtering (content filter strengths = NONE, topic/word policies removed) | Last resort — use if `detect` mode itself causes issues |

### How each mode works

**enforce**: All content filters at LOW strength with action=BLOCK. Topic policies, word filters, PII, and regex patterns all actively block. This is the default.

**detect**: Content filters stay at LOW strength (detection active, trace data produced in logs) but action=NONE (never blocks). Word filters evaluate with action=NONE. Topic policies are removed entirely (Terraform provider doesn't support action fields for topics yet — [#45915](https://github.com/hashicorp/terraform-provider-aws/issues/45915)). PII and regex patterns use action=NONE.

**permissive**: Content filter strengths set to NONE (no detection), topic and word policies removed entirely, PII and regex actions set to ANONYMIZE with action=NONE. One content filter (INSULTS) stays at LOW strength with action=NONE to satisfy the AWS API requirement that at least one filter strength must be non-NONE.

### Detect mode logging

In detect mode, guardrail trace events appear in application logs:

- **INFO level**: `Guardrail trace: action=NONE` — confirms guardrail evaluated but didn't block
- **DEBUG level**: Full trace details (which filters/topics matched and their assessments)

Log locations by deployment:

| Deployment | Log location |
|---|---|
| Local dev | Terminal / stdout |
| App Runner | CloudWatch Logs → `/aws/apprunner/<service-name>/.../application` |
| EKS | `kubectl logs -n bond-ai <pod>` or CloudWatch container logs |

To see full trace details in production, temporarily set `LOG_LEVEL=DEBUG` in the environment.

### Switching modes

```bash
# In environments/<env>.tfvars, set:
guardrails_mode = "detect"    # or "permissive" or "enforce"

# Clear pinned version so the new auto-published version is used:
bedrock_guardrail_version = ""

# Apply
cd deployment/terraform-existing-vpc
terraform init -upgrade   # only needed first time after provider upgrade
terraform plan
terraform apply

# Get new version
terraform output guardrail_published_version   # e.g. "4"

# Migrate existing agents — Aurora
BEDROCK_GUARDRAIL_ID=<id> \
BEDROCK_GUARDRAIL_VERSION=<new_version> \
AURORA_CLUSTER_ARN=<cluster_arn> \
DATABASE_SECRET_ARN=<secret_arn> \
poetry run python deployment/terraform-existing-vpc/scripts/migrate_guardrails.py --dry-run

# Then apply (remove --dry-run)
BEDROCK_GUARDRAIL_ID=<id> \
BEDROCK_GUARDRAIL_VERSION=<new_version> \
AURORA_CLUSTER_ARN=<cluster_arn> \
DATABASE_SECRET_ARN=<secret_arn> \
poetry run python deployment/terraform-existing-vpc/scripts/migrate_guardrails.py --batch-size 5 --delay 10

# Migrate existing agents — local SQLite
BEDROCK_GUARDRAIL_ID=<id> \
BEDROCK_GUARDRAIL_VERSION=<new_version> \
METADATA_DB_URL="sqlite:///.metadata.db" \
poetry run python deployment/terraform-existing-vpc/scripts/migrate_guardrails.py --batch-size 5 --delay 10

# Update local .env
BEDROCK_GUARDRAIL_VERSION="<new_version>"

# Restart backend to pick up new version
```

### Expected test results by mode

| Test | enforce | detect | permissive |
|------|---------|--------|------------|
| Guardrail exists | PASS | PASS | PASS |
| Guardrail blocks exploit | PASS | **FAIL** (expected) | **FAIL** (expected) |
| Guardrail allows benign | PASS | PASS | PASS |
| Agents guardrail version | PASS | PASS (after migration) | PASS (after migration) |

## Step-by-Step: Updating Guardrails

### 1. Edit the guardrail config

Modify `guardrails.tf` — topic policies, word filters, regex patterns, content filters, or PII settings.

### 2. Deploy

```bash
cd deployment/terraform-existing-vpc
terraform plan    # Verify only guardrail + version resources change
terraform apply   # Publishes a new guardrail version automatically
```

Note the new version from the output:
```bash
terraform output guardrail_published_version   # e.g. "4"
```

### 3. Run API tests against the new version

These are fast (~20s) and don't need a running backend:

```bash
BEDROCK_GUARDRAIL_ID=<id> \
BEDROCK_GUARDRAIL_VERSION=<new_version> \
poetry run python -m pytest tests/test_bedrock_guardrails.py::TestGuardrailCommandInjection \
    --integration -v > /tmp/guardrail_api_tests.txt 2>&1
```

Review results. If false positives appear, revise topic definitions and repeat from step 1.

### 4. Update version references

**Local `.env`:**
```
BEDROCK_GUARDRAIL_VERSION="<new_version>"
```

**Deployed environment** (if version is pinned in tfvars):
```
bedrock_guardrail_version = "<new_version>"
```
Then `terraform apply` again to update the backend env vars.

### 5. Migrate all existing agents

The migration script queries both Aurora and local SQLite for agent IDs:

```bash
# Dry run first
BEDROCK_GUARDRAIL_ID=<id> \
BEDROCK_GUARDRAIL_VERSION=<new_version> \
AURORA_CLUSTER_ARN=<cluster_arn> \
DATABASE_SECRET_ARN=<secret_arn> \
METADATA_DB_URL="sqlite:///.metadata.db" \
poetry run python deployment/terraform-existing-vpc/scripts/migrate_guardrails.py --dry-run

# Then apply (same env vars, remove --dry-run)
BEDROCK_GUARDRAIL_ID=<id> \
BEDROCK_GUARDRAIL_VERSION=<new_version> \
AURORA_CLUSTER_ARN=<cluster_arn> \
DATABASE_SECRET_ARN=<secret_arn> \
METADATA_DB_URL="sqlite:///.metadata.db" \
poetry run python deployment/terraform-existing-vpc/scripts/migrate_guardrails.py --batch-size 5 --delay 10
```

**Local-only (no Aurora):**
```bash
BEDROCK_GUARDRAIL_ID=<id> \
BEDROCK_GUARDRAIL_VERSION=<new_version> \
METADATA_DB_URL="sqlite:///.metadata.db" \
poetry run python deployment/terraform-existing-vpc/scripts/migrate_guardrails.py
```

**Single agent:**
```bash
poetry run python deployment/terraform-existing-vpc/scripts/migrate_guardrails.py --agent-id <AGENT_ID>
```

### 6. Restart local backend and run smoke tests

Restart so the backend picks up the new `BEDROCK_GUARDRAIL_VERSION` from `.env`, then:

```bash
# Deployment smoke tests (includes guardrail checks)
poetry run python deployment/terraform-existing-vpc/scripts/smoke_test_deployment.py \
    --env <env> --region <region>

# Guardrail-specific integration tests
poetry run python -m pytest tests/test_bedrock_guardrails.py::TestGuardrailIntegration \
    --integration -v > /tmp/guardrail_integration.txt 2>&1
```

## What Gets Blocked (in enforce mode)

| Layer | What it catches | Config location |
|-------|----------------|-----------------|
| **Topic policies** (semantic) | OS command execution, reverse shells, system file access | `topic_policy_config` in guardrails.tf |
| **Word filters** (exact match) | `reverse shell`, `meterpreter`, `metasploit`, `/etc/shadow`, `nc -e`, `ncat -e`, `bind shell`, `mkfifo backpipe` | `word_policy_config` in guardrails.tf |
| **Regex patterns** | `/etc/shadow`, `/proc/self/environ`, `/dev/tcp/`, `socket.connect`, `base64 -d \| bash` | `regexes_config` in guardrails.tf |
| **Content filters** | Prompt injection, violence, misconduct, hate, sexual, insults (all LOW) | `content_policy_config` in guardrails.tf |
| **PII filters** | AWS keys (BLOCK), SSN/CC/bank/email/phone (ANONYMIZE) | `sensitive_information_policy_config` in guardrails.tf |

**Note:** Utility Converse API calls (image analysis, thread compaction, icon selection) do **not** use guardrails. These are system-to-system calls with controlled inputs where guardrails only caused false positives.

## Known Limitations

**AWS API constraint:** At least one content filter strength must be non-NONE. The INSULTS filter stays at LOW in all modes to satisfy this. In detect/permissive modes its action is NONE so it never blocks.

**Topic policies lack detect mode:** The Terraform AWS provider does not yet support `input_action`/`output_action` for `topic_policy_config` ([#45915](https://github.com/hashicorp/terraform-provider-aws/issues/45915)). Topics are excluded entirely in detect/permissive modes instead of set to detect-only.

**Output-side false positives:** Topic policies evaluate both input and output. When the agent generates responses containing shell commands, credential management advice, or security tooling recommendations, the output can be truncated. There is no way to make topic policies input-only.

Affected prompts are documented as `TODO: revisit` comments in `test_guardrails_smoke.py` and as `xfail` tests in `test_bedrock_guardrails.py`.

## Downstream Fork Sync

When syncing these changes to a downstream fork:

1. Merge or cherry-pick the branch (includes provider v6 upgrade + EKS module v21)
2. Run `terraform init -upgrade` to pull new providers and modules
3. Set `guardrails_mode` in your environment's tfvars (e.g. `"permissive"` or `"detect"`)
4. `terraform plan` — verify no destructive changes (especially EKS resources if `enable_eks = true`)
5. `terraform apply`
6. Get new version: `terraform output guardrail_published_version`
7. Run migration script for Aurora agents AND local agents (see "Switching modes" above)
8. Update `.env` with new `BEDROCK_GUARDRAIL_VERSION`
9. Restart backend
10. Run smoke tests to verify
