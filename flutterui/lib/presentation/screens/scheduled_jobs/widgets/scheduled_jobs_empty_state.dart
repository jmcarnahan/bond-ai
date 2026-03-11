import 'package:flutter/material.dart';

class ScheduledJobsEmptyState extends StatelessWidget {
  final VoidCallback onCreateJob;

  const ScheduledJobsEmptyState({super.key, required this.onCreateJob});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.schedule,
            size: 64,
            color: theme.colorScheme.onSurfaceVariant.withValues(alpha: 0.5),
          ),
          const SizedBox(height: 16),
          Text(
            'No Scheduled Jobs',
            style: theme.textTheme.headlineSmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Schedule agents to run automatically on a recurring basis.',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant.withValues(alpha: 0.7),
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: onCreateJob,
            icon: const Icon(Icons.add),
            label: const Text('Create Scheduled Job'),
          ),
        ],
      ),
    );
  }
}
