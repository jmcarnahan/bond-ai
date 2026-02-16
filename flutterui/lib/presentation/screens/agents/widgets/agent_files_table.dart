import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/providers/create_agent_form_provider.dart';
import 'package:flutterui/presentation/widgets/common/bondai_widgets.dart';

class AgentFilesTable extends ConsumerWidget {
  const AgentFilesTable({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final formState = ref.watch(createAgentFormProvider);
    final formNotifier = ref.read(createAgentFormProvider.notifier);
    final theme = Theme.of(context);

    final files =
        formState.uploadedFiles
            .map(
              (file) => FileInfo(
                fileId: file.fileId,
                fileName: file.fileName,
                mimeType: file.mimeType,
                selectedTool: file.selectedTool,
              ),
            )
            .toList();

    final isKnowledgeBase = formState.fileStorage == 'knowledge_base';
    final maxFilesText = isKnowledgeBase ? 'Unlimited' : 'Max 5';

    return BondAIContainer(
      icon: Icons.folder_open,
      title: 'Uploaded Files ($maxFilesText)',
      actionButton: BondAIUploadButton(
        onPressed: () => formNotifier.uploadFile(),
        isUploading: formState.isUploadingFile,
        enabled: !formState.isLoading,
      ),
      children: [
        // File Storage Mode Selector
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'File Storage Mode',
              style: theme.textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: RadioListTile<String>(
                    title: const Text('Direct'),
                    subtitle: const Text('5 files max'),
                    value: 'direct',
                    groupValue: formState.fileStorage,
                    onChanged: formState.isLoading
                        ? null
                        : (value) => formNotifier.setFileStorage(value!),
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                  ),
                ),
                Expanded(
                  child: RadioListTile<String>(
                    title: const Text('Knowledge Base'),
                    subtitle: const Text('Unlimited files'),
                    value: 'knowledge_base',
                    groupValue: formState.fileStorage,
                    onChanged: formState.isLoading
                        ? null
                        : (value) => formNotifier.setFileStorage(value!),
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                  ),
                ),
              ],
            ),
            const Divider(height: 24),
          ],
        ),
        BondAIFileUploader(
          files: files,
          isUploading: formState.isUploadingFile,
          availableTools: formState.enableCodeInterpreter
              ? const ['code_interpreter', 'file_search']
              : const ['file_search'],
          onAddFile: () => formNotifier.uploadFile(),
          onRemoveFile: (fileId) => formNotifier.removeFile(fileId),
          onToolChanged:
              (fileId, tool) =>
                  formNotifier.updateFileSelectedTool(fileId, tool),
          enabled: !formState.isLoading,
          emptyStateMessage: 'No files uploaded yet',
          emptyStateDescription: isKnowledgeBase
              ? 'Upload files for your agent (e.g. PDFs, CSVs, images, etc.). Knowledge Base mode supports unlimited files.'
              : 'Upload files for your agent (e.g. PDFs, CSVs, images, etc.). You can include up to 5 files.',
        ),
      ],
    );
  }
}
