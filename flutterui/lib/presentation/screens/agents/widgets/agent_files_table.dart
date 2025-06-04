import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/core/constants/app_constants.dart';
import 'package:flutterui/providers/create_agent_form_provider.dart';

class AgentFilesTable extends ConsumerWidget {
  const AgentFilesTable({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final formState = ref.watch(createAgentFormProvider);
    final formNotifier = ref.read(createAgentFormProvider.notifier);

    return Card(
      elevation: 0.0,
      margin: AppSpacing.verticalSm,
      shape: RoundedRectangleBorder(
        borderRadius: AppBorderRadius.allMd,
        side: BorderSide(
          color: theme.colorScheme.outlineVariant.withValues(alpha: 0.5),
        ),
      ),
      color: theme.colorScheme.surfaceContainer,
      child: Padding(
        padding: AppSpacing.allXl,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildHeader(context, formState, formNotifier),
            if (formState.uploadedFiles.isEmpty)
              _buildEmptyState(context)
            else
              _buildFilesTable(context, formState, formNotifier),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context, CreateAgentFormState formState, CreateAgentFormNotifier formNotifier) {
    final theme = Theme.of(context);
    
    return Row(
      children: [
        Icon(
          Icons.folder_open,
          color: theme.colorScheme.primary,
          size: 24,
        ),
        const SizedBox(width: 12),
        Text(
          'Uploaded Files',
          style: theme.textTheme.titleLarge?.copyWith(
            fontWeight: FontWeight.bold,
          ),
        ),
        const Spacer(),
        _buildUploadButton(context, formState, formNotifier),
      ],
    );
  }

  Widget _buildUploadButton(BuildContext context, CreateAgentFormState formState, CreateAgentFormNotifier formNotifier) {
    final isUploading = formState.isUploadingFile;
    final isLoading = formState.isLoading;
    
    return ElevatedButton.icon(
      onPressed: (isUploading || isLoading) ? null : () => formNotifier.uploadFile(),
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
      margin: const EdgeInsets.only(top: 24.0),
      padding: const EdgeInsets.all(32.0),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(12.0),
        border: Border.all(
          color: theme.colorScheme.outline.withValues(alpha: 0.3),
          style: BorderStyle.solid,
        ),
      ),
      child: Center(
        child: Column(
          children: [
            Icon(
              Icons.upload_file,
              color: theme.colorScheme.onSurfaceVariant,
              size: 48,
            ),
            const SizedBox(height: 16.0),
            Text(
              'No files uploaded yet',
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w500,
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 8.0),
            Text(
              'Upload files to use with Code Interpreter or File Search',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFilesTable(BuildContext context, CreateAgentFormState formState, CreateAgentFormNotifier formNotifier) {
    final theme = Theme.of(context);
    const double maxTableHeight = 400.0; // Maximum height before scrolling kicks in
    const double rowHeight = 56.0; // Approximate height per row
    const double headerHeight = 48.0; // Height of the header row
    
    return Container(
      margin: const EdgeInsets.only(top: 16.0),
      decoration: BoxDecoration(
        border: Border.all(
          color: theme.colorScheme.outline.withValues(alpha: 0.3),
        ),
        borderRadius: BorderRadius.circular(8.0),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          _buildTableHeader(context),
          // Constrain the scrollable area to prevent unlimited growth
          ConstrainedBox(
            constraints: BoxConstraints(
              maxHeight: formState.uploadedFiles.length > 6 
                  ? maxTableHeight - headerHeight 
                  : (formState.uploadedFiles.length * rowHeight),
            ),
            child: formState.uploadedFiles.length > 6
                ? Scrollbar(
                    child: SingleChildScrollView(
                      child: Column(
                        children: formState.uploadedFiles.map((file) => 
                          Container(
                            key: ValueKey('file_row_${file.fileId}'),
                            child: _buildFileRow(context, file, formState, formNotifier),
                          )
                        ).toList(),
                      ),
                    ),
                  )
                : Column(
                    children: formState.uploadedFiles.map((file) => 
                      Container(
                        key: ValueKey('file_row_${file.fileId}'),
                        child: _buildFileRow(context, file, formState, formNotifier),
                      )
                    ).toList(),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildTableHeader(BuildContext context) {
    final theme = Theme.of(context);
    final headerStyle = theme.textTheme.labelLarge?.copyWith(
      fontWeight: FontWeight.bold,
      color: theme.colorScheme.onSurfaceVariant,
    );
    
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 12.0),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
        borderRadius: const BorderRadius.only(
          topLeft: Radius.circular(8.0),
          topRight: Radius.circular(8.0),
        ),
      ),
      child: Row(
        children: [
          Expanded(
            flex: 3,
            child: Text('File Name', style: headerStyle),
          ),
          Expanded(
            flex: 2,
            child: Text('MIME Type', style: headerStyle),
          ),
          Expanded(
            flex: 2,
            child: Text('Tool', style: headerStyle),
          ),
          const SizedBox(width: 48), // Space for delete button
        ],
      ),
    );
  }

  Widget _buildFileRow(BuildContext context, UploadedFileInfo file, CreateAgentFormState formState, CreateAgentFormNotifier formNotifier) {
    final theme = Theme.of(context);
    final isLoading = formState.isLoading;
    
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(
            color: theme.colorScheme.outline.withValues(alpha: 0.2),
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
                  size: 20,
                ),
                const SizedBox(width: 8),
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
            child: _buildToolDropdown(context, file, formState, formNotifier),
          ),
          IconButton(
            onPressed: isLoading ? null : () => formNotifier.removeFile(file.fileId),
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

  Widget _buildToolDropdown(BuildContext context, UploadedFileInfo file, CreateAgentFormState formState, CreateAgentFormNotifier formNotifier) {
    final theme = Theme.of(context);
    final isLoading = formState.isLoading;
    
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12.0),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(8.0),
        border: Border.all(
          color: theme.colorScheme.outline.withValues(alpha: 0.3),
        ),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          key: ValueKey('dropdown_${file.fileId}'),
          value: file.selectedTool,
          isDense: true,
          style: theme.textTheme.bodyMedium,
          onChanged: isLoading 
              ? null 
              : (value) {
                  if (value != null) {
                    formNotifier.updateFileSelectedTool(file.fileId, value);
                  }
                },
          items: const [
            DropdownMenuItem(
              value: 'code_interpreter',
              child: Row(
                children: [
                  Icon(Icons.code, size: 16),
                  SizedBox(width: 8),
                  Text('Code Interpreter'),
                ],
              ),
            ),
            DropdownMenuItem(
              value: 'file_search',
              child: Row(
                children: [
                  Icon(Icons.search, size: 16),
                  SizedBox(width: 8),
                  Text('File Search'),
                ],
              ),
            ),
          ],
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

  String _formatMimeType(String mimeType) {
    // Simplify common mime types for display
    if (mimeType.startsWith('application/vnd.openxmlformats-officedocument.')) {
      if (mimeType.contains('spreadsheet')) return 'Excel';
      if (mimeType.contains('wordprocessing')) return 'Word';
      if (mimeType.contains('presentation')) return 'PowerPoint';
    }
    if (mimeType == 'text/csv') return 'CSV';
    if (mimeType == 'text/plain') return 'Text';
    if (mimeType == 'application/pdf') return 'PDF';
    if (mimeType.startsWith('image/')) return 'Image';
    
    // For others, show a simplified version
    final parts = mimeType.split('/');
    if (parts.length > 1) {
      return parts[1].toUpperCase();
    }
    return mimeType;
  }
}