import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutterui/data/models/agent_model.dart'; // Added for AgentDetailModel
import 'package:flutterui/providers/services/service_providers.dart';
import '../core/utils/logger.dart';

// Class to hold uploaded file information
class UploadedFileInfo {
  final String fileId;
  final String fileName;
  final int fileSize;
  final DateTime uploadedAt;

  const UploadedFileInfo({
    required this.fileId,
    required this.fileName,
    required this.fileSize,
    required this.uploadedAt,
  });

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is UploadedFileInfo &&
          runtimeType == other.runtimeType &&
          fileId == other.fileId;

  @override
  int get hashCode => fileId.hashCode;
}



// State class for the form
class CreateAgentFormState {
  final String name;
  final String description;
  final String instructions;
  final bool enableCodeInterpreter;
  final bool enableFileSearch;
  final List<UploadedFileInfo> codeInterpreterFiles;
  final List<UploadedFileInfo> fileSearchFiles;
  final bool isLoading;
  final bool isUploadingFile;
  final String? errorMessage;

  CreateAgentFormState({
    this.name = '',
    this.description = '',
    this.instructions = '',
    this.enableCodeInterpreter = false,
    this.enableFileSearch = false,
    this.codeInterpreterFiles = const [],
    this.fileSearchFiles = const [],
    this.isLoading = false,
    this.isUploadingFile = false,
    this.errorMessage,
  });

  CreateAgentFormState copyWith({
    String? name,
    String? description,
    String? instructions,
    bool? enableCodeInterpreter,
    bool? enableFileSearch,
    List<UploadedFileInfo>? codeInterpreterFiles,
    List<UploadedFileInfo>? fileSearchFiles,
    bool? isLoading,
    bool? isUploadingFile,
    String? errorMessage,
    bool clearErrorMessage = false, // Utility to easily clear error
  }) {
    return CreateAgentFormState(
      name: name ?? this.name,
      description: description ?? this.description,
      instructions: instructions ?? this.instructions,
      enableCodeInterpreter: enableCodeInterpreter ?? this.enableCodeInterpreter,
      enableFileSearch: enableFileSearch ?? this.enableFileSearch,
      codeInterpreterFiles: codeInterpreterFiles ?? this.codeInterpreterFiles,
      fileSearchFiles: fileSearchFiles ?? this.fileSearchFiles,
      isLoading: isLoading ?? this.isLoading,
      isUploadingFile: isUploadingFile ?? this.isUploadingFile,
      errorMessage: clearErrorMessage ? null : errorMessage ?? this.errorMessage,
    );
  }
}

// Notifier for the form state
class CreateAgentFormNotifier extends StateNotifier<CreateAgentFormState> {
  final Ref _ref;
  // agentId can be passed to the constructor if this becomes a family provider
  // final String? _agentId; 

  CreateAgentFormNotifier(this._ref /*, this._agentId */) : super(CreateAgentFormState());

  void setName(String name) {
    state = state.copyWith(name: name);
  }

  void setDescription(String description) {
    state = state.copyWith(description: description);
  }

  void setInstructions(String instructions) {
    state = state.copyWith(instructions: instructions);
  }

  // Combined method for text field changes
  void updateField({String? name, String? description, String? instructions}) {
    state = state.copyWith(
      name: name ?? state.name,
      description: description ?? state.description,
      instructions: instructions ?? state.instructions,
    );
  }

  void setEnableCodeInterpreter(bool enable) {
    state = state.copyWith(enableCodeInterpreter: enable);
    // If disabling code interpreter, clear associated files
    if (!enable) {
      state = state.copyWith(codeInterpreterFiles: []);
    }
  }

  void setEnableFileSearch(bool enable) {
    state = state.copyWith(enableFileSearch: enable);
    // If disabling file search, clear associated files
    if (!enable) {
      state = state.copyWith(fileSearchFiles: []);
    }
  }

  void setLoading(bool isLoading) { // Added method to control loading state externally
    state = state.copyWith(isLoading: isLoading);
  }

  // File management methods
  Future<void> uploadFileForTool(String toolType) async {
    if (state.isUploadingFile) return;

    try {
      FilePickerResult? result = await FilePicker.platform.pickFiles(
        type: FileType.any,
        allowMultiple: false,
      );

      if (result != null && result.files.isNotEmpty) {
        final file = result.files.first;
        if (file.bytes != null && file.name != null) {
          state = state.copyWith(isUploadingFile: true, clearErrorMessage: true);

          final agentService = _ref.read(agentServiceProvider);
          final uploadResponse = await agentService.uploadFile(
            file.name!,
            file.bytes!,
          );

          final fileInfo = UploadedFileInfo(
            fileId: uploadResponse.providerFileId,
            fileName: file.name!,
            fileSize: file.size,
            uploadedAt: DateTime.now(),
          );

          // Add file to appropriate tool list
          if (toolType == 'code_interpreter') {
            final updatedFiles = [...state.codeInterpreterFiles, fileInfo];
            state = state.copyWith(codeInterpreterFiles: updatedFiles);
          } else if (toolType == 'file_search') {
            final updatedFiles = [...state.fileSearchFiles, fileInfo];
            state = state.copyWith(fileSearchFiles: updatedFiles);
          }

          logger.i('File uploaded successfully: ${file.name} -> ${uploadResponse.providerFileId}');
        }
      }
    } catch (e) {
      logger.i('Error uploading file: ${e.toString()}');
      state = state.copyWith(errorMessage: 'Failed to upload file: ${e.toString()}');
    } finally {
      state = state.copyWith(isUploadingFile: false);
    }
  }

  void removeFileFromTool(String toolType, String fileId) {
    if (toolType == 'code_interpreter') {
      final updatedFiles = state.codeInterpreterFiles
          .where((file) => file.fileId != fileId)
          .toList();
      state = state.copyWith(codeInterpreterFiles: updatedFiles);
    } else if (toolType == 'file_search') {
      final updatedFiles = state.fileSearchFiles
          .where((file) => file.fileId != fileId)
          .toList();
      state = state.copyWith(fileSearchFiles: updatedFiles);
    }
  }

  void resetState() {
    state = CreateAgentFormState(); // Resets to default values including isLoading = false
  }

  // Load agent data for editing
  Future<void> loadAgentForEditing(String agentId) async {
    state = state.copyWith(isLoading: true, clearErrorMessage: true);
    
    try {
      final agentService = _ref.read(agentServiceProvider);
      final agentDetail = await agentService.getAgentDetails(agentId);
      
      // Extract tool types and file IDs
      final bool hasCodeInterpreter = agentDetail.tools.any((tool) => tool['type'] == 'code_interpreter');
      final bool hasFileSearch = agentDetail.tools.any((tool) => tool['type'] == 'file_search');
      
      List<UploadedFileInfo> codeInterpreterFiles = [];
      List<UploadedFileInfo> fileSearchFiles = [];
      
      if (agentDetail.toolResources != null) {
        // Load code interpreter files
        if (agentDetail.toolResources!.codeInterpreter?.fileIds != null) {
          codeInterpreterFiles = agentDetail.toolResources!.codeInterpreter!.fileIds
              .map((fileId) => UploadedFileInfo(
                    fileId: fileId,
                    fileName: 'File $fileId', // We don't have the original filename
                    fileSize: 0,
                    uploadedAt: DateTime.now(),
                  ))
              .toList();
        }
        
        // Load file search files
        if (agentDetail.toolResources!.fileSearch?.fileIds != null) {
          fileSearchFiles = agentDetail.toolResources!.fileSearch!.fileIds
              .map((fileId) => UploadedFileInfo(
                    fileId: fileId,
                    fileName: 'File $fileId', // We don't have the original filename
                    fileSize: 0,
                    uploadedAt: DateTime.now(),
                  ))
              .toList();
        }
      }
      
      // Update state with loaded data
      state = state.copyWith(
        name: agentDetail.name,
        description: agentDetail.description ?? '',
        instructions: agentDetail.instructions ?? '',
        enableCodeInterpreter: hasCodeInterpreter,
        enableFileSearch: hasFileSearch,
        codeInterpreterFiles: codeInterpreterFiles,
        fileSearchFiles: fileSearchFiles,
        isLoading: false,
      );
      
      logger.i("[CreateAgentFormNotifier] Loaded agent data for editing: ${agentDetail.name}");
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: "Failed to load agent details: ${e.toString()}",
      );
      logger.e("[CreateAgentFormNotifier] Error loading agent for editing: $e");
    }
  }

  // agentId is passed from the screen to determine create vs update
  Future<bool> saveAgent({String? agentId}) async {
    state = state.copyWith(isLoading: true, clearErrorMessage: true);

    if (state.name.isEmpty) {
      state = state.copyWith(isLoading: false, errorMessage: "Agent name cannot be empty.");
      return false;
    }
    if (state.instructions.isEmpty) {
      state = state.copyWith(isLoading: false, errorMessage: "Instructions cannot be empty.");
      return false;
    }

    List<Map<String, dynamic>> tools = [];
    if (state.enableCodeInterpreter) {
      tools.add({"type": "code_interpreter"});
    }
    if (state.enableFileSearch) {
      tools.add({"type": "file_search"});
    }

    // Build tool resources if files are associated
    AgentToolResourcesModel? toolResources;
    if (state.codeInterpreterFiles.isNotEmpty || state.fileSearchFiles.isNotEmpty) {
      toolResources = AgentToolResourcesModel(
        codeInterpreter: state.codeInterpreterFiles.isNotEmpty
            ? ToolResourceFilesListModel(
                fileIds: state.codeInterpreterFiles.map((f) => f.fileId).toList())
            : null,
        fileSearch: state.fileSearchFiles.isNotEmpty
            ? ToolResourceFilesListModel(
                fileIds: state.fileSearchFiles.map((f) => f.fileId).toList())
            : null,
      );
    }

    // For create, ID is usually not sent or is empty. Backend generates it.
    // For update, ID is crucial.
    // The AgentDetailModel requires an ID, so we provide a placeholder for create.
    final agentData = AgentDetailModel(
      id: agentId ?? '', // Use provided agentId for update, or empty for create
      name: state.name,
      description: state.description.isNotEmpty ? state.description : null,
      instructions: state.instructions.isNotEmpty ? state.instructions : null,
      model: "gpt-4-turbo-preview", // TODO: Make this configurable
      tools: tools,
      toolResources: toolResources,
    );

    try {
      final agentService = _ref.read(agentServiceProvider);
      if (agentId == null || agentId.isEmpty) {
        // Create new agent
        await agentService.createAgent(agentData);
        logger.i('Agent created: ${state.name}');
      } else {
        // Update existing agent
        await agentService.updateAgent(agentId, agentData);
        logger.i('Agent updated: ${state.name}');
      }
      
      state = state.copyWith(isLoading: false);
      // Consider resetting form or specific fields upon successful save
      // resetState(); 
      return true;
    } catch (e) {
      logger.i('Error saving agent: ${e.toString()}');
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
      return false;
    }
  }
}

// Provider definition
// If CreateAgentScreen needs to load an agent for editing using agentId,
// this should become a family provider:
// StateNotifierProvider.family<CreateAgentFormNotifier, CreateAgentFormState, String?>
final createAgentFormProvider =
    StateNotifierProvider<CreateAgentFormNotifier, CreateAgentFormState>((ref) {
  return CreateAgentFormNotifier(ref);
});
