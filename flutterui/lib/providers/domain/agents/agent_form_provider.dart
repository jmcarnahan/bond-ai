import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:file_picker/file_picker.dart';

import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/data/services/agent_service.dart';
import 'package:flutterui/data/services/file_service.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import 'package:flutterui/providers/models_provider.dart';
import 'package:flutterui/providers/domain/base/error_handler.dart';
import 'agent_form_state.dart';
import '../../../core/utils/logger.dart';

class AgentFormNotifier extends StateNotifier<AgentFormState>
    with ErrorHandlerMixin<AgentFormState> {
  final AgentService _agentService;
  final FileService _fileService;
  final String? Function() _getDefaultModel;

  AgentFormNotifier(
    this._agentService, 
    this._fileService, 
    this._getDefaultModel,
  ) : super(const AgentFormState());

  @override
  void handleAppError(AppError error) {
    state = state.copyWith(
      ui: state.ui.copyWith(
        isLoading: false,
        isUploadingFile: false,
        errorMessage: error.message,
      ),
    );
  }

  void setName(String name) {
    _updateData((data) => data.copyWith(name: name));
  }

  void setDescription(String description) {
    _updateData((data) => data.copyWith(description: description));
  }

  void setInstructions(String instructions) {
    _updateData((data) => data.copyWith(instructions: instructions));
  }

  void setEnableCodeInterpreter(bool enable) {
    final newData = state.data.copyWith(enableCodeInterpreter: enable);
    final updatedData =
        !enable ? newData.copyWith(codeInterpreterFiles: []) : newData;

    state = state.copyWith(
      data: updatedData,
      ui: state.ui.copyWith(isDirty: true, clearError: true),
    );
  }

  void setEnableFileSearch(bool enable) {
    final newData = state.data.copyWith(enableFileSearch: enable);
    final updatedData =
        !enable ? newData.copyWith(fileSearchFiles: []) : newData;

    state = state.copyWith(
      data: updatedData,
      ui: state.ui.copyWith(isDirty: true, clearError: true),
    );
  }

  Future<void> uploadFileForTool(String toolType) async {
    if (state.ui.isUploadingFile) return;

    try {
      FilePickerResult? result = await FilePicker.platform.pickFiles(
        type: FileType.any,
        allowMultiple: false,
      );

      if (result != null && result.files.isNotEmpty) {
        final file = result.files.first;
        if (file.bytes != null) {
          state = state.copyWith(
            ui: state.ui.copyWith(isUploadingFile: true, clearError: true),
          );

          final uploadResponse = await _fileService.uploadFile(
            file.name,
            file.bytes!,
          );

          final fileInfo = UploadedFileInfo(
            fileId: uploadResponse.providerFileId,
            fileName: file.name,
            fileSize: file.size,
            uploadedAt: DateTime.now(),
          );

          _addFileToTool(toolType, fileInfo);
          logger.i(
            'File uploaded successfully: ${file.name} -> ${uploadResponse.providerFileId}',
          );
        }
      }
    } catch (error, stackTrace) {
      handleError(error, stackTrace);
    } finally {
      state = state.copyWith(ui: state.ui.copyWith(isUploadingFile: false));
    }
  }

  void removeFileFromTool(String toolType, String fileId) {
    List<UploadedFileInfo> updatedFiles;

    if (toolType == 'code_interpreter') {
      updatedFiles =
          state.data.codeInterpreterFiles
              .where((file) => file.fileId != fileId)
              .toList();
      _updateData((data) => data.copyWith(codeInterpreterFiles: updatedFiles));
    } else if (toolType == 'file_search') {
      updatedFiles =
          state.data.fileSearchFiles
              .where((file) => file.fileId != fileId)
              .toList();
      _updateData((data) => data.copyWith(fileSearchFiles: updatedFiles));
    }
  }

  void resetForm() {
    state = const AgentFormState();
  }

  Future<void> loadAgentForEditing(String agentId) async {
    state = state.copyWith(
      ui: state.ui.copyWith(isLoading: true, clearError: true),
      editingAgentId: agentId,
    );

    try {
      final agentDetail = await _agentService.getAgentDetails(agentId);

      final hasCodeInterpreter = agentDetail.tools.any(
        (tool) => tool['type'] == 'code_interpreter',
      );
      final hasFileSearch = agentDetail.tools.any(
        (tool) => tool['type'] == 'file_search',
      );

      List<UploadedFileInfo> codeInterpreterFiles = [];
      List<UploadedFileInfo> fileSearchFiles = [];

      if (agentDetail.toolResources != null) {
        if (agentDetail.toolResources!.codeInterpreter?.fileIds != null) {
          codeInterpreterFiles =
              agentDetail.toolResources!.codeInterpreter!.fileIds
                  .map(
                    (fileId) => UploadedFileInfo(
                      fileId: fileId,
                      fileName: 'File $fileId',
                      fileSize: 0,
                      uploadedAt: DateTime.now(),
                    ),
                  )
                  .toList();
        }

        if (agentDetail.toolResources!.fileSearch?.fileIds != null) {
          fileSearchFiles =
              agentDetail.toolResources!.fileSearch!.fileIds
                  .map(
                    (fileId) => UploadedFileInfo(
                      fileId: fileId,
                      fileName: 'File $fileId',
                      fileSize: 0,
                      uploadedAt: DateTime.now(),
                    ),
                  )
                  .toList();
        }
      }

      final formData = AgentFormData(
        name: agentDetail.name,
        description: agentDetail.description ?? '',
        instructions: agentDetail.instructions ?? '',
        enableCodeInterpreter: hasCodeInterpreter,
        enableFileSearch: hasFileSearch,
        codeInterpreterFiles: codeInterpreterFiles,
        fileSearchFiles: fileSearchFiles,
      );

      state = state.copyWith(
        data: formData,
        ui: state.ui.copyWith(isLoading: false, isDirty: false),
      );

      logger.i(
        "[AgentFormNotifier] Loaded agent data for editing: ${agentDetail.name}",
      );
    } catch (error, stackTrace) {
      handleError(error, stackTrace);
    }
  }

  Future<bool> saveAgent() async {
    if (!state.canSave) return false;

    state = state.copyWith(
      ui: state.ui.copyWith(isLoading: true, clearError: true),
    );

    try {
      // Check if we can get the default model before building agent data
      String? defaultModel = _getDefaultModel();
      
      // If model is null, models might not be loaded yet, wait and retry
      if (defaultModel == null) {
        logger.w('[AgentFormNotifier] Model is null, waiting for models to load...');
        
        // Wait up to 3 seconds for models to load
        for (int i = 0; i < 6; i++) {
          await Future.delayed(const Duration(milliseconds: 500));
          defaultModel = _getDefaultModel();
          if (defaultModel != null) {
            logger.i('[AgentFormNotifier] Models loaded after ${(i + 1) * 500}ms');
            break;
          }
        }
        
        // If still null after waiting, fail the save
        if (defaultModel == null) {
          state = state.copyWith(
            ui: state.ui.copyWith(
              isLoading: false,
              errorMessage: "Unable to determine AI model. Please refresh and try again.",
            ),
          );
          logger.e('[AgentFormNotifier] Failed to load models after 3 seconds');
          return false;
        }
      }
      
      final agentData = _buildAgentData();

      if (state.isEditing) {
        await _agentService.updateAgent(state.editingAgentId!, agentData);
        logger.i('Agent updated: ${state.data.name}');
      } else {
        await _agentService.createAgent(agentData);
        logger.i('Agent created: ${state.data.name}');
      }

      state = state.copyWith(
        ui: state.ui.copyWith(isLoading: false, isDirty: false),
      );

      return true;
    } catch (error, stackTrace) {
      handleError(error, stackTrace);
      return false;
    }
  }

  void _updateData(AgentFormData Function(AgentFormData) updater) {
    state = state.copyWith(
      data: updater(state.data),
      ui: state.ui.copyWith(isDirty: true, clearError: true),
    );
  }

  void _addFileToTool(String toolType, UploadedFileInfo fileInfo) {
    if (toolType == 'code_interpreter') {
      final updatedFiles = [...state.data.codeInterpreterFiles, fileInfo];
      _updateData((data) => data.copyWith(codeInterpreterFiles: updatedFiles));
    } else if (toolType == 'file_search') {
      final updatedFiles = [...state.data.fileSearchFiles, fileInfo];
      _updateData((data) => data.copyWith(fileSearchFiles: updatedFiles));
    }
  }

  AgentDetailModel _buildAgentData() {
    List<Map<String, dynamic>> tools = [];
    if (state.data.enableCodeInterpreter) {
      tools.add({"type": "code_interpreter"});
    }
    if (state.data.enableFileSearch) {
      tools.add({"type": "file_search"});
    }

    AgentToolResourcesModel? toolResources;
    if (state.data.codeInterpreterFiles.isNotEmpty ||
        state.data.fileSearchFiles.isNotEmpty) {
      toolResources = AgentToolResourcesModel(
        codeInterpreter:
            state.data.codeInterpreterFiles.isNotEmpty
                ? ToolResourceFilesListModel(
                  fileIds:
                      state.data.codeInterpreterFiles
                          .map((f) => f.fileId)
                          .toList(),
                )
                : null,
        fileSearch:
            state.data.fileSearchFiles.isNotEmpty
                ? ToolResourceFilesListModel(
                  fileIds:
                      state.data.fileSearchFiles.map((f) => f.fileId).toList(),
                )
                : null,
      );
    }

    // Get the default model from the provider
    // Note: The model null check is done in saveAgent() before calling this method
    final defaultModel = _getDefaultModel()!;
    
    return AgentDetailModel(
      id: state.editingAgentId ?? '',
      name: state.data.name,
      description:
          state.data.description.isNotEmpty ? state.data.description : null,
      instructions:
          state.data.instructions.isNotEmpty ? state.data.instructions : null,
      model: defaultModel,
      tools: tools,
      toolResources: toolResources,
      files: [],
    );
  }
}

final agentFormProvider =
    StateNotifierProvider<AgentFormNotifier, AgentFormState>((ref) {
      final agentService = ref.watch(agentServiceProvider);
      final fileService = ref.watch(fileServiceProvider);
      
      // Create a function that captures the ref context
      String? getDefaultModel() {
        return ref.read(defaultModelProvider);
      }
      
      return AgentFormNotifier(agentService, fileService, getDefaultModel);
    });

final agentFormDataProvider = Provider<AgentFormData>((ref) {
  return ref.watch(agentFormProvider.select((state) => state.data));
});

final agentFormUiProvider = Provider<AgentFormUiState>((ref) {
  return ref.watch(agentFormProvider.select((state) => state.ui));
});
