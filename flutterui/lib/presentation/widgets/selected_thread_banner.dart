import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/providers/thread_provider.dart';

class SelectedThreadBanner extends ConsumerWidget {
  const SelectedThreadBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final selectedThread = ref.watch(selectedThreadProvider);

    if (selectedThread == null) {
      return const SizedBox.shrink();
    }

    String threadDisplayName = selectedThread.name;
    if (threadDisplayName.isEmpty) {
      threadDisplayName = 'Thread ID: ${selectedThread.id}';
    }

    return Material(
      elevation: 4.0,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
        height: 50,
        color: Colors.green.withAlpha((0.5 * 255).round()),
        child: Center(
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Flexible(
                child: Text(
                  'Active Thread: $threadDisplayName',
                  style: TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                  ),
                  overflow: TextOverflow.ellipsis,
                  maxLines: 1,
                ),
              ),
              MouseRegion(
                cursor: SystemMouseCursors.click,
                child: GestureDetector(
                  onTap: () {
                    ref.read(threadsProvider.notifier).deselectThread();
                  },
                  child: Icon(
                    Icons.close,
                    color: Colors.white,
                  ),
                ),
              )
            ],
          ),
        ),
    )
    );
  }
}
