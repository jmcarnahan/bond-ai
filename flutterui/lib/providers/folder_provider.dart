import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/data/models/folder_model.dart';
import 'package:flutterui/providers/agent_provider.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import '../core/utils/logger.dart';

/// All folders for the current user, sorted by sortOrder.
final foldersProvider = FutureProvider<List<FolderModel>>((ref) async {
  final folderService = ref.watch(folderServiceProvider);
  try {
    final folders = await folderService.getFolders();
    logger.i("[foldersProvider] Loaded ${folders.length} folders");
    // Defensive sort by sortOrder (backend already sorts, but be safe)
    folders.sort((a, b) => a.sortOrder.compareTo(b.sortOrder));
    return folders;
  } catch (e) {
    logger.e("[foldersProvider] Error fetching folders: ${e.toString()}");
    rethrow;
  }
});

/// Which folder is currently "open" on the agents screen (null = main screen).
final currentFolderProvider = StateProvider<String?>((ref) => null);

/// Whether the user is in reorder mode.
final isReorderModeProvider = StateProvider<bool>((ref) => false);

/// The name of the currently open folder (for breadcrumb display).
final currentFolderNameProvider = Provider<String?>((ref) {
  final currentFolderId = ref.watch(currentFolderProvider);
  if (currentFolderId == null) return null;

  final foldersAsync = ref.watch(foldersProvider);
  return foldersAsync.whenOrNull(
    data: (folders) {
      final match = folders.where((f) => f.id == currentFolderId);
      return match.isNotEmpty ? match.first.name : null;
    },
  );
});

/// Sort agents by sortOrder ascending, nulls at end (preserving original order for nulls).
List<AgentListItemModel> _sortBySortOrder(List<AgentListItemModel> agents) {
  final withOrder = agents.where((a) => a.sortOrder != null).toList()
    ..sort((a, b) => a.sortOrder!.compareTo(b.sortOrder!));
  final withoutOrder = agents.where((a) => a.sortOrder == null).toList();
  return [...withOrder, ...withoutOrder];
}

/// Agents visible in the current view, sorted by sortOrder:
/// - Main screen: agents NOT in any folder
/// - Inside a folder: agents in that folder
final visibleAgentsProvider = Provider<AsyncValue<List<AgentListItemModel>>>((ref) {
  final currentFolder = ref.watch(currentFolderProvider);
  final agentsAsync = ref.watch(agentsProvider);

  return agentsAsync.whenData((agents) {
    List<AgentListItemModel> filtered;
    if (currentFolder == null) {
      filtered = agents.where((a) => a.folderId == null).toList();
    } else {
      filtered = agents.where((a) => a.folderId == currentFolder).toList();
    }
    return _sortBySortOrder(filtered);
  });
});

/// Sidebar agents: only agents NOT in any folder, sorted by sortOrder.
final sidebarAgentsProvider = Provider<AsyncValue<List<AgentListItemModel>>>((ref) {
  final agentsAsync = ref.watch(agentsProvider);
  return agentsAsync.whenData((agents) {
    final filtered = agents.where((a) => a.folderId == null).toList();
    return _sortBySortOrder(filtered);
  });
});
