import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/group_model.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import 'package:flutterui/core/utils/logger.dart';

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
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Share with Additional Groups',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              'Optionally share this agent with existing groups. Members of selected groups will also be able to access this agent.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).textTheme.bodySmall?.color,
              ),
            ),
            const SizedBox(height: 16),
            
            if (_isLoading)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(16.0),
                  child: CircularProgressIndicator(),
                ),
              )
            else if (_errorMessage != null)
              Center(
                child: Column(
                  children: [
                    Icon(
                      Icons.error_outline,
                      color: Theme.of(context).colorScheme.error,
                      size: 48,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _errorMessage!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 8),
                    ElevatedButton(
                      onPressed: _loadAvailableGroups,
                      child: const Text('Retry'),
                    ),
                  ],
                ),
              )
            else if (_availableGroups?.isEmpty ?? true)
              Center(
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    children: [
                      Icon(
                        Icons.groups,
                        color: Theme.of(context).colorScheme.secondary,
                        size: 48,
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        'No additional groups available for sharing.',
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Create or join groups to share agents with multiple users.',
                        style: Theme.of(context).textTheme.bodySmall,
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
              )
            else
              Column(
                children: _availableGroups!.map((group) {
                  final isSelected = widget.selectedGroupIds.contains(group.id);
                  return CheckboxListTile(
                    title: Text(group.name),
                    subtitle: group.description != null
                        ? Text(group.description!)
                        : null,
                    secondary: group.isOwner
                        ? Icon(
                            Icons.admin_panel_settings,
                            color: Theme.of(context).colorScheme.primary,
                          )
                        : Icon(
                            Icons.group,
                            color: Theme.of(context).colorScheme.secondary,
                          ),
                    value: isSelected,
                    onChanged: (bool? value) {
                      _toggleGroupSelection(group.id);
                    },
                    contentPadding: EdgeInsets.zero,
                  );
                }).toList(),
              ),
          ],
        ),
      ),
    );
  }
}