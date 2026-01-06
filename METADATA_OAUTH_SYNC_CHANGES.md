# Metadata OAuth Sync Changes - To Reapply After Upstream Merge

**Date:** December 1, 2025
**Status:** Changes backed out, ready for upstream merge
**Patch File:** `/tmp/metadata-oauth-sync-changes.patch`

---

## Overview

These changes were made to fix the ConnectionConfig table sync issues but have been backed out to prepare for an upstream merge. They need to be carefully reapplied after merging upstream changes.

## Issues These Changes Addressed

1. **Foreign Key Violation** - `connection_name='atlassian'` not found in `connection_configs` table
2. **Missing Sync Call** - `BedrockMetadata.create_all()` wasn't calling parent method
3. **Initialization Order** - `self.session` created after `create_all()` was called
4. **OAuth Redirect URI** - Missing column in ConnectionConfig model

## Changes Made (Now Reverted)

### bondable/bond/providers/metadata.py

#### 1. Added Imports (lines 9-11)
```python
import os
import json
import uuid
```

#### 2. Added oauth_redirect_uri Column (line 119)
```python
class ConnectionConfig(Base):
    # ... existing fields ...
    oauth_client_id = Column(String, nullable=True)
    oauth_authorize_url = Column(String, nullable=True)
    oauth_token_url = Column(String, nullable=True)
    oauth_redirect_uri = Column(String, nullable=True)  # OAuth callback URL
    oauth_scopes = Column(String, nullable=True)
```

#### 3. Fixed Initialization Order (lines 185-189)
**Critical: session must exist before create_all() calls get_db_session()**
```python
def __init__(self, metadata_db_url):
    self.metadata_db_url = metadata_db_url
    self.engine = create_engine(self.metadata_db_url, echo=False)
    self.session = scoped_session(sessionmaker(bind=self.engine))  # MOVED BEFORE create_all()
    self.create_all()
    LOGGER.info(f"Created Metadata instance using database engine: {self.metadata_db_url}")
```

#### 4. Updated create_all() (lines 194-198)
```python
def create_all(self):
    # This method should be overriden by subclasses to create all necessary tables
    Base.metadata.create_all(self.engine)
    # Sync connection configs from environment to database
    self.sync_connection_configs()
```

#### 5. Added sync_connection_configs() Method (lines 200-300)
```python
def sync_connection_configs(self):
    """
    Sync connection configurations from BOND_MCP_CONFIG environment variable to database.

    This ensures that connection_configs table is populated with the latest config,
    which is required for foreign key constraints in connection_oauth_states.
    """
    try:
        # Get MCP config from environment
        mcp_config_str = os.getenv('BOND_MCP_CONFIG', '{}')
        if not mcp_config_str or mcp_config_str == '{}':
            LOGGER.debug("No BOND_MCP_CONFIG found, skipping connection config sync")
            return

        mcp_config = json.loads(mcp_config_str)
        servers = mcp_config.get('mcpServers', {})

        if not servers:
            LOGGER.debug("No MCP servers in config, skipping connection config sync")
            return

        session = self.get_db_session()
        synced_count = 0

        for name, server_config in servers.items():
            auth_type = server_config.get('auth_type', 'bond_jwt')

            # Only sync OAuth2 connections (those requiring user authorization)
            if auth_type != 'oauth2':
                continue

            # Check if connection already exists
            existing = session.query(ConnectionConfig).filter(
                ConnectionConfig.name == name
            ).first()

            if existing:
                # Update existing connection config with latest values
                try:
                    existing.display_name = server_config.get('display_name', name.title())
                    existing.description = server_config.get('description', f"Connect to {name}")
                    existing.url = server_config.get('url', '')
                    existing.transport = server_config.get('transport', 'sse')
                    oauth_config = server_config.get('oauth_config', {})
                    existing.oauth_client_id = oauth_config.get('client_id')
                    existing.oauth_authorize_url = oauth_config.get('authorize_url')
                    existing.oauth_token_url = oauth_config.get('token_url')
                    existing.oauth_redirect_uri = oauth_config.get('redirect_uri')
                    existing.oauth_scopes = oauth_config.get('scopes')
                    existing.icon_url = server_config.get('icon_url')
                    existing.updated_at = datetime.datetime.now()
                    synced_count += 1
                    LOGGER.info(f"Updated connection config for '{name}' in database")
                except Exception as update_error:
                    LOGGER.warning(f"Could not update existing connection '{name}': {update_error}. Schema may need migration.")
                    session.rollback()
                continue

            # Extract OAuth configuration
            oauth_config = server_config.get('oauth_config', {})
            extra_config = {}

            # Copy non-OAuth fields to extra_config
            for key in ['cloud_id', 'site_url']:
                if key in server_config:
                    extra_config[key] = server_config[key]

            # Create new connection config
            config = ConnectionConfig(
                id=str(uuid.uuid4()),
                name=name,
                display_name=server_config.get('display_name', name.title()),
                description=server_config.get('description', f"Connect to {name}"),
                url=server_config.get('url', ''),
                transport=server_config.get('transport', 'sse'),
                auth_type=auth_type,
                oauth_client_id=oauth_config.get('client_id'),
                oauth_authorize_url=oauth_config.get('authorize_url'),
                oauth_token_url=oauth_config.get('token_url'),
                oauth_redirect_uri=oauth_config.get('redirect_uri'),
                oauth_scopes=oauth_config.get('scopes'),
                icon_url=server_config.get('icon_url'),
                extra_config=extra_config,
                enabled=True,
                created_at=datetime.datetime.now(),
                updated_at=datetime.datetime.now()
            )

            session.add(config)
            synced_count += 1
            LOGGER.info(f"Synced connection config for '{name}' to database")

        if synced_count > 0:
            session.commit()
            LOGGER.info(f"Successfully synced {synced_count} connection config(s) to database")

        session.close()

    except Exception as e:
        LOGGER.error(f"Error syncing connection configs to database: {e}")
        # Don't raise - this is non-critical initialization
```

### bondable/bond/providers/bedrock/BedrockMetadata.py

#### Fixed create_all() Override (lines 90-93)
```python
def create_all(self):
    """Create all tables including Bedrock-specific ones"""
    super().create_all()  # CHANGED: Now calls parent which includes sync
    LOGGER.info("Created all Bedrock metadata tables")
```

---

## Known Issues to Address When Reapplying

### 1. Schema Migration Problem
**Issue:** Adding `oauth_redirect_uri` column to model doesn't add it to existing database tables.

**Solutions to Consider:**
- Use Alembic for proper migrations
- Add `ALTER TABLE` capability with version checking
- Accept that first deployment after reapply will fail UPDATE logic (non-blocking with error handling)
- Consider removing the UPDATE logic entirely (only CREATE new records)

### 2. Foreign Key Constraint Brittleness
**Architecture Question:** Should we remove foreign key constraints and use runtime validation instead?

**Current Design:**
```python
connection_name = Column(String, ForeignKey('connection_configs.name'), nullable=False)
```

**Proposed Alternative:**
```python
connection_name = Column(String, nullable=False)  # No FK constraint
# Then validate at runtime:
if connection_name not in mcp_config['mcpServers']:
    raise ValueError(f"Unknown connection: {connection_name}")
```

**Benefits of Removing FK:**
- No startup failures from sync issues
- Configuration is always source of truth
- Simpler, more resilient design
- Easy to add new connections without DB migration

**To Discuss:** Should we make this architectural change when reapplying?

### 3. Error Handling in UPDATE Logic
The UPDATE logic has try/except to handle missing columns:
```python
try:
    existing.oauth_redirect_uri = oauth_config.get('redirect_uri')
    # ... other fields ...
except Exception as update_error:
    LOGGER.warning(f"Could not update existing connection '{name}': {update_error}. Schema may need migration.")
    session.rollback()
```

This prevents startup failures but means schema changes won't take effect until column is manually added.

---

## Reapplication Strategy

### Option A: Apply Exactly As-Is (Risky)
1. Merge upstream changes
2. Reapply patch: `git apply /tmp/metadata-oauth-sync-changes.patch`
3. Deploy and accept that UPDATE logic will fail once
4. Manually add column to database or wait for recreation

### Option B: Apply With Architectural Changes (Recommended)
1. Merge upstream changes
2. Reapply patch manually
3. **Remove foreign key constraints** from:
   - `UserConnectionToken.connection_name`
   - `ConnectionOAuthState.connection_name`
4. **Add runtime validation** in connection endpoints
5. **Make sync fully optional** (warn but never block)
6. Deploy and test

### Option C: Apply With Migration Strategy
1. Merge upstream changes
2. Set up Alembic for database migrations
3. Reapply changes with proper migration for new column
4. Deploy with migration system in place

---

## Testing After Reapplication

1. **Fresh Database Test** - Deploy to new environment, verify sync creates records
2. **Existing Database Test** - Deploy to agent-space, verify graceful handling of missing column
3. **OAuth Flow Test** - Complete Atlassian OAuth end-to-end
4. **Restart Test** - Verify backend doesn't break on restart

---

## Files to Review After Merge

Before reapplying these changes, check if upstream has made changes to:
- `bondable/bond/providers/metadata.py` - Especially ConnectionConfig model
- `bondable/bond/providers/bedrock/BedrockMetadata.py` - create_all() method
- Connection-related endpoints in `bondable/rest/routers/connections.py`

---

## Related Documentation

- **DEPLOYMENT_PLAN_AGENT_SPACE.md** - Session 2 section documents all the issues and lessons learned
- **/tmp/metadata-oauth-sync-changes.patch** - Git patch file with exact diff
- **MCP_ATLASSIAN_DEPLOYMENT.md** - Original OAuth deployment guide

---

## Questions for Discussion

1. Should we remove foreign key constraints for more resilient design?
2. Do we want to set up Alembic for proper migrations?
3. Should sync logic UPDATE existing records or only CREATE new ones?
4. Can we simplify by removing ConnectionConfig table entirely?

---

**Remember:** These changes fixed real bugs but introduced schema migration complexity. Consider architectural improvements when reapplying.
