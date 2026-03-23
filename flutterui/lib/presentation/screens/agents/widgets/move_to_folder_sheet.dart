import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/folder_model.dart';
import 'package:flutterui/providers/folder_provider.dart';

/// Bottom sheet allowing a user to pick a folder for an agent.
/// Returns the selected folder_id, or empty string '' for "Main Screen" (remove from folder).
/// Returns null if dismissed.
Future<String?> showMoveToFolderSheet(
  BuildContext context, {
  required WidgetRef ref,
  String? currentFolderId,
}) {
  return showModalBottomSheet<String>(
    context: context,
    builder: (context) => _MoveToFolderContent(
      currentFolderId: currentFolderId,
    ),
  );
}

class _MoveToFolderContent extends ConsumerWidget {
  final String? currentFolderId;

  const _MoveToFolderContent({this.currentFolderId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final foldersAsync = ref.watch(foldersProvider);
    final colorScheme = Theme.of(context).colorScheme;

    return SafeArea(
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxHeight: MediaQuery.of(context).size.height * 0.6,
        ),
        child: SingleChildScrollView(
          child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: Text(
              'Move to folder',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
            ),
          ),
          // Main Screen option (remove from folder)
          ListTile(
            leading: const Icon(Icons.home_outlined),
            title: const Text('Main Screen'),
            selected: currentFolderId == null,
            selectedColor: colorScheme.primary,
            onTap: () => Navigator.pop(context, ''),
          ),
          const Divider(height: 1),
          // Folder list
          foldersAsync.when(
            data: (folders) {
              if (folders.isEmpty) {
                return const Padding(
                  padding: EdgeInsets.all(16),
                  child: Text('No folders yet. Create one from the agents screen.'),
                );
              }
              return ListView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: folders.length,
                itemBuilder: (context, index) {
                  final folder = folders[index];
                  return ListTile(
                    leading: const Icon(Icons.folder_rounded),
                    title: Text(folder.name),
                    trailing: Text(
                      '${folder.agentCount}',
                      style: TextStyle(color: colorScheme.onSurfaceVariant),
                    ),
                    selected: folder.id == currentFolderId,
                    selectedColor: colorScheme.primary,
                    onTap: () => Navigator.pop(context, folder.id),
                  );
                },
              );
            },
            loading: () => const Padding(
              padding: EdgeInsets.all(16),
              child: Center(child: CircularProgressIndicator()),
            ),
            error: (_, __) => const Padding(
              padding: EdgeInsets.all(16),
              child: Text('Failed to load folders.'),
            ),
          ),
          const SizedBox(height: 8),
        ],
      ),
        ),
      ),
    );
  }
}
