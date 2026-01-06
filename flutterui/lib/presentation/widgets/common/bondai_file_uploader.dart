import 'package:flutter/material.dart';
import 'package:flutterui/core/constants/app_constants.dart';

class FileInfo {
  final String fileId;
  final String fileName;
  final String mimeType;
  final String? selectedTool;
  final int? fileSize;
  final DateTime? uploadedAt;

  const FileInfo({
    required this.fileId,
    required this.fileName,
    required this.mimeType,
    this.selectedTool,
    this.fileSize,
    this.uploadedAt,
  });
}

class BondAIFileUploader extends StatelessWidget {
  final List<FileInfo> files;
  final bool isUploading;
  final VoidCallback onAddFile;
  final void Function(String fileId) onRemoveFile;
  final void Function(String fileId, String tool)? onToolChanged;
  final String? selectedTool;
  final List<String> availableTools;
  final bool showTools;
  final bool enabled;
  final String emptyStateMessage;
  final String emptyStateDescription;

  const BondAIFileUploader({
    super.key,
    required this.files,
    required this.isUploading,
    required this.onAddFile,
    required this.onRemoveFile,
    this.onToolChanged,
    this.selectedTool,
    this.availableTools = const ['code_interpreter', 'file_search'],
    this.showTools = true,
    this.enabled = true,
    this.emptyStateMessage = 'No files uploaded yet',
    this.emptyStateDescription = 'Upload files to enhance your agent\'s capabilities',
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    if (files.isEmpty) {
      return _buildEmptyState(context, theme);
    }

    return _buildFilesTable(context, theme);
  }

  Widget _buildEmptyState(BuildContext context, ThemeData theme) {
    return Container(
      padding: AppSpacing.allHuge,
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
        borderRadius: AppBorderRadius.allLg,
        border: Border.all(
          color: theme.colorScheme.outlineVariant.withValues(alpha: 0.2),
          width: 1,
        ),
      ),
      child: Center(
        child: Column(
          children: [
            Icon(
              Icons.upload_file,
              color: theme.colorScheme.onSurfaceVariant,
              size: AppSizes.iconEnormous / 2,
            ),
            SizedBox(height: AppSpacing.xl),
            Text(
              emptyStateMessage,
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w500,
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            SizedBox(height: AppSpacing.md),
            Text(
              emptyStateDescription,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFilesTable(BuildContext context, ThemeData theme) {
    const double maxTableHeight = 400.0;
    const double headerHeight = 56.0;

    return Container(
      decoration: BoxDecoration(
        border: Border.all(
          color: theme.colorScheme.outlineVariant.withValues(alpha: 0.3),
        ),
        borderRadius: AppBorderRadius.allMd,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          _buildTableHeader(context, theme),
          if (files.length > 6)
            ConstrainedBox(
              constraints: BoxConstraints(
                maxHeight: maxTableHeight - headerHeight,
              ),
              child: Scrollbar(
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: files.map((file) =>
                      Container(
                        key: ValueKey('file_row_${file.fileId}'),
                        child: _buildFileRow(context, theme, file),
                      )
                    ).toList(),
                  ),
                ),
              ),
            )
          else
            Column(
              mainAxisSize: MainAxisSize.min,
              children: files.map((file) =>
                Container(
                  key: ValueKey('file_row_${file.fileId}'),
                  child: _buildFileRow(context, theme, file),
                )
              ).toList(),
            ),
        ],
      ),
    );
  }

  Widget _buildTableHeader(BuildContext context, ThemeData theme) {
    final headerStyle = theme.textTheme.labelLarge?.copyWith(
      fontWeight: FontWeight.bold,
      color: theme.colorScheme.onSurfaceVariant,
    );

    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: AppSpacing.xl,
        vertical: AppSpacing.lg,
      ),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
        borderRadius: AppBorderRadius.topMd,
      ),
      child: Row(
        children: [
          Expanded(
            flex: 3,
            child: Text('File Name', style: headerStyle),
          ),
          if (!showTools)
            Expanded(
              flex: 2,
              child: Text('Type', style: headerStyle),
            ),
          if (showTools) ...[
            Expanded(
              flex: 2,
              child: Text('MIME Type', style: headerStyle),
            ),
            Expanded(
              flex: 2,
              child: Text('Tool', style: headerStyle),
            ),
          ],
          SizedBox(width: AppSizes.iconLg + (AppSpacing.md * 2)),
        ],
      ),
    );
  }

  Widget _buildFileRow(BuildContext context, ThemeData theme, FileInfo file) {
    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: AppSpacing.xl,
        vertical: AppSpacing.lg,
      ),
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(
            color: theme.colorScheme.outlineVariant.withValues(alpha: 0.2),
          ),
        ),
      ),
      child: Row(
        children: [
          Expanded(
            flex: 3,
            child: Row(
              children: [
                Icon(
                  _getFileIcon(file.fileName),
                  color: theme.colorScheme.primary,
                  size: AppSizes.iconMd,
                ),
                SizedBox(width: AppSpacing.md),
                Expanded(
                  child: Text(
                    file.fileName,
                    style: theme.textTheme.bodyMedium,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ),
          if (!showTools)
            Expanded(
              flex: 2,
              child: Text(
                _formatMimeType(file.mimeType),
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          if (showTools) ...[
            Expanded(
              flex: 2,
              child: Text(
                _formatMimeType(file.mimeType),
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
            Expanded(
              flex: 2,
              child: _buildToolDropdown(context, theme, file),
            ),
          ],
          IconButton(
            onPressed: enabled ? () => onRemoveFile(file.fileId) : null,
            icon: Icon(
              Icons.delete_outline,
              color: theme.colorScheme.error,
              size: AppSizes.iconMd,
            ),
            tooltip: 'Remove file',
            visualDensity: VisualDensity.compact,
            padding: EdgeInsets.all(AppSpacing.md),
          ),
        ],
      ),
    );
  }

  Widget _buildToolDropdown(BuildContext context, ThemeData theme, FileInfo file) {
    if (!showTools || onToolChanged == null) {
      return const SizedBox.shrink();
    }

    return Container(
      height: 36,
      padding: EdgeInsets.symmetric(horizontal: AppSpacing.lg),
      decoration: BoxDecoration(
        borderRadius: AppBorderRadius.allMd,
        border: Border.all(
          color: theme.colorScheme.outlineVariant.withValues(alpha: 0.3),
        ),
        color: theme.colorScheme.surfaceContainerLow,
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          key: ValueKey('dropdown_${file.fileId}'),
          value: file.selectedTool ?? availableTools.first,
          isDense: true,
          style: theme.textTheme.bodyMedium,
          onChanged: enabled
              ? (value) {
                  if (value != null) {
                    onToolChanged!(file.fileId, value);
                  }
                }
              : null,
          items: availableTools.map((tool) => DropdownMenuItem(
            value: tool,
            child: Row(
              children: [
                Icon(
                  tool == 'code_interpreter' ? Icons.code : Icons.search,
                  size: AppSizes.iconSm,
                ),
                SizedBox(width: AppSpacing.md),
                Text(_formatToolName(tool)),
              ],
            ),
          )).toList(),
        ),
      ),
    );
  }

  IconData _getFileIcon(String fileName) {
    final extension = fileName.split('.').last.toLowerCase();

    switch (extension) {
      case 'pdf':
        return Icons.picture_as_pdf;
      case 'doc':
      case 'docx':
        return Icons.description;
      case 'xls':
      case 'xlsx':
        return Icons.table_chart;
      case 'ppt':
      case 'pptx':
        return Icons.slideshow;
      case 'txt':
        return Icons.text_snippet;
      case 'csv':
        return Icons.grid_on;
      case 'json':
        return Icons.data_object;
      case 'py':
      case 'js':
      case 'html':
      case 'css':
      case 'dart':
      case 'java':
      case 'cpp':
      case 'c':
        return Icons.code;
      case 'jpg':
      case 'jpeg':
      case 'png':
      case 'gif':
      case 'webp':
        return Icons.image;
      case 'mp4':
      case 'avi':
      case 'mov':
      case 'wmv':
        return Icons.video_file;
      case 'mp3':
      case 'wav':
      case 'ogg':
        return Icons.audio_file;
      case 'zip':
      case 'rar':
      case '7z':
      case 'tar':
      case 'gz':
        return Icons.folder_zip;
      default:
        return Icons.insert_drive_file;
    }
  }

  String _formatMimeType(String mimeType) {
    if (mimeType.startsWith('application/vnd.openxmlformats-officedocument.')) {
      if (mimeType.contains('spreadsheet')) return 'Excel';
      if (mimeType.contains('wordprocessing')) return 'Word';
      if (mimeType.contains('presentation')) return 'PowerPoint';
    }
    if (mimeType == 'text/csv') return 'CSV';
    if (mimeType == 'text/plain') return 'Text';
    if (mimeType == 'application/pdf') return 'PDF';
    if (mimeType.startsWith('image/')) return 'Image';
    if (mimeType.startsWith('video/')) return 'Video';
    if (mimeType.startsWith('audio/')) return 'Audio';

    final parts = mimeType.split('/');
    if (parts.length > 1) {
      return parts[1].toUpperCase();
    }
    return mimeType;
  }

  String _formatToolName(String tool) {
    switch (tool) {
      case 'code_interpreter':
        return 'Code Interpreter';
      case 'file_search':
        return 'File Search';
      default:
        return tool.replaceAll('_', ' ').split(' ')
            .map((word) => word[0].toUpperCase() + word.substring(1))
            .join(' ');
    }
  }
}

class BondAIUploadButton extends StatelessWidget {
  final VoidCallback onPressed;
  final bool isUploading;
  final bool enabled;
  final String? label;
  final IconData? icon;

  const BondAIUploadButton({
    super.key,
    required this.onPressed,
    this.isUploading = false,
    this.enabled = true,
    this.label,
    this.icon,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return ElevatedButton.icon(
      onPressed: (enabled && !isUploading) ? onPressed : null,
      icon: isUploading
          ? SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: theme.colorScheme.onPrimary,
              ),
            )
          : Icon(icon ?? Icons.add, size: 18),
      label: Text(
        isUploading
            ? 'Uploading...'
            : label ?? 'Add File',
      ),
      style: ElevatedButton.styleFrom(
        padding: EdgeInsets.symmetric(
          horizontal: AppSpacing.xl,
          vertical: AppSpacing.lg,
        ),
        shape: RoundedRectangleBorder(
          borderRadius: AppBorderRadius.allMd,
        ),
      ),
    );
  }
}
