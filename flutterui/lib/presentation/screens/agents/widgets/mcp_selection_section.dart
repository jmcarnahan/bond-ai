import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/core/constants/app_constants.dart';
import 'package:flutterui/data/models/mcp_model.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import 'package:flutterui/core/utils/logger.dart';
import 'package:flutterui/presentation/widgets/common/bondai_widgets.dart';

class McpSelectionSection extends ConsumerStatefulWidget {
  final Set<String> selectedToolNames;
  final Set<String> selectedResourceUris;
  final bool enabled;
  final void Function(Set<String>) onToolsChanged;
  final void Function(Set<String>) onResourcesChanged;

  const McpSelectionSection({
    super.key,
    required this.selectedToolNames,
    required this.selectedResourceUris,
    required this.enabled,
    required this.onToolsChanged,
    required this.onResourcesChanged,
  });

  @override
  ConsumerState<McpSelectionSection> createState() =>
      _McpSelectionSectionState();
}

class _McpSelectionSectionState extends ConsumerState<McpSelectionSection> {
  McpToolsGroupedResponse? _groupedData;
  List<McpResourceModel>? _resources;
  Map<String, bool> _expandedServers = {};
  bool _isLoading = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadMcpData();
  }

  Future<void> _loadMcpData() async {
    if (_isLoading) {
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final mcpService = ref.read(mcpServiceProvider);
      logger.i('[McpSelectionSection] MCP service obtained, loading tools and resources...');

      final results = await Future.wait([
        mcpService.getToolsGrouped(),
        mcpService.getResources(),
      ]);

      logger.i('[McpSelectionSection] Both requests completed successfully');

      final grouped = results[0] as McpToolsGroupedResponse;
      final resources = results[1] as List<McpResourceModel>;

      // Auto-upgrade bare tool names to qualified format
      if (widget.selectedToolNames.isNotEmpty) {
        final upgraded = _upgradeToolNames(widget.selectedToolNames, grouped);
        if (upgraded.length != widget.selectedToolNames.length ||
            !upgraded.containsAll(widget.selectedToolNames)) {
          // Schedule the callback after build to avoid setState during build
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted) {
              widget.onToolsChanged(upgraded);
            }
          });
        }
      }

      // Initialize expanded state: expand servers that contain pre-selected tools
      final expandedServers = <String, bool>{};
      for (final server in grouped.servers) {
        final hasSelectedTools = server.tools.any(
          (tool) => _isToolSelected(server.serverName, tool.name),
        );
        expandedServers[server.serverName] = hasSelectedTools;
      }

      setState(() {
        _groupedData = grouped;
        _resources = resources;
        _expandedServers = expandedServers;
        _isLoading = false;
      });

      // Log server details
      logger.i('[McpSelectionSection] Loaded ${grouped.totalServers} servers with ${grouped.totalTools} tools and ${resources.length} resources');
      for (final server in grouped.servers) {
        final status = server.connectionStatus;
        logger.i(
          '[McpSelectionSection] Server "${server.displayName}": ${server.toolCount} tools, connected=${status.connected}, valid=${status.valid}',
        );
      }
    } catch (e) {
      logger.e('[McpSelectionSection] Error loading MCP data: $e');

      setState(() {
        _isLoading = false;
        _errorMessage = e.toString();
      });
    }
  }

  /// Check if a tool is selected, supporting both qualified (server:tool)
  /// and bare (tool) name formats for backward compatibility.
  bool _isToolSelected(String serverName, String toolName) {
    // Check qualified name first (new format)
    if (widget.selectedToolNames.contains('$serverName:$toolName')) return true;
    // Backward compat: check bare name (legacy agents saved before qualification)
    if (widget.selectedToolNames.contains(toolName)) return true;
    return false;
  }

  /// Upgrade bare tool names to qualified "server_name:tool_name" format.
  /// Returns the upgraded set. Bare names map to the first matching server
  /// (preserving backward-compatible behavior).
  Set<String> _upgradeToolNames(
    Set<String> current,
    McpToolsGroupedResponse grouped,
  ) {
    final upgraded = <String>{};
    for (final name in current) {
      if (name.contains(':')) {
        upgraded.add(name); // Already qualified
      } else {
        // Bare name — find first server with this tool
        bool found = false;
        for (final server in grouped.servers) {
          // Match by exact name or displayName (which strips b.{hash}. prefix)
          final matchingTool = server.tools.cast<McpToolModel?>().firstWhere(
            (t) => t!.name == name || t.displayName == name,
            orElse: () => null,
          );
          if (matchingTool != null) {
            // Use matchingTool.name (not the input bare name) to preserve
            // the actual tool name format from the MCP server
            upgraded.add('${server.serverName}:${matchingTool.name}');
            found = true;
            break;
          }
        }
        if (!found) upgraded.add(name); // Keep as-is if not found
      }
    }
    return upgraded;
  }

  void _onToolSelectionChanged(
      String serverName, String toolName, bool selected) {
    if (!widget.enabled) return;

    final qualifiedName = '$serverName:$toolName';
    final updatedSelection = Set<String>.from(widget.selectedToolNames);
    if (selected) {
      updatedSelection.add(qualifiedName);
    } else {
      // Remove both qualified and bare forms to avoid duplicates
      updatedSelection.remove(qualifiedName);
      updatedSelection.remove(toolName);
    }
    widget.onToolsChanged(updatedSelection);
  }

  void _onResourceSelectionChanged(String resourceUri, bool selected) {
    if (!widget.enabled) return;

    final updatedSelection = Set<String>.from(widget.selectedResourceUris);
    if (selected) {
      updatedSelection.add(resourceUri);
    } else {
      updatedSelection.remove(resourceUri);
    }
    widget.onResourcesChanged(updatedSelection);
  }

  void _selectAllToolsInServer(String serverName, bool select) {
    if (!widget.enabled) return;

    final server = _groupedData?.servers.firstWhere(
      (s) => s.serverName == serverName,
    );
    if (server == null) return;

    final updatedSelection = Set<String>.from(widget.selectedToolNames);
    for (final tool in server.tools) {
      final qualifiedName = '$serverName:${tool.name}';
      if (select) {
        updatedSelection.add(qualifiedName);
      } else {
        // Remove both qualified and bare forms
        updatedSelection.remove(qualifiedName);
        updatedSelection.remove(tool.name);
      }
    }
    widget.onToolsChanged(updatedSelection);
  }

  void _toggleServerExpanded(String serverName) {
    setState(() {
      _expandedServers[serverName] = !(_expandedServers[serverName] ?? false);
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(height: AppSpacing.xxl),
        BondAIContainer(
          icon: Icons.build_circle,
          title: 'Tools & Resources',
          subtitle: 'Select tools and resources to enable for this agent',
          margin: EdgeInsets.zero,
          children: [
            if (_isLoading)
              BondAILoadingState(message: 'Loading MCP tools and resources...'),
            if (_errorMessage != null)
              BondAIErrorState(
                message: 'Error loading MCP data',
                errorDetails: _errorMessage!,
                onRetry: _loadMcpData,
              ),
            if (!_isLoading && _errorMessage == null) ...[
              _buildToolsSection(theme),
              if ((_groupedData == null || _groupedData!.servers.isEmpty) &&
                  (_resources == null || _resources!.isEmpty))
                SizedBox(height: AppSpacing.xl),
              if ((_groupedData == null || _groupedData!.servers.isEmpty) &&
                  (_resources == null || _resources!.isEmpty))
                Divider(
                  color: theme.colorScheme.outlineVariant.withValues(
                    alpha: 0.2,
                  ),
                  height: 1,
                ),
              SizedBox(height: AppSpacing.xxl),
              _buildResourcesSection(theme),
            ],
          ],
        ),
      ],
    );
  }

  Widget _buildToolsSection(ThemeData theme) {
    if (_groupedData == null || _groupedData!.servers.isEmpty) {
      return BondAIResourceUnavailable(
        message: 'No tools available',
        description:
            'Please contact the administrator to enable external tools',
        type: ResourceUnavailableType.empty,
        showBorder: false,
        padding: EdgeInsets.zero,
        iconSize: AppSizes.iconEnormous / 2,
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Header with total count
        Padding(
          padding: const EdgeInsets.only(bottom: AppSpacing.sm),
          child: Text(
            'Available Tools (${_groupedData!.totalTools} from ${_groupedData!.totalServers} servers)',
            style: theme.textTheme.titleSmall?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
        // Tool limit guidance
        Padding(
          padding: const EdgeInsets.only(bottom: AppSpacing.md),
          child: Text(
            'For best results, select no more than 5 tools per agent.',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ),
        // Warning when too many tools selected
        if (widget.selectedToolNames.length > 5)
          Container(
            margin: const EdgeInsets.only(bottom: AppSpacing.md),
            padding: const EdgeInsets.all(AppSpacing.md),
            decoration: BoxDecoration(
              color: Colors.amber.shade50,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.amber.shade300),
            ),
            child: Row(
              children: [
                Icon(Icons.warning_amber_rounded, color: Colors.amber.shade800, size: 20),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Text(
                    'You have ${widget.selectedToolNames.length} tools selected. '
                    'Agents with more than 5 tools may experience reduced performance.',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: Colors.amber.shade900,
                    ),
                  ),
                ),
              ],
            ),
          ),
        // Server groups
        ..._groupedData!.servers.map(
          (server) => _buildServerGroup(server, theme),
        ),
      ],
    );
  }

  Widget _buildServerGroup(McpServerWithTools server, ThemeData theme) {
    final isExpanded = _expandedServers[server.serverName] ?? false;
    final status = server.connectionStatus;

    // Count selected tools in this server
    final selectedCount = server.tools.where(
      (tool) => _isToolSelected(server.serverName, tool.name),
    ).length;

    return Card(
      margin: const EdgeInsets.only(bottom: AppSpacing.md),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppBorderRadius.md),
        side: BorderSide(
          color: theme.colorScheme.outlineVariant.withValues(alpha: 0.3),
        ),
      ),
      child: Column(
        children: [
          // Server header (always visible, clickable to expand/collapse)
          InkWell(
            onTap: () => _toggleServerExpanded(server.serverName),
            borderRadius: BorderRadius.vertical(
              top: Radius.circular(AppBorderRadius.md),
              bottom: isExpanded ? Radius.zero : Radius.circular(AppBorderRadius.md),
            ),
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Row(
                children: [
                  // Expand/collapse icon
                  Icon(
                    isExpanded ? Icons.expand_more : Icons.chevron_right,
                    color: theme.colorScheme.onSurfaceVariant,
                    size: 24,
                  ),
                  const SizedBox(width: AppSpacing.sm),

                  // Server icon
                  _buildServerIcon(server, theme),
                  const SizedBox(width: AppSpacing.md),

                  // Server name, description, and tool count
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Text(
                              server.displayName,
                              style: theme.textTheme.titleSmall?.copyWith(
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            if (server.isUserDefined) ...[
                              const SizedBox(width: 6),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                decoration: BoxDecoration(
                                  color: theme.colorScheme.tertiary.withValues(alpha: 0.15),
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: Text(
                                  'Personal',
                                  style: theme.textTheme.labelSmall?.copyWith(
                                    color: theme.colorScheme.tertiary,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                              ),
                            ],
                            if (selectedCount > 0) ...[
                              const SizedBox(width: AppSpacing.sm),
                              Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 6,
                                  vertical: 2,
                                ),
                                decoration: BoxDecoration(
                                  color: theme.colorScheme.primary.withValues(alpha: 0.1),
                                  borderRadius: BorderRadius.circular(10),
                                ),
                                child: Text(
                                  '$selectedCount selected',
                                  style: theme.textTheme.labelSmall?.copyWith(
                                    color: theme.colorScheme.primary,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                              ),
                            ],
                          ],
                        ),
                        if (server.description != null) ...[
                          const SizedBox(height: 2),
                          Text(
                            server.description!,
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: theme.colorScheme.onSurfaceVariant,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                        const SizedBox(height: 2),
                        Text(
                          '${server.toolCount} tools',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                  ),

                  // Connection status badge
                  _buildConnectionStatusBadge(status, theme),
                ],
              ),
            ),
          ),

          // Connection warning banner (if needed)
          if (status.needsAttention || status.needsConnection)
            _buildConnectionWarningBanner(server, status, theme),

          // Expanded tools list
          if (isExpanded) ...[
            Divider(height: 1, color: theme.colorScheme.outlineVariant.withValues(alpha: 0.3)),
            Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Select All / Deselect All buttons
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      TextButton(
                        onPressed: widget.enabled && status.valid
                            ? () => _selectAllToolsInServer(server.serverName, true)
                            : null,
                        child: const Text('Select All'),
                      ),
                      const SizedBox(width: AppSpacing.sm),
                      TextButton(
                        onPressed: widget.enabled && status.valid
                            ? () => _selectAllToolsInServer(server.serverName, false)
                            : null,
                        child: const Text('Deselect All'),
                      ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.sm),

                  // Individual tools
                  ...server.tools.map(
                    (tool) => BondAITile(
                      type: BondAITileType.checkbox,
                      title: tool.displayName, // Use displayName for UI (strips b.{hash}. prefix)
                      subtitle: tool.description,
                      value: _isToolSelected(server.serverName, tool.name),
                      enabled: widget.enabled && status.valid,
                      onChanged: (value) => _onToolSelectionChanged(server.serverName, tool.name, value ?? false),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildServerIcon(McpServerWithTools server, ThemeData theme) {
    if (server.iconUrl != null) {
      return ClipRRect(
        borderRadius: BorderRadius.circular(4),
        child: Image.network(
          server.iconUrl!,
          width: 24,
          height: 24,
          errorBuilder: (_, __, ___) => Icon(
            Icons.cloud,
            size: 24,
            color: theme.colorScheme.primary,
          ),
        ),
      );
    }

    return Icon(
      Icons.cloud,
      size: 24,
      color: theme.colorScheme.primary,
    );
  }

  Widget _buildConnectionStatusBadge(McpConnectionStatusInfo status, ThemeData theme) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: status.statusColor.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: status.statusColor.withValues(alpha: 0.3),
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: status.statusColor,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 6),
          Text(
            status.statusText,
            style: theme.textTheme.labelSmall?.copyWith(
              color: status.statusColor,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildConnectionWarningBanner(
    McpServerWithTools server,
    McpConnectionStatusInfo status,
    ThemeData theme,
  ) {
    final isExpired = status.needsAttention;
    final backgroundColor = isExpired
        ? theme.colorScheme.errorContainer
        : theme.colorScheme.primaryContainer;
    final foregroundColor = isExpired
        ? theme.colorScheme.onErrorContainer
        : theme.colorScheme.onPrimaryContainer;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md, vertical: AppSpacing.sm),
      color: backgroundColor,
      child: Row(
        children: [
          Icon(
            isExpired ? Icons.warning_amber : Icons.info_outline,
            size: 16,
            color: foregroundColor,
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              isExpired
                  ? 'Connection expired. Reconnect to use these tools.'
                  : 'Not connected. Connect to use these tools.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: foregroundColor,
              ),
            ),
          ),
          TextButton(
            onPressed: () {
              // Navigate to connections screen
              Navigator.of(context).pushNamed('/connections');
            },
            style: TextButton.styleFrom(
              foregroundColor: foregroundColor,
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
              minimumSize: Size.zero,
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            child: Text(isExpired ? 'Reconnect' : 'Connect'),
          ),
        ],
      ),
    );
  }

  Widget _buildResourcesSection(ThemeData theme) {
    if (_resources == null || _resources!.isEmpty) {
      return BondAIResourceUnavailable(
        message: 'No resources available',
        description:
            'Please contact the administrator to enable external resources',
        type: ResourceUnavailableType.empty,
        showBorder: false,
        padding: EdgeInsets.zero,
        iconSize: AppSizes.iconEnormous / 2,
      );
    }

    return BondAIContainerSection(
      title: 'Available Resources (${_resources!.length})',
      children:
          _resources!
              .map(
                (resource) => BondAITile(
                  type: BondAITileType.checkbox,
                  title: resource.name ?? resource.uri,
                  subtitle: resource.description,
                  description: '${resource.mimeType} • ${resource.uri}',
                  value: widget.selectedResourceUris.contains(resource.uri),
                  enabled: widget.enabled,
                  onChanged:
                      (value) => _onResourceSelectionChanged(
                        resource.uri,
                        value ?? false,
                      ),
                ),
              )
              .toList(),
    );
  }
}
