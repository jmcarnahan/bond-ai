import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/data/services/agent_service.dart';
import 'package:flutterui/providers/agent_provider.dart'; // For agentServiceProvider

// State for the Create/Edit Agent Form
@immutable
class CreateAgentFormState {
  final String? agentId; // Null if creating, non-null if editing
  final TextEditingController nameController;
  final TextEditingController descriptionController;
  final TextEditingController instructionsController;

  final bool isCodeInterpreterEnabled;
  final bool isFileSearchEnabled;

  final List<AgentFileDetailModel> codeInterpreterFiles;
  final List<AgentFileDetailModel> fileSearchFiles;

  final bool isLoading; // For loading agent details or saving
  final bool isUploadingFile;
  final String? errorMessage;

  const CreateAgentFormState({
    this.agentId,
    required this.nameController,
    required this.descriptionController,
    required this.instructionsController,
    this.isCodeInterpreterEnabled = false,
    this.isFileSearchEnabled = false,
    this.codeInterpreterFiles = const [],
    this.fileSearchFiles = const [],
    this.isLoading = false,
    this.isUploadingFile = false,
    this.errorMessage,
  });

  CreateAgentFormState copyWith({
    String? agentId,
    TextEditingController? nameController,
    TextEditingController? descriptionController,
    TextEditingController? instructionsController,
    bool? isCodeInterpreterEnabled,
    bool? isFileSearchEnabled,
    List<AgentFileDetailModel>? codeInterpreterFiles,
    List<AgentFileDetailModel>? fileSearchFiles,
    bool? isLoading,
    bool? isUploadingFile,
    String? errorMessage,
    bool clearErrorMessage = false,
  }) {
    return CreateAgentFormState(
      agentId: agentId ?? this.agentId,
      nameController: nameController ?? this.nameController,
      descriptionController:
          descriptionController ?? this.descriptionController,
      instructionsController:
          instructionsController ?? this.instructionsController,
      isCodeInterpreterEnabled:
          isCodeInterpreterEnabled ?? this.isCodeInterpreterEnabled,
      isFileSearchEnabled: isFileSearchEnabled ?? this.isFileSearchEnabled,
      codeInterpreterFiles: codeInterpreterFiles ?? this.codeInterpreterFiles,
      fileSearchFiles: fileSearchFiles ?? this.fileSearchFiles,
      isLoading: isLoading ?? this.isLoading,
      isUploadingFile: isUploadingFile ?? this.isUploadingFile,
      errorMessage:
          clearErrorMessage ? null : errorMessage ?? this.errorMessage,
    );
  }
}

// Notifier for the Create/Edit Agent Form
class CreateAgentFormNotifier extends StateNotifier<CreateAgentFormState> {
  final AgentService _agentService;
  final Ref _ref; // Changed from Reader to Ref

  CreateAgentFormNotifier(
    this._agentService,
    this._ref,
  ) // Changed _read to _ref
  : super(
        CreateAgentFormState(
          nameController: TextEditingController(),
          descriptionController: TextEditingController(),
          instructionsController: TextEditingController(),
        ),
      );

  Future<void> loadAgentForEdit(String agentId) async {
    state = state.copyWith(
      isLoading: true,
      errorMessage: null,
      clearErrorMessage: true,
    );
    try {
      final agentDetail = await _agentService.getAgentDetails(agentId);
      state.nameController.text = agentDetail.name;
      state.descriptionController.text = agentDetail.description ?? '';
      state.instructionsController.text = agentDetail.instructions ?? '';

      bool ciEnabled = false;
      List<AgentFileDetailModel> ciFiles = [];
      bool fsEnabled = false;
      List<AgentFileDetailModel> fsFiles = [];

      for (var tool in agentDetail.tools) {
        if (tool['type'] == 'code_interpreter') {
          ciEnabled = true;
          if (agentDetail.toolResources?.codeInterpreter?.files != null) {
            ciFiles = agentDetail.toolResources!.codeInterpreter!.files!;
          }
        }
        if (tool['type'] == 'file_search') {
          fsEnabled = true;
          if (agentDetail.toolResources?.fileSearch?.files != null) {
            fsFiles = agentDetail.toolResources!.fileSearch!.files!;
          }
        }
      }

      state = state.copyWith(
        agentId: agentId,
        isCodeInterpreterEnabled: ciEnabled,
        codeInterpreterFiles: ciFiles,
        isFileSearchEnabled: fsEnabled,
        fileSearchFiles: fsFiles,
        isLoading: false,
      );
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: 'Failed to load agent: ${e.toString()}',
      );
    }
  }

  void toggleTool(String toolType, bool enabled) {
    if (toolType == 'code_interpreter') {
      state = state.copyWith(isCodeInterpreterEnabled: enabled);
    } else if (toolType == 'file_search') {
      state = state.copyWith(isFileSearchEnabled: enabled);
    }
  }

  Future<void> addFile(String toolType) async {
    state = state.copyWith(
      isUploadingFile: true,
      errorMessage: null,
      clearErrorMessage: true,
    );
    try {
      FilePickerResult? result = await FilePicker.platform.pickFiles(
        type:
            FileType
                .any, // Or be more specific, e.g., FileType.custom(allowedExtensions: ['csv', 'pdf'])
      );

      if (result != null && result.files.single.path != null) {
        PlatformFile file = result.files.single;
        Uint8List fileBytes = file.bytes ?? (await _readFileBytes(file.path!));

        final uploadedFile = await _agentService.uploadFile(
          file.name,
          fileBytes,
        );
        final newFileDetail = AgentFileDetailModel(
          fileId: uploadedFile.providerFileId,
          fileName: uploadedFile.fileName,
        );

        if (toolType == 'code_interpreter') {
          state = state.copyWith(
            codeInterpreterFiles: [
              ...state.codeInterpreterFiles,
              newFileDetail,
            ],
            isUploadingFile: false,
          );
        } else if (toolType == 'file_search') {
          state = state.copyWith(
            fileSearchFiles: [...state.fileSearchFiles, newFileDetail],
            isUploadingFile: false,
          );
        }
      } else {
        state = state.copyWith(isUploadingFile: false); // User canceled picker
      }
    } catch (e) {
      state = state.copyWith(
        isUploadingFile: false,
        errorMessage: 'Failed to upload file: ${e.toString()}',
      );
    }
  }

  Future<Uint8List> _readFileBytes(String path) async {
    // This is a placeholder if file.bytes is null (e.g. on web sometimes)
    // For mobile, file.bytes should typically be populated.
    // For a more robust solution, consider platform-specific file reading.
    throw UnimplementedError(
      "Reading file bytes from path not fully implemented for all platforms without dart:io directly.",
    );
    // If using dart:io (not for web):
    // import 'dart:io';
    // return await File(path).readAsBytes();
  }

  Future<void> deleteFile(String toolType, String fileId) async {
    state = state.copyWith(
      isLoading: true,
      errorMessage: null,
      clearErrorMessage: true,
    ); // Use general isLoading for simplicity here
    try {
      await _agentService.deleteFile(fileId);
      if (toolType == 'code_interpreter') {
        state = state.copyWith(
          codeInterpreterFiles:
              state.codeInterpreterFiles
                  .where((f) => f.fileId != fileId)
                  .toList(),
          isLoading: false,
        );
      } else if (toolType == 'file_search') {
        state = state.copyWith(
          fileSearchFiles:
              state.fileSearchFiles.where((f) => f.fileId != fileId).toList(),
          isLoading: false,
        );
      }
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: 'Failed to delete file: ${e.toString()}',
      );
    }
  }

  Future<bool> saveAgent() async {
    state = state.copyWith(
      isLoading: true,
      errorMessage: null,
      clearErrorMessage: true,
    );
    try {
      List<Map<String, dynamic>> tools = [];
      if (state.isCodeInterpreterEnabled) {
        tools.add({"type": "code_interpreter"});
      }
      if (state.isFileSearchEnabled) {
        tools.add({"type": "file_search"});
      }

      final agentData = AgentDetailModel(
        id: state.agentId ?? '', // ID is empty for create, non-empty for update
        name: state.nameController.text,
        description: state.descriptionController.text,
        instructions: state.instructionsController.text,
        tools: tools,
        toolResources: AgentToolResourcesModel(
          codeInterpreter:
              state.isCodeInterpreterEnabled
                  ? ToolResourceFilesListModel(
                    fileIds:
                        state.codeInterpreterFiles
                            .map((f) => f.fileId)
                            .toList(),
                    files:
                        state
                            .codeInterpreterFiles, // For UI consistency, backend primarily uses fileIds
                  )
                  : null,
          fileSearch:
              state.isFileSearchEnabled
                  ? ToolResourceFilesListModel(
                    fileIds:
                        state.fileSearchFiles.map((f) => f.fileId).toList(),
                    files: state.fileSearchFiles,
                  )
                  : null,
        ),
        // model and metadata can be added later if needed
      );

      if (state.agentId == null) {
        // Create new agent
        await _agentService.createAgent(agentData);
      } else {
        // Update existing agent
        await _agentService.updateAgent(state.agentId!, agentData);
      }
      state = state.copyWith(isLoading: false);
      _ref.invalidate(agentsProvider); // Changed to _ref.invalidate()
      return true;
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: 'Failed to save agent: ${e.toString()}',
      );
      return false;
    }
  }

  @override
  void dispose() {
    state.nameController.dispose();
    state.descriptionController.dispose();
    state.instructionsController.dispose();
    super.dispose();
  }
}

final createAgentFormNotifierProvider = StateNotifierProvider.autoDispose
    .family<CreateAgentFormNotifier, CreateAgentFormState, String?>((
      ref,
      agentId,
    ) {
      final agentService = ref.watch(agentServiceProvider);
      final notifier = CreateAgentFormNotifier(
        agentService,
        ref,
      ); // Pass ref directly
      if (agentId != null) {
        notifier.loadAgentForEdit(agentId);
      }
      return notifier;
    });
