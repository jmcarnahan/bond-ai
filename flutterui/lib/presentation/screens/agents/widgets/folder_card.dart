import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/folder_model.dart';
import 'package:flutterui/providers/core_providers.dart';

class FolderCard extends ConsumerWidget {
  final FolderModel folder;
  final VoidCallback onTap;
  final VoidCallback? onRename;
  final VoidCallback? onDelete;
  final bool isHighlighted;

  const FolderCard({
    super.key,
    required this.folder,
    required this.onTap,
    this.onRename,
    this.onDelete,
    this.isHighlighted = false,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final appThemeInstance = ref.watch(appThemeProvider);
    final themeData = appThemeInstance.themeData;
    final colorScheme = themeData.colorScheme;
    final textTheme = themeData.textTheme;

    return Card(
      elevation: isHighlighted ? 4.0 : 2.0,
      shadowColor: isHighlighted
          ? colorScheme.primary.withValues(alpha: 0.3)
          : colorScheme.shadow.withValues(alpha: 0.15),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12.0),
        side: BorderSide(
          color: isHighlighted
              ? colorScheme.primary
              : colorScheme.outlineVariant.withValues(alpha: 0.5),
          width: isHighlighted ? 2.0 : 1.0,
        ),
      ),
      color: isHighlighted
          ? colorScheme.primary.withValues(alpha: 0.05)
          : themeData.cardTheme.color ?? colorScheme.surface,
      child: InkWell(
        onTap: onTap,
        onLongPress: () => _showContextMenu(context, colorScheme),
        borderRadius: BorderRadius.circular(12.0),
        child: Container(
          padding: const EdgeInsets.all(6.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.center,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              // Folder icon
              Icon(
                Icons.folder_rounded,
                size: 48,
                color: isHighlighted
                    ? colorScheme.primary
                    : colorScheme.primary.withValues(alpha: 0.7),
              ),
              const SizedBox(height: 8),
              // Folder name
              Tooltip(
                message: folder.name,
                child: Text(
                  folder.name,
                  style: textTheme.titleSmall?.copyWith(
                    color: colorScheme.onSurface,
                    fontWeight: FontWeight.w600,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  textAlign: TextAlign.center,
                ),
              ),
              const SizedBox(height: 4),
              // Agent count badge
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  '${folder.agentCount} agent${folder.agentCount == 1 ? '' : 's'}',
                  style: TextStyle(
                    fontSize: 10,
                    color: colorScheme.onSurfaceVariant,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showContextMenu(BuildContext context, ColorScheme colorScheme) {
    if (onRename == null && onDelete == null) return;

    showModalBottomSheet(
      context: context,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (onRename != null)
              ListTile(
                leading: const Icon(Icons.edit),
                title: const Text('Rename folder'),
                onTap: () {
                  Navigator.pop(context);
                  onRename!();
                },
              ),
            if (onDelete != null)
              ListTile(
                leading: Icon(Icons.delete, color: colorScheme.error),
                title: Text('Delete folder', style: TextStyle(color: colorScheme.error)),
                onTap: () {
                  Navigator.pop(context);
                  onDelete!();
                },
              ),
          ],
        ),
      ),
    );
  }
}
