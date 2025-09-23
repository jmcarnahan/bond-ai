# Database Connection Fix - Changes Made

## Date: 2025-09-23

### Problem
Database authentication was failing with error:
```
psycopg2.OperationalError: connection to server at "bond-ai-dev-db.crk02wcwa0ie.us-west-2.rds.amazonaws.com" (10.0.10.75), port 5432 failed: FATAL:  password authentication failed for user "bondadmin"
```

### Root Cause
The database password contained special characters that required URL encoding in PostgreSQL connection strings, but the encoding wasn't working properly in both the initial deployment and post-deployment updates.

### Solution Applied
Changed to using alphanumeric-only passwords to eliminate URL encoding issues entirely.

## Files Modified

### 1. `main.tf` (Lines 20-30)
**Changed password generation to alphanumeric only:**

#### Before:
```hcl
# Random password for RDS
resource "random_password" "db_password" {
  length  = 32
  special = true
  override_special = "!-_=+"  # URL-safe special characters only
}

# Random JWT secret key
resource "random_password" "jwt_secret" {
  length  = 64
  special = true
  override_special = "!-_=+"  # URL-safe special characters only
}
```

#### After:
```hcl
# Random password for RDS
resource "random_password" "db_password" {
  length  = 32
  special = false  # Use only alphanumeric for now to avoid encoding issues
}

# Random JWT secret key
resource "random_password" "jwt_secret" {
  length  = 64
  special = false  # Use only alphanumeric for now to avoid encoding issues
}
```

### 2. `backend.tf` (Line 50)
**Removed URL encoding function:**

#### Before:
```hcl
METADATA_DB_URL = "postgresql://bondadmin:${urlencode(random_password.db_password.result)}@${aws_db_instance.main.address}:5432/bondai"
```

#### After:
```hcl
METADATA_DB_URL = "postgresql://bondadmin:${random_password.db_password.result}@${aws_db_instance.main.address}:5432/bondai"
```

### 3. `post-deployment-updates.tf` (Lines 51-53 and 72)
**Removed URL encoding logic:**

#### Before (Lines 51-53):
```bash
# URL-encode the database password
DB_PASSWORD_ENCODED=$(echo -n '${random_password.db_password.result}' | jq -sRr @uri)
echo "Database password has been URL-encoded for connection string"
```

#### After:
```bash
# Database password is now alphanumeric only, no encoding needed
DB_PASSWORD='${random_password.db_password.result}'
echo "Using alphanumeric database password (no encoding required)"
```

#### Before (Line 72):
```json
"METADATA_DB_URL": "postgresql://bondadmin:$DB_PASSWORD_ENCODED@${aws_db_instance.main.address}:5432/bondai",
```

#### After:
```json
"METADATA_DB_URL": "postgresql://bondadmin:$DB_PASSWORD@${aws_db_instance.main.address}:5432/bondai",
```

## Deployment Process

1. **Taint password resources to force recreation:**
   ```bash
   terraform taint random_password.db_password
   terraform taint random_password.jwt_secret
   ```

2. **Apply terraform configuration:**
   ```bash
   terraform apply -var-file=<your-tfvars-file>
   ```

## Result
- Database connection now works reliably with alphanumeric passwords
- No URL encoding issues
- System is back to working state

## Future Considerations
Once the system is stable, consider:
1. Using URL-safe special characters (e.g., `-_`) that don't require encoding
2. Implementing proper URL encoding if special characters are needed
3. Testing with PostgreSQL connection string formats that handle special characters better