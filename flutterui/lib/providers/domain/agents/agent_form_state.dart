import 'package:flutter/foundation.dart';

@immutable
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

  @override
  String toString() => 'UploadedFileInfo(fileId: $fileId, fileName: $fileName)';
}

@immutable
class AgentFormData {
  final String name;
  final String description;
  final String instructions;
  final bool enableCodeInterpreter;
  final bool enableFileSearch;
  final List<UploadedFileInfo> codeInterpreterFiles;
  final List<UploadedFileInfo> fileSearchFiles;

  const AgentFormData({
    this.name = '',
    this.description = '',
    this.instructions = '',
    this.enableCodeInterpreter = false,
    this.enableFileSearch = false,
    this.codeInterpreterFiles = const [],
    this.fileSearchFiles = const [],
  });

  AgentFormData copyWith({
    String? name,
    String? description,
    String? instructions,
    bool? enableCodeInterpreter,
    bool? enableFileSearch,
    List<UploadedFileInfo>? codeInterpreterFiles,
    List<UploadedFileInfo>? fileSearchFiles,
  }) {
    return AgentFormData(
      name: name ?? this.name,
      description: description ?? this.description,
      instructions: instructions ?? this.instructions,
      enableCodeInterpreter: enableCodeInterpreter ?? this.enableCodeInterpreter,
      enableFileSearch: enableFileSearch ?? this.enableFileSearch,
      codeInterpreterFiles: codeInterpreterFiles ?? this.codeInterpreterFiles,
      fileSearchFiles: fileSearchFiles ?? this.fileSearchFiles,
    );
  }

  bool get isValid => name.trim().isNotEmpty;

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is AgentFormData &&
        other.name == name &&
        other.description == description &&
        other.instructions == instructions &&
        other.enableCodeInterpreter == enableCodeInterpreter &&
        other.enableFileSearch == enableFileSearch &&
        _listEquals(other.codeInterpreterFiles, codeInterpreterFiles) &&
        _listEquals(other.fileSearchFiles, fileSearchFiles);
  }

  @override
  int get hashCode {
    return Object.hash(
      name,
      description,
      instructions,
      enableCodeInterpreter,
      enableFileSearch,
      Object.hashAll(codeInterpreterFiles),
      Object.hashAll(fileSearchFiles),
    );
  }

  bool _listEquals<T>(List<T> a, List<T> b) {
    if (a.length != b.length) return false;
    for (int i = 0; i < a.length; i++) {
      if (a[i] != b[i]) return false;
    }
    return true;
  }
}

@immutable
class AgentFormUiState {
  final bool isLoading;
  final bool isUploadingFile;
  final String? errorMessage;
  final bool isDirty;

  const AgentFormUiState({
    this.isLoading = false,
    this.isUploadingFile = false,
    this.errorMessage,
    this.isDirty = false,
  });

  AgentFormUiState copyWith({
    bool? isLoading,
    bool? isUploadingFile,
    String? errorMessage,
    bool? isDirty,
    bool clearError = false,
  }) {
    return AgentFormUiState(
      isLoading: isLoading ?? this.isLoading,
      isUploadingFile: isUploadingFile ?? this.isUploadingFile,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      isDirty: isDirty ?? this.isDirty,
    );
  }

  bool get hasError => errorMessage != null;
  bool get isBusy => isLoading || isUploadingFile;

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is AgentFormUiState &&
        other.isLoading == isLoading &&
        other.isUploadingFile == isUploadingFile &&
        other.errorMessage == errorMessage &&
        other.isDirty == isDirty;
  }

  @override
  int get hashCode {
    return Object.hash(isLoading, isUploadingFile, errorMessage, isDirty);
  }
}

@immutable
class AgentFormState {
  final AgentFormData data;
  final AgentFormUiState ui;
  final String? editingAgentId;

  const AgentFormState({
    this.data = const AgentFormData(),
    this.ui = const AgentFormUiState(),
    this.editingAgentId,
  });

  AgentFormState copyWith({
    AgentFormData? data,
    AgentFormUiState? ui,
    String? editingAgentId,
    bool clearEditingAgentId = false,
  }) {
    return AgentFormState(
      data: data ?? this.data,
      ui: ui ?? this.ui,
      editingAgentId: clearEditingAgentId ? null : (editingAgentId ?? this.editingAgentId),
    );
  }

  bool get isEditing => editingAgentId != null;
  bool get canSave => data.isValid && !ui.isBusy;

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is AgentFormState &&
        other.data == data &&
        other.ui == ui &&
        other.editingAgentId == editingAgentId;
  }

  @override
  int get hashCode {
    return Object.hash(data, ui, editingAgentId);
  }
}