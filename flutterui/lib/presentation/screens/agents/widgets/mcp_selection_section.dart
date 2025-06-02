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
    if (_isLoading) return;

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final mcpService = ref.read(mcpServiceProvider);
      final results = await Future.wait([
        mcpService.getTools(),
        mcpService.getResources(),
      ]);

      setState(() {
        _tools = results[0] as List<McpToolModel>;
        _resources = results[1] as List<McpResourceModel>;
        _isLoading = false;
      });

      logger.i(
        'Loaded ${_tools!.length} MCP tools and ${_resources!.length} MCP resources',
      );
    } catch (e) {
      setState(() {
        _isLoading = false;
        _errorMessage = e.toString();
      });
      logger.e('Error loading MCP data: $e');
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
          'MCP Tools & Resources',
          style: theme.textTheme.titleLarge?.copyWith(
            color: theme.colorScheme.onSurface,
            fontWeight: FontWeight.w600,
          ),
        ),
        SizedBox(height: AppSpacing.md),
        Text(
          'Select MCP tools and resources to enable for this agent',
          style: theme.textTheme.bodyMedium?.copyWith(
            color: theme.colorScheme.onSurface.withOpacity(0.7),
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
          color: theme.colorScheme.outlineVariant.withOpacity(0.5),
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
        side: BorderSide(color: theme.colorScheme.error.withOpacity(0.5)),
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
        'No MCP tools available\n\nConfigure MCP servers in your backend to enable external tools',
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
        'No MCP resources available\n\nConfigure MCP servers in your backend to enable external resources',
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
          color: theme.colorScheme.outlineVariant.withOpacity(0.5),
        ),
      ),
      color: theme.colorScheme.surfaceContainer,
      child: Padding(
        padding: AppSpacing.allXl,
        child: Column(
          children: [
            Icon(
              Icons.info_outline,
              color: theme.colorScheme.onSurface.withOpacity(0.5),
              size: 24,
            ),
            SizedBox(height: AppSpacing.sm),
            Text(
              message,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurface.withOpacity(0.7),
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
                  ? theme.colorScheme.primary.withOpacity(0.5)
                  : theme.colorScheme.outlineVariant.withOpacity(0.5),
        ),
      ),
      color:
          isSelected
              ? theme.colorScheme.primaryContainer.withOpacity(0.1)
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
                    ? theme.colorScheme.onSurface.withOpacity(0.7)
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
                  ? theme.colorScheme.primary.withOpacity(0.5)
                  : theme.colorScheme.outlineVariant.withOpacity(0.5),
        ),
      ),
      color:
          isSelected
              ? theme.colorScheme.primaryContainer.withOpacity(0.1)
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
                        ? theme.colorScheme.onSurface.withOpacity(0.7)
                        : theme.disabledColor,
              ),
            ),
            SizedBox(height: AppSpacing.xs),
            Text(
              '${resource.mimeType} • ${resource.uri}',
              style: theme.textTheme.bodySmall?.copyWith(
                color:
                    widget.enabled
                        ? theme.colorScheme.onSurface.withOpacity(0.5)
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
