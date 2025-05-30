import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutterui/core/constants/app_constants.dart';
import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/providers/thread_provider.dart';
import 'thread_list_item.dart';

class ThreadsListView extends ConsumerWidget {
  final List<Thread> threads;
  final String? selectedThreadId;
  final bool isFromAgentChat;
  final void Function(Thread) onThreadSelected;

  const ThreadsListView({
    super.key,
    required this.threads,
    required this.selectedThreadId,
    required this.isFromAgentChat,
    required this.onThreadSelected,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return RefreshIndicator(
      onRefresh: () => ref.read(threadsProvider.notifier).fetchThreads(),
      child: ListView.separated(
        padding: AppSpacing.allMd,
        itemCount: threads.length,
        separatorBuilder: (context, index) => SizedBox(height: AppSpacing.xs),
        itemBuilder: (context, index) {
          // Show newest threads first
          final thread = threads[threads.length - 1 - index];
          final isSelected = thread.id == selectedThreadId;

          return ThreadListItem(
            thread: thread,
            isSelected: isSelected,
            isFromAgentChat: isFromAgentChat,
            onTap: () => onThreadSelected(thread),
          );
        },
      ),
    );
  }
}