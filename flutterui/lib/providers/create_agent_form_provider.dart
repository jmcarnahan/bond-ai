import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/data/services/agent_service.dart';
import 'package:flutterui/data/services/file_service.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import 'package:flutterui/providers/models_provider.dart';
import '../core/utils/logger.dart';

class UploadedFileInfo {
  final String fileId;
  final String fileName;
  final int fileSize;
  final String mimeType;
  final String selectedTool; // 'code_interpreter' or 'file_search'
  final DateTime uploadedAt;

  const UploadedFileInfo({
    required this.fileId,
    required this.fileName,
    required this.fileSize,
    required this.mimeType,
    required this.selectedTool,
    required this.uploadedAt,
  });

  UploadedFileInfo copyWith({
    String? fileId,
    String? fileName,
    int? fileSize,
    String? mimeType,
    String? selectedTool,
    DateTime? uploadedAt,
  }) {
    return UploadedFileInfo(
      fileId: fileId ?? this.fileId,
      fileName: fileName ?? this.fileName,
      fileSize: fileSize ?? this.fileSize,
      mimeType: mimeType ?? this.mimeType,
      selectedTool: selectedTool ?? this.selectedTool,
      uploadedAt: uploadedAt ?? this.uploadedAt,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is UploadedFileInfo &&
          runtimeType == other.runtimeType &&
          fileId == other.fileId;

  @override
  int get hashCode => fileId.hashCode;
}

class CreateAgentFormState {
  final String name;
  final String description;
  final String instructions;
  final String introduction;
  final String reminder;
  final List<UploadedFileInfo> uploadedFiles;
  final Set<String> selectedMcpTools;
  final Set<String> selectedMcpResources;
  final Set<String> selectedGroupIds;
  final bool isLoading;
  final bool isUploadingFile;
  final String? errorMessage;

  CreateAgentFormState({
    this.name = '',
    this.description = '',
    this.instructions = '',
    this.introduction = '',
    this.reminder = '',
    this.uploadedFiles = const [],
    this.selectedMcpTools = const {},
    this.selectedMcpResources = const {},
    this.selectedGroupIds = const {},
    this.isLoading = false,
    this.isUploadingFile = false,
    this.errorMessage,
  });

  CreateAgentFormState copyWith({
    String? name,
    String? description,
    String? instructions,
    String? introduction,
    String? reminder,
    List<UploadedFileInfo>? uploadedFiles,
    Set<String>? selectedMcpTools,
    Set<String>? selectedMcpResources,
    Set<String>? selectedGroupIds,
    bool? isLoading,
    bool? isUploadingFile,
    String? errorMessage,
    bool clearErrorMessage = false,
  }) {
    return CreateAgentFormState(
      name: name ?? this.name,
      description: description ?? this.description,
      instructions: instructions ?? this.instructions,
      introduction: introduction ?? this.introduction,
      reminder: reminder ?? this.reminder,
      uploadedFiles: uploadedFiles ?? this.uploadedFiles,
      selectedMcpTools: selectedMcpTools ?? this.selectedMcpTools,
      selectedMcpResources: selectedMcpResources ?? this.selectedMcpResources,
      selectedGroupIds: selectedGroupIds ?? this.selectedGroupIds,
      isLoading: isLoading ?? this.isLoading,
      isUploadingFile: isUploadingFile ?? this.isUploadingFile,
      errorMessage:
          clearErrorMessage ? null : errorMessage ?? this.errorMessage,
    );
  }
}

class CreateAgentFormNotifier extends StateNotifier<CreateAgentFormState> {
  final AgentService _agentService;
  final FileService _fileService;
  final String? Function() _getDefaultModel;

  CreateAgentFormNotifier({
    required AgentService agentService,
    required FileService fileService,
    required String? Function() getDefaultModel,
  })  : _agentService = agentService,
        _fileService = fileService,
        _getDefaultModel = getDefaultModel,
        super(CreateAgentFormState());

  void setName(String name) {
    state = state.copyWith(name: name);
  }

  void setDescription(String description) {
    state = state.copyWith(description: description);
  }

  void setInstructions(String instructions) {
    state = state.copyWith(instructions: instructions);
  }

  void setIntroduction(String introduction) {
    state = state.copyWith(introduction: introduction);
  }

  void setReminder(String reminder) {
    state = state.copyWith(reminder: reminder);
  }

  void updateField({
    String? name,
    String? description,
    String? instructions,
    String? introduction,
    String? reminder,
  }) {
    state = state.copyWith(
      name: name ?? state.name,
      description: description ?? state.description,
      instructions: instructions ?? state.instructions,
      introduction: introduction ?? state.introduction,
      reminder: reminder ?? state.reminder,
    );
  }

  void updateFileSelectedTool(String fileId, String selectedTool) {
    final updatedFiles =
        state.uploadedFiles.map((file) {
          if (file.fileId == fileId) {
            return file.copyWith(selectedTool: selectedTool);
          }
          return file;
        }).toList();

    state = state.copyWith(uploadedFiles: updatedFiles);
  }

  void setLoading(bool isLoading) {
    state = state.copyWith(isLoading: isLoading);
  }

  void cancelLoading() {
    // Cancel any ongoing operations and clear loading state
    state = state.copyWith(
      isLoading: false,
      isUploadingFile: false,
      clearErrorMessage: true,
    );
    logger.i("[CreateAgentFormNotifier] Loading operations cancelled");
  }

  void setSelectedMcpTools(Set<String> tools) {
    state = state.copyWith(selectedMcpTools: tools);
  }

  void setSelectedMcpResources(Set<String> resources) {
    state = state.copyWith(selectedMcpResources: resources);
  }

  void setSelectedGroupIds(Set<String> groupIds) {
    state = state.copyWith(selectedGroupIds: groupIds);
  }

  Future<void> uploadFile() async {
    if (state.isUploadingFile) return;

    try {
      FilePickerResult? result = await FilePicker.platform.pickFiles(
        type: FileType.any,
        allowMultiple: false,
      );

      if (result != null && result.files.isNotEmpty) {
        final file = result.files.first;
        if (file.bytes != null) {
          state = state.copyWith(
            isUploadingFile: true,
            clearErrorMessage: true,
          );

          final uploadResponse = await _fileService.uploadFile(
            file.name,
            file.bytes!,
          );

          final fileInfo = UploadedFileInfo(
            fileId: uploadResponse.providerFileId,
            fileName: file.name,
            fileSize: file.size,
            mimeType: uploadResponse.mimeType,
            selectedTool: uploadResponse.suggestedTool,
            uploadedAt: DateTime.now(),
          );

          // Check if file already exists in the list
          final existingFileIndex = state.uploadedFiles.indexWhere(
            (f) => f.fileId == uploadResponse.providerFileId,
          );

          if (existingFileIndex != -1) {
            // File already exists, don't add duplicate
            logger.i(
              'File already uploaded: ${file.name} -> ${uploadResponse.providerFileId}',
            );
          } else {
            // Add new file
            final updatedFiles = [...state.uploadedFiles, fileInfo];
            state = state.copyWith(uploadedFiles: updatedFiles);

            logger.i(
              'File uploaded successfully: ${file.name} -> ${uploadResponse.providerFileId}',
            );
          }
        }
      }
    } catch (e) {
      logger.i('Error uploading file: ${e.toString()}');
      state = state.copyWith(
        errorMessage: 'Failed to upload file: ${e.toString()}',
      );
    } finally {
      state = state.copyWith(isUploadingFile: false);
    }
  }

  void removeFile(String fileId) {
    final updatedFiles =
        state.uploadedFiles.where((file) => file.fileId != fileId).toList();
    state = state.copyWith(uploadedFiles: updatedFiles);
  }

  void resetState() {
    state = CreateAgentFormState();
  }

  Future<void> loadAgentForEditing(String agentId) async {
    state = state.copyWith(isLoading: true, clearErrorMessage: true);

    try {
      final agentDetail = await _agentService.getAgentDetails(agentId);

      List<UploadedFileInfo> uploadedFiles = [];

      if (agentDetail.toolResources != null) {
        // Collect all file IDs from both tools
        Set<String> allFileIds = {};
        Map<String, String> fileIdToTool = {};

        if (agentDetail.toolResources!.codeInterpreter?.fileIds != null) {
          for (String fileId
              in agentDetail.toolResources!.codeInterpreter!.fileIds) {
            allFileIds.add(fileId);
            fileIdToTool[fileId] = 'code_interpreter';
          }
        }

        if (agentDetail.toolResources!.fileSearch?.fileIds != null) {
          for (String fileId
              in agentDetail.toolResources!.fileSearch!.fileIds) {
            allFileIds.add(fileId);
            fileIdToTool[fileId] = 'file_search';
          }
        }

        // Fetch file details for all file IDs
        if (allFileIds.isNotEmpty) {
          try {
            // Add timeout to prevent hanging on file details fetch
            final fileDetailsList = await _fileService
                .getFileDetails(allFileIds.toList())
                .timeout(
                  const Duration(seconds: 15),
                  onTimeout: () {
                    logger.w(
                      "[CreateAgentFormNotifier] File details fetch timed out, using placeholders",
                    );
                    throw Exception('File details fetch timed out');
                  },
                );

            uploadedFiles =
                fileDetailsList.map((fileDetails) {
                  return UploadedFileInfo(
                    fileId: fileDetails.fileId,
                    fileName: fileDetails.fileName,
                    fileSize: 0, // File size not available from API
                    mimeType: fileDetails.mimeType,
                    selectedTool:
                        fileIdToTool[fileDetails.fileId] ?? 'file_search',
                    uploadedAt: DateTime.now(),
                  );
                }).toList();

            logger.i(
              "[CreateAgentFormNotifier] Loaded ${uploadedFiles.length} file details for editing",
            );
          } catch (e) {
            logger.e(
              "[CreateAgentFormNotifier] Failed to fetch file details: $e",
            );
            // Fallback to creating placeholder entries
            uploadedFiles =
                allFileIds.map((fileId) {
                  return UploadedFileInfo(
                    fileId: fileId,
                    fileName: 'File $fileId',
                    fileSize: 0,
                    mimeType: 'unknown',
                    selectedTool: fileIdToTool[fileId] ?? 'file_search',
                    uploadedAt: DateTime.now(),
                  );
                }).toList();
            logger.i(
              "[CreateAgentFormNotifier] Created ${uploadedFiles.length} placeholder file entries",
            );
          }
        }
      }

      state = state.copyWith(
        name: agentDetail.name,
        description: agentDetail.description ?? '',
        instructions: agentDetail.instructions ?? '',
        introduction: agentDetail.introduction ?? '',
        reminder: agentDetail.reminder ?? '',
        uploadedFiles: uploadedFiles,
        selectedMcpTools:
            agentDetail.mcpTools != null
                ? Set<String>.from(agentDetail.mcpTools!)
                : {},
        selectedMcpResources:
            agentDetail.mcpResources != null
                ? Set<String>.from(agentDetail.mcpResources!)
                : {},
        isLoading: false,
      );

      logger.i(
        "[CreateAgentFormNotifier] Loaded agent data for editing: ${agentDetail.name}",
      );
      // logger.i("[CreateAgentFormNotifier] MCP Tools: ${agentDetail.mcpTools}");
      // logger.i(
      //   "[CreateAgentFormNotifier] MCP Resources: ${agentDetail.mcpResources}",
      // );
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: "Failed to load agent details: ${e.toString()}",
      );
      logger.e("[CreateAgentFormNotifier] Error loading agent for editing: $e");
    }
  }

  Future<bool> saveAgent({String? agentId}) async {
    state = state.copyWith(isLoading: true, clearErrorMessage: true);
    
    logger.i('[CreateAgentFormNotifier] Starting saveAgent for: ${state.name}');

    if (state.name.isEmpty) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: "Agent name cannot be empty.",
      );
      return false;
    }
    if (state.instructions.isEmpty) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: "Instructions cannot be empty.",
      );
      return false;
    }

    // Always include both tools
    List<Map<String, dynamic>> tools = [
      {"type": "code_interpreter"},
      {"type": "file_search"},
    ];

    // Group files by selected tool
    final codeInterpreterFiles =
        state.uploadedFiles
            .where((file) => file.selectedTool == 'code_interpreter')
            .map((f) => f.fileId)
            .toList();

    final fileSearchFiles =
        state.uploadedFiles
            .where((file) => file.selectedTool == 'file_search')
            .map((f) => f.fileId)
            .toList();

    AgentToolResourcesModel? toolResources;
    if (codeInterpreterFiles.isNotEmpty || fileSearchFiles.isNotEmpty) {
      toolResources = AgentToolResourcesModel(
        codeInterpreter:
            codeInterpreterFiles.isNotEmpty
                ? ToolResourceFilesListModel(fileIds: codeInterpreterFiles)
                : null,
        fileSearch:
            fileSearchFiles.isNotEmpty
                ? ToolResourceFilesListModel(fileIds: fileSearchFiles)
                : null,
      );
    }

    // Get the default model from the provider
    String? defaultModel = _getDefaultModel();
    
    // If model is null, models might not be loaded yet, wait and retry
    if (defaultModel == null) {
      logger.w('[CreateAgentFormNotifier] Model is null, waiting for models to load...');
      
      // Wait up to 3 seconds for models to load
      for (int i = 0; i < 6; i++) {
        await Future.delayed(const Duration(milliseconds: 500));
        defaultModel = _getDefaultModel();
        if (defaultModel != null) {
          logger.i('[CreateAgentFormNotifier] Models loaded after ${(i + 1) * 500}ms');
          break;
        }
      }
      
      // If still null after waiting, fail the save
      if (defaultModel == null) {
        state = state.copyWith(
          isLoading: false,
          errorMessage: "Unable to determine AI model. Please refresh and try again.",
        );
        logger.e('[CreateAgentFormNotifier] Failed to load models after 3 seconds');
        return false;
      }
    }
    
    logger.i('[CreateAgentFormNotifier] Using model for agent creation: $defaultModel');
    
    final agentData = AgentDetailModel(
      id: agentId ?? '',
      name: state.name,
      description: state.description.isNotEmpty ? state.description : null,
      instructions: state.instructions.isNotEmpty ? state.instructions : null,
      introduction: state.introduction.isNotEmpty ? state.introduction : null,
      reminder: state.reminder.isNotEmpty ? state.reminder : null,
      model: defaultModel, // guaranteed non-null by check above
      tools: tools,
      toolResources: toolResources,
      mcpTools:
          state.selectedMcpTools.isNotEmpty
              ? state.selectedMcpTools.toList()
              : null,
      mcpResources:
          state.selectedMcpResources.isNotEmpty
              ? state.selectedMcpResources.toList()
              : null,
      files: [],
      groupIds:
          state.selectedGroupIds.isNotEmpty
              ? state.selectedGroupIds.toList()
              : null,
    );

    logger.i(
      "[CreateAgentFormNotifier] Saving agent with MCP tools: ${state.selectedMcpTools}",
    );
    logger.i(
      "[CreateAgentFormNotifier] Saving agent with MCP resources: ${state.selectedMcpResources}",
    );

    try {
      if (agentId == null || agentId.isEmpty) {
        await _agentService.createAgent(agentData);
        logger.i('Agent created: ${state.name}');
      } else {
        await _agentService.updateAgent(agentId, agentData);
        logger.i('Agent updated: ${state.name}');
      }

      state = state.copyWith(isLoading: false);
      return true;
    } catch (e) {
      logger.i('Error saving agent: ${e.toString()}');
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
      return false;
    }
  }

  Future<bool> deleteAgent(String agentId) async {
    state = state.copyWith(isLoading: true, clearErrorMessage: true);

    try {
      await _agentService.deleteAgent(agentId);
      logger.i('Agent deleted: $agentId');

      state = state.copyWith(isLoading: false);
      return true;
    } catch (e) {
      logger.e('Error deleting agent: ${e.toString()}');
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
      return false;
    }
  }
}

final createAgentFormProvider =
    StateNotifierProvider<CreateAgentFormNotifier, CreateAgentFormState>((ref) {
      final agentService = ref.watch(agentServiceProvider);
      final fileService = ref.watch(fileServiceProvider);
      
      // Create a function that captures the ref context
      String? getDefaultModel() {
        final model = ref.read(defaultModelProvider);
        logger.i('[CreateAgentFormProvider] defaultModelProvider returned: $model');
        if (model == null) {
          logger.w('[CreateAgentFormProvider] defaultModelProvider is null - models not loaded yet');
        }
        return model;
      }
      
      return CreateAgentFormNotifier(
        agentService: agentService,
        fileService: fileService,
        getDefaultModel: getDefaultModel,
      );
    });
