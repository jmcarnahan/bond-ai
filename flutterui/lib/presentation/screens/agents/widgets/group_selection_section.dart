import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/group_model.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import 'package:flutterui/core/utils/logger.dart';

class GroupSelectionSection extends ConsumerStatefulWidget {
  final Set<String> selectedGroupIds;
  final Function(Set<String>) onGroupSelectionChanged;

  const GroupSelectionSection({
    super.key,
    required this.selectedGroupIds,
    required this.onGroupSelectionChanged,
  });

  @override
  ConsumerState<GroupSelectionSection> createState() => _GroupSelectionSectionState();
}

class _GroupSelectionSectionState extends ConsumerState<GroupSelectionSection> {
  List<AvailableGroup>? _availableGroups;
  bool _isLoading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadAvailableGroups();
  }

  Future<void> _loadAvailableGroups() async {
    try {
      setState(() {
        _isLoading = true;
        _errorMessage = null;
      });

      final agentService = ref.read(agentServiceProvider);
      final groups = await agentService.getAvailableGroups();
      
      setState(() {
        _availableGroups = groups;
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
              'Share with Groups',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              'Select groups to share this agent with. Members of selected groups will be able to access this agent.',
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
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(16.0),
                  child: Text(
                    'No groups available for sharing. Create or join groups to share agents.',
                    textAlign: TextAlign.center,
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