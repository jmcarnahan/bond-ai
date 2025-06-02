import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutterui/core/constants/app_constants.dart';
import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/providers/thread_provider.dart';

class ThreadListItem extends ConsumerWidget {
  final Thread thread;
  final bool isSelected;
  final bool isFromAgentChat;
  final VoidCallback onTap;

  const ThreadListItem({
    super.key,
    required this.thread,
    required this.isSelected,
    required this.isFromAgentChat,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);

    return Card(
      elevation: isSelected ? AppElevation.sm : AppElevation.xs,
      margin: AppSpacing.verticalSm,
      shape: RoundedRectangleBorder(
        borderRadius: AppBorderRadius.allMd,
        side: isSelected
            ? BorderSide(
                color: theme.colorScheme.primary,
                width: 1.5,
              )
            : BorderSide(
                color: theme.dividerColor,
                width: 0.5,
              ),
      ),
      child: ListTile(
        tileColor: isSelected
            ? theme.colorScheme.primary.withValues(alpha: 0.5)
            : null,
        leading: _buildLeadingIcon(theme),
        title: _buildTitle(theme),
        subtitle: _buildSubtitle(theme),
        trailing: _buildTrailing(context, ref, theme),
        onTap: onTap,
        contentPadding: AppSpacing.horizontalXl.add(AppSpacing.verticalMd),
      ),
    );
  }

  Widget _buildLeadingIcon(ThemeData theme) {
    return Icon(
      isSelected ? Icons.chat_bubble : Icons.chat_bubble_outline,
      color: isSelected
          ? theme.colorScheme.primary
          : theme.colorScheme.onSurface.withValues(alpha: 0.7),
      size: AppSizes.iconLg,
    );
  }

  Widget _buildTitle(ThemeData theme) {
    final displayName = thread.name.isNotEmpty ? thread.name : "Unnamed Thread";
    
    return Text(
      displayName,
      style: isSelected
          ? theme.textTheme.bodyLarge?.copyWith(
              fontWeight: FontWeight.bold,
              color: theme.colorScheme.primary,
            )
          : theme.textTheme.bodyLarge?.copyWith(
              color: theme.colorScheme.onSurface,
            ),
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
    );
  }

  Widget? _buildSubtitle(ThemeData theme) {
    if (thread.description == null || thread.description!.isEmpty) {
      return null;
    }

    return Text(
      thread.description!,
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
      style: theme.textTheme.bodyMedium?.copyWith(
        color: theme.colorScheme.onSurface.withValues(alpha: 0.7),
      ),
    );
  }

  Widget? _buildTrailing(BuildContext context, WidgetRef ref, ThemeData theme) {
    if (isFromAgentChat) return null;

    return IconButton(
      icon: Icon(
        Icons.delete_outline,
        color: theme.colorScheme.error.withValues(alpha: 0.8),
        size: AppSizes.iconMd,
      ),
      tooltip: 'Delete Thread',
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