import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/firestore_provider.dart' as firestore;
import '../../core/utils/logger.dart';

/// Widget that listens for incoming Firestore messages and processes them
class FirestoreListener extends ConsumerStatefulWidget {
  final Widget child;

  const FirestoreListener({
    super.key,
    required this.child,
  });

  @override
  ConsumerState<FirestoreListener> createState() => _FirestoreListenerState();
}

class _FirestoreListenerState extends ConsumerState<FirestoreListener> {
  @override
  void initState() {
    super.initState();
    final isEnabled = ref.read(firestore.isFirestoreEnabledProvider);
    if (isEnabled) {
      logger.i('[FirestoreListener] Widget initialized - Firestore listener ACTIVE');
    } else {
      logger.i('[FirestoreListener] Widget initialized - Firestore listener INACTIVE (no FIRESTORE_DATABASE_ID)');
    }
  }

  @override
  Widget build(BuildContext context) {
    final isEnabled = ref.watch(firestore.isFirestoreEnabledProvider);

    // If Firestore is not enabled, just return the child widget
    if (!isEnabled) {
      return widget.child;
    }

    // Watch the stream to ensure it stays active
    ref.watch(firestore.incomingMessageStreamProvider);

    // Listen to incoming messages stream
    ref.listen(firestore.incomingMessageStreamProvider, (previous, next) {
      if (next.hasValue && next.value != null) {
        // Process the message
        ref.read(firestore.messageProcessorProvider.notifier).processMessage(next.value!);
      } else if (next.hasError) {
        logger.e('[FirestoreListener] Stream error: ${next.error}');
      }
    });

    return widget.child;
  }
}
