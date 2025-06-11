import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/providers/thread_provider.dart';
import 'thread_list_item.dart';

class ThreadsListView extends ConsumerWidget {
  final List<Thread> threads;
  final String? selectedThreadId;
  final void Function(Thread) onThreadSelected;

  const ThreadsListView({
    super.key,
    required this.threads,
    required this.selectedThreadId,
    required this.onThreadSelected,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Container(
      color: Colors.grey.shade50,
      child: RefreshIndicator(
        onRefresh: () => ref.read(threadsProvider.notifier).fetchThreads(),
        color: const Color(0xFFC8102E),
        child: ListView.builder(
          padding: const EdgeInsets.symmetric(vertical: 16),
          itemCount: threads.length,
          itemBuilder: (context, index) {
            // Show newest threads first
            final thread = threads[threads.length - 1 - index];
            final isSelected = thread.id == selectedThreadId;

            return ThreadListItem(
              thread: thread,
              isSelected: isSelected,
              onTap: () => onThreadSelected(thread),
            );
          },
        ),
      ),
    );
  }
}