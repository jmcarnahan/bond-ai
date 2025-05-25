import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/core/theme/mcafee_theme.dart'; // For CustomColors
import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/main.dart'; // For appThemeProvider
import 'package:flutterui/providers/thread_provider.dart';
import 'package:flutterui/providers/thread_chat/thread_chat_providers.dart'; // For chatSessionNotifierProvider
// Ensure your ChatScreen path is correct if you use direct navigation
// import 'package:flutterui/presentation/screens/chat/chat_screen.dart';

class ThreadsScreen extends ConsumerWidget {
  final bool isFromAgentChat;

  const ThreadsScreen({super.key, this.isFromAgentChat = false});

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
    // Get the globally selected thread ID
    final String? globalSelectedThreadId = ref.watch(selectedThreadIdProvider); 
    final ThemeData theme = Theme.of(context); // Get theme data
    final appTheme = ref.watch(appThemeProvider); // Get appTheme for logo
    final customColors = theme.extension<CustomColors>(); // Get custom colors
    final appBarBackgroundColor = customColors?.brandingSurface ?? McAfeeTheme.mcafeeDarkBrandingSurface;


    // Listen for errors from threadProvider and show a SnackBar
    ref.listen<String?>(threadErrorProvider, (previous, next) {
      if (next != null) {
        ScaffoldMessenger.of(
          context,
        ).removeCurrentSnackBar(); // Remove any existing snackbar
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(next),
            // backgroundColor: Colors.red, // Uses theme.snackBarTheme.backgroundColor
            duration: const Duration(seconds: 3),
          ),
        );
        ref.read(threadErrorProvider.notifier).state =
            null; // Reset error after showing
      }
    });

    return Scaffold(
      appBar: AppBar(
        backgroundColor: appBarBackgroundColor,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.white),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Image.asset(
              appTheme.logoIcon,
              height: 24,
              width: 24,
            ),
            const SizedBox(width: 8),
            Text(
              'Threads',
              style: theme.textTheme.titleLarge?.copyWith(color: Colors.white),
            ),
          ],
        ),
        // centerTitle: true, // Already set in McAfeeTheme's appBarTheme
        // Optional: Add a refresh button if desired
        // actions: [
        //   IconButton(
        //     icon: const Icon(Icons.refresh, color: Colors.white),
        //     onPressed: () => ref.read(threadsProvider.notifier).fetchThreads(),
        //   ),
        // ],
      ),
      body: Padding( // Added padding around the body content
        padding: const EdgeInsets.all(8.0),
        child: threadsAsyncValue.when(
          data: (threads) {
            if (threads.isEmpty) {
              return Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      'No threads yet. Create one!',
                      style: theme.textTheme.bodyLarge,
                    ),
                    const SizedBox(height: 16),
                    ElevatedButton.icon(
                      icon: const Icon(Icons.add),
                      label: const Text('Create Thread'),
                      onPressed: () => _showCreateThreadDialog(context, ref),
                      // ElevatedButton uses theme by default
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
                  final thread = threads[threads.length - 1 - index];
                  // Determine if this thread is the globally selected one
                  final bool isActive = thread.id == globalSelectedThreadId; 

                  return Card( // Wrap ListTile in a Card for better separation and styling
                    elevation: isActive ? 2 : 1,
                    margin: const EdgeInsets.symmetric(vertical: 4.0, horizontal: 0),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8.0),
                      side: isActive
                          ? BorderSide(color: theme.colorScheme.primary, width: 1.5)
                          : BorderSide(color: theme.dividerColor, width: 0.5),
                    ),
                    child: ListTile(
                      tileColor: isActive
                          ? theme.colorScheme.primary.withOpacity(0.05) // Softer highlight
                          : null, // Use card background
                      leading: Icon(
                        isActive ? Icons.chat_bubble : Icons.chat_bubble_outline,
                        color: isActive
                            ? theme.colorScheme.primary
                            : theme.colorScheme.onSurface.withOpacity(0.7),
                        size: 28,
                      ),
                      title: Text(
                        thread.name.isNotEmpty ? thread.name : "Unnamed Thread",
                        style: isActive
                            ? theme.textTheme.bodyLarge?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: theme.colorScheme.primary,
                              )
                            : theme.textTheme.bodyLarge?.copyWith(
                                color: theme.colorScheme.onSurface,
                              ),
                      ),
                      subtitle: thread.description != null &&
                              thread.description!.isNotEmpty
                          ? Text(
                              thread.description!,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: theme.textTheme.bodyMedium?.copyWith(
                                color: theme.colorScheme.onSurface.withOpacity(0.7),
                              ),
                            )
                          : null,
                      trailing: isFromAgentChat
                          ? null // Hide delete button if from agent chat
                          : IconButton(
                              icon: Icon(
                                Icons.delete_outline,
                                color: theme.colorScheme.error.withOpacity(0.8),
                              ),
                              tooltip: 'Delete Thread',
                              onPressed: () async {
                                final confirm = await showDialog<bool>(
                                  context: context,
                                  builder: (context) => AlertDialog(
                                    title: const Text('Delete Thread?'),
                                    content: Text(
                                      'Are you sure you want to delete "${thread.name.isNotEmpty ? thread.name : "this unnamed thread"}"? This action cannot be undone.',
                                    ),
                                    actions: [
                                      TextButton(
                                        onPressed: () =>
                                            Navigator.of(context).pop(false),
                                        child: const Text('Cancel'),
                                      ),
                                      TextButton(
                                        onPressed: () =>
                                            Navigator.of(context).pop(true),
                                        child: Text(
                                          'Delete',
                                          style: TextStyle(
                                              color: theme.colorScheme.error),
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
                    // Set this thread as the globally selected one
                    ref.read(threadsProvider.notifier).selectThread(thread.id);
                    // Pop back to the previous screen (e.g., ChatScreen or HomeScreen)
                    // The previous screen should react to the change in selectedThreadProvider
                    Navigator.pop(context); 
                  },
                ),
              );
            },
          ),
        );
      },
      loading: () => Center(
            child: CircularProgressIndicator(
              valueColor: AlwaysStoppedAnimation<Color>(theme.colorScheme.primary),
            ),
          ),
      error: (err, stack) => Center(
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    Icons.error_outline,
                    color: theme.colorScheme.error,
                    size: 48,
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'Error loading threads: ${err.toString()}',
                    textAlign: TextAlign.center,
                    style: theme.textTheme.bodyLarge
                        ?.copyWith(color: theme.colorScheme.error),
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    icon: const Icon(Icons.refresh),
                    label: const Text('Retry'),
                    onPressed: () =>
                        ref.read(threadsProvider.notifier).fetchThreads(),
                    // ElevatedButton uses theme by default
                  ),
                ],
              ),
            ),
          ),
    ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _showCreateThreadDialog(context, ref),
        backgroundColor: theme.colorScheme.primary,
        foregroundColor: theme.colorScheme.onPrimary,
        child: const Icon(Icons.add),
        tooltip: 'Create New Thread',
      ),
    );
  }
}
