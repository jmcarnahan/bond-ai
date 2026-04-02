# Guardrails Update Guide

How to modify Bedrock Guardrails configuration and keep all environments in sync.

## Files That Matter

| File | Purpose |
|------|---------|
| `deployment/terraform-existing-vpc/guardrails.tf` | Guardrail definition (topics, word filters, regex, PII, content filters) |
| `deployment/terraform-existing-vpc/scripts/migrate_guardrails.py` | Batch-migrate existing agents to a new guardrail version |
| `.env` | Local dev: `BEDROCK_GUARDRAIL_ID` and `BEDROCK_GUARDRAIL_VERSION` |
| `environments/<env>.tfvars` | Deployed env: `bedrock_guardrail_version` (if pinned) |
| `tests/test_bedrock_guardrails.py` | Direct guardrail API tests (fast, no backend needed) |
| `tests/test_guardrails_smoke.py` | End-to-end tests against running backend |

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
poetry run python -m pytest tests/test_guardrails_smoke.py \
    --integration -v > /tmp/guardrail_smoke.txt 2>&1
```

These are slow (~10 min) because each test invokes the agent end-to-end.

## What Gets Blocked

| Layer | What it catches | Config location |
|-------|----------------|-----------------|
| **Topic policies** (semantic) | OS command execution, reverse shells, system file access | `topic_policy_config` in guardrails.tf |
| **Word filters** (exact match) | `reverse shell`, `meterpreter`, `metasploit`, `/etc/shadow`, `nc -e`, `ncat -e`, `bind shell`, `mkfifo backpipe` | `word_policy_config` in guardrails.tf |
| **Regex patterns** | `/etc/shadow`, `/proc/self/environ`, `/dev/tcp/`, `socket.connect`, `base64 -d \| bash` | `regexes_config` in guardrails.tf |
| **Content filters** | Prompt injection, violence, misconduct, hate, sexual, insults (all LOW) | `content_policy_config` in guardrails.tf |
| **PII filters** | AWS keys (BLOCK), SSN/CC/bank/email/phone (ANONYMIZE) | `sensitive_information_policy_config` in guardrails.tf |

## Known Limitations

**Output-side false positives:** Topic policies evaluate both input and output. When the agent generates responses containing shell commands, credential management advice, or security tooling recommendations, the output can be truncated. There is no way to make topic policies input-only.

Affected prompts are documented as `TODO: revisit` comments in `test_guardrails_smoke.py` and as `xfail` tests in `test_bedrock_guardrails.py`.

## Downstream Fork Sync

When syncing guardrail changes to a downstream fork:

1. Cherry-pick or merge the `guardrails.tf` changes
2. `terraform apply` in the downstream environment
3. Update `.env` / tfvars with the new version number
4. Run the migration script with that environment's Aurora credentials
5. Run the API tests to verify
