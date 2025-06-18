import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/providers/thread_provider.dart';
import 'package:flutterui/presentation/widgets/app_drawer.dart';
import 'widgets/threads_app_bar.dart';
import 'widgets/threads_list_view.dart';
import 'widgets/threads_empty_state.dart';
import 'widgets/threads_loading_state.dart';
import 'widgets/create_thread_dialog.dart';
import 'logic/threads_controller.dart';
import 'package:flutterui/core/error_handling/error_handling_mixin.dart';
import 'package:flutterui/core/error_handling/error_handler.dart';

class ThreadsScreen extends ConsumerStatefulWidget {
  const ThreadsScreen({super.key});

  @override
  ConsumerState<ThreadsScreen> createState() => _ThreadsScreenState();
}

class _ThreadsScreenState extends ConsumerState<ThreadsScreen> with ErrorHandlingMixin {
  late final ThreadsController _controller;

  @override
  void initState() {
    super.initState();
    _controller = ThreadsController(ref: ref, context: context);
    _controller.initializeThreads();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Refresh threads whenever we navigate to this screen
    // Use Future to avoid modifying provider during build
    Future.microtask(() => _controller.refreshThreads());
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

  @override
  Widget build(BuildContext context) {
    final threadsAsyncValue = ref.watch(threadsProvider);
    final selectedThreadId = ref.watch(selectedThreadIdProvider);

    ref.listen<String?>(threadErrorProvider, (previous, next) {
      if (next != null && context.mounted) {
        _controller.showErrorSnackBar(next);
        ref.read(threadErrorProvider.notifier).state = null;
      }
    });

    return Scaffold(
      drawer: const AppDrawer(),
      appBar: const ThreadsAppBar(),
      body: threadsAsyncValue.when(
        data: (threads) => _buildDataState(threads, selectedThreadId),
        loading: () => const ThreadsLoadingState(),
        error: (error, stack) {
          // Use automatic error detection and handling
          WidgetsBinding.instance.addPostFrameCallback((_) {
            handleAutoError(error, ref, serviceErrorMessage: 'Failed to load threads');
          });
          
          // Check if this is an authentication error to show appropriate UI
          final appError = error is Exception ? AppError.fromException(error) : null;
          if (appError?.type == ErrorType.authentication) {
            // Show loading while redirecting to login
            return const Center(
              child: CircularProgressIndicator(),
            );
          }
          
          // Show a fallback UI with retry button for other errors
          return Center(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20.0, vertical: 40.0),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(
                    Icons.refresh,
                    size: 64,
                  ),
                  const SizedBox(height: 20),
                  const Text(
                    'Unable to Load Threads',
                    style: TextStyle(fontSize: 18),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Tap below to try again',
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 20),
                  ElevatedButton.icon(
                    icon: const Icon(Icons.refresh),
                    label: const Text('Retry'),
                    onPressed: _onRetry,
                  ),
                ],
              ),
            ),
          );
        },
      ),
      floatingActionButton: Container(
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          boxShadow: [
            BoxShadow(
              color: Theme.of(context).colorScheme.primary.withOpacity(0.3),
              blurRadius: 12,
              spreadRadius: 2,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: FloatingActionButton(
          onPressed: _showCreateThreadDialog,
          backgroundColor: Theme.of(context).colorScheme.primary,
          foregroundColor: Colors.white,
          tooltip: 'Start New Conversation',
          elevation: 0,
          child: const Icon(Icons.add_comment_rounded, size: 28),
        ),
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
      onThreadSelected: _onThreadSelected,
    );
  }
}
