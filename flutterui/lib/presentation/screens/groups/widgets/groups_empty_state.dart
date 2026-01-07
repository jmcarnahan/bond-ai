import 'package:flutter/material.dart';

class GroupsEmptyState extends StatelessWidget {
  final VoidCallback onCreateGroup;

  const GroupsEmptyState({
    super.key,
    required this.onCreateGroup,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.group_outlined,
            size: 64,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(height: 16),
          Text(
            'No groups yet',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 8),
          const Text(
            'Create your first group to get started',
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          ElevatedButton.icon(
            onPressed: onCreateGroup,
            icon: const Icon(Icons.add),
            label: const Text('Create Group'),
          ),
        ],
      ),
    );
  }
}
