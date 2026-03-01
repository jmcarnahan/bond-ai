# OAuth2 Provider Configuration

Bond AI supports multiple OAuth2 providers for authentication. You can configure which providers are available through environment variables.

## Supported Providers

- **Okta OAuth2** - Sign in with Okta (supports enterprise SSO)
- **Cognito OAuth2** - Sign in with AWS Cognito
- **Google OAuth2** - Sign in with Google accounts (also supported)

## Configuration Methods

### Method 1: Individual Provider Flags

Enable or disable specific providers using these environment variables:

```bash
# Enable/disable Okta OAuth2 (default: true)
OAUTH2_ENABLE_OKTA=true

# Enable/disable Cognito OAuth2 (default: true)
OAUTH2_ENABLE_COGNITO=true
```

### Method 2: Explicit Provider List

Override individual flags by explicitly listing enabled providers:

```bash
# Only enable specific providers
OAUTH2_ENABLED_PROVIDERS=okta,cognito  # Both providers
OAUTH2_ENABLED_PROVIDERS=okta          # Only Okta
OAUTH2_ENABLED_PROVIDERS=cognito       # Only Cognito
```

## Provider-Specific Configuration

### Okta OAuth2

```bash
# Required settings
OKTA_DOMAIN=https://your-domain.okta.com
OKTA_CLIENT_ID=your-okta-client-id
OKTA_CLIENT_SECRET=your-okta-client-secret

# Optional settings
OKTA_REDIRECT_URI=http://localhost:8000/auth/okta/callback
OKTA_VALID_EMAILS=user1@example.com,user2@example.com
```

### Cognito OAuth2

```bash
# Required settings
COGNITO_DOMAIN=https://your-pool.auth.us-east-1.amazoncognito.com
COGNITO_CLIENT_ID=your-cognito-client-id
COGNITO_CLIENT_SECRET=your-cognito-client-secret

# Optional settings
COGNITO_REDIRECT_URI=http://localhost:8000/auth/cognito/callback
COGNITO_VALID_EMAILS=user1@example.com,user2@example.com
```

## Common Configuration Examples

### Okta + Cognito
```bash
OAUTH2_ENABLED_PROVIDERS=okta,cognito
```

### Okta Only
```bash
OAUTH2_ENABLED_PROVIDERS=okta
```

### Cognito Only
```bash
OAUTH2_ENABLED_PROVIDERS=cognito
```

### Disable Okta
```bash
OAUTH2_ENABLE_OKTA=false
```

## How It Works

1. **Provider Discovery**: The backend checks environment variables to determine which providers to enable
2. **Automatic Detection**: Providers are only enabled if they have valid credentials configured
3. **Dynamic UI**: The login screen automatically shows buttons for enabled providers
4. **Fallback**: If no providers are properly configured, the system defaults to the first configured provider

## Security Notes

- Never commit credentials to version control
- Use secret management systems in production (e.g., AWS Secrets Manager, HashiCorp Vault)
- Always use HTTPS in production for redirect URIs
- Consider using `VALID_EMAILS` to restrict access during development/testing

## Troubleshooting

### Provider Not Showing Up
1. Check that credentials are configured
2. Check backend logs for configuration warnings
3. Verify the `/providers` endpoint returns your provider

### Authentication Fails
1. Verify redirect URI matches exactly in provider config
2. Check that client ID and secret are correct
3. For Okta, ensure the app has proper authorization policies
4. For Cognito, ensure the app client has the correct callback URLs configured
