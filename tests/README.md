# Bond AI Test Suite Documentation

## Overview

This directory contains the test suite for the Bond AI project, which focuses on building and using agents with AWS Bedrock Agents and MCP (Model Context Protocol) integration. The tests are organized to validate core functionality, integrations, and end-to-end workflows.

## Quick Start

### Run all tests without local services
```bash
SKIP_MCP_TESTS=true pytest tests/ -v
```

### Run specific test categories
```bash
# Unit tests only
pytest tests/test_cache.py tests/test_config.py tests/test_broker.py -v

# Integration tests with AWS
pytest tests/test_bedrock_* -v

# REST API tests
pytest tests/test_rest_api.py tests/test_*_endpoint.py -v
```

## Test Files and Dependencies

### Core Component Tests (No External Dependencies)

| Test File | Description | Dependencies | Type |
|-----------|-------------|--------------|------|
| `test_agent.py` | Core agent functionality and lifecycle | None | Unit |
| `test_broker.py` | Message broker and routing logic | None | Unit |
| `test_builder.py` | Builder pattern implementation | None | Unit |
| `test_cache.py` | Caching functionality | None | Unit |
| `test_config.py` | Configuration management | None | Unit |
| `test_threads.py` | Thread management | Temp SQLite DB (auto-created) | Unit |
| `test_bond_providers.py` | Provider interface and abstraction | None | Unit |

### AWS Bedrock Integration Tests

| Test File | Description | AWS Dependencies | Local Dependencies | Type |
|-----------|-------------|------------------|-------------------|------|
| `test_bedrock_provider_integration.py` | Bedrock provider lifecycle, agent creation/deletion | AWS Bedrock | None | Integration |
| `test_bedrock_threads_integration.py` | Thread management with Bedrock | AWS Bedrock | None | Integration |
| `test_bedrock_stream_response_integration.py` | Streaming response functionality | AWS Bedrock | MCP server (optional, port 5555) | Integration |
| `test_bedrock_files.py` | File handling and vector stores | AWS Bedrock, S3 | None | Integration |
| `test_bedrock_image_streaming.py` | Image generation and streaming | AWS Bedrock | None | Integration |
| `test_bedrock_attachment_conversion.py` | Attachment format conversion | AWS Bedrock, S3 | None | Integration |
| `test_bedrock_crud_mcp_simple.py` | CRUD operations for Bedrock agents | AWS Bedrock | None | Integration |
| `test_bedrock_mcp_functionality.py` | MCP tool integration with Bedrock | AWS Bedrock | **MCP server (port 5555)** | Integration |

### REST API Tests

| Test File | Description | Dependencies | Type |
|-----------|-------------|--------------|------|
| `test_rest_api.py` | Comprehensive REST API endpoints | FastAPI TestClient, Temp SQLite DB | End-to-End |
| `test_auth_oauth2.py` | OAuth2 authentication flow | FastAPI TestClient, Temp SQLite DB | Integration |
| `test_okta_oauth2.py` | Okta OAuth integration | FastAPI TestClient, Temp SQLite DB | Integration |
| `test_models_endpoint.py` | Model management endpoints | FastAPI TestClient, Temp SQLite DB | Integration |

### Configuration and Default Tests

| Test File | Description | Dependencies | Type |
|-----------|-------------|--------------|------|
| `test_default_agent.py` | Default agent configuration and behavior | Varies (mocked) | Integration |
| `test_default_model_integration.py` | Default model selection and configuration | None | Integration |
| `test_env_models_config.py` | Environment-based model configuration | None | Unit |
| `test_models_integration.py` | Model integration and selection | None | Integration |

## External Service Dependencies

### AWS Services Required
Most Bedrock tests require:
- **AWS Credentials**: Via AWS CLI, environment variables, or IAM role
- **AWS Region**: Set via `AWS_REGION` or `AWS_DEFAULT_REGION`
- **Bedrock Access**: Appropriate IAM permissions for Bedrock
- **S3 Access**: For file/attachment tests (optional)
- **Environment Variables**:
  - `BEDROCK_AGENT_ROLE_ARN`: Required for some agent creation tests
  - `BOND_PROVIDER_CLASS`: Set to use Bedrock provider

### Local Services

#### MCP Server (Optional for most tests)
- **Port**: 5555
- **Required for**:
  - `test_bedrock_mcp_functionality.py` (can skip with `SKIP_MCP_TESTS=true`)
  - `test_bedrock_stream_response_integration.py` (partially)
- **Skip if unavailable**: `SKIP_MCP_TESTS=true pytest tests/ -v`

#### No REST API Server Required
All REST API tests use FastAPI's `TestClient` which creates an in-memory test server. No need to run the API separately.

#### Database
Tests that need a database automatically create temporary SQLite databases. No setup required.

## Environment Setup

### Minimal Setup (Unit Tests Only)
```bash
# No special setup needed
pytest tests/test_cache.py tests/test_config.py tests/test_broker.py -v
```

### AWS Integration Setup
```bash
# Configure AWS credentials
aws configure

# Set required environment variables
export AWS_REGION=us-east-1
export BEDROCK_AGENT_ROLE_ARN=arn:aws:iam::YOUR_ACCOUNT:role/YOUR_ROLE
export BOND_PROVIDER_CLASS=bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider

# Run Bedrock tests
pytest tests/test_bedrock_* -v
```

### Full Setup with MCP
```bash
# Start MCP server on port 5555
# (Refer to your MCP server documentation)

# Run all tests including MCP
pytest tests/ -v
```

## Test Categories

### By Independence Level

**Fully Self-Contained (15 tests)**
- All unit tests
- Most integration tests with mocked dependencies
- FastAPI tests with TestClient

**AWS-Dependent (8 tests)**
- All `test_bedrock_*` files
- Require AWS credentials and appropriate permissions

**Local Service-Dependent (2 tests)**
- `test_bedrock_mcp_functionality.py` - Requires MCP server
- `test_bedrock_stream_response_integration.py` - Optionally uses MCP server

## Running Tests

### Run all tests
```bash
pytest tests/ -v
```

### Run with coverage
```bash
pytest tests/ --cov=bondable --cov-report=html -v
```

### Run specific test file
```bash
pytest tests/test_rest_api.py -v
```

### Run with specific markers (if configured)
```bash
pytest tests/ -m "not requires_mcp" -v
```

### Skip slow tests
```bash
pytest tests/ --ignore=tests/test_bedrock_stream_response_integration.py -v
```

## Archived Tests

The `tests/.archive/` directory contains older, experimental, or superseded test files that were used during development. These include:
- Debug scripts (`debug_bedrock_events.py`)
- Phase development tests (`test_bedrock_phase1.py`)
- Demo scripts (`test_bedrock_threads_demo.py`)
- Superseded implementations

These are kept for reference but are not part of the active test suite.

## Contributing

When adding new tests:
1. Use pytest framework for consistency
2. Document external dependencies clearly
3. Add appropriate skip markers for tests requiring external services
4. Include the test in the appropriate section of this README
5. Follow existing naming conventions:
   - `test_*.py` for test files
   - `test_*` for test functions
   - `Test*` for test classes

## Troubleshooting

### Common Issues

1. **MCP Tests Failing**
   - Ensure MCP server is running on port 5555
   - Or skip with: `SKIP_MCP_TESTS=true pytest tests/ -v`

2. **AWS Tests Failing**
   - Check AWS credentials: `aws sts get-caller-identity`
   - Ensure `BEDROCK_AGENT_ROLE_ARN` is set correctly
   - Verify IAM permissions for Bedrock

3. **Database Errors**
   - Tests create temp databases automatically
   - If issues persist, check write permissions in temp directory

4. **Import Errors**
   - Ensure project is installed: `pip install -e .`
   - Check Python path includes project root
