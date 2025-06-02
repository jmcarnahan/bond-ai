import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/providers/thread_provider.dart';
import 'widgets/threads_app_bar.dart';
import 'widgets/threads_list_view.dart';
import 'widgets/threads_empty_state.dart';
import 'widgets/threads_error_state.dart';
import 'widgets/threads_loading_state.dart';
import 'widgets/create_thread_dialog.dart';
import 'logic/threads_controller.dart';

class ThreadsScreen extends ConsumerStatefulWidget {
  final bool isFromAgentChat;

  const ThreadsScreen({super.key, this.isFromAgentChat = false});

  @override
  ConsumerState<ThreadsScreen> createState() => _ThreadsScreenState();
}

class _ThreadsScreenState extends ConsumerState<ThreadsScreen> {
  late final ThreadsController _controller;

  @override
  void initState() {
    super.initState();
    _controller = ThreadsController(ref: ref, context: context);
    _controller.initializeThreads();
  }

  void _showCreateThreadDialog() {
    showCreateThreadDialog(context);
  }

  void _onThreadSelected(Thread thread) {
    _controller.selectThread(thread);
  }

  void _onRetry() {
    _controller.refreshThreads();
  }

  void _onBack() {
    _controller.navigateBack();
  }

  @override
  Widget build(BuildContext context) {
    final threadsAsyncValue = ref.watch(threadsProvider);
    final selectedThreadId = ref.watch(selectedThreadIdProvider);
    final theme = Theme.of(context);

    ref.listen<String?>(threadErrorProvider, (previous, next) {
      if (next != null && context.mounted) {
        _controller.showErrorSnackBar(next);
        ref.read(threadErrorProvider.notifier).state = null;
      }
    });

    return Scaffold(
      appBar: ThreadsAppBar(onBack: _onBack),
      body: threadsAsyncValue.when(
        data: (threads) => _buildDataState(threads, selectedThreadId),
        loading: () => const ThreadsLoadingState(),
        error: (error, stack) => ThreadsErrorState(
          error: error.toString(),
          onRetry: _onRetry,
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _showCreateThreadDialog,
        backgroundColor: theme.colorScheme.primary,
        foregroundColor: theme.colorScheme.onPrimary,
        tooltip: 'Create New Thread',
        child: const Icon(Icons.add),
      ),
    );
  }

  Widget _buildDataState(List<Thread> threads, String? selectedThreadId) {
    if (threads.isEmpty) {
      return ThreadsEmptyState(onCreateThread: _showCreateThreadDialog);
    }

    return ThreadsListView(
      threads: threads,
      selectedThreadId: selectedThreadId,
      isFromAgentChat: widget.isFromAgentChat,
      onThreadSelected: _onThreadSelected,
    );
  }
}
