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
    // Error listener is now handled in the ThreadsScreen build method
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
    logger.i('Selecting thread: ${thread.name} (${thread.id})');
    _notifier.selectThread(thread.id);
    Navigator.of(context).pop();
  }

  void showCreateThreadDialog() {
    // Import and use the dialog
    // This method is used for consistency but the actual dialog
    // is shown from the widget level
  }

  void navigateBack() {
    Navigator.of(context).pop();
  }
}