# Patch Application Guide: Bond AI Fork Improvements

## Overview
This guide provides step-by-step instructions for applying the `bondai-fork-improvements.patch` to the upstream Bond AI repository.

**Patch File**: `bondai-fork-improvements.patch`
**Lines**: 620 lines
**Files Modified**: 5 files
**Type**: Unified diff format

---

## What's Included in This Patch

### 1. MCP (Model Context Protocol) Enhancements
**Files**: `bondable/bond/providers/bedrock/BedrockMCP.py`, `bondable/rest/routers/mcp.py`

- **OAuth2 Token Support**: Added support for passing OAuth2 tokens to MCP servers
- **Atlassian Integration**: Added `X-Atlassian-Cloud-Id` header support for Atlassian MCP servers
- **Improved Transport Handling**: Updated to use `fastmcp.StreamableHttpTransport` for better SSE support
- **Enhanced Debugging**: Added OpenAPI spec logging for MCP action group creation
- **Better Error Handling**: Improved error logging with full exception details and tracebacks

### 2. Bedrock Agent Error Handling & Logging
**File**: `bondable/bond/providers/bedrock/BedrockAgent.py`

- **User-Friendly Error Messages**: Added helpful error messages for `internalServerException` errors
- **Enhanced Tool Execution Logging**: Improved logging for MCP tool execution with success status and result previews
- **Better Exception Handling**: Added detailed parameter logging when tools fail
- **Improved Event Processing**: Enhanced logging throughout the event stream processing
- **Status Code Tracking**: Better HTTP status code handling for tool responses

### 3. Authentication & Connection Logging Improvements
**File**: `bondable/rest/routers/connections.py`

- **Security Enhancement**: Removed sensitive user information (emails, IDs) from logs
- **Reduced Log Verbosity**: Changed many INFO level logs to DEBUG to reduce noise
- **Cleaner Log Messages**: Streamlined authorization and OAuth callback logging
- **Better Error-Level Logging**: Improved logging for actual failures vs normal operations

### 4. Dependency Updates
**Files**: `pyproject.toml`, `poetry.lock`

- **fastmcp**: Updated from `>=2.13.0` to `^2.13.2`
- **mcp**: Updated from `^1.9.1` to `^1.23.1`
- **Removed unused dependency**: Removed `keyring` from optional dependencies

---

## Prerequisites

### Required Tools
- Git version 2.0 or higher
- Python 3.12 (for testing after applying)
- Poetry (for dependency management)

### Before You Start
1. **Ensure you have a clean working directory**:
   ```bash
   git status
   # Should show: "nothing to commit, working tree clean"
   ```

2. **Create a backup branch** (recommended):
   ```bash
   git branch backup-before-patch
   ```

3. **Ensure you're on the target branch**:
   ```bash
   git checkout main  # or your target branch
   ```

---

## Application Instructions

### Step 1: Verify Patch Contents
First, review what the patch will change:

```bash
# View patch statistics
git apply --stat bondai-fork-improvements.patch

# Check if patch will apply cleanly (dry run)
git apply --check bondai-fork-improvements.patch
```

**Expected Output**: No errors. If you see errors, see the Troubleshooting section below.

### Step 2: Apply the Patch
Apply the patch to your working directory:

```bash
# Apply the patch
git apply bondai-fork-improvements.patch

# Verify the changes
git status
git diff
```

**Expected Result**: 5 files modified (4 Python files + 2 dependency files)

### Step 3: Review the Changes
Carefully review each modified file:

```bash
# Review each file
git diff bondable/bond/providers/bedrock/BedrockAgent.py
git diff bondable/bond/providers/bedrock/BedrockMCP.py
git diff bondable/rest/routers/connections.py
git diff bondable/rest/routers/mcp.py
git diff pyproject.toml
git diff poetry.lock
```

### Step 4: Update Dependencies
After applying the patch, update your Python dependencies:

```bash
# Update dependencies using Poetry
poetry lock --no-update
poetry install

# Or if you need to update all dependencies
poetry update fastmcp mcp
```

### Step 5: Commit the Changes
Once you've verified the changes, commit them:

```bash
# Stage all changes
git add bondable/ pyproject.toml poetry.lock

# Create a descriptive commit
git commit -m "Apply fork improvements: MCP enhancements, Bedrock error handling, and logging improvements

- Add OAuth2 token support and Atlassian integration for MCP
- Enhance Bedrock Agent error handling with user-friendly messages
- Improve logging throughout authentication and tool execution
- Update fastmcp to 2.13.2 and mcp to 1.23.1
- Remove sensitive information from logs for security

Co-authored-by: McAfee Engineering <engineering@mcafee.com>"
```

### Alternative: Apply as Multiple Commits
If you prefer to apply changes as separate logical commits:

```bash
# Apply the patch without committing
git apply bondai-fork-improvements.patch

# Stage and commit by logical groups
git add bondable/bond/providers/bedrock/BedrockMCP.py bondable/rest/routers/mcp.py
git commit -m "Add MCP OAuth2 and Atlassian integration support"

git add bondable/bond/providers/bedrock/BedrockAgent.py
git commit -m "Enhance Bedrock Agent error handling and logging"

git add bondable/rest/routers/connections.py
git commit -m "Improve authentication logging and remove sensitive data"

git add pyproject.toml poetry.lock
git commit -m "Update fastmcp and mcp dependencies"
```

---

## Verification & Testing

### 1. Code Review Checklist
- [ ] All changes are present in the expected files
- [ ] No unexpected files were modified
- [ ] Dependency versions are correctly updated
- [ ] No merge conflicts or syntax errors

### 2. Functional Testing

#### Test MCP Integration
```bash
# Start the application
poetry run python -m bondable.rest.main

# Test MCP OAuth flow
# - Navigate to MCP connections
# - Authorize an Atlassian MCP server
# - Verify OAuth token is passed correctly
# - Check logs for "X-Atlassian-Cloud-Id" header
```

#### Test Bedrock Agent
```bash
# Test error handling
# - Send a query that triggers an internalServerException
# - Verify user-friendly error message appears
# - Check logs for detailed error information

# Test tool execution
# - Execute an MCP tool through Bedrock Agent
# - Verify success/failure is logged correctly
# - Check result preview appears in logs
```

#### Test Logging
```bash
# Check log levels
# - Verify sensitive information is not logged
# - Confirm DEBUG level logs are properly categorized
# - Ensure INFO logs are meaningful and concise
```

### 3. Automated Tests
```bash
# Run the test suite
poetry run pytest tests/

# Run specific MCP tests
poetry run pytest tests/test_mcp*.py -v

# Check for any breaking changes
poetry run pytest tests/ --tb=short
```

---

## Troubleshooting

### Issue: Patch Doesn't Apply Cleanly

**Symptom**: `git apply --check` reports errors or conflicts

**Solution**:
```bash
# Option 1: Apply with 3-way merge
git apply --3way bondai-fork-improvements.patch

# Option 2: See what's failing
git apply --reject bondai-fork-improvements.patch
# This creates .rej files showing what didn't apply
# Manually merge these changes

# Option 3: Check your starting point
git log --oneline -10
# Ensure you're at a commit close to where the patch was created
```

### Issue: Dependency Conflicts

**Symptom**: Poetry fails to install updated dependencies

**Solution**:
```bash
# Clear Poetry cache
poetry cache clear --all pypi

# Remove poetry.lock and regenerate
rm poetry.lock
poetry install

# If still failing, check Python version
python --version  # Should be 3.12.x
```

### Issue: Tests Failing After Patch

**Symptom**: Tests that passed before now fail

**Solution**:
```bash
# Check which tests are failing
poetry run pytest tests/ -v --tb=line

# Common issues:
# 1. Log level changes - Update test assertions for DEBUG vs INFO
# 2. Error messages changed - Update expected error text in tests
# 3. New headers added - Update MCP integration tests to expect X-Atlassian-Cloud-Id
```

### Issue: Import Errors

**Symptom**: `ImportError` for fastmcp or mcp modules

**Solution**:
```bash
# Ensure dependencies are installed
poetry install --sync

# Verify versions
poetry show fastmcp  # Should be 2.13.2
poetry show mcp      # Should be 1.23.1

# If wrong versions, force update
poetry update fastmcp mcp
```

---

## Rollback Instructions

If you need to undo the patch:

### Before Committing
```bash
# Simply reset your working directory
git reset --hard HEAD
git clean -fd
```

### After Committing
```bash
# Revert the commit
git revert HEAD

# Or reset to before the patch (loses commit)
git reset --hard HEAD~1

# Or restore from backup branch
git reset --hard backup-before-patch
```

### Manual Rollback
```bash
# Reverse the patch
git apply --reverse bondai-fork-improvements.patch

# Restore old dependencies
git checkout HEAD -- pyproject.toml poetry.lock
poetry install
```

---

## What's NOT Included

This patch **excludes** the following from the McAfee fork:

- All deployment documentation (`deployment/*.md` files)
- McAfee-specific operational guides
- Test scripts for VPC and connectivity
- Architecture diagrams
- Environment-specific configuration files

These remain in the fork for operational purposes and are not intended for upstream contribution.

---

## Post-Application Recommendations

### 1. Code Review
- Have another developer review the changes
- Ensure the Atlassian MCP integration makes sense for your use case
- Verify log level changes align with your logging strategy

### 2. Documentation Updates
- Update your README if MCP capabilities have expanded
- Document the new OAuth2 token flow for MCP servers
- Add examples of using Atlassian MCP integration

### 3. Release Notes
Consider adding to release notes:
```markdown
## Enhancements
- Added OAuth2 token support for MCP servers
- Improved Bedrock Agent error messages for better user experience
- Enhanced logging throughout MCP and authentication flows
- Added support for Atlassian MCP server integration

## Dependencies
- Updated fastmcp to 2.13.2
- Updated mcp to 1.23.1

## Security
- Removed sensitive user information from logs
```

---

## Support

If you encounter issues not covered in this guide:

1. **Check Git logs**: `git log --oneline --graph --all` to understand your branch state
2. **Review original changes**: Compare with the McAfee fork at specific commits
3. **Contact the McAfee team**: Reference this patch and specific error messages

---

## Summary

**Quick Application**:
```bash
# 1. Backup
git branch backup-before-patch

# 2. Verify
git apply --check bondai-fork-improvements.patch

# 3. Apply
git apply bondai-fork-improvements.patch

# 4. Update dependencies
poetry install

# 5. Test
poetry run pytest tests/

# 6. Commit
git add bondable/ pyproject.toml poetry.lock
git commit -m "Apply fork improvements: MCP enhancements and error handling"
```

**Files Modified**: 5
**Estimated Time**: 15-30 minutes (including testing)
**Risk Level**: Low (all improvements, no breaking changes)

---

*Generated for Bond AI upstream integration - 2025*
