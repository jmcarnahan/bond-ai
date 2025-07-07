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

    return BondAIContainer(
      icon: Icons.folder_open,
      title: 'Uploaded Files (Max 5)',
      actionButton: BondAIUploadButton(
        onPressed: () => formNotifier.uploadFile(),
        isUploading: formState.isUploadingFile,
        enabled: !formState.isLoading,
      ),
      children: [
        BondAIFileUploader(
          files: files,
          isUploading: formState.isUploadingFile,
          onAddFile: () => formNotifier.uploadFile(),
          onRemoveFile: (fileId) => formNotifier.removeFile(fileId),
          onToolChanged:
              (fileId, tool) =>
                  formNotifier.updateFileSelectedTool(fileId, tool),
          enabled: !formState.isLoading,
          emptyStateMessage: 'No files uploaded yet',
          emptyStateDescription:
              'Upload files for your agent (e.g. PDFs, CSVs, images, etc.). You can include up to 5 files.',
        ),
      ],
    );
  }
}
