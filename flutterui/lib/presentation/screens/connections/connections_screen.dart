import 'dart:convert';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../providers/connections_provider.dart';
import '../../../data/models/connection_model.dart';
import '../../../data/models/user_mcp_server_model.dart';
import '../../../data/services/user_mcp_server_service.dart';
import '../../../providers/services/service_providers.dart';
import '../../widgets/app_drawer.dart';
import 'add_mcp_server_dialog.dart';

// Conditional import for web-specific functionality
import 'connections_web_utils_stub.dart'
    if (dart.library.html) 'connections_web_utils.dart' as web_utils;

class ConnectionsScreen extends ConsumerStatefulWidget {
  static const String routeName = '/connections';

  const ConnectionsScreen({super.key});

  @override
  ConsumerState<ConnectionsScreen> createState() => _ConnectionsScreenState();
}

class _ConnectionsScreenState extends ConsumerState<ConnectionsScreen> {
  String? _successConnection;
  String? _errorConnection;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();

    // Check for OAuth callback query parameters (web only)
    if (kIsWeb) {
      final params = web_utils.getCurrentQueryParams();
      _successConnection = params['connection_success'];
      _errorConnection = params['connection_error'];
      _errorMessage = params['error'];

      // Clear query params from URL to prevent showing message on refresh
      if (_successConnection != null || _errorConnection != null) {
        web_utils.clearQueryParams();
      }
    }

    // Load connections when screen initializes
    Future.microtask(() {
      ref.read(connectionsNotifierProvider.notifier).loadConnections();

      // Show success/error message after connections load
      if (_successConnection != null) {
        _showSuccessMessage(_successConnection!);
      } else if (_errorConnection != null) {
        _showErrorMessage(_errorConnection!, _errorMessage);
      }
    });
  }

  void _showSuccessMessage(String connectionName) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: [
              const Icon(Icons.check_circle, color: Colors.white),
              const SizedBox(width: 8),
              Expanded(
                child: Text('Successfully connected to $connectionName!'),
              ),
            ],
          ),
          backgroundColor: Colors.green,
          duration: const Duration(seconds: 4),
        ),
      );
    });
  }

  void _showErrorMessage(String connectionName, String? error) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: [
              const Icon(Icons.error, color: Colors.white),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Failed to connect to $connectionName${error != null ? ': $error' : ''}',
                ),
              ),
            ],
          ),
          backgroundColor: Colors.red,
          duration: const Duration(seconds: 5),
        ),
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final connectionsState = ref.watch(connectionsNotifierProvider);
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final textTheme = theme.textTheme;

    return Scaffold(
      backgroundColor: colorScheme.surface,
      drawer: const AppDrawer(),
      appBar: AppBar(
        title: Text('Connections', style: textTheme.titleLarge?.copyWith(
          color: colorScheme.onSurface, fontWeight: FontWeight.bold)),
        backgroundColor: colorScheme.surface,
        foregroundColor: colorScheme.onSurface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        iconTheme: IconThemeData(color: colorScheme.onSurface),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header description
            Text(
              'External Services',
              style: textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Connect external services to enhance your AI assistant with additional capabilities. '
              'These connections allow the assistant to access and interact with your data in external systems.',
              style: textTheme.bodyMedium?.copyWith(
                color: colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 24),

            // Connections list
            _ConnectionsCard(
              connections: connectionsState.connections,
              isLoading: connectionsState.isLoading,
              error: connectionsState.error,
              onConnect: (connectionName) async {
                // Get OAuth authorization URL
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Starting OAuth flow...'),
                    duration: Duration(seconds: 1),
                  ),
                );

                final url = await ref
                    .read(connectionsNotifierProvider.notifier)
                    .getAuthorizationUrl(connectionName);

                if (!context.mounted) return;

                if (url != null) {
                  if (kIsWeb) {
                    // On web: navigate in the same window
                    // User will be redirected back after OAuth completes
                    web_utils.navigateSameWindow(url);
                  } else {
                    // On mobile: open external browser (deep links handle return)
                    final uri = Uri.parse(url);
                    if (await canLaunchUrl(uri)) {
                      await launchUrl(uri, mode: LaunchMode.externalApplication);

                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Opening browser for authentication...'),
                            backgroundColor: Colors.blue,
                            duration: Duration(seconds: 3),
                          ),
                        );
                      }
                    } else {
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Could not open browser. Please try again.'),
                            backgroundColor: Colors.red,
                            duration: Duration(seconds: 3),
                          ),
                        );
                      }
                    }
                  }
                } else {
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('Failed to get authorization URL. Please try again.'),
                        backgroundColor: Colors.red,
                        duration: Duration(seconds: 3),
                      ),
                    );
                  }
                }
              },
              onDisconnect: (connectionName) async {
                final confirmed = await showDialog<bool>(
                  context: context,
                  builder: (context) => AlertDialog(
                    title: const Text('Disconnect'),
                    content: Text('Are you sure you want to disconnect from $connectionName?'),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.of(context).pop(false),
                        child: const Text('Cancel'),
                      ),
                      TextButton(
                        onPressed: () => Navigator.of(context).pop(true),
                        child: const Text('Disconnect'),
                      ),
                    ],
                  ),
                );
                if (confirmed == true) {
                  await ref
                      .read(connectionsNotifierProvider.notifier)
                      .disconnect(connectionName);
                }
              },
              onRefresh: () {
                ref.read(connectionsNotifierProvider.notifier).loadConnections();
              },
            ),

            const SizedBox(height: 32),

            // My MCP Servers section
            _MyMcpServersSection(
              onServersChanged: () {
                // Refresh connections list when user servers change
                ref.read(connectionsNotifierProvider.notifier).loadConnections();
              },
            ),
          ],
        ),
      ),
    );
  }
}

/// Section for managing user-defined MCP server configurations
class _MyMcpServersSection extends ConsumerStatefulWidget {
  final VoidCallback onServersChanged;

  const _MyMcpServersSection({required this.onServersChanged});

  @override
  ConsumerState<_MyMcpServersSection> createState() => _MyMcpServersSectionState();
}

class _MyMcpServersSectionState extends ConsumerState<_MyMcpServersSection> {
  List<UserMcpServerModel>? _servers;
  bool _isLoading = true;
  String? _error;

  UserMcpServerService get _service => ref.read(userMcpServerServiceProvider);

  @override
  void initState() {
    super.initState();
    Future.microtask(() => _loadServers());
  }

  Future<void> _loadServers() async {
    setState(() { _isLoading = true; _error = null; });
    try {
      final response = await _service.listServers();
      if (mounted) {
        setState(() { _servers = response.servers; _isLoading = false; });
      }
    } catch (e) {
      if (mounted) {
        // Show empty state with a subtle error hint — don't block the UI
        // (common cause: table not yet created after migration)
        final errorStr = e.toString();
        final isServerError = errorStr.contains('500') || errorStr.contains('502');
        setState(() {
          _servers = [];
          _error = isServerError ? null : errorStr; // Only show non-server errors
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _addServer() async {
    final result = await Navigator.of(context).push<Map<String, dynamic>>(
      MaterialPageRoute(builder: (_) => const AddMcpServerPage()),
    );
    if (result == null) return;

    try {
      // Check if this is a JSON import
      if (result.containsKey('_import')) {
        await _service.importServer(
          serverName: result['server_name'] as String,
          config: Map<String, dynamic>.from(result['config'] as Map),
        );
      } else {
        await _service.createServer(
          serverName: result['server_name'],
          displayName: result['display_name'],
          description: result['description'],
          url: result['url'],
          transport: result['transport'] ?? 'streamable-http',
          authType: result['auth_type'] ?? 'none',
          headers: result['headers'] != null
              ? Map<String, String>.from(result['headers'])
              : null,
          oauthConfig: result['oauth_config'] != null
              ? Map<String, dynamic>.from(result['oauth_config'])
              : null,
          extraConfig: result['extra_config'] != null
              ? Map<String, dynamic>.from(result['extra_config'])
              : null,
        );
      }
      await _loadServers();
      widget.onServersChanged();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('MCP server added'), backgroundColor: Colors.green),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _editServer(UserMcpServerModel server) async {
    final result = await Navigator.of(context).push<Map<String, dynamic>>(
      MaterialPageRoute(builder: (_) => AddMcpServerPage(existingServer: server)),
    );
    if (result == null) return;

    try {
      if (result.containsKey('_import')) {
        // JSON tab edit: delete old server and re-import with updated config
        final config = Map<String, dynamic>.from(result['config'] as Map);
        final serverName = result['server_name'] as String? ?? server.serverName;
        await _service.deleteServer(server.id);
        await _service.importServer(serverName: serverName, config: config);
      } else {
        // Form tab edit: update individual fields
        await _service.updateServer(
          server.id,
          displayName: result['display_name'],
          description: result['description'],
          url: result['url'],
          transport: result['transport'],
          authType: result['auth_type'],
          headers: result['headers'] != null
              ? Map<String, String>.from(result['headers'])
              : null,
          oauthConfig: result['oauth_config'] != null
              ? Map<String, dynamic>.from(result['oauth_config'])
              : null,
          extraConfig: result['extra_config'] != null
              ? Map<String, dynamic>.from(result['extra_config'])
              : null,
        );
      }
      await _loadServers();
      widget.onServersChanged();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('MCP server updated'), backgroundColor: Colors.green),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _deleteServer(UserMcpServerModel server) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete MCP Server'),
        content: Text('Are you sure you want to delete "${server.displayName}"?'),
        actions: [
          TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.of(ctx).pop(true), child: const Text('Delete')),
        ],
      ),
    );
    if (confirmed != true) return;

    try {
      await _service.deleteServer(server.id);
      await _loadServers();
      widget.onServersChanged();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('MCP server deleted'), backgroundColor: Colors.green),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('$e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _testServer(UserMcpServerModel server) async {
    try {
      final result = await _service.testServer(server.id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(result.success
                ? 'Connected! Found ${result.toolCount} tools.'
                : 'Connection failed: ${result.error}'),
            backgroundColor: result.success ? Colors.green : Colors.red,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Test failed: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _exportServer(UserMcpServerModel server) async {
    try {
      final data = await _service.exportServer(server.id);
      final jsonStr = const JsonEncoder.withIndent('  ').convert(data);
      await Clipboard.setData(ClipboardData(text: jsonStr));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Config copied to clipboard'), backgroundColor: Colors.green),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Export failed: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final textTheme = theme.textTheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              'My MCP Servers',
              style: textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
            ),
            FilledButton.icon(
              onPressed: _addServer,
              icon: const Icon(Icons.add, size: 18),
              label: const Text('Add Server'),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Text(
          'Add your own MCP servers to use with your agents. These servers are personal to your account.',
          style: textTheme.bodyMedium?.copyWith(color: colorScheme.onSurfaceVariant),
        ),
        const SizedBox(height: 16),

        if (_isLoading)
          const Center(child: Padding(padding: EdgeInsets.all(16), child: CircularProgressIndicator())),

        if (_error != null)
          Card(
            color: colorScheme.errorContainer,
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Text('Error loading servers: $_error', style: TextStyle(color: colorScheme.onErrorContainer)),
            ),
          ),

        if (!_isLoading && _error == null && (_servers == null || _servers!.isEmpty))
          Card(
            elevation: 0,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: BorderSide(color: colorScheme.outlineVariant),
            ),
            child: Padding(
              padding: const EdgeInsets.all(32),
              child: Center(
                child: Column(
                  children: [
                    Icon(Icons.dns_outlined, size: 48, color: colorScheme.onSurfaceVariant),
                    const SizedBox(height: 8),
                    Text('No custom MCP servers yet',
                        style: textTheme.bodyLarge?.copyWith(color: colorScheme.onSurfaceVariant)),
                    const SizedBox(height: 4),
                    Text('Add a server to get started',
                        style: textTheme.bodySmall?.copyWith(color: colorScheme.onSurfaceVariant)),
                  ],
                ),
              ),
            ),
          ),

        if (!_isLoading && _servers != null && _servers!.isNotEmpty)
          Card(
            elevation: 0,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: BorderSide(color: colorScheme.outlineVariant),
            ),
            child: Column(
              children: _servers!.asMap().entries.map((e) {
                final idx = e.key;
                final server = e.value;
                return Column(
                  children: [
                    if (idx > 0) Divider(height: 1, color: colorScheme.outlineVariant),
                    ListTile(
                      leading: Icon(
                        server.authType == 'oauth2'
                            ? Icons.lock_outline
                            : server.authType == 'header'
                                ? Icons.key
                                : Icons.public,
                        color: colorScheme.primary,
                      ),
                      title: Text(server.displayName),
                      subtitle: Text(
                        '${server.url}\n${server.authType} | ${server.transport}',
                        style: textTheme.bodySmall,
                      ),
                      isThreeLine: true,
                      trailing: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          IconButton(
                            icon: const Icon(Icons.play_arrow, size: 20),
                            tooltip: 'Test connection',
                            onPressed: () => _testServer(server),
                          ),
                          IconButton(
                            icon: const Icon(Icons.download, size: 20),
                            tooltip: 'Export JSON',
                            onPressed: () => _exportServer(server),
                          ),
                          IconButton(
                            icon: const Icon(Icons.edit, size: 20),
                            tooltip: 'Edit',
                            onPressed: () => _editServer(server),
                          ),
                          IconButton(
                            icon: Icon(Icons.delete_outline, size: 20, color: colorScheme.error),
                            tooltip: 'Delete',
                            onPressed: () => _deleteServer(server),
                          ),
                        ],
                      ),
                    ),
                  ],
                );
              }).toList(),
            ),
          ),
      ],
    );
  }
}

class _ConnectionsCard extends StatelessWidget {
  final List<ConnectionStatus> connections;
  final bool isLoading;
  final String? error;
  final Function(String) onConnect;
  final Function(String) onDisconnect;
  final VoidCallback onRefresh;

  const _ConnectionsCard({
    required this.connections,
    required this.isLoading,
    this.error,
    required this.onConnect,
    required this.onDisconnect,
    required this.onRefresh,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final textTheme = theme.textTheme;

    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: colorScheme.outlineVariant,
          width: 1,
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Available Connections',
                  style: textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: colorScheme.onSurface,
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.refresh, size: 20),
                  onPressed: onRefresh,
                  tooltip: 'Refresh',
                  color: colorScheme.primary,
                ),
              ],
            ),
            const SizedBox(height: 16),
            if (isLoading)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(16.0),
                  child: CircularProgressIndicator(),
                ),
              )
            else if (error != null)
              Padding(
                padding: const EdgeInsets.all(16.0),
                child: Text(
                  'Error loading connections: $error',
                  style: textTheme.bodyMedium?.copyWith(
                    color: colorScheme.error,
                  ),
                ),
              )
            else if (connections.isEmpty)
              Padding(
                padding: const EdgeInsets.all(16.0),
                child: Text(
                  'No connections available. Configure MCP servers in the backend to enable connections.',
                  style: textTheme.bodyMedium?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                  ),
                ),
              )
            else
              ...connections.map((connection) => _ConnectionRow(
                    connection: connection,
                    onConnect: () => onConnect(connection.name),
                    onDisconnect: () => onDisconnect(connection.name),
                  )),
          ],
        ),
      ),
    );
  }
}

class _ConnectionRow extends StatelessWidget {
  final ConnectionStatus connection;
  final VoidCallback onConnect;
  final VoidCallback onDisconnect;

  const _ConnectionRow({
    required this.connection,
    required this.onConnect,
    required this.onDisconnect,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final textTheme = theme.textTheme;

    // Determine status color and icon
    Color statusColor;
    IconData statusIcon;
    String statusText;

    if (!connection.connected) {
      statusColor = colorScheme.onSurfaceVariant;
      statusIcon = Icons.link_off;
      statusText = 'Not Connected';
    } else if (!connection.valid && !connection.hasRefreshToken) {
      statusColor = colorScheme.error;
      statusIcon = Icons.warning;
      statusText = 'Expired';
    } else {
      statusColor = Colors.green;
      statusIcon = Icons.check_circle;
      statusText = 'Connected';
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      child: Row(
        children: [
          // Connection icon
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: colorScheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(
              Icons.extension,
              color: colorScheme.onSurfaceVariant,
              size: 24,
            ),
          ),
          const SizedBox(width: 16),
          // Connection info
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  connection.displayName,
                  style: textTheme.bodyLarge?.copyWith(
                    fontWeight: FontWeight.w500,
                  ),
                ),
                if (connection.description != null) ...[
                  const SizedBox(height: 2),
                  Text(
                    connection.description!,
                    style: textTheme.bodySmall?.copyWith(
                      color: colorScheme.onSurfaceVariant,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
                const SizedBox(height: 4),
                Row(
                  children: [
                    Icon(statusIcon, size: 14, color: statusColor),
                    const SizedBox(width: 4),
                    Text(
                      statusText,
                      style: textTheme.bodySmall?.copyWith(
                        color: statusColor,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          // Action buttons based on connection state
          if (connection.connected && connection.valid)
            // Connected and valid: show Disconnect
            OutlinedButton(
              onPressed: onDisconnect,
              style: OutlinedButton.styleFrom(
                foregroundColor: colorScheme.error,
                side: BorderSide(color: colorScheme.error.withValues(alpha: 0.5)),
              ),
              child: const Text('Disconnect'),
            )
          else if (connection.connected && !connection.valid)
            // Connected but expired: show Reconnect AND Clear Token
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Clear token button for debugging
                IconButton(
                  onPressed: onDisconnect,
                  icon: const Icon(Icons.delete_outline, size: 20),
                  tooltip: 'Clear expired token',
                  style: IconButton.styleFrom(
                    foregroundColor: colorScheme.error,
                  ),
                ),
                const SizedBox(width: 4),
                FilledButton(
                  onPressed: onConnect,
                  child: const Text('Reconnect'),
                ),
              ],
            )
          else
            // Not connected: show Connect
            FilledButton(
              onPressed: onConnect,
              child: const Text('Connect'),
            ),
        ],
      ),
    );
  }
}
