# Model Configuration Protection

## Overview
This document explains the protection measures implemented for model configuration files in the Bond AI codebase.

## Purpose
Model configuration changes can significantly impact operational costs. To ensure proper oversight and prevent unintended cost implications, we've implemented GitHub CODEOWNERS protection for all files containing model configurations.

## Protected Files

### Critical Model Configuration Files
These files directly control which AI models are used and have the highest impact on costs:

1. **`/bondable/bond/providers/openai/OAIAProvider.py`**
   - Contains: `AZURE_OPENAI_DEPLOYMENT` environment variable with default `'gpt-4o-mini'`
   - Impact: Direct model deployment configuration

2. **`/flutterui/lib/providers/domain/agents/agent_form_provider.dart`**
   - Contains: Hardcoded `model: "gpt-4o-mini"` in `_buildAgentData()` method
   - Impact: Frontend model selection

3. **`/flutterui/lib/providers/create_agent_form_provider.dart`**
   - Contains: Hardcoded `model: "gpt-4o-mini"` in `saveAgent()` method
   - Impact: Agent creation model selection

4. **`/.env`**
   - Contains: `OPENAI_DEPLOYMENT="gpt-4o-mini"`
   - Impact: Environment configuration

### Additional Protected Files
These files are also protected as they reference models:

- `/bondable/bond/providers/openai/` (entire directory)
- `/tests/test_bond_providers.py` (test models)
- `/tests/test_rest_api.py` (test models)
- `/scripts/api_demo.py` (demo model usage)

## Protection Rules
- **Owner Required**: @jmcarnahan must approve ALL changes to protected files
- **No Exceptions**: Even minor changes require owner approval
- **Automatic**: GitHub will automatically request review when PRs modify these files

## Best Practices

### Model Selection Guidelines
- Always consider cost implications when selecting models
- Default to cost-effective models unless advanced capabilities are required
- Document rationale for using more expensive models

### Code Improvements Needed
1. **Environment Variable Consistency**: Code uses `AZURE_OPENAI_DEPLOYMENT` but `.env` defines `OPENAI_DEPLOYMENT`
2. **Configuration Centralization**: Flutter files should read from configuration instead of hardcoding models
3. **Default Safety**: Ensure defaults use cost-effective options

## How to Request Changes
1. Create a PR with your changes
2. GitHub will automatically request review from @jmcarnahan
3. Include justification for model changes in PR description
4. Wait for owner approval before merging

## Model Cost Considerations
Different models have varying cost structures:
- **gpt-4o-mini**: Most cost-effective option for general use
- **gpt-4o**: Higher cost, use only when advanced capabilities are required
- **gpt-4**: Premium tier, require explicit justification

Always evaluate if the task requires the capabilities of more expensive models before making changes.
