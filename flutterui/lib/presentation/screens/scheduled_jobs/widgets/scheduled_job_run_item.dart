import 'package:flutter/material.dart';
import 'package:flutterui/data/models/scheduled_job_model.dart';

class ScheduledJobRunItem extends StatelessWidget {
  final ScheduledJobRun run;
  final VoidCallback onTap;

  const ScheduledJobRunItem({
    super.key,
    required this.run,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return ListTile(
      leading: Icon(
        run.status == 'completed'
            ? Icons.check_circle
            : run.status == 'failed'
                ? Icons.error
                : Icons.help_outline,
        color: run.status == 'completed'
            ? Colors.green
            : run.status == 'failed'
                ? colorScheme.error
                : colorScheme.onSurfaceVariant,
        size: 20,
      ),
      title: Text(
        run.threadName,
        style: theme.textTheme.bodyMedium,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
      subtitle: run.createdAt != null
          ? Text(
              _formatDate(run.createdAt!),
              style: theme.textTheme.bodySmall?.copyWith(
                color: colorScheme.onSurfaceVariant,
              ),
            )
          : null,
      trailing: Icon(Icons.chevron_right, color: colorScheme.onSurfaceVariant),
      onTap: onTap,
    );
  }

  String _formatDate(DateTime dt) {
    return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} '
        '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
  }
}
