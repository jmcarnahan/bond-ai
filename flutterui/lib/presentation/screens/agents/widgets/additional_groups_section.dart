import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/core/constants/app_constants.dart';
import 'package:flutterui/data/models/group_model.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import 'package:flutterui/core/utils/logger.dart';
import 'package:flutterui/presentation/widgets/common/bondai_widgets.dart';

class AdditionalGroupsSection extends ConsumerStatefulWidget {
  final Set<String> selectedGroupIds;
  final Function(Set<String>) onGroupSelectionChanged;
  final String? agentName;
  final Map<String, String> groupPermissions;
  final Function(Map<String, String>)? onGroupPermissionsChanged;

  const AdditionalGroupsSection({
    super.key,
    required this.selectedGroupIds,
    required this.onGroupSelectionChanged,
    this.agentName,
    this.groupPermissions = const {},
    this.onGroupPermissionsChanged,
  });

  @override
  ConsumerState<AdditionalGroupsSection> createState() => _AdditionalGroupsSectionState();
}

class _AdditionalGroupsSectionState extends ConsumerState<AdditionalGroupsSection> {
  List<AvailableGroup>? _availableGroups;
  bool _isLoading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadAvailableGroups();
  }

  @override
  void didUpdateWidget(AdditionalGroupsSection oldWidget) {
    super.didUpdateWidget(oldWidget);
  }

  Future<void> _loadAvailableGroups() async {
    try {
      setState(() {
        _isLoading = true;
        _errorMessage = null;
      });

      final agentService = ref.read(agentServiceProvider);
      final allGroups = await agentService.getAvailableGroups();

      // Filter out default groups (groups that end with "Default Group")
      final filteredGroups = allGroups.where((group) {
        // Filter out any group that follows the default group naming pattern
        return !group.name.endsWith('Default Group');
      }).toList();

      setState(() {
        _availableGroups = filteredGroups;
        _isLoading = false;
      });
    } catch (e) {
      logger.e('Error loading available groups: $e');
      setState(() {
        _errorMessage = 'Failed to load groups: $e';
        _isLoading = false;
      });
    }
  }

  void _toggleGroupSelection(String groupId) {
    final newSelection = Set<String>.from(widget.selectedGroupIds);
    if (newSelection.contains(groupId)) {
      newSelection.remove(groupId);
      // Also remove the permission entry
      if (widget.onGroupPermissionsChanged != null) {
        final newPerms = Map<String, String>.from(widget.groupPermissions);
        newPerms.remove(groupId);
        widget.onGroupPermissionsChanged!(newPerms);
      }
    } else {
      newSelection.add(groupId);
      // Set default permission for newly added group
      if (widget.onGroupPermissionsChanged != null) {
        final newPerms = Map<String, String>.from(widget.groupPermissions);
        newPerms[groupId] = 'can_use';
        widget.onGroupPermissionsChanged!(newPerms);
      }
    }
    widget.onGroupSelectionChanged(newSelection);
  }

  void _onPermissionChanged(String groupId, String permission) {
    if (widget.onGroupPermissionsChanged != null) {
      final newPerms = Map<String, String>.from(widget.groupPermissions);
      newPerms[groupId] = permission;
      widget.onGroupPermissionsChanged!(newPerms);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return BondAIContainer(
      icon: Icons.groups,
      title: 'Share with Additional Groups',
      subtitle: 'Optionally share this agent with existing groups. Members of selected groups will also be able to access this agent.',
      margin: EdgeInsets.only(top: AppSpacing.xl),
      children: [
        if (_isLoading)
          BondAILoadingState(
            message: 'Loading groups...',
            showBackground: false,
          )
        else if (_errorMessage != null)
          BondAIErrorState(
            message: 'Failed to load groups',
            errorDetails: _errorMessage!,
            onRetry: _loadAvailableGroups,
            showIcon: false,
            padding: EdgeInsets.zero,
          )
        else if (_availableGroups?.isEmpty ?? true)
          BondAIResourceUnavailable(
            message: 'No additional groups available for sharing.',
            description: 'Create or join groups to share agents with multiple users.',
            icon: Icons.groups,
            type: ResourceUnavailableType.empty,
            showBorder: false,
            padding: EdgeInsets.zero,
          )
        else
          Column(
            children: _availableGroups!.map((group) {
              final isSelected = widget.selectedGroupIds.contains(group.id);
              final permission = widget.groupPermissions[group.id] ?? 'can_use';
              return Column(
                children: [
                  BondAITile(
                    type: BondAITileType.checkbox,
                    title: group.name,
                    subtitle: group.description,
                    leading: group.isOwner
                        ? Icon(
                            Icons.admin_panel_settings,
                            color: theme.colorScheme.primary,
                          )
                        : Icon(
                            Icons.group,
                            color: theme.colorScheme.secondary,
                          ),
                    value: isSelected,
                    onChanged: (bool? value) {
                      _toggleGroupSelection(group.id);
                    },
                  ),
                  if (isSelected)
                    Padding(
                      padding: const EdgeInsets.only(left: 56, right: 16, bottom: 8),
                      child: Row(
                        children: [
                          Text(
                            'Permission: ',
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: theme.colorScheme.onSurfaceVariant,
                            ),
                          ),
                          const SizedBox(width: 8),
                          SegmentedButton<String>(
                            segments: const [
                              ButtonSegment<String>(
                                value: 'can_use',
                                label: Text('Can Use'),
                                icon: Icon(Icons.visibility, size: 16),
                              ),
                              ButtonSegment<String>(
                                value: 'can_edit',
                                label: Text('Can Edit'),
                                icon: Icon(Icons.edit, size: 16),
                              ),
                            ],
                            selected: {permission},
                            onSelectionChanged: (Set<String> selected) {
                              _onPermissionChanged(group.id, selected.first);
                            },
                            style: SegmentedButton.styleFrom(
                              textStyle: theme.textTheme.labelSmall,
                              visualDensity: VisualDensity.compact,
                            ),
                          ),
                        ],
                      ),
                    ),
                ],
              );
            }).toList(),
          ),
      ],
    );
  }
}
