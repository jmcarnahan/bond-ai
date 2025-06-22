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
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final mcpService = ref.read(mcpServiceProvider);
      // logger.i('[McpSelectionSection] MCP service obtained: $mcpService');

      final results = await Future.wait([
        mcpService.getTools(),
        mcpService.getResources(),
      ]);

      final tools = results[0] as List<McpToolModel>;
      final resources = results[1] as List<McpResourceModel>;

      setState(() {
        _tools = tools;
        _resources = resources;
        _isLoading = false;
      });

      // Log tool details
      // for (int i = 0; i < tools.length; i++) {
      //   logger.i(
      //     '[McpSelectionSection] Tool ${i + 1}: ${tools[i].name} - ${tools[i].description}',
      //   );
      // }

      // Log resource details
      // for (int i = 0; i < resources.length; i++) {
      //   logger.i(
      //     '[McpSelectionSection] Resource ${i + 1}: ${resources[i].name} (${resources[i].uri})',
      //   );
      // }
    } catch (e) {
      logger.e('[McpSelectionSection] Error loading MCP data: $e');

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
              if ((_tools == null || _tools!.isEmpty) &&
                  (_resources == null || _resources!.isEmpty))
                SizedBox(height: AppSpacing.xl),
              if ((_tools == null || _tools!.isEmpty) &&
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
    if (_tools == null || _tools!.isEmpty) {
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

    return BondAIContainerSection(
      title: 'Available Tools (${_tools!.length})',
      children:
          _tools!
              .map(
                (tool) => BondAITile(
                  type: BondAITileType.checkbox,
                  title: tool.name,
                  subtitle: tool.description,
                  value: widget.selectedToolNames.contains(tool.name),
                  enabled: widget.enabled,
                  onChanged:
                      (value) =>
                          _onToolSelectionChanged(tool.name, value ?? false),
                ),
              )
              .toList(),
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
