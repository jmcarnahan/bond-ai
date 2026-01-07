import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/providers/create_agent_form_provider.dart';

class ToolFileUploadSection extends ConsumerWidget {
  final String toolType;
  final String toolName;
  final bool isEnabled;
  final List<UploadedFileInfo> files;

  const ToolFileUploadSection({
    super.key,
    required this.toolType,
    required this.toolName,
    required this.isEnabled,
    required this.files,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final formState = ref.watch(createAgentFormProvider);
    final formNotifier = ref.read(createAgentFormProvider.notifier);

    if (!isEnabled) {
      return const SizedBox.shrink();
    }

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 8.0),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  toolType == 'code_interpreter' ? Icons.code : Icons.search,
                  color: theme.colorScheme.primary,
                ),
                const SizedBox(width: 8.0),
                Text(
                  '$toolName Files',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const Spacer(),
                _buildUploadButton(context, formState, formNotifier),
              ],
            ),
            const SizedBox(height: 12.0),
            if (files.isEmpty)
              _buildEmptyState(context)
            else
              _buildFileList(context, formNotifier),
          ],
        ),
      ),
    );
  }

  Widget _buildUploadButton(BuildContext context, CreateAgentFormState formState, CreateAgentFormNotifier formNotifier) {
    final isUploading = formState.isUploadingFile;

    return ElevatedButton.icon(
      onPressed: isUploading ? null : () => formNotifier.uploadFile(),
      icon: isUploading
          ? SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: Theme.of(context).colorScheme.onPrimary,
              ),
            )
          : const Icon(Icons.add, size: 18),
      label: Text(isUploading ? 'Uploading...' : 'Add File'),
      style: ElevatedButton.styleFrom(
        padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
      ),
    );
  }

  Widget _buildEmptyState(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.all(24.0),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(8.0),
        border: Border.all(
          color: theme.colorScheme.outline.withValues(alpha: 0.5),
          style: BorderStyle.solid,
        ),
      ),
      child: Row(
        children: [
          Icon(
            Icons.upload_file,
            color: theme.colorScheme.onSurfaceVariant,
            size: 32,
          ),
          const SizedBox(width: 16.0),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'No files uploaded yet',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const SizedBox(height: 4.0),
                Text(
                  'Upload files to use with $toolName',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFileList(BuildContext context, CreateAgentFormNotifier formNotifier) {
    return Column(
      children: files.map((file) => _buildFileItem(context, file, formNotifier)).toList(),
    );
  }

  Widget _buildFileItem(BuildContext context, UploadedFileInfo file, CreateAgentFormNotifier formNotifier) {
    final theme = Theme.of(context);

    return Container(
      margin: const EdgeInsets.only(bottom: 8.0),
      padding: const EdgeInsets.all(12.0),
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        borderRadius: BorderRadius.circular(8.0),
        border: Border.all(
          color: theme.colorScheme.outline.withValues(alpha: 0.3),
        ),
      ),
      child: Row(
        children: [
          Icon(
            _getFileIcon(file.fileName),
            color: theme.colorScheme.primary,
            size: 20,
          ),
          const SizedBox(width: 12.0),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  file.fileName,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w500,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2.0),
                Text(
                  '${_formatFileSize(file.fileSize)} • Uploaded ${_formatDate(file.uploadedAt)}',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            onPressed: () => formNotifier.removeFile(file.fileId),
            icon: Icon(
              Icons.delete_outline,
              color: theme.colorScheme.error,
              size: 20,
            ),
            tooltip: 'Remove file',
            visualDensity: VisualDensity.compact,
          ),
        ],
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
        return Icons.code;
      case 'jpg':
      case 'jpeg':
      case 'png':
      case 'gif':
        return Icons.image;
      default:
        return Icons.insert_drive_file;
    }
  }

  String _formatFileSize(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    if (bytes < 1024 * 1024 * 1024) return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
    return '${(bytes / (1024 * 1024 * 1024)).toStringAsFixed(1)} GB';
  }

  String _formatDate(DateTime date) {
    final now = DateTime.now();
    final diff = now.difference(date);

    if (diff.inMinutes < 1) return 'just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return '${date.day}/${date.month}/${date.year}';
  }
}
