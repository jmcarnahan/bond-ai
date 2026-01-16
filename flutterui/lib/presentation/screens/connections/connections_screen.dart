import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../providers/connections_provider.dart';
import '../../../data/models/connection_model.dart';
import '../../widgets/app_drawer.dart';

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
  }

  void _showErrorMessage(String connectionName, String? error) {
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
        title: const Text('Connections'),
        backgroundColor: colorScheme.surface,
        surfaceTintColor: Colors.transparent,
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
          ],
        ),
      ),
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
    } else if (!connection.valid) {
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
