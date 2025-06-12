import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/providers/thread_provider.dart';

class ThreadListItem extends ConsumerWidget {
  final Thread thread;
  final bool isSelected;
  final VoidCallback onTap;

  const ThreadListItem({
    super.key,
    required this.thread,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        color: theme.colorScheme.surface,
        border: Border.all(
          color: isSelected ? theme.colorScheme.primary : theme.colorScheme.outline,
          width: isSelected ? 2.0 : 1.0,
        ),
        boxShadow: [
          BoxShadow(
            color: isSelected 
                ? theme.colorScheme.primary.withValues(alpha: 0.15)
                : theme.colorScheme.onSurface.withValues(alpha: 0.05),
            blurRadius: isSelected ? 12 : 8,
            offset: const Offset(0, 4),
            spreadRadius: isSelected ? 1 : 0,
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(16),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                _buildLeadingIcon(theme, isSelected),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _buildTitle(theme, isSelected),
                      const SizedBox(height: 4),
                      _buildTimestamp(theme),
                    ],
                  ),
                ),
                const SizedBox(width: 12),
                _buildDeleteButton(context, ref, theme),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildLeadingIcon(ThemeData theme, bool selected) {
    
    return Container(
      width: 48,
      height: 48,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: selected
              ? [theme.colorScheme.primary.withValues(alpha: 0.8), theme.colorScheme.primary]
              : [theme.colorScheme.onSurface.withValues(alpha: 0.1), theme.colorScheme.onSurface.withValues(alpha: 0.2)],
        ),
      ),
      child: Icon(
        selected ? Icons.chat_bubble : Icons.chat_bubble_outline,
        color: selected ? theme.colorScheme.onPrimary : theme.colorScheme.onSurface,
        size: 24,
      ),
    );
  }

  Widget _buildTitle(ThemeData theme, bool selected) {
    final displayName = thread.name.isNotEmpty ? thread.name : "Unnamed Conversation";
    
    return Text(
      displayName,
      style: TextStyle(
        fontSize: 16,
        fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
        color: selected ? theme.colorScheme.primary : theme.colorScheme.onSurface,
        letterSpacing: 0.2,
      ),
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
    );
  }

  Widget _buildTimestamp(ThemeData theme) {
    // Use updatedAt if available, otherwise fall back to createdAt
    final timestamp = thread.updatedAt ?? thread.createdAt;
    
    if (timestamp == null) {
      return const SizedBox.shrink();
    }

    // Format the timestamp with date and time
    final formattedTime = DateFormat('MMM d, y • h:mm a').format(timestamp);

    return Text(
      formattedTime,
      style: TextStyle(
        fontSize: 13,
        color: theme.colorScheme.onSurfaceVariant.withValues(alpha: 0.7),
      ),
    );
  }

  Widget _buildDeleteButton(BuildContext context, WidgetRef ref, ThemeData theme) {
    return IconButton(
      icon: Icon(
        Icons.delete_outline,
        color: theme.colorScheme.onSurfaceVariant.withValues(alpha: 0.7),
        size: 20,
      ),
      tooltip: 'Delete Conversation',
      onPressed: () => _showDeleteConfirmation(context, ref, theme),
    );
  }

  Future<void> _showDeleteConfirmation(
    BuildContext context,
    WidgetRef ref,
    ThemeData theme,
  ) async {
    final displayName = thread.name.isNotEmpty ? thread.name : "this unnamed thread";
    
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Thread?'),
        content: Text(
          'Are you sure you want to delete "$displayName"? This action cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            style: TextButton.styleFrom(
              foregroundColor: theme.colorScheme.error,
            ),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirm == true && context.mounted) {
      try {
        await ref.read(threadsProvider.notifier).removeThread(thread.id);
      } catch (e) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Failed to delete thread: ${e.toString()}'),
              backgroundColor: theme.colorScheme.error,
            ),
          );
        }
      }
    }
  }
}