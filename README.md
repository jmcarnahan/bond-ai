# Bond AI

A full-stack application for creating and using AI agents with OpenAI or AWS Bedrock APIs. Features a FastAPI backend with MCP (Model Context Protocol) support and a Flutter web frontend.

## Quick Start

```bash
# Clone and setup
git clone https://github.com/jmcarnahan/bond-ai.git
cd bond-ai

# Backend setup
poetry install
cp .env.example .env
# Edit .env with your API keys

# Run all components (in separate terminals)
# 1. MCP Server
fastmcp run scripts/my_server.py --transport streamable-http --port 5555

# 2. Backend API
uvicorn bondable.rest.main:app --reload --host 0.0.0.0 --port 8000

# 3. Frontend (from flutterui directory)
cd flutterui && flutter run -d chrome --web-port=5000 --target lib/main.dart
```

## Prerequisites

- **Python 3.12** 
- **Poetry** (for Python dependency management)
- **Flutter SDK** (3.7.2 or higher)
- **Chrome browser** (for Flutter web development)
- **API Keys**: Either OpenAI API key OR AWS credentials for Bedrock

## Installation

### Backend Setup

1. **Install Poetry** (if not already installed):
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. **Install Python dependencies**:
```bash
poetry config virtualenvs.in-project true
poetry install
poetry shell
```

3. **Configure environment**:
```bash
cp .env.example .env
```

Edit `.env` and configure your provider:

#### For OpenAI:
```env
BOND_PROVIDER_CLASS="bondable.bond.providers.openai.OAIAProvider.OAIAProvider"
OPENAI_KEY="sk-proj-YOUR_API_KEY"
OPENAI_PROJECT="proj_YOUR_PROJECT_ID"
OPENAI_DEFAULT_MODEL="gpt-4o"
```

#### For AWS Bedrock:
```env
BOND_PROVIDER_CLASS="bondable.bond.providers.bedrock.BedrockProvider.BedrockProvider"
AWS_ACCESS_KEY_ID="your_access_key"
AWS_SECRET_ACCESS_KEY="your_secret_key"
AWS_REGION="us-east-1"
BEDROCK_DEFAULT_MODEL="us.anthropic.claude-3-5-sonnet-20241022-v2:0"
```

4. **Configure authentication** (optional but recommended):
```env
JWT_SECRET_KEY="$(openssl rand -hex 32)"  # Generate a secure key
OAUTH2_ENABLED_PROVIDERS=google
```

### Frontend Setup

1. **Navigate to Flutter directory**:
```bash
cd flutterui
```

2. **Install Flutter dependencies**:
```bash
flutter pub get
```

3. **Configure frontend environment**:
```bash
cp .env.example .env  # Create if doesn't exist
```

Edit `flutterui/.env`:
```env
API_BASE_URL=http://localhost:8000
ENABLE_AGENTS=true
```

4. **Choose a theme** (optional):
```bash
# Use generic Bond AI theme (default)
dart tool/generate_theme.dart

# OR use McAfee theme
dart tool/generate_theme.dart --config theme_configs/mcafee_config.json
```

For more theming options, see the [Flutter Theming Guide](flutterui/THEMING.md).

## Running the Application

You'll need three terminal windows to run all components:

### Terminal 1: MCP Server
```bash
# From project root
fastmcp run scripts/my_server.py --transport streamable-http --port 5555
```

### Terminal 2: Backend API
```bash
# From project root
uvicorn bondable.rest.main:app --reload --host 0.0.0.0 --port 8000
```

### Terminal 3: Frontend
```bash
# From flutterui directory
flutter run -d chrome --web-port=5000 --target lib/main.dart
```

Access the application at: **http://localhost:5000**

## Architecture Overview

### Backend (`bondable/`)
- **FastAPI REST API** - Main backend service
- **Provider System** - Abstracts OpenAI and AWS Bedrock APIs
- **MCP Integration** - Model Context Protocol for tool access
- **Authentication** - OAuth2 support (Google, Okta)

### Frontend (`flutterui/`)
- **Flutter Web** - Cross-platform UI framework
- **Riverpod** - State management
- **Real-time Updates** - Optional Firestore integration
- **Customizable Themes** - Switch between branded themes (see [Theming Guide](flutterui/THEMING.md))

### Key Directories
```
bond-ai/
├── bondable/          # Backend Python package
│   ├── bond/         # Core agent logic
│   │   └── providers/ # AI provider implementations
│   └── rest/         # FastAPI application
├── flutterui/        # Flutter frontend
├── scripts/          # Utility scripts
│   ├── my_server.py  # MCP server implementation
│   └── my_client.py  # MCP client example
└── tests/            # Test suite
```

## API Documentation

Once running, access the interactive API documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Testing

Run the test suite:
```bash
poetry run pytest
```

For specific test categories:
```bash
poetry run pytest tests/test_rest_api.py  # API tests
poetry run pytest tests/test_bedrock_*.py  # Bedrock tests
```

## Environment Variables

### Essential Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `BOND_PROVIDER_CLASS` | AI provider class | `bondable.bond.providers.openai.OAIAProvider.OAIAProvider` |
| `JWT_SECRET_KEY` | JWT signing key | Generate with `openssl rand -hex 32` |
| `BOND_METADATA_DB_URL` | Database URL | `sqlite:///bond_metadata.db` |

### Provider-Specific

**OpenAI:**
- `OPENAI_KEY` - API key
- `OPENAI_PROJECT` - Project ID
- `OPENAI_DEFAULT_MODEL` - Default model

**AWS Bedrock:**
- `AWS_ACCESS_KEY_ID` - AWS access key
- `AWS_SECRET_ACCESS_KEY` - AWS secret key
- `AWS_REGION` - AWS region
- `BEDROCK_DEFAULT_MODEL` - Default Bedrock model
- `BEDROCK_S3_BUCKET` - S3 bucket for files
- `BEDROCK_AGENT_ROLE_ARN` - IAM role for agents

### Optional Features

**OAuth2 Authentication:**
- `OAUTH2_ENABLED_PROVIDERS` - Comma-separated providers
- Google OAuth: `GOOGLE_AUTH_CREDS_JSON`
- Okta OAuth: `OKTA_DOMAIN`, `OKTA_CLIENT_ID`, `OKTA_CLIENT_SECRET`

**MCP Configuration:**
- `BOND_MCP_CONFIG` - JSON configuration for MCP servers

## Troubleshooting

### Common Issues

**Port already in use:**
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Kill process on port 5555
lsof -ti:5555 | xargs kill -9
```

**Flutter web not loading:**
- Ensure Chrome is installed
- Check CORS settings in `bondable/rest/main.py`
- Verify `API_BASE_URL` in `flutterui/.env`

**Authentication errors:**
- Regenerate JWT_SECRET_KEY
- Check OAuth2 redirect URIs match configuration

**AWS Bedrock issues:**
- Verify model access in AWS Console
- Check IAM permissions
- Ensure S3 bucket exists and is accessible

### Logs

Backend logs location: `logs/bondable_debug.log`

Enable debug logging:
```python
# In bondable/rest/logging_config.yaml
level: DEBUG
```

## Additional Documentation

- [AWS Bedrock Setup Guide](bondable/bond/providers/bedrock/AWS_SETUP.md)
- [OAuth2 Configuration](docs/oauth2-configuration.md)
- [API Migration Guide](docs/BEDROCK_AGENTS_MIGRATION_PLAN.md)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
- GitHub Issues: https://github.com/jmcarnahan/bond-ai/issues
- Documentation: See `/docs` directory for detailed guides