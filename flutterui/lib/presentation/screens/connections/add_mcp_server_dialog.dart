import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../data/models/user_mcp_server_model.dart';

/// Full-screen page for adding or editing a user-defined MCP server configuration.
/// Supports both a structured form and raw JSON import.
class AddMcpServerPage extends StatefulWidget {
  final UserMcpServerModel? existingServer;

  const AddMcpServerPage({super.key, this.existingServer});

  @override
  State<AddMcpServerPage> createState() => _AddMcpServerPageState();
}

class _AddMcpServerPageState extends State<AddMcpServerPage> with SingleTickerProviderStateMixin {
  late final TabController _tabController;
  final _formKey = GlobalKey<FormState>();

  // Form fields
  late final TextEditingController _displayNameController;
  late final TextEditingController _serverNameController;
  late final TextEditingController _descriptionController;
  late final TextEditingController _urlController;
  late String _transport;
  late String _authType;

  // Header auth
  final List<MapEntry<TextEditingController, TextEditingController>> _headerEntries = [];

  // OAuth fields
  late final TextEditingController _clientIdController;
  late final TextEditingController _clientSecretController;
  late final TextEditingController _authorizeUrlController;
  late final TextEditingController _tokenUrlController;
  late final TextEditingController _scopesController;
  late final TextEditingController _redirectUriController;
  late final TextEditingController _providerController;

  // Extra config
  late final TextEditingController _cloudIdController;
  late final TextEditingController _siteUrlController;

  // JSON import
  late final TextEditingController _jsonController;
  String? _jsonError;

  bool get _isEditing => widget.existingServer != null;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    final s = widget.existingServer;

    _displayNameController = TextEditingController(text: s?.displayName ?? '');
    _serverNameController = TextEditingController(text: s?.serverName ?? '');
    _descriptionController = TextEditingController(text: s?.description ?? '');
    _urlController = TextEditingController(text: s?.url ?? '');
    _transport = s?.transport ?? 'streamable-http';
    _authType = s?.authType ?? 'none';

    _clientIdController = TextEditingController(text: s?.oauthConfig?.clientId ?? '');
    _clientSecretController = TextEditingController();
    _authorizeUrlController = TextEditingController(text: s?.oauthConfig?.authorizeUrl ?? '');
    _tokenUrlController = TextEditingController(text: s?.oauthConfig?.tokenUrl ?? '');
    _scopesController = TextEditingController(text: s?.oauthConfig?.scopes ?? '');
    _redirectUriController = TextEditingController(text: s?.oauthConfig?.redirectUri ?? '');
    _providerController = TextEditingController(text: s?.oauthConfig?.provider ?? '');

    _cloudIdController = TextEditingController(text: s?.extraConfig?['cloud_id']?.toString() ?? '');
    _siteUrlController = TextEditingController(text: s?.extraConfig?['site_url']?.toString() ?? '');

    _jsonController = TextEditingController();

    // Pre-populate JSON tab when editing
    if (_isEditing && s != null) {
      final config = <String, dynamic>{
        'url': s.url,
        'transport': s.transport,
        'display_name': s.displayName,
      };
      if (s.description != null) config['description'] = s.description;
      if (s.authType != 'none') config['auth_type'] = s.authType;
      if (s.oauthConfig != null) {
        config['oauth_config'] = s.oauthConfig!.toJson();
      }
      if (s.extraConfig != null) {
        for (final entry in s.extraConfig!.entries) {
          config[entry.key] = entry.value;
        }
      }
      final fullJson = {s.serverName: config};
      _jsonController.text = const JsonEncoder.withIndent('  ').convert(fullJson);
    }

    if (!_isEditing) {
      _displayNameController.addListener(_autoGenerateServerName);
    }
  }

  void _autoGenerateServerName() {
    final display = _displayNameController.text;
    final slug = display
        .toLowerCase()
        .replaceAll(RegExp(r'[^a-z0-9]+'), '_')
        .replaceAll(RegExp(r'^_+|_+$'), '');
    if (slug.isNotEmpty && RegExp(r'^[a-z]').hasMatch(slug)) {
      _serverNameController.text = slug.length > 64 ? slug.substring(0, 64) : slug;
    }
  }

  @override
  void dispose() {
    _tabController.dispose();
    if (!_isEditing) _displayNameController.removeListener(_autoGenerateServerName);
    _displayNameController.dispose();
    _serverNameController.dispose();
    _descriptionController.dispose();
    _urlController.dispose();
    _clientIdController.dispose();
    _clientSecretController.dispose();
    _authorizeUrlController.dispose();
    _tokenUrlController.dispose();
    _scopesController.dispose();
    _redirectUriController.dispose();
    _providerController.dispose();
    _cloudIdController.dispose();
    _siteUrlController.dispose();
    _jsonController.dispose();
    for (final entry in _headerEntries) {
      entry.key.dispose();
      entry.value.dispose();
    }
    super.dispose();
  }

  void _addHeaderEntry() {
    setState(() {
      _headerEntries.add(MapEntry(TextEditingController(), TextEditingController()));
    });
  }

  void _removeHeaderEntry(int index) {
    setState(() {
      _headerEntries[index].key.dispose();
      _headerEntries[index].value.dispose();
      _headerEntries.removeAt(index);
    });
  }

  Map<String, dynamic>? _buildFormResult() {
    if (!_formKey.currentState!.validate()) return null;

    final result = <String, dynamic>{
      'server_name': _serverNameController.text.trim(),
      'display_name': _displayNameController.text.trim(),
      'url': _urlController.text.trim(),
      'transport': _transport,
      'auth_type': _authType,
    };

    final desc = _descriptionController.text.trim();
    if (desc.isNotEmpty) result['description'] = desc;

    if (_authType == 'header') {
      final headers = <String, String>{};
      for (final entry in _headerEntries) {
        final key = entry.key.text.trim();
        final value = entry.value.text.trim();
        if (key.isNotEmpty && value.isNotEmpty) {
          headers[key] = value;
        }
      }
      if (headers.isNotEmpty) result['headers'] = headers;
    }

    if (_authType == 'oauth2') {
      result['oauth_config'] = {
        'client_id': _clientIdController.text.trim(),
        'client_secret': _clientSecretController.text.trim(),
        'authorize_url': _authorizeUrlController.text.trim(),
        'token_url': _tokenUrlController.text.trim(),
        if (_scopesController.text.trim().isNotEmpty)
          'scopes': _scopesController.text.trim(),
        'redirect_uri': _redirectUriController.text.trim(),
        if (_providerController.text.trim().isNotEmpty)
          'provider': _providerController.text.trim(),
      };
    }

    final extraConfig = <String, dynamic>{};
    if (_cloudIdController.text.trim().isNotEmpty) {
      extraConfig['cloud_id'] = _cloudIdController.text.trim();
    }
    if (_siteUrlController.text.trim().isNotEmpty) {
      extraConfig['site_url'] = _siteUrlController.text.trim();
    }
    if (extraConfig.isNotEmpty) result['extra_config'] = extraConfig;

    return result;
  }

  /// Parse JSON in any of these formats:
  /// 1. {"server_name": "x", "config": {...}}  — full import format
  /// 2. {"url": "...", ...}                     — raw config object
  /// 3. "my_server": {"url": "...", ...}        — BOND_MCP_CONFIG entry (not valid JSON alone)
  Map<String, dynamic>? _buildJsonImportResult() {
    var text = _jsonController.text.trim();
    if (text.isEmpty) {
      setState(() => _jsonError = 'Please paste a JSON configuration');
      return null;
    }

    // Format 3: "server_name": { ... } — wrap in braces to make valid JSON
    if (text.startsWith('"') && !text.startsWith('{')) {
      text = '{$text}';
    }

    try {
      final parsed = json.decode(text) as Map<String, dynamic>;

      // Format 1: {"server_name": "x", "config": {...}}
      if (parsed.containsKey('config') && parsed.containsKey('server_name')) {
        setState(() => _jsonError = null);
        return {'_import': true, ...parsed};
      }

      // Format 2: {"url": "...", ...} — raw config, infer server name
      if (parsed.containsKey('url')) {
        final serverName = _inferServerName(parsed);
        setState(() => _jsonError = null);
        return {'_import': true, 'server_name': serverName, 'config': parsed};
      }

      // Format 3 (after wrapping): {"my_server": {"url": "...", ...}}
      // Single key whose value is a map with "url"
      if (parsed.length == 1) {
        final entry = parsed.entries.first;
        if (entry.value is Map<String, dynamic>) {
          final config = entry.value as Map<String, dynamic>;
          if (config.containsKey('url')) {
            final serverName = _sanitizeServerName(entry.key);
            setState(() => _jsonError = null);
            return {'_import': true, 'server_name': serverName, 'config': config};
          }
        }
      }

      setState(() => _jsonError =
          'Could not parse config. Supported formats:\n'
          '  "name": { "url": "..." }  (from BOND_MCP_CONFIG)\n'
          '  { "url": "..." }  (raw config)\n'
          '  { "server_name": "...", "config": { "url": "..." } }');
      return null;
    } catch (e) {
      setState(() => _jsonError = 'Invalid JSON: $e');
      return null;
    }
  }

  String _inferServerName(Map<String, dynamic> config) {
    final displayName = config['display_name'] as String? ?? 'imported';
    return _sanitizeServerName(displayName);
  }

  String _sanitizeServerName(String name) {
    final slug = name
        .toLowerCase()
        .replaceAll(RegExp(r'[^a-z0-9]+'), '_')
        .replaceAll(RegExp(r'^_+|_+$'), '');
    if (slug.isNotEmpty && RegExp(r'^[a-z]').hasMatch(slug)) {
      return slug.length > 64 ? slug.substring(0, 64) : slug;
    }
    return 'imported_server';
  }

  void _onSave() {
    if (_isEditing || _tabController.index == 0) {
      final result = _buildFormResult();
      if (result != null) Navigator.of(context).pop(result);
    } else {
      final result = _buildJsonImportResult();
      if (result != null) Navigator.of(context).pop(result);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Scaffold(
      backgroundColor: colorScheme.surface,
      appBar: AppBar(
        title: Text(_isEditing ? 'Edit MCP Server' : 'Add MCP Server',
          style: theme.textTheme.titleLarge?.copyWith(
            color: colorScheme.onSurface, fontWeight: FontWeight.bold)),
        backgroundColor: colorScheme.surface,
        foregroundColor: colorScheme.onSurface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back, color: colorScheme.onSurface),
          onPressed: () => Navigator.of(context).pop(),
        ),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(48),
          child: Container(
            decoration: BoxDecoration(
              border: Border(bottom: BorderSide(color: colorScheme.outlineVariant)),
            ),
            child: TabBar(
              controller: _tabController,
              labelColor: colorScheme.primary,
              unselectedLabelColor: colorScheme.onSurfaceVariant,
              indicatorColor: colorScheme.primary,
              indicatorWeight: 3,
              labelStyle: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w600),
              tabs: [
                const Tab(text: 'Form'),
                Tab(text: _isEditing ? 'JSON' : 'Import JSON'),
              ],
            ),
          ),
        ),
      ),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('Cancel'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                flex: 2,
                child: FilledButton(
                  onPressed: _onSave,
                  child: Text(_isEditing ? 'Save Changes' : 'Save'),
                ),
              ),
            ],
          ),
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildFormTab(),
          _buildJsonTab(),
        ],
      ),
    );
  }

  Widget _buildFormTab() {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Basic Information',
                style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold, color: colorScheme.onSurface)),
            const SizedBox(height: 16),
            TextFormField(
              controller: _displayNameController,
              decoration: const InputDecoration(
                labelText: 'Display Name',
                hintText: 'My Custom Server',
                border: OutlineInputBorder(),
              ),
              validator: (v) => v == null || v.trim().isEmpty ? 'Required' : null,
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _serverNameController,
              decoration: const InputDecoration(
                labelText: 'Server Name (identifier)',
                hintText: 'my_custom_server',
                helperText: 'Lowercase letters, digits, underscores. Starts with letter.',
                border: OutlineInputBorder(),
              ),
              enabled: !_isEditing,
              validator: (v) {
                if (v == null || v.trim().isEmpty) return 'Required';
                if (!RegExp(r'^[a-z][a-z0-9_]{0,63}$').hasMatch(v.trim())) {
                  return 'Must start with lowercase letter, only a-z, 0-9, _';
                }
                return null;
              },
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _descriptionController,
              decoration: const InputDecoration(
                labelText: 'Description (optional)',
                hintText: 'What does this server provide?',
                border: OutlineInputBorder(),
              ),
              maxLines: 2,
            ),

            const SizedBox(height: 32),
            Text('Connection',
                style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold, color: colorScheme.onSurface)),
            const SizedBox(height: 16),
            TextFormField(
              controller: _urlController,
              decoration: const InputDecoration(
                labelText: 'Server URL',
                hintText: 'http://localhost:5555/mcp',
                border: OutlineInputBorder(),
              ),
              validator: (v) {
                if (v == null || v.trim().isEmpty) return 'Required';
                final uri = Uri.tryParse(v.trim());
                if (uri == null || !uri.hasScheme || !uri.hasAuthority) return 'Must be a valid URL';
                return null;
              },
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              value: _transport,
              decoration: const InputDecoration(labelText: 'Transport', border: OutlineInputBorder()),
              items: const [
                DropdownMenuItem(value: 'streamable-http', child: Text('Streamable HTTP')),
                DropdownMenuItem(value: 'sse', child: Text('SSE')),
              ],
              onChanged: (v) => setState(() => _transport = v!),
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              value: _authType,
              decoration: const InputDecoration(labelText: 'Auth Type', border: OutlineInputBorder()),
              items: const [
                DropdownMenuItem(value: 'none', child: Text('None')),
                DropdownMenuItem(value: 'header', child: Text('Header (API Key)')),
                DropdownMenuItem(value: 'oauth2', child: Text('OAuth2')),
              ],
              onChanged: (v) => setState(() => _authType = v!),
            ),

            // Header auth
            if (_authType == 'header') ...[
              const SizedBox(height: 32),
              Text('Headers',
                  style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold, color: colorScheme.onSurface)),
              const SizedBox(height: 8),
              ..._headerEntries.asMap().entries.map((e) {
                final idx = e.key;
                final entry = e.value;
                return Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Row(
                    children: [
                      Expanded(
                        child: TextFormField(
                          controller: entry.key,
                          decoration: const InputDecoration(labelText: 'Header Name', border: OutlineInputBorder(), isDense: true),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: TextFormField(
                          controller: entry.value,
                          decoration: const InputDecoration(labelText: 'Value', border: OutlineInputBorder(), isDense: true),
                          obscureText: true,
                        ),
                      ),
                      const SizedBox(width: 4),
                      IconButton(
                        icon: Icon(Icons.remove_circle_outline, size: 20, color: colorScheme.error),
                        onPressed: () => _removeHeaderEntry(idx),
                      ),
                    ],
                  ),
                );
              }),
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  onPressed: _addHeaderEntry,
                  icon: const Icon(Icons.add, size: 18),
                  label: const Text('Add Header'),
                ),
              ),
            ],

            // OAuth2
            if (_authType == 'oauth2') ...[
              const SizedBox(height: 32),
              Text('OAuth2 Configuration',
                  style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.bold, color: colorScheme.onSurface)),
              const SizedBox(height: 16),
              TextFormField(
                controller: _providerController,
                decoration: const InputDecoration(
                  labelText: 'Provider (optional)',
                  hintText: 'e.g., atlassian, microsoft, github',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _clientIdController,
                decoration: const InputDecoration(labelText: 'Client ID', border: OutlineInputBorder()),
                validator: (v) => _authType == 'oauth2' && (v == null || v.trim().isEmpty) ? 'Required' : null,
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _clientSecretController,
                decoration: InputDecoration(
                  labelText: 'Client Secret',
                  hintText: _isEditing ? '(leave empty to keep existing)' : null,
                  border: const OutlineInputBorder(),
                ),
                obscureText: true,
                validator: (v) {
                  if (_authType == 'oauth2' && !_isEditing && (v == null || v.trim().isEmpty)) return 'Required';
                  return null;
                },
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _authorizeUrlController,
                decoration: const InputDecoration(
                  labelText: 'Authorize URL',
                  hintText: 'https://auth.example.com/authorize',
                  border: OutlineInputBorder(),
                ),
                validator: (v) => _authType == 'oauth2' && (v == null || v.trim().isEmpty) ? 'Required' : null,
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _tokenUrlController,
                decoration: const InputDecoration(
                  labelText: 'Token URL',
                  hintText: 'https://auth.example.com/oauth/token',
                  border: OutlineInputBorder(),
                ),
                validator: (v) => _authType == 'oauth2' && (v == null || v.trim().isEmpty) ? 'Required' : null,
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _scopesController,
                decoration: const InputDecoration(
                  labelText: 'Scopes (optional)',
                  hintText: 'read write offline_access',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _redirectUriController,
                decoration: const InputDecoration(
                  labelText: 'Redirect URI',
                  hintText: 'http://localhost:8000/connections/{name}/callback',
                  border: OutlineInputBorder(),
                ),
                validator: (v) => _authType == 'oauth2' && (v == null || v.trim().isEmpty) ? 'Required' : null,
              ),
            ],

            // Extra config
            const SizedBox(height: 32),
            Text('Extra Configuration',
                style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold, color: colorScheme.onSurface)),
            const SizedBox(height: 8),
            Text('Optional provider-specific fields.',
                style: theme.textTheme.bodySmall?.copyWith(color: colorScheme.onSurfaceVariant)),
            const SizedBox(height: 16),
            TextFormField(
              controller: _cloudIdController,
              decoration: const InputDecoration(
                labelText: 'Cloud ID (optional)',
                hintText: 'e.g., Atlassian Cloud ID',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _siteUrlController,
              decoration: const InputDecoration(
                labelText: 'Site URL (optional)',
                hintText: 'e.g., https://your-site.atlassian.net',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 80), // Bottom padding for save button
          ],
        ),
      ),
    );
  }

  Widget _buildJsonTab() {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(_isEditing ? 'JSON Configuration' : 'Import from JSON',
              style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold, color: colorScheme.onSurface)),
          const SizedBox(height: 8),
          Text(
            _isEditing
                ? 'View or edit the server configuration as JSON. Note: client_secret is not shown for security. Use the Export button on the server list for a full backup including secrets.'
                : 'Paste a server entry directly from BOND_MCP_CONFIG, or a standalone JSON config object.',
            style: theme.textTheme.bodyMedium?.copyWith(color: colorScheme.onSurfaceVariant),
          ),
          const SizedBox(height: 16),

          // Example card (only for new servers)
          if (!_isEditing) Card(
            elevation: 0,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(8),
              side: BorderSide(color: colorScheme.outlineVariant),
            ),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('Example', style: theme.textTheme.labelLarge?.copyWith(fontWeight: FontWeight.bold)),
                      IconButton(
                        icon: const Icon(Icons.copy, size: 18),
                        tooltip: 'Copy example',
                        onPressed: () {
                          Clipboard.setData(const ClipboardData(text: _exampleJson));
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Example copied to clipboard')),
                          );
                        },
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    _exampleJson,
                    style: theme.textTheme.bodySmall?.copyWith(
                      fontFamily: 'monospace',
                      color: colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 20),

          TextFormField(
            controller: _jsonController,
            decoration: InputDecoration(
              labelText: 'JSON Configuration',
              hintText: 'Paste your JSON config here...',
              alignLabelWithHint: true,
              errorText: _jsonError,
              border: const OutlineInputBorder(),
            ),
            maxLines: 15,
            style: theme.textTheme.bodySmall?.copyWith(fontFamily: 'monospace'),
          ),
          const SizedBox(height: 80), // Bottom padding for save button
        ],
      ),
    );
  }
}

const _exampleJson = '''"my_server": {
  "url": "http://localhost:5557/mcp",
  "transport": "streamable-http",
  "display_name": "My Service",
  "description": "Connect to my service"
}''';
