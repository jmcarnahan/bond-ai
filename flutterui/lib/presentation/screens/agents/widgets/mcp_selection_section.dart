import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutterui/core/constants/app_constants.dart';
import 'package:flutterui/data/models/mcp_model.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import 'package:flutterui/core/utils/logger.dart';

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
  List<McpToolModel>? _tools;
  List<McpResourceModel>? _resources;
  bool _isLoading = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadMcpData();
  }

  Future<void> _loadMcpData() async {
    if (_isLoading) {
      logger.i(
        '[McpSelectionSection] _loadMcpData called but already loading, returning',
      );
      return;
    }

    logger.i('[McpSelectionSection] Starting to load MCP data...');
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      logger.i('[McpSelectionSection] Getting MCP service provider...');
      final mcpService = ref.read(mcpServiceProvider);
      logger.i(
        '[McpSelectionSection] MCP service obtained: $mcpService',
      );

      logger.i(
        '[McpSelectionSection] Starting parallel requests for tools and resources...',
      );
      final results = await Future.wait([
        mcpService.getTools(),
        mcpService.getResources(),
      ]);

      logger.i(
        '[McpSelectionSection] Both requests completed, processing results...',
      );
      final tools = results[0] as List<McpToolModel>;
      final resources = results[1] as List<McpResourceModel>;

      logger.i(
        '[McpSelectionSection] Received ${tools.length} tools and ${resources.length} resources',
      );

      setState(() {
        _tools = tools;
        _resources = resources;
        _isLoading = false;
      });

      logger.i(
        '[McpSelectionSection] Successfully loaded ${_tools!.length} MCP tools and ${_resources!.length} MCP resources',
      );

      // Log tool details
      for (int i = 0; i < tools.length; i++) {
        logger.i(
          '[McpSelectionSection] Tool ${i + 1}: ${tools[i].name} - ${tools[i].description}',
        );
      }

      // Log resource details
      for (int i = 0; i < resources.length; i++) {
        logger.i(
          '[McpSelectionSection] Resource ${i + 1}: ${resources[i].name} (${resources[i].uri})',
        );
      }
    } catch (e, stackTrace) {
      logger.e('[McpSelectionSection] Error loading MCP data: $e');
      logger.e('[McpSelectionSection] Stack trace: $stackTrace');

      setState(() {
        _isLoading = false;
        _errorMessage = e.toString();
      });
    }
  }

  void _onToolSelectionChanged(String toolName, bool selected) {
    if (!widget.enabled) return;

    final updatedSelection = Set<String>.from(widget.selectedToolNames);
    if (selected) {
      updatedSelection.add(toolName);
    } else {
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

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(height: AppSpacing.xxl),
        Text(
          'Tools & Resources',
          style: theme.textTheme.titleLarge?.copyWith(
            color: theme.colorScheme.onSurface,
            fontWeight: FontWeight.w600,
          ),
        ),
        SizedBox(height: AppSpacing.md),
        Text(
          'Select tools and resources to enable for this agent',
          style: theme.textTheme.bodyMedium?.copyWith(
            color: theme.colorScheme.onSurface.withValues(alpha: .7),
          ),
        ),
        SizedBox(height: AppSpacing.lg),
        if (_isLoading) _buildLoadingState(theme),
        if (_errorMessage != null) _buildErrorState(theme),
        if (!_isLoading && _errorMessage == null) ...[
          _buildToolsSection(theme),
          SizedBox(height: AppSpacing.xl),
          _buildResourcesSection(theme),
        ],
      ],
    );
  }

  Widget _buildLoadingState(ThemeData theme) {
    return Card(
      elevation: 0.0,
      margin: AppSpacing.verticalSm,
      shape: RoundedRectangleBorder(
        borderRadius: AppBorderRadius.allMd,
        side: BorderSide(
          color: theme.colorScheme.outlineVariant.withValues(alpha: .5),
        ),
      ),
      color: theme.colorScheme.surfaceContainer,
      child: Padding(
        padding: AppSpacing.allXl,
        child: Row(
          children: [
            SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                valueColor: AlwaysStoppedAnimation(theme.colorScheme.primary),
              ),
            ),
            SizedBox(width: AppSpacing.lg),
            Text(
              'Loading MCP tools and resources...',
              style: theme.textTheme.bodyMedium,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildErrorState(ThemeData theme) {
    return Card(
      elevation: 0.0,
      margin: AppSpacing.verticalSm,
      shape: RoundedRectangleBorder(
        borderRadius: AppBorderRadius.allMd,
        side: BorderSide(color: theme.colorScheme.error.withValues(alpha: .5)),
      ),
      color: theme.colorScheme.errorContainer,
      child: Padding(
        padding: AppSpacing.allXl,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.error_outline,
                  color: theme.colorScheme.error,
                  size: 20,
                ),
                SizedBox(width: AppSpacing.md),
                Expanded(
                  child: Text(
                    'Error loading MCP data',
                    style: theme.textTheme.titleSmall?.copyWith(
                      color: theme.colorScheme.error,
                    ),
                  ),
                ),
              ],
            ),
            SizedBox(height: AppSpacing.sm),
            Text(
              _errorMessage!,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.error,
              ),
            ),
            SizedBox(height: AppSpacing.md),
            TextButton.icon(
              onPressed: _loadMcpData,
              icon: Icon(Icons.refresh, size: 16),
              label: Text('Retry'),
              style: TextButton.styleFrom(
                foregroundColor: theme.colorScheme.error,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildToolsSection(ThemeData theme) {
    if (_tools == null || _tools!.isEmpty) {
      return _buildEmptyState(
        theme,
        'No tools available\n\nPlease contact the administrator to enable external tools',
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Available Tools (${_tools!.length})',
          style: theme.textTheme.titleMedium?.copyWith(
            color: theme.colorScheme.onSurface,
            fontWeight: FontWeight.w500,
          ),
        ),
        SizedBox(height: AppSpacing.md),
        ..._tools!.map((tool) => _buildToolItem(theme, tool)),
      ],
    );
  }

  Widget _buildResourcesSection(ThemeData theme) {
    if (_resources == null || _resources!.isEmpty) {
      return _buildEmptyState(
        theme,
        'No resources available\n\nPlease contact the administrator to enable external resources',
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Available Resources (${_resources!.length})',
          style: theme.textTheme.titleMedium?.copyWith(
            color: theme.colorScheme.onSurface,
            fontWeight: FontWeight.w500,
          ),
        ),
        SizedBox(height: AppSpacing.md),
        ..._resources!.map((resource) => _buildResourceItem(theme, resource)),
      ],
    );
  }

  Widget _buildEmptyState(ThemeData theme, String message) {
    return Card(
      elevation: 0.0,
      margin: AppSpacing.verticalSm,
      shape: RoundedRectangleBorder(
        borderRadius: AppBorderRadius.allMd,
        side: BorderSide(
          color: theme.colorScheme.outlineVariant.withValues(alpha: .5),
        ),
      ),
      color: theme.colorScheme.surfaceContainer,
      child: Padding(
        padding: AppSpacing.allXl,
        child: Column(
          children: [
            Icon(
              Icons.info_outline,
              color: theme.colorScheme.onSurface.withValues(alpha: .5),
              size: 24,
            ),
            SizedBox(height: AppSpacing.sm),
            Text(
              message,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurface.withValues(alpha: .7),
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildToolItem(ThemeData theme, McpToolModel tool) {
    final isSelected = widget.selectedToolNames.contains(tool.name);

    return Card(
      elevation: 0.0,
      margin: AppSpacing.verticalSm,
      shape: RoundedRectangleBorder(
        borderRadius: AppBorderRadius.allMd,
        side: BorderSide(
          color:
              isSelected
                  ? theme.colorScheme.primary.withValues(alpha: .5)
                  : theme.colorScheme.outlineVariant.withValues(alpha: .5),
        ),
      ),
      color:
          isSelected
              ? theme.colorScheme.primaryContainer.withValues(alpha: .1)
              : theme.colorScheme.surfaceContainer,
      child: CheckboxListTile(
        title: Text(
          tool.name,
          style: theme.textTheme.titleSmall?.copyWith(
            color:
                widget.enabled
                    ? theme.colorScheme.onSurface
                    : theme.disabledColor,
            fontWeight: FontWeight.w500,
          ),
        ),
        subtitle: Text(
          tool.description,
          style: theme.textTheme.bodySmall?.copyWith(
            color:
                widget.enabled
                    ? theme.colorScheme.onSurface.withValues(alpha: .7)
                    : theme.disabledColor,
          ),
        ),
        value: isSelected,
        onChanged:
            widget.enabled
                ? (bool? value) =>
                    _onToolSelectionChanged(tool.name, value ?? false)
                : null,
        activeColor: theme.colorScheme.primary,
        contentPadding: AppSpacing.horizontalXl.add(AppSpacing.verticalLg),
      ),
    );
  }

  Widget _buildResourceItem(ThemeData theme, McpResourceModel resource) {
    final isSelected = widget.selectedResourceUris.contains(resource.uri);

    return Card(
      elevation: 0.0,
      margin: AppSpacing.verticalSm,
      shape: RoundedRectangleBorder(
        borderRadius: AppBorderRadius.allMd,
        side: BorderSide(
          color:
              isSelected
                  ? theme.colorScheme.primary.withValues(alpha: .5)
                  : theme.colorScheme.outlineVariant.withValues(alpha: .5),
        ),
      ),
      color:
          isSelected
              ? theme.colorScheme.primaryContainer.withValues(alpha: .1)
              : theme.colorScheme.surfaceContainer,
      child: CheckboxListTile(
        title: Text(
          resource.name,
          style: theme.textTheme.titleSmall?.copyWith(
            color:
                widget.enabled
                    ? theme.colorScheme.onSurface
                    : theme.disabledColor,
            fontWeight: FontWeight.w500,
          ),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              resource.description,
              style: theme.textTheme.bodySmall?.copyWith(
                color:
                    widget.enabled
                        ? theme.colorScheme.onSurface.withValues(alpha: .7)
                        : theme.disabledColor,
              ),
            ),
            SizedBox(height: AppSpacing.xs),
            Text(
              '${resource.mimeType} • ${resource.uri}',
              style: theme.textTheme.bodySmall?.copyWith(
                color:
                    widget.enabled
                        ? theme.colorScheme.onSurface.withValues(alpha: .5)
                        : theme.disabledColor,
                fontFamily: 'monospace',
              ),
            ),
          ],
        ),
        value: isSelected,
        onChanged:
            widget.enabled
                ? (bool? value) =>
                    _onResourceSelectionChanged(resource.uri, value ?? false)
                : null,
        activeColor: theme.colorScheme.primary,
        contentPadding: AppSpacing.horizontalXl.add(AppSpacing.verticalLg),
      ),
    );
  }
}
