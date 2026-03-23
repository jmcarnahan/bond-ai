import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/data/models/folder_model.dart';
import 'package:flutterui/providers/agent_provider.dart';
import 'package:flutterui/providers/folder_provider.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import 'package:flutterui/providers/core_providers.dart';
import 'package:flutterui/presentation/screens/agents/widgets/agent_card.dart';
import 'package:flutterui/presentation/widgets/agent_icon.dart';
import 'package:flutterui/presentation/screens/agents/widgets/folder_card.dart';
import 'package:flutterui/presentation/screens/agents/widgets/folder_dialogs.dart';
import 'package:flutterui/presentation/screens/agents/widgets/move_to_folder_sheet.dart';
import 'package:flutterui/presentation/screens/agents/create_agent_screen.dart';
import 'package:flutterui/core/error_handling/error_handling_mixin.dart';
import 'package:flutterui/core/error_handling/error_handler.dart';
import 'package:flutterui/presentation/widgets/app_drawer.dart';
import 'package:flutterui/presentation/widgets/connection_status_indicator.dart';
import 'package:flutterui/core/utils/logger.dart';

class AgentsScreen extends ConsumerStatefulWidget {
  const AgentsScreen({super.key});

  @override
  ConsumerState<AgentsScreen> createState() => _AgentsScreenState();
}

class _AgentsScreenState extends ConsumerState<AgentsScreen> with ErrorHandlingMixin {
  // Local state for reorder mode — shadows provider data during reorder
  List<AgentListItemModel>? _localAgents;
  List<FolderModel>? _localFolders;

  void _enterReorderMode(List<AgentListItemModel> agents, List<FolderModel> folders) {
    setState(() {
      _localAgents = List.from(agents);
      _localFolders = List.from(folders);
    });
    ref.read(isReorderModeProvider.notifier).state = true;
  }

  void _exitReorderMode() {
    setState(() {
      _localAgents = null;
      _localFolders = null;
    });
    ref.read(isReorderModeProvider.notifier).state = false;
    // Sync with server to pick up persisted order
    ref.invalidate(agentsProvider);
    ref.invalidate(foldersProvider);
  }

  void _navigateToCreateAgent({String? agentId}) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => CreateAgentScreen(agentId: agentId),
      ),
    ).then((_) {
      ref.invalidate(agentsProvider);
      ref.invalidate(foldersProvider);
    });
  }

  Future<void> _createFolder() async {
    final name = await showCreateFolderDialog(context);
    if (name == null || name.isEmpty) return;
    try {
      final folderService = ref.read(folderServiceProvider);
      await folderService.createFolder(name);
      ref.invalidate(foldersProvider);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(_humanizeError(e, 'create folder'))),
        );
      }
    }
  }

  Future<void> _renameFolder(String folderId, String currentName) async {
    final newName = await showRenameFolderDialog(context, currentName);
    if (newName == null || newName.isEmpty || newName == currentName) return;
    try {
      final folderService = ref.read(folderServiceProvider);
      await folderService.updateFolder(folderId, name: newName);
      ref.invalidate(foldersProvider);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(_humanizeError(e, 'rename folder'))),
        );
      }
    }
  }

  Future<void> _deleteFolder(String folderId, String folderName) async {
    final confirmed = await showDeleteFolderDialog(context, folderName);
    if (confirmed != true) return;

    if (ref.read(currentFolderProvider) == folderId) {
      ref.read(currentFolderProvider.notifier).state = null;
    }

    try {
      final folderService = ref.read(folderServiceProvider);
      await folderService.deleteFolder(folderId);
      ref.invalidate(foldersProvider);
      ref.invalidate(agentsProvider);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(_humanizeError(e, 'delete folder'))),
        );
      }
    }
  }

  Future<void> _assignAgentToFolder(String agentId, String? folderId) async {
    try {
      final folderService = ref.read(folderServiceProvider);
      await folderService.assignAgent(agentId, folderId);
      ref.invalidate(agentsProvider);
      ref.invalidate(foldersProvider);
    } catch (e) {
      logger.e("[AgentsScreen] Error assigning agent to folder: $e");
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(_humanizeError(e, 'move agent'))),
        );
      }
    }
  }

  Future<void> _reorderAgents(int oldIndex, int newIndex) async {
    if (_localAgents == null) return;
    final currentFolder = ref.read(currentFolderProvider);

    setState(() {
      if (newIndex > oldIndex) newIndex -= 1;
      final item = _localAgents!.removeAt(oldIndex);
      _localAgents!.insert(newIndex, item);
    });

    try {
      final folderService = ref.read(folderServiceProvider);
      await folderService.reorderAgents(
        currentFolder,
        _localAgents!.map((a) => a.id).toList(),
      );
    } catch (e) {
      // On failure, revert to server state
      _exitReorderMode();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(_humanizeError(e, 'reorder agents'))),
        );
      }
    }
  }

  Future<void> _reorderFolders(int oldIndex, int newIndex) async {
    if (_localFolders == null) return;

    setState(() {
      if (newIndex > oldIndex) newIndex -= 1;
      final item = _localFolders!.removeAt(oldIndex);
      _localFolders!.insert(newIndex, item);
    });

    try {
      final folderService = ref.read(folderServiceProvider);
      await folderService.reorderFolders(
        _localFolders!.map((f) => f.id).toList(),
      );
    } catch (e) {
      _exitReorderMode();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(_humanizeError(e, 'reorder folders'))),
        );
      }
    }
  }

  String _humanizeError(Object e, String action) {
    final msg = e.toString();
    if (msg.contains('409')) return 'A folder with that name already exists.';
    if (msg.contains('404')) return 'Folder not found. It may have been deleted.';
    if (msg.contains('400')) return 'Invalid input. Please check and try again.';
    if (msg.contains('SocketException') || msg.contains('ClientException')) {
      return 'Network error. Please check your connection.';
    }
    return 'Failed to $action. Please try again.';
  }

  Future<void> _showMoveToFolder(String agentId, String? currentFolderId) async {
    final result = await showMoveToFolderSheet(
      context,
      ref: ref,
      currentFolderId: currentFolderId,
    );
    if (result == null) return;
    final targetFolderId = result.isEmpty ? null : result;
    if (targetFolderId == currentFolderId) return;
    await _assignAgentToFolder(agentId, targetFolderId);
  }

  @override
  Widget build(BuildContext context) {
    final agentsAsyncValue = ref.watch(agentsProvider);
    final foldersAsyncValue = ref.watch(foldersProvider);
    final visibleAgents = ref.watch(visibleAgentsProvider);
    final currentFolderId = ref.watch(currentFolderProvider);
    final currentFolderName = ref.watch(currentFolderNameProvider);
    final isReorderMode = ref.watch(isReorderModeProvider);
    final appTheme = ref.watch(appThemeProvider);

    final ThemeData currentThemeData = Theme.of(context);
    final TextTheme textTheme = currentThemeData.textTheme;
    final ColorScheme colorScheme = currentThemeData.colorScheme;

    final bool isInsideFolder = currentFolderId != null;

    return Scaffold(
      backgroundColor: colorScheme.surface,
      appBar: PreferredSize(
        preferredSize: const Size.fromHeight(kToolbarHeight + 8),
        child: Container(
          decoration: BoxDecoration(
            color: colorScheme.surface,
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.1),
                blurRadius: 4,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          child: AppBar(
            title: isInsideFolder
                ? Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      InkWell(
                        onTap: () {
                          _exitReorderMode();
                          ref.read(currentFolderProvider.notifier).state = null;
                        },
                        child: Text(
                          'Agents',
                          style: TextStyle(
                            color: colorScheme.primary,
                            fontSize: 18,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 8),
                        child: Icon(
                          Icons.chevron_right,
                          color: colorScheme.onSurfaceVariant,
                          size: 20,
                        ),
                      ),
                      Flexible(
                        child: Text(
                          currentFolderName ?? '',
                          style: TextStyle(
                            color: colorScheme.onSurface,
                            fontSize: 18,
                            fontWeight: FontWeight.w600,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  )
                : Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: colorScheme.onSurface.withValues(alpha: 0.1),
                        ),
                        child: Image.asset(
                          appTheme.logoIcon,
                          height: 24,
                          width: 24,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            'Agents',
                            style: TextStyle(
                              color: colorScheme.onSurface,
                              fontSize: 18,
                              fontWeight: FontWeight.w600,
                              letterSpacing: 0.5,
                            ),
                          ),
                          Text(
                            appTheme.brandingMessage,
                            style: TextStyle(
                              color: colorScheme.onSurface.withValues(alpha: 0.7),
                              fontSize: 12,
                              fontWeight: FontWeight.w400,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
            centerTitle: true,
            backgroundColor: Colors.transparent,
            elevation: 0,
            leading: isInsideFolder
                ? IconButton(
                    icon: Icon(Icons.arrow_back, color: colorScheme.onSurface),
                    onPressed: () {
                      _exitReorderMode();
                      ref.read(currentFolderProvider.notifier).state = null;
                    },
                  )
                : Builder(
                    builder: (context) => IconButton(
                      icon: Icon(Icons.menu, color: colorScheme.onSurface),
                      onPressed: () => Scaffold.of(context).openDrawer(),
                    ),
                  ),
            actions: [
              // Reorder mode toggle
              Tooltip(
                message: isReorderMode ? 'Done Reordering' : 'Reorder',
                child: IconButton(
                  icon: Icon(
                    isReorderMode ? Icons.check : Icons.swap_vert,
                    color: isReorderMode ? colorScheme.primary : colorScheme.onSurfaceVariant,
                  ),
                  onPressed: () {
                    if (isReorderMode) {
                      _exitReorderMode();
                    } else {
                      final agents = visibleAgents.valueOrNull ?? [];
                      final folders = isInsideFolder
                          ? <FolderModel>[]
                          : (foldersAsyncValue.valueOrNull ?? <FolderModel>[]);
                      _enterReorderMode(agents, folders);
                    }
                  },
                ),
              ),
              // Hide create buttons in reorder mode
              if (!isReorderMode) ...[
                if (!isInsideFolder)
                  Tooltip(
                    message: 'New Folder',
                    child: IconButton(
                      icon: Icon(Icons.create_new_folder_outlined, color: colorScheme.onSurfaceVariant),
                      onPressed: _createFolder,
                    ),
                  ),
                Tooltip(
                  message: 'New Agent',
                  child: IconButton(
                    icon: Icon(Icons.person_add_alt_1_outlined, color: colorScheme.onSurfaceVariant),
                    onPressed: () => _navigateToCreateAgent(),
                  ),
                ),
              ],
              const ConnectionStatusIndicator(),
              const SizedBox(width: 8),
            ],
          ),
        ),
      ),
      drawer: isInsideFolder ? null : const AppDrawer(),
      body: _buildBody(
        agentsAsyncValue: agentsAsyncValue,
        foldersAsyncValue: foldersAsyncValue,
        visibleAgents: visibleAgents,
        isInsideFolder: isInsideFolder,
        isReorderMode: isReorderMode,
        textTheme: textTheme,
        colorScheme: colorScheme,
      ),
    );
  }

  Widget _buildBody({
    required AsyncValue agentsAsyncValue,
    required AsyncValue foldersAsyncValue,
    required AsyncValue visibleAgents,
    required bool isInsideFolder,
    required bool isReorderMode,
    required TextTheme textTheme,
    required ColorScheme colorScheme,
  }) {
    // Show loading if agents are still loading
    if (agentsAsyncValue is AsyncLoading) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(
              valueColor: AlwaysStoppedAnimation<Color>(colorScheme.primary),
            ),
            const SizedBox(height: 20),
            Text(
              'Loading Agents...',
              style: textTheme.bodyLarge?.copyWith(
                color: colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      );
    }

    // Show error
    if (agentsAsyncValue is AsyncError) {
      final err = (agentsAsyncValue as AsyncError).error;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        handleAutoError(err, ref, serviceErrorMessage: 'Failed to load agents');
      });

      final appError = err is Exception ? AppError.fromException(err) : null;
      if (appError?.type == ErrorType.authentication) {
        return const Center(child: CircularProgressIndicator());
      }

      return Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 32.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.error_outline, size: 64, color: colorScheme.error),
              const SizedBox(height: 20),
              Text(
                'Unable to Load Agents',
                style: textTheme.headlineSmall?.copyWith(color: colorScheme.onSurface),
              ),
              const SizedBox(height: 8),
              Text(
                'Tap below to try again',
                textAlign: TextAlign.center,
                style: textTheme.bodyMedium?.copyWith(color: colorScheme.onSurfaceVariant),
              ),
              const SizedBox(height: 20),
              ElevatedButton.icon(
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
                onPressed: () {
                  ref.invalidate(agentsProvider);
                  ref.invalidate(foldersProvider);
                },
              ),
            ],
          ),
        ),
      );
    }

    return visibleAgents.when(
      data: (agents) {
        final folders = isInsideFolder
            ? <FolderModel>[]
            : (foldersAsyncValue.valueOrNull ?? <FolderModel>[]);

        if (agents.isEmpty && folders.isEmpty) {
          return Center(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 32.0),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    isInsideFolder ? Icons.folder_open : Icons.smart_toy_outlined,
                    size: 80,
                    color: colorScheme.onSurfaceVariant.withValues(alpha: 0.5),
                  ),
                  const SizedBox(height: 24),
                  Text(
                    isInsideFolder ? 'Empty Folder' : 'No Agents Yet',
                    style: textTheme.headlineSmall?.copyWith(
                      color: colorScheme.onSurface,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    isInsideFolder
                        ? 'Drag agents here or use "Move to folder" from the main screen'
                        : 'Create your first AI assistant to get started',
                    textAlign: TextAlign.center,
                    style: textTheme.bodyMedium?.copyWith(
                      color: colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
          );
        }

        if (isReorderMode && _localAgents != null) {
          return _buildReorderGrid(
            _localFolders ?? [],
            _localAgents!,
            isInsideFolder,
            colorScheme,
          );
        } else {
          return _buildNormalGrid(folders, agents, isInsideFolder, colorScheme);
        }
      },
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (_, __) => const SizedBox.shrink(),
    );
  }

  // ==================== REORDER MODE ====================

  Widget _buildReorderGrid(
    List<FolderModel> folders,
    List<AgentListItemModel> agents,
    bool isInsideFolder,
    ColorScheme colorScheme,
  ) {
    return ListView(
      padding: const EdgeInsets.all(16.0),
      children: [
        // Folders section (only on main screen)
        if (folders.isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text(
              'Folders',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: colorScheme.onSurfaceVariant,
                letterSpacing: 0.5,
              ),
            ),
          ),
          ReorderableListView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            buildDefaultDragHandles: false,
            itemCount: folders.length,
            onReorder: _reorderFolders,
            itemBuilder: (context, index) {
              final folder = folders[index];
              return _buildReorderFolderTile(folder, index, colorScheme);
            },
          ),
          const SizedBox(height: 16),
        ],
        // Agents section
        if (agents.isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text(
              'Agents',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: colorScheme.onSurfaceVariant,
                letterSpacing: 0.5,
              ),
            ),
          ),
          ReorderableListView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            buildDefaultDragHandles: false,
            itemCount: agents.length,
            onReorder: _reorderAgents,
            itemBuilder: (context, index) {
              final agent = agents[index];
              return _buildReorderAgentTile(agent, index, colorScheme);
            },
          ),
        ],
      ],
    );
  }

  Widget _buildReorderFolderTile(FolderModel folder, int index, ColorScheme colorScheme) {
    return Card(
      key: ValueKey('folder_${folder.id}'),
      margin: const EdgeInsets.symmetric(vertical: 4),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: BorderSide(color: colorScheme.outlineVariant.withValues(alpha: 0.3)),
      ),
      child: ListTile(
        leading: Icon(Icons.folder_rounded, color: colorScheme.primary, size: 32),
        title: Text(folder.name, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text('${folder.agentCount} agent${folder.agentCount == 1 ? '' : 's'}'),
        trailing: ReorderableDragStartListener(
          index: index,
          child: Padding(
            padding: const EdgeInsets.all(8.0),
            child: Icon(Icons.drag_handle, color: colorScheme.onSurfaceVariant),
          ),
        ),
      ),
    );
  }

  Widget _buildReorderAgentTile(AgentListItemModel agent, int index, ColorScheme colorScheme) {
    return Card(
      key: ValueKey('agent_${agent.id}'),
      margin: const EdgeInsets.symmetric(vertical: 4),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: BorderSide(color: colorScheme.outlineVariant.withValues(alpha: 0.3)),
      ),
      child: ListTile(
        leading: AgentIcon(
          agentName: agent.name,
          metadata: agent.metadata,
          size: 36,
          showBackground: true,
          isSelected: false,
        ),
        title: Text(agent.name, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: agent.description != null && agent.description!.isNotEmpty
            ? Text(agent.description!, maxLines: 1, overflow: TextOverflow.ellipsis)
            : null,
        trailing: ReorderableDragStartListener(
          index: index,
          child: Padding(
            padding: const EdgeInsets.all(8.0),
            child: Icon(Icons.drag_handle, color: colorScheme.onSurfaceVariant),
          ),
        ),
      ),
    );
  }

  // ==================== NORMAL MODE ====================

  Widget _buildNormalGrid(
    List<FolderModel> folders,
    List<AgentListItemModel> agents,
    bool isInsideFolder,
    ColorScheme colorScheme,
  ) {
    final totalCount = folders.length + agents.length;

    return Column(
      children: [
        // "Remove from folder" drop zone when inside a folder
        if (isInsideFolder)
          DragTarget<String>(
            onWillAcceptWithDetails: (_) => true,
            onAcceptWithDetails: (details) {
              _assignAgentToFolder(details.data, null);
            },
            builder: (context, candidateData, rejectedData) {
              final isActive = candidateData.isNotEmpty;
              return AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 16),
                decoration: BoxDecoration(
                  color: isActive
                      ? colorScheme.errorContainer
                      : colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
                  border: Border(
                    bottom: BorderSide(
                      color: isActive
                          ? colorScheme.error
                          : colorScheme.outlineVariant.withValues(alpha: 0.3),
                      width: isActive ? 2 : 1,
                    ),
                  ),
                ),
                alignment: Alignment.center,
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      isActive ? Icons.output_rounded : Icons.info_outline,
                      color: isActive
                          ? colorScheme.onErrorContainer
                          : colorScheme.onSurfaceVariant,
                      size: 18,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      isActive
                          ? 'Drop to move back to main screen'
                          : 'Drag agents here to move them out of this folder',
                      style: TextStyle(
                        color: isActive
                            ? colorScheme.onErrorContainer
                            : colorScheme.onSurfaceVariant,
                        fontWeight: isActive ? FontWeight.w600 : FontWeight.w400,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
        // Grid
        Expanded(
          child: GridView.builder(
            padding: const EdgeInsets.all(16.0),
            gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
              maxCrossAxisExtent: 240,
              childAspectRatio: 0.85,
              crossAxisSpacing: 12.0,
              mainAxisSpacing: 12.0,
            ),
            itemCount: totalCount,
            itemBuilder: (context, index) {
              // Folders first
              if (index < folders.length) {
                final folder = folders[index];
                return DragTarget<String>(
                  onWillAcceptWithDetails: (_) => true,
                  onAcceptWithDetails: (details) {
                    _assignAgentToFolder(details.data, folder.id);
                  },
                  builder: (context, candidateData, rejectedData) {
                    return FolderCard(
                      folder: folder,
                      isHighlighted: candidateData.isNotEmpty,
                      onTap: () {
                        ref.read(currentFolderProvider.notifier).state = folder.id;
                      },
                      onRename: () => _renameFolder(folder.id, folder.name),
                      onDelete: () => _deleteFolder(folder.id, folder.name),
                    );
                  },
                );
              }

              // Agent cards
              final agent = agents[index - folders.length];
              return Draggable<String>(
                data: agent.id,
                feedback: Material(
                  elevation: 8,
                  borderRadius: BorderRadius.circular(12),
                  child: SizedBox(
                    width: 220,
                    height: 220,
                    child: Opacity(
                      opacity: 0.85,
                      child: AgentCard(agent: agent),
                    ),
                  ),
                ),
                childWhenDragging: Opacity(
                  opacity: 0.3,
                  child: AgentCard(agent: agent),
                ),
                child: GestureDetector(
                  onSecondaryTapUp: (details) {
                    _showAgentContextMenu(
                      context,
                      details.globalPosition,
                      agent.id,
                      agent.folderId,
                    );
                  },
                  onLongPress: () {
                    _showMoveToFolder(agent.id, agent.folderId);
                  },
                  child: AgentCard(agent: agent),
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  void _showAgentContextMenu(
    BuildContext context,
    Offset position,
    String agentId,
    String? folderId,
  ) {
    showMenu(
      context: context,
      position: RelativeRect.fromLTRB(
        position.dx,
        position.dy,
        position.dx + 1,
        position.dy + 1,
      ),
      items: [
        const PopupMenuItem(
          value: 'move',
          child: ListTile(
            leading: Icon(Icons.drive_file_move_outlined),
            title: Text('Move to folder...'),
            contentPadding: EdgeInsets.zero,
            dense: true,
          ),
        ),
      ],
    ).then((value) {
      if (value == 'move') {
        _showMoveToFolder(agentId, folderId);
      }
    });
  }
}
