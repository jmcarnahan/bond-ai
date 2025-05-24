import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/providers/thread_provider.dart';
import 'package:flutterui/providers/thread_chat_provider.dart'; // For chatSessionNotifierProvider
// Ensure your ChatScreen path is correct if you use direct navigation
// import 'package:flutterui/presentation/screens/chat/chat_screen.dart';

class ThreadsScreen extends ConsumerWidget {
  const ThreadsScreen({super.key});

  void _showCreateThreadDialog(BuildContext context, WidgetRef ref) {
    final TextEditingController nameController = TextEditingController();
    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text('Create New Thread'),
          content: TextField(
            controller: nameController,
            decoration: const InputDecoration(hintText: "Optional thread name"),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Cancel'),
            ),
            TextButton(
              onPressed: () {
                final name = nameController.text.trim();
                ref
                    .read(threadsProvider.notifier)
                    .addThread(name: name.isNotEmpty ? name : null);
                Navigator.of(context).pop();
              },
              child: const Text('Create'),
            ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final threadsAsyncValue = ref.watch(threadsProvider);
    final activeChatSessionState = ref.watch(
      chatSessionNotifierProvider,
    ); // Watch the full state
    final String? activeThreadId =
        activeChatSessionState.currentThreadId; // Get currentThreadId

    // Listen for errors from threadProvider and show a SnackBar
    ref.listen<String?>(threadErrorProvider, (previous, next) {
      if (next != null) {
        ScaffoldMessenger.of(
          context,
        ).removeCurrentSnackBar(); // Remove any existing snackbar
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(next),
            backgroundColor: Colors.red,
            duration: const Duration(seconds: 3),
          ),
        );
        ref.read(threadErrorProvider.notifier).state =
            null; // Reset error after showing
      }
    });

    return Scaffold(
      appBar: AppBar(
        title: const Text('Threads'),
        // Optional: Add a refresh button if desired
        // actions: [
        //   IconButton(
        //     icon: const Icon(Icons.refresh),
        //     onPressed: () => ref.read(threadsProvider.notifier).fetchThreads(),
        //   ),
        // ],
      ),
      body: threadsAsyncValue.when(
        data: (threads) {
          if (threads.isEmpty) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Text('No threads yet. Create one!'),
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    icon: const Icon(Icons.add),
                    label: const Text('Create Thread'),
                    onPressed: () => _showCreateThreadDialog(context, ref),
                  ),
                ],
              ),
            );
          }
          return RefreshIndicator(
            onRefresh: () => ref.read(threadsProvider.notifier).fetchThreads(),
            child: ListView.builder(
              itemCount: threads.length,
              itemBuilder: (context, index) {
                // Display threads in reverse chronological order (newest first)
                final thread = threads[threads.length - 1 - index];
                final bool isActive = thread.id == activeThreadId;

                return ListTile(
                  tileColor:
                      isActive
                          ? Theme.of(
                            context,
                          ).colorScheme.primary.withOpacity(0.15)
                          : null,
                  leading:
                      isActive
                          ? Icon(
                            Icons.chat_bubble,
                            color: Theme.of(context).colorScheme.primary,
                          )
                          : const Icon(
                            Icons.chat_bubble_outline,
                          ), // Default icon or null
                  title: Text(
                    thread.name.isNotEmpty ? thread.name : "Unnamed Thread",
                    style:
                        isActive
                            ? TextStyle(
                              fontWeight: FontWeight.bold,
                              color: Theme.of(context).colorScheme.primary,
                            )
                            : null,
                  ),
                  subtitle:
                      thread.description != null &&
                              thread.description!.isNotEmpty
                          ? Text(
                            thread.description!,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          )
                          : null,
                  trailing: IconButton(
                    icon: const Icon(
                      Icons.delete_outline,
                      color: Colors.redAccent,
                    ),
                    tooltip: 'Delete Thread',
                    onPressed: () async {
                      final confirm = await showDialog<bool>(
                        context: context,
                        builder:
                            (context) => AlertDialog(
                              title: const Text('Delete Thread?'),
                              content: Text(
                                'Are you sure you want to delete "${thread.name.isNotEmpty ? thread.name : "this unnamed thread"}"? This action cannot be undone.',
                              ),
                              actions: [
                                TextButton(
                                  onPressed:
                                      () => Navigator.of(context).pop(false),
                                  child: const Text('Cancel'),
                                ),
                                TextButton(
                                  onPressed:
                                      () => Navigator.of(context).pop(true),
                                  child: const Text(
                                    'Delete',
                                    style: TextStyle(color: Colors.red),
                                  ),
                                ),
                              ],
                            ),
                      );
                      if (confirm == true) {
                        await ref
                            .read(threadsProvider.notifier)
                            .removeThread(thread.id);
                      }
                    },
                  ),
                  onTap: () {
                    ref
                        .read(chatSessionNotifierProvider.notifier)
                        .setCurrentThread(thread.id);
                    // Pop back to the previous screen (expected to be ChatScreen)
                    // which will then rebuild with the new thread's context.
                    Navigator.pop(context);
                  },
                );
              },
            ),
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error:
            (err, stack) => Center(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(
                      Icons.error_outline,
                      color: Colors.red,
                      size: 48,
                    ),
                    const SizedBox(height: 16),
                    Text(
                      'Error loading threads: ${err.toString()}',
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 16),
                    ElevatedButton.icon(
                      icon: const Icon(Icons.refresh),
                      label: const Text('Retry'),
                      onPressed:
                          () =>
                              ref.read(threadsProvider.notifier).fetchThreads(),
                    ),
                  ],
                ),
              ),
            ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _showCreateThreadDialog(context, ref),
        child: const Icon(Icons.add),
        tooltip: 'Create New Thread',
      ),
    );
  }
}
