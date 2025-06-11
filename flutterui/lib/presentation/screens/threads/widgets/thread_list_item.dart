import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

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
    const mcAfeeRed = Color(0xFFC8102E);

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        color: Colors.white,
        border: Border.all(
          color: isSelected ? mcAfeeRed : Colors.grey.shade200,
          width: isSelected ? 2.0 : 1.0,
        ),
        boxShadow: [
          BoxShadow(
            color: isSelected 
                ? mcAfeeRed.withOpacity(0.15)
                : Colors.black.withOpacity(0.05),
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
                      if (thread.description != null && thread.description!.isNotEmpty) ...[
                        const SizedBox(height: 4),
                        _buildSubtitle(theme)!,
                      ],
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
    const mcAfeeRed = Color(0xFFC8102E);
    const darkBlue = Color(0xFF1A1A2E);
    
    return Container(
      width: 48,
      height: 48,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: selected
              ? [mcAfeeRed.withOpacity(0.8), mcAfeeRed]
              : [darkBlue.withOpacity(0.1), darkBlue.withOpacity(0.2)],
        ),
      ),
      child: Icon(
        selected ? Icons.chat_bubble : Icons.chat_bubble_outline,
        color: selected ? Colors.white : darkBlue,
        size: 24,
      ),
    );
  }

  Widget _buildTitle(ThemeData theme, bool selected) {
    const mcAfeeRed = Color(0xFFC8102E);
    const darkBlue = Color(0xFF1A1A2E);
    final displayName = thread.name.isNotEmpty ? thread.name : "Unnamed Conversation";
    
    return Text(
      displayName,
      style: TextStyle(
        fontSize: 16,
        fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
        color: selected ? mcAfeeRed : darkBlue,
        letterSpacing: 0.2,
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
      style: TextStyle(
        fontSize: 14,
        color: Colors.grey.shade600,
      ),
    );
  }

  Widget _buildDeleteButton(BuildContext context, WidgetRef ref, ThemeData theme) {
    return IconButton(
      icon: Icon(
        Icons.delete_outline,
        color: Colors.grey.shade400,
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