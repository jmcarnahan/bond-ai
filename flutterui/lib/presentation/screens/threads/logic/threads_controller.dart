import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/providers/thread_provider.dart';
import '../../../../core/utils/logger.dart';

class ThreadsController {
  final WidgetRef ref;
  final BuildContext context;

  ThreadsController({
    required this.ref,
    required this.context,
  });

  ThreadsNotifier get _notifier => ref.read(threadsProvider.notifier);

  void initializeThreads() {
    // Always refresh threads when the screen is shown to get latest data
    // Already using addPostFrameCallback which is safe
    WidgetsBinding.instance.addPostFrameCallback((_) {
      refreshThreads();
    });
  }

  void showErrorSnackBar(String error) {
    ScaffoldMessenger.of(context)
      ..removeCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(error),
          duration: const Duration(seconds: 3),
          backgroundColor: Theme.of(context).colorScheme.error,
        ),
      );
  }

  Future<void> refreshThreads() async {
    try {
      await _notifier.fetchThreads();
    } catch (e) {
      logger.e('Error refreshing threads: $e');
    }
  }

  void selectThread(Thread thread) {
    logger.i('[ThreadsController]Selecting thread: ${thread.name} (${thread.id})');
    _notifier.selectThread(thread.id);
    // Don't use Navigator.pop() in mobile app - we use bottom navigation
    // The thread selection will trigger navigation through the provider
  }

  void showCreateThreadDialog() {}

  void navigateBack() {
    // Don't use Navigator.pop() in mobile app - we use bottom navigation
  }
}
