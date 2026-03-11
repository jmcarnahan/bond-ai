import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/providers/thread_provider.dart';
import 'package:flutterui/providers/config_provider.dart';
import 'package:flutterui/main.dart' show navigationIndexProvider, isUserNavigatingProvider;

/// Navigate to a specific thread in the Conversation screen.
///
/// Sets the selected thread, switches to the Conversation tab,
/// and clears the route stack back to the root.
void navigateToThread(WidgetRef ref, BuildContext context, String threadId) {
  ref.read(selectedThreadIdProvider.notifier).state = threadId;

  final navItems = ref.read(bottomNavItemsProvider);
  final chatIndex = navItems.indexWhere((item) => item.label == 'Conversation');

  ref.read(isUserNavigatingProvider.notifier).state = true;
  if (chatIndex != -1) {
    ref.read(navigationIndexProvider.notifier).state = chatIndex;
  }

  Navigator.pushNamedAndRemoveUntil(context, '/', (route) => false);

  Future.delayed(const Duration(milliseconds: 500), () {
    ref.read(isUserNavigatingProvider.notifier).state = false;
  });
}
