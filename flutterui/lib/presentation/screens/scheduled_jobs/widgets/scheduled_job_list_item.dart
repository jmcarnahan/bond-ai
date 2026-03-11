import 'package:flutter/material.dart';
import 'package:flutterui/data/models/scheduled_job_model.dart';

class ScheduledJobListItem extends StatelessWidget {
  final ScheduledJob job;
  final VoidCallback onTap;
  final VoidCallback onEdit;
  final VoidCallback onToggle;
  final VoidCallback? onViewThread;

  const ScheduledJobListItem({
    super.key,
    required this.job,
    required this.onTap,
    required this.onEdit,
    required this.onToggle,
    this.onViewThread,
  });

  String _humanReadableSchedule(String cron, String timezone) {
    // Short timezone label for display (e.g. "America/Chicago" → "CST" or just the city)
    final tzShort = timezone == 'UTC'
        ? 'UTC'
        : timezone.contains('/') ? timezone.split('/').last.replaceAll('_', ' ') : timezone;

    switch (cron) {
      case '0 * * * *':
        return 'Every hour';
      case '0 */4 * * *':
        return 'Every 4 hours';
      case '0 9 * * *':
        return 'Daily at 9:00 AM ($tzShort)';
      case '0 9 * * 1':
        return 'Weekly on Monday ($tzShort)';
      case '0 9 1 * *':
        return 'First of month ($tzShort)';
      case '*/5 * * * *':
        return 'Every 5 minutes';
      default:
        return '$cron ($tzShort)';
    }
  }

  String _timeAgo(DateTime? dt) {
    if (dt == null) return 'Never';
    final diff = DateTime.now().difference(dt);
    if (diff.isNegative || diff.inMinutes < 1) return 'Just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return '${dt.month}/${dt.day}/${dt.year}';
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    // Status dot color
    Color statusColor;
    if (!job.isEnabled) {
      statusColor = colorScheme.onSurfaceVariant.withValues(alpha: 0.4);
    } else if (job.lastRunStatus == 'failed') {
      statusColor = colorScheme.error;
    } else {
      statusColor = Colors.green;
    }

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
        child: Row(
          children: [
            // Status dot
            Container(
              width: 12,
              height: 12,
              decoration: BoxDecoration(
                color: statusColor,
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: 12),
            // Main content
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    job.name,
                    style: theme.textTheme.bodyLarge?.copyWith(
                      fontWeight: FontWeight.w600,
                      color: job.isEnabled
                          ? colorScheme.onSurface
                          : colorScheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Icon(Icons.schedule, size: 14, color: colorScheme.onSurfaceVariant),
                      const SizedBox(width: 4),
                      Text(
                        _humanReadableSchedule(job.schedule, job.timezone),
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 2),
                  Row(
                    children: [
                      if (job.lastRunAt != null) ...[
                        Text(
                          'Last run: ${_timeAgo(job.lastRunAt)}',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: colorScheme.onSurfaceVariant,
                          ),
                        ),
                        if (job.lastRunStatus != null) ...[
                          const SizedBox(width: 4),
                          Text(
                            '- ${job.lastRunStatus == 'completed' ? 'Success' : 'Failed'}',
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: job.lastRunStatus == 'completed'
                                  ? Colors.green
                                  : colorScheme.error,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ],
                      ] else
                        Text(
                          'No runs yet',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: colorScheme.onSurfaceVariant.withValues(alpha: 0.6),
                          ),
                        ),
                    ],
                  ),
                  if (job.nextRunAt != null && job.isEnabled) ...[
                    const SizedBox(height: 2),
                    Text(
                      'Next: ${_formatNextRun(job.nextRunAt!)}',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: colorScheme.primary,
                        fontSize: 11,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            // Action buttons
            if (job.lastThreadId != null && onViewThread != null)
              IconButton(
                onPressed: onViewThread,
                icon: Icon(Icons.chat_bubble_outline, size: 20, color: colorScheme.primary),
                tooltip: 'View last thread',
              ),
            IconButton(
              onPressed: onEdit,
              icon: Icon(Icons.edit_outlined, size: 20, color: colorScheme.onSurfaceVariant),
              tooltip: 'Edit',
            ),
            Switch(
              value: job.isEnabled,
              onChanged: (_) => onToggle(),
            ),
          ],
        ),
      ),
    );
  }

  String _formatNextRun(DateTime dt) {
    final now = DateTime.now();
    final diff = dt.difference(now);
    final time = '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';

    if (diff.isNegative) return 'overdue';

    // Same day: show relative + time
    if (dt.year == now.year && dt.month == now.month && dt.day == now.day) {
      if (diff.inMinutes < 1) return 'in <1m (today $time)';
      if (diff.inMinutes < 60) return 'in ${diff.inMinutes}m (today $time)';
      return 'in ${diff.inHours}h (today $time)';
    }

    // Tomorrow
    final tomorrow = now.add(const Duration(days: 1));
    if (dt.year == tomorrow.year && dt.month == tomorrow.month && dt.day == tomorrow.day) {
      return 'tomorrow $time';
    }

    return '${dt.month}/${dt.day} $time';
  }
}
