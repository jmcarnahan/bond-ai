# OAuth2 Provider Configuration

Bond AI supports multiple OAuth2 providers for authentication. You can configure which providers are available through environment variables.

## Supported Providers

- **Google OAuth2** - Sign in with Google accounts
- **Okta OAuth2** - Sign in with Okta (supports enterprise SSO)

## Configuration Methods

### Method 1: Individual Provider Flags

Enable or disable specific providers using these environment variables:

```bash
# Enable/disable Google OAuth2 (default: true)
OAUTH2_ENABLE_GOOGLE=true

# Enable/disable Okta OAuth2 (default: true)
OAUTH2_ENABLE_OKTA=true
```

### Method 2: Explicit Provider List

Override individual flags by explicitly listing enabled providers:

```bash
# Only enable specific providers
OAUTH2_ENABLED_PROVIDERS=google,okta  # Both providers
OAUTH2_ENABLED_PROVIDERS=google       # Only Google
OAUTH2_ENABLED_PROVIDERS=okta         # Only Okta
```

## Provider-Specific Configuration

### Google OAuth2

```bash
# Option 1: Use GCP Secret Manager (recommended)
GOOGLE_AUTH_CREDS_SECRET_ID=google_auth_creds

# Option 2: Direct credentials (development only)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret

# Optional settings
GOOGLE_AUTH_REDIRECT_URI=http://localhost:8000/auth/google/callback
GOOGLE_AUTH_VALID_EMAILS=user1@example.com,user2@example.com
```

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

## Common Configuration Examples

### Both Providers (Default)
```bash
# No additional configuration needed if both are configured
# Both will be available by default
```

### Google Only
```bash
OAUTH2_ENABLED_PROVIDERS=google
```

### Okta Only
```bash
OAUTH2_ENABLED_PROVIDERS=okta
```

### Disable Okta
```bash
OAUTH2_ENABLE_OKTA=false
```

## How It Works

1. **Provider Discovery**: The backend checks environment variables to determine which providers to enable
2. **Automatic Detection**: Providers are only enabled if they have valid credentials configured
3. **Dynamic UI**: The login screen automatically shows buttons for enabled providers
4. **Fallback**: If no providers are properly configured, the system defaults to Google

## Security Notes

- Never commit credentials to version control
- Use secret management systems in production (e.g., GCP Secret Manager, AWS Secrets Manager)
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
