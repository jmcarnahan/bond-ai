# AWS Bedrock Provider for Bond AI

This directory contains the AWS Bedrock implementation of the Bond AI provider interface.

## Overview

The Bedrock provider enables Bond AI to use AWS Bedrock's Converse API for generative AI capabilities. Unlike OpenAI's Assistants API, Bedrock doesn't have built-in thread management or vector stores, so this implementation provides these features using:

- **Thread Management**: Stored in metadata database
- **Message History**: Persisted in database for conversation continuity
- **File Storage**: AWS S3 (Phase 3)
- **Vector Stores**: Bedrock Knowledge Bases (Phase 4)
- **Agent Interactions**: Bedrock Converse API with streaming (Phase 2)

## Current Status

### Phase 1: Foundation and Thread Management ✅ Complete

- **BedrockProvider**: Main provider class with AWS client initialization
- **BedrockMetadata**: Extended metadata storage with message persistence
- **BedrockThreads**: Thread management implementation

### Phase 2: Agent Implementation and Streaming 🚧 Pending

- Agent configuration and management
- Streaming response handling
- Tool integration

### Phase 3: File Management 📋 Planned

- S3-based file storage
- Multimodal support

### Phase 4: Vector Stores 📋 Planned

- Knowledge Base integration
- RAG capabilities

### Phase 5: Testing and Integration 📋 Planned

- Comprehensive test suite
- Documentation

## Configuration

### Environment Variables

```bash
# AWS Configuration
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key

# Bedrock Configuration  
export BEDROCK_DEFAULT_MODEL=anthropic.claude-3-haiku-20240307-v1:0
export BEDROCK_S3_BUCKET=your-bucket-name  # For file storage

# Provider Selection
export BOND_PROVIDER_CLASS=bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider

# Database (uses Bond's standard database configuration)
export METADATA_DB_URL=sqlite:///bond_metadata.db
```

### AWS Permissions Required

Your AWS credentials need the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
        "bedrock:ListFoundationModels"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow", 
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket-name",
        "arn:aws:s3:::your-bucket-name/*"
      ]
    }
  ]
}
```

## Testing

### Phase 1 Tests

Run the Phase 1 test suite:

```bash
python tests/test_bedrock_phase1.py
```

This tests:
- Provider initialization
- Message storage and retrieval
- Thread management
- Model configuration

## Usage Example

```python
from bondable.bond.providers.bedrock.BedrockProvider import BedrockProvider

# Initialize provider
provider = BedrockProvider.provider()

# Create a thread
thread_id = provider.threads.create_thread_resource()

# Add messages (Phase 1 - manual)
provider.threads.add_message(
    thread_id=thread_id,
    user_id="user123",
    role="user",
    content="Hello, how are you?"
)

# Get messages
messages = provider.threads.get_messages(thread_id)

# Once Phase 2 is complete, you'll be able to:
# agent = provider.agents.get_agent("agent_id")
# response = agent.stream_response("Hello!", thread_id)
```

## Architecture Notes

### Message Storage

Messages are stored in the `bedrock_messages` table with:
- Full conversation history per thread
- Support for multimodal content (text, images, documents)
- Message ordering via `message_index`
- User-based isolation

### Thread Management

Threads are virtual - they exist as:
1. A UUID identifier
2. Records in the `threads` table (standard Bond)
3. Associated messages in `bedrock_messages`

### Model Mapping

The provider includes friendly name mapping:
- `claude-3-haiku` → `anthropic.claude-3-haiku-20240307-v1:0`
- `claude-3.5-sonnet` → `anthropic.claude-3-5-sonnet-20241022-v2:0`
- etc.

## Development

### Adding a New Feature

1. Update the appropriate module
2. Add tests to the test suite
3. Update this README
4. Update the IMPLEMENTATION_PLAN.md if needed

### Database Migrations

When adding new tables:
1. Add them to `BedrockMetadata.py`
2. The `create_all()` method will create them on initialization
3. Consider migration scripts for production deployments

## Known Limitations

1. **No Built-in Thread Persistence**: Unlike OpenAI, threads exist only in our database
2. **Model Availability**: Model access depends on your AWS region and account permissions
3. **Cost Considerations**: Bedrock pricing differs from OpenAI - monitor usage carefully

## Future Enhancements

- Bedrock Agents API integration (beyond Converse)
- Guardrails support
- Multi-region failover
- Advanced caching strategies