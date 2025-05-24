import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/providers/create_agent_form_provider.dart';

class CreateAgentScreen extends ConsumerWidget {
  static const routeName = '/create-agent'; // For new agent
  static const editRouteNamePattern = '/edit-agent/:agentId'; // For editing

  final String? agentId; // Null if creating, non-null if editing

  const CreateAgentScreen({super.key, this.agentId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final formState = ref.watch(createAgentFormNotifierProvider(agentId));
    final formNotifier = ref.read(
      createAgentFormNotifierProvider(agentId).notifier,
    );

    return Scaffold(
      appBar: AppBar(
        title: Text(agentId == null ? 'Create Agent' : 'Edit Agent'),
        actions: [
          IconButton(
            icon: const Icon(Icons.save),
            onPressed:
                formState.isLoading || formState.isUploadingFile
                    ? null
                    : () async {
                      final success = await formNotifier.saveAgent();
                      if (success) {
                        Navigator.of(context).pop();
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text(
                              'Agent ${agentId == null ? "created" : "updated"} successfully!',
                            ),
                            backgroundColor: Colors.green,
                          ),
                        );
                      }
                    },
          ),
        ],
      ),
      body: Stack(
        children: [
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (formState.errorMessage != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 16.0),
                      child: Text(
                        formState.errorMessage!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                    ),
                  TextField(
                    controller: formState.nameController,
                    decoration: const InputDecoration(labelText: 'Agent Name'),
                    enabled: !formState.isLoading,
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: formState.descriptionController,
                    decoration: const InputDecoration(
                      labelText: 'Description (Optional)',
                    ),
                    maxLines: 2,
                    enabled: !formState.isLoading,
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: formState.instructionsController,
                    decoration: const InputDecoration(
                      labelText: 'Instructions',
                      hintText:
                          'Enter system prompt or instructions for the agent...',
                      border: OutlineInputBorder(),
                    ),
                    maxLines: 5,
                    enabled: !formState.isLoading,
                  ),
                  const SizedBox(height: 24),
                  _buildToolSection(
                    context,
                    formNotifier,
                    formState,
                    'Code Interpreter',
                    'code_interpreter',
                    formState.isCodeInterpreterEnabled,
                    formState.codeInterpreterFiles,
                  ),
                  const SizedBox(height: 16),
                  _buildToolSection(
                    context,
                    formNotifier,
                    formState,
                    'File Search',
                    'file_search',
                    formState.isFileSearchEnabled,
                    formState.fileSearchFiles,
                  ),
                ],
              ),
            ),
          ),
          if (formState.isLoading || formState.isUploadingFile)
            Container(
              color: Colors.black.withOpacity(0.5),
              child: Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const CircularProgressIndicator(),
                    const SizedBox(height: 16),
                    Text(
                      formState.isUploadingFile
                          ? 'Uploading file...'
                          : 'Saving agent...',
                      style: const TextStyle(color: Colors.white, fontSize: 16),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildToolSection(
    BuildContext context,
    CreateAgentFormNotifier formNotifier,
    CreateAgentFormState formState,
    String title,
    String toolType,
    bool isEnabled,
    List<AgentFileDetailModel> files,
  ) {
    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(12.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(title, style: Theme.of(context).textTheme.titleLarge),
                Switch(
                  value: isEnabled,
                  onChanged:
                      (bool value) => formNotifier.toggleTool(toolType, value),
                  activeColor: Theme.of(context).colorScheme.primary,
                ),
              ],
            ),
            if (isEnabled) ...[
              const SizedBox(height: 8),
              Text(
                'Associated Files:',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              if (files.isEmpty)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 8.0),
                  child: Text('No files associated yet.'),
                ),
              ListView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: files.length,
                itemBuilder: (context, index) {
                  final file = files[index];
                  return ListTile(
                    leading: const Icon(Icons.insert_drive_file),
                    title: Text(file.fileName),
                    trailing: IconButton(
                      icon: const Icon(Icons.delete, color: Colors.red),
                      onPressed:
                          formState.isLoading || formState.isUploadingFile
                              ? null
                              : () => formNotifier.deleteFile(
                                toolType,
                                file.fileId,
                              ),
                    ),
                  );
                },
              ),
              const SizedBox(height: 8),
              Align(
                alignment: Alignment.centerRight,
                child: ElevatedButton.icon(
                  icon: const Icon(Icons.add_to_drive),
                  label: const Text('Add File'),
                  onPressed:
                      formState.isLoading || formState.isUploadingFile
                          ? null
                          : () => formNotifier.addFile(toolType),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
