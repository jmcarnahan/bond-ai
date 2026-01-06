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

  const AdditionalGroupsSection({
    super.key,
    required this.selectedGroupIds,
    required this.onGroupSelectionChanged,
    this.agentName,
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
    } else {
      newSelection.add(groupId);
    }
    widget.onGroupSelectionChanged(newSelection);
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
              return BondAITile(
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
              );
            }).toList(),
          ),
      ],
    );
  }
}
