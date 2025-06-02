import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/providers/create_agent_form_provider.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/data/models/api_response_models.dart';
import 'package:flutterui/data/services/agent_service.dart';
import 'package:flutterui/data/services/agent_service/agent_file_service.dart';

class MockAgentService implements AgentService {
  List<AgentListItemModel> mockAgents = [];
  AgentDetailModel? mockAgentDetail;
  FileUploadResponseModel? mockUploadResponse;
  bool shouldThrowError = false;
  String? errorMessage;
  bool createAgentCalled = false;
  bool updateAgentCalled = false;
  bool uploadFileCalled = false;
  bool getAgentDetailsCalled = false;
  bool deleteAgentCalled = false;
  AgentDetailModel? lastCreatedAgent;
  AgentDetailModel? lastUpdatedAgent;
  String? lastUpdatedAgentId;
  String? lastUploadedFileName;
  Uint8List? lastUploadedFileBytes;
  String? lastDeletedAgentId;
  String? lastGetDetailsAgentId;

  @override
  Future<List<AgentListItemModel>> getAgents() async {
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock get agents error');
    }
    return mockAgents;
  }

  @override
  Future<AgentDetailModel> getAgentDetails(String agentId) async {
    getAgentDetailsCalled = true;
    lastGetDetailsAgentId = agentId;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock get agent details error');
    }
    return mockAgentDetail ?? AgentDetailModel(
      id: agentId,
      name: 'Mock Agent',
      description: 'Mock Description',
      instructions: 'Mock Instructions',
      model: 'gpt-4',
      tools: [],
      toolResources: null,
      files: [],
    );
  }

  @override
  Future<AgentResponseModel> createAgent(AgentDetailModel agent) async {
    createAgentCalled = true;
    lastCreatedAgent = agent;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock create agent error');
    }
    final agentId = 'new-agent-${mockAgents.length}';
    mockAgents.add(AgentListItemModel(
      id: agentId,
      name: agent.name,
      description: agent.description,
      model: agent.model,
    ));
    return AgentResponseModel(agentId: agentId, name: agent.name);
  }

  @override
  Future<AgentResponseModel> updateAgent(String agentId, AgentDetailModel agent) async {
    updateAgentCalled = true;
    lastUpdatedAgentId = agentId;
    lastUpdatedAgent = agent;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock update agent error');
    }
    return AgentResponseModel(agentId: agentId, name: agent.name);
  }

  @override
  Future<void> deleteAgent(String agentId) async {
    deleteAgentCalled = true;
    lastDeletedAgentId = agentId;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock delete agent error');
    }
    mockAgents.removeWhere((agent) => agent.id == agentId);
  }

  @override
  Future<FileUploadResponseModel> uploadFile(String fileName, Uint8List fileBytes) async {
    uploadFileCalled = true;
    lastUploadedFileName = fileName;
    lastUploadedFileBytes = fileBytes;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock upload file error');
    }
    return mockUploadResponse ?? FileUploadResponseModel(
      providerFileId: 'provider-${fileName.hashCode}',
      fileName: fileName,
      message: 'File uploaded successfully',
    );
  }

  @override
  Future<void> deleteFile(String providerFileId) async {
    throw UnimplementedError();
  }

  @override
  Future<List<FileInfoModel>> getFiles() async {
    throw UnimplementedError();
  }

  @override
  Future<FileInfoModel> getFileInfo(String providerFileId) async {
    throw UnimplementedError();
  }

  @override
  void dispose() {
  }
}

void main() {
  group('Create Agent Form Provider Tests', () {
    late MockAgentService mockAgentService;
    late ProviderContainer container;

    setUp(() {
      mockAgentService = MockAgentService();
      container = ProviderContainer(
        overrides: [
          agentServiceProvider.overrideWithValue(mockAgentService),
        ],
      );
    });

    tearDown(() {
      container.dispose();
    });

    group('UploadedFileInfo', () {
      test('should create instance with required fields', () {
        final fileInfo = UploadedFileInfo(
          fileId: 'test-file-id',
          fileName: 'test.txt',
          fileSize: 1024,
          uploadedAt: DateTime(2023, 1, 1),
        );

        expect(fileInfo.fileId, equals('test-file-id'));
        expect(fileInfo.fileName, equals('test.txt'));
        expect(fileInfo.fileSize, equals(1024));
        expect(fileInfo.uploadedAt, equals(DateTime(2023, 1, 1)));
      });

      test('should implement equality correctly', () {
        final fileInfo1 = UploadedFileInfo(
          fileId: 'same-id',
          fileName: 'file1.txt',
          fileSize: 100,
          uploadedAt: DateTime.now(),
        );

        final fileInfo2 = UploadedFileInfo(
          fileId: 'same-id',
          fileName: 'file2.txt',
          fileSize: 200,
          uploadedAt: DateTime.now().add(Duration(hours: 1)),
        );

        final fileInfo3 = UploadedFileInfo(
          fileId: 'different-id',
          fileName: 'file1.txt',
          fileSize: 100,
          uploadedAt: DateTime.now(),
        );

        expect(fileInfo1, equals(fileInfo2));
        expect(fileInfo1, isNot(equals(fileInfo3)));
        expect(fileInfo1.hashCode, equals(fileInfo2.hashCode));
      });
    });

    group('CreateAgentFormState', () {
      test('should create default state', () {
        final state = CreateAgentFormState();

        expect(state.name, isEmpty);
        expect(state.description, isEmpty);
        expect(state.instructions, isEmpty);
        expect(state.enableCodeInterpreter, isFalse);
        expect(state.enableFileSearch, isFalse);
        expect(state.codeInterpreterFiles, isEmpty);
        expect(state.fileSearchFiles, isEmpty);
        expect(state.isLoading, isFalse);
        expect(state.isUploadingFile, isFalse);
        expect(state.errorMessage, isNull);
      });

      test('should create state with custom values', () {
        final files = [UploadedFileInfo(
          fileId: 'test-file',
          fileName: 'test.txt',
          fileSize: 1024,
          uploadedAt: DateTime.now(),
        )];

        final state = CreateAgentFormState(
          name: 'Test Agent',
          description: 'Test Description',
          instructions: 'Test Instructions',
          enableCodeInterpreter: true,
          enableFileSearch: true,
          codeInterpreterFiles: files,
          fileSearchFiles: files,
          isLoading: true,
          isUploadingFile: true,
          errorMessage: 'Test Error',
        );

        expect(state.name, equals('Test Agent'));
        expect(state.description, equals('Test Description'));
        expect(state.instructions, equals('Test Instructions'));
        expect(state.enableCodeInterpreter, isTrue);
        expect(state.enableFileSearch, isTrue);
        expect(state.codeInterpreterFiles, equals(files));
        expect(state.fileSearchFiles, equals(files));
        expect(state.isLoading, isTrue);
        expect(state.isUploadingFile, isTrue);
        expect(state.errorMessage, equals('Test Error'));
      });

      test('should copy with new values', () {
        final originalState = CreateAgentFormState(
          name: 'Original',
          description: 'Original Desc',
          instructions: 'Original Instructions',
          errorMessage: 'Original Error',
        );

        final newState = originalState.copyWith(
          name: 'Updated',
          enableCodeInterpreter: true,
        );

        expect(newState.name, equals('Updated'));
        expect(newState.description, equals('Original Desc'));
        expect(newState.instructions, equals('Original Instructions'));
        expect(newState.enableCodeInterpreter, isTrue);
        expect(newState.errorMessage, equals('Original Error'));
      });

      test('should clear error message when specified', () {
        final state = CreateAgentFormState(errorMessage: 'Error');
        final newState = state.copyWith(clearErrorMessage: true);

        expect(state.errorMessage, equals('Error'));
        expect(newState.errorMessage, isNull);
      });
    });

    group('CreateAgentFormNotifier', () {
      late CreateAgentFormNotifier notifier;

      setUp(() {
        notifier = container.read(createAgentFormProvider.notifier);
      });

      test('should start with default state', () {
        expect(notifier.state.name, isEmpty);
        expect(notifier.state.description, isEmpty);
        expect(notifier.state.instructions, isEmpty);
        expect(notifier.state.enableCodeInterpreter, isFalse);
        expect(notifier.state.enableFileSearch, isFalse);
        expect(notifier.state.isLoading, isFalse);
        expect(notifier.state.errorMessage, isNull);
      });

      group('Field Updates', () {
        test('should update name', () {
          notifier.setName('Test Agent');
          expect(notifier.state.name, equals('Test Agent'));
        });

        test('should update description', () {
          notifier.setDescription('Test Description');
          expect(notifier.state.description, equals('Test Description'));
        });

        test('should update instructions', () {
          notifier.setInstructions('Test Instructions');
          expect(notifier.state.instructions, equals('Test Instructions'));
        });

        test('should update multiple fields at once', () {
          notifier.updateField(
            name: 'Updated Name',
            description: 'Updated Description',
            instructions: 'Updated Instructions',
          );

          expect(notifier.state.name, equals('Updated Name'));
          expect(notifier.state.description, equals('Updated Description'));
          expect(notifier.state.instructions, equals('Updated Instructions'));
        });

        test('should update only specified fields', () {
          notifier.setName('Initial Name');
          notifier.setDescription('Initial Description');
          
          notifier.updateField(name: 'Updated Name');

          expect(notifier.state.name, equals('Updated Name'));
          expect(notifier.state.description, equals('Initial Description'));
        });

        test('should handle empty string updates', () {
          notifier.setName('Initial');
          notifier.setName('');
          expect(notifier.state.name, isEmpty);
        });

        test('should handle special characters', () {
          const specialText = 'Agent with émojis 🤖 and spëcial chars @#\$%';
          notifier.setName(specialText);
          expect(notifier.state.name, equals(specialText));
        });
      });

      group('Tool Configuration', () {
        test('should enable code interpreter', () {
          notifier.setEnableCodeInterpreter(true);
          expect(notifier.state.enableCodeInterpreter, isTrue);
        });

        test('should disable code interpreter and clear files', () {
          final files = [UploadedFileInfo(
            fileId: 'test-file',
            fileName: 'test.txt',
            fileSize: 1024,
            uploadedAt: DateTime.now(),
          )];

          notifier.state = notifier.state.copyWith(
            enableCodeInterpreter: true,
            codeInterpreterFiles: files,
          );

          notifier.setEnableCodeInterpreter(false);

          expect(notifier.state.enableCodeInterpreter, isFalse);
          expect(notifier.state.codeInterpreterFiles, isEmpty);
        });

        test('should enable file search', () {
          notifier.setEnableFileSearch(true);
          expect(notifier.state.enableFileSearch, isTrue);
        });

        test('should disable file search and clear files', () {
          final files = [UploadedFileInfo(
            fileId: 'test-file',
            fileName: 'test.txt',
            fileSize: 1024,
            uploadedAt: DateTime.now(),
          )];

          notifier.state = notifier.state.copyWith(
            enableFileSearch: true,
            fileSearchFiles: files,
          );

          notifier.setEnableFileSearch(false);

          expect(notifier.state.enableFileSearch, isFalse);
          expect(notifier.state.fileSearchFiles, isEmpty);
        });
      });

      group('Loading State', () {
        test('should set loading state', () {
          notifier.setLoading(true);
          expect(notifier.state.isLoading, isTrue);

          notifier.setLoading(false);
          expect(notifier.state.isLoading, isFalse);
        });
      });

      group('File Management', () {
        test('should remove code interpreter file', () {
          final files = [
            UploadedFileInfo(
              fileId: 'file-1',
              fileName: 'test1.txt',
              fileSize: 1024,
              uploadedAt: DateTime.now(),
            ),
            UploadedFileInfo(
              fileId: 'file-2',
              fileName: 'test2.txt',
              fileSize: 2048,
              uploadedAt: DateTime.now(),
            ),
          ];

          notifier.state = notifier.state.copyWith(codeInterpreterFiles: files);
          notifier.removeFileFromTool('code_interpreter', 'file-1');

          expect(notifier.state.codeInterpreterFiles, hasLength(1));
          expect(notifier.state.codeInterpreterFiles.first.fileId, equals('file-2'));
        });

        test('should remove file search file', () {
          final files = [
            UploadedFileInfo(
              fileId: 'file-1',
              fileName: 'test1.txt',
              fileSize: 1024,
              uploadedAt: DateTime.now(),
            ),
            UploadedFileInfo(
              fileId: 'file-2',
              fileName: 'test2.txt',
              fileSize: 2048,
              uploadedAt: DateTime.now(),
            ),
          ];

          notifier.state = notifier.state.copyWith(fileSearchFiles: files);
          notifier.removeFileFromTool('file_search', 'file-1');

          expect(notifier.state.fileSearchFiles, hasLength(1));
          expect(notifier.state.fileSearchFiles.first.fileId, equals('file-2'));
        });

        test('should handle removing non-existent file', () {
          final files = [UploadedFileInfo(
            fileId: 'existing-file',
            fileName: 'test.txt',
            fileSize: 1024,
            uploadedAt: DateTime.now(),
          )];

          notifier.state = notifier.state.copyWith(codeInterpreterFiles: files);
          notifier.removeFileFromTool('code_interpreter', 'non-existent-file');

          expect(notifier.state.codeInterpreterFiles, hasLength(1));
          expect(notifier.state.codeInterpreterFiles.first.fileId, equals('existing-file'));
        });

        test('should handle unknown tool type', () {
          final initialFiles = [UploadedFileInfo(
            fileId: 'test-file',
            fileName: 'test.txt',
            fileSize: 1024,
            uploadedAt: DateTime.now(),
          )];

          notifier.state = notifier.state.copyWith(codeInterpreterFiles: initialFiles);
          notifier.removeFileFromTool('unknown_tool', 'test-file');

          expect(notifier.state.codeInterpreterFiles, hasLength(1));
        });
      });

      group('State Reset', () {
        test('should reset to default state', () {
          notifier.setName('Test Name');
          notifier.setDescription('Test Description');
          notifier.setEnableCodeInterpreter(true);
          notifier.setLoading(true);

          notifier.resetState();

          expect(notifier.state.name, isEmpty);
          expect(notifier.state.description, isEmpty);
          expect(notifier.state.instructions, isEmpty);
          expect(notifier.state.enableCodeInterpreter, isFalse);
          expect(notifier.state.enableFileSearch, isFalse);
          expect(notifier.state.codeInterpreterFiles, isEmpty);
          expect(notifier.state.fileSearchFiles, isEmpty);
          expect(notifier.state.isLoading, isFalse);
          expect(notifier.state.isUploadingFile, isFalse);
          expect(notifier.state.errorMessage, isNull);
        });
      });

      group('Load Agent for Editing', () {
        test('should load agent details successfully', () async {
          final mockAgent = AgentDetailModel(
            id: 'test-agent-id',
            name: 'Test Agent',
            description: 'Test Description',
            instructions: 'Test Instructions',
            model: 'gpt-4',
            tools: [
              {'type': 'code_interpreter'},
              {'type': 'file_search'},
            ],
            toolResources: AgentToolResourcesModel(
              codeInterpreter: ToolResourceFilesListModel(
                fileIds: ['code-file-1', 'code-file-2'],
              ),
              fileSearch: ToolResourceFilesListModel(
                fileIds: ['search-file-1'],
              ),
            ),
            files: [],
          );
          mockAgentService.mockAgentDetail = mockAgent;

          await notifier.loadAgentForEditing('test-agent-id');

          expect(notifier.state.name, equals('Test Agent'));
          expect(notifier.state.description, equals('Test Description'));
          expect(notifier.state.instructions, equals('Test Instructions'));
          expect(notifier.state.enableCodeInterpreter, isTrue);
          expect(notifier.state.enableFileSearch, isTrue);
          expect(notifier.state.codeInterpreterFiles, hasLength(2));
          expect(notifier.state.fileSearchFiles, hasLength(1));
          expect(notifier.state.isLoading, isFalse);
          expect(notifier.state.errorMessage, isNull);
          expect(mockAgentService.getAgentDetailsCalled, isTrue);
          expect(mockAgentService.lastGetDetailsAgentId, equals('test-agent-id'));
        });

        test('should handle agent with no tools', () async {
          final mockAgent = AgentDetailModel(
            id: 'simple-agent-id',
            name: 'Simple Agent',
            description: null,
            instructions: null,
            model: 'gpt-4',
            tools: [],
            toolResources: null,
            files: [],
          );
          mockAgentService.mockAgentDetail = mockAgent;

          await notifier.loadAgentForEditing('simple-agent-id');

          expect(notifier.state.name, equals('Simple Agent'));
          expect(notifier.state.description, isEmpty);
          expect(notifier.state.instructions, isEmpty);
          expect(notifier.state.enableCodeInterpreter, isFalse);
          expect(notifier.state.enableFileSearch, isFalse);
          expect(notifier.state.codeInterpreterFiles, isEmpty);
          expect(notifier.state.fileSearchFiles, isEmpty);
        });

        test('should handle load agent error', () async {
          mockAgentService.shouldThrowError = true;
          mockAgentService.errorMessage = 'Agent not found';

          await notifier.loadAgentForEditing('non-existent-id');

          expect(notifier.state.isLoading, isFalse);
          expect(notifier.state.errorMessage, contains('Agent not found'));
        });

        test('should handle agent with empty tool resources', () async {
          final mockAgent = AgentDetailModel(
            id: 'test-agent-id',
            name: 'Test Agent',
            description: 'Test Description',
            instructions: 'Test Instructions',
            model: 'gpt-4',
            tools: [
              {'type': 'code_interpreter'},
            ],
            toolResources: AgentToolResourcesModel(
              codeInterpreter: ToolResourceFilesListModel(fileIds: []),
              fileSearch: null,
            ),
            files: [],
          );
          mockAgentService.mockAgentDetail = mockAgent;

          await notifier.loadAgentForEditing('test-agent-id');

          expect(notifier.state.enableCodeInterpreter, isTrue);
          expect(notifier.state.enableFileSearch, isFalse);
          expect(notifier.state.codeInterpreterFiles, isEmpty);
          expect(notifier.state.fileSearchFiles, isEmpty);
        });
      });

      group('Save Agent', () {
        test('should create new agent successfully', () async {
          notifier.setName('New Agent');
          notifier.setDescription('New Description');
          notifier.setInstructions('New Instructions');
          notifier.setEnableCodeInterpreter(true);

          final result = await notifier.saveAgent();

          expect(result, isTrue);
          expect(notifier.state.isLoading, isFalse);
          expect(notifier.state.errorMessage, isNull);
          expect(mockAgentService.createAgentCalled, isTrue);
          expect(mockAgentService.lastCreatedAgent?.name, equals('New Agent'));
          expect(mockAgentService.lastCreatedAgent?.description, equals('New Description'));
          expect(mockAgentService.lastCreatedAgent?.instructions, equals('New Instructions'));
          expect(mockAgentService.lastCreatedAgent?.tools, hasLength(1));
          expect(mockAgentService.lastCreatedAgent?.tools.first['type'], equals('code_interpreter'));
        });

        test('should update existing agent successfully', () async {
          notifier.setName('Updated Agent');
          notifier.setInstructions('Updated Instructions');
          notifier.setEnableFileSearch(true);

          final result = await notifier.saveAgent(agentId: 'existing-agent-id');

          expect(result, isTrue);
          expect(mockAgentService.updateAgentCalled, isTrue);
          expect(mockAgentService.lastUpdatedAgentId, equals('existing-agent-id'));
          expect(mockAgentService.lastUpdatedAgent?.name, equals('Updated Agent'));
          expect(mockAgentService.lastUpdatedAgent?.tools.first['type'], equals('file_search'));
        });

        test('should fail when name is empty', () async {
          notifier.setName('');
          notifier.setInstructions('Valid Instructions');

          final result = await notifier.saveAgent();

          expect(result, isFalse);
          expect(notifier.state.errorMessage, contains('name cannot be empty'));
          expect(mockAgentService.createAgentCalled, isFalse);
        });

        test('should fail when instructions are empty', () async {
          notifier.setName('Valid Name');
          notifier.setInstructions('');

          final result = await notifier.saveAgent();

          expect(result, isFalse);
          expect(notifier.state.errorMessage, contains('Instructions cannot be empty'));
          expect(mockAgentService.createAgentCalled, isFalse);
        });

        test('should handle save error', () async {
          notifier.setName('Test Agent');
          notifier.setInstructions('Test Instructions');
          mockAgentService.shouldThrowError = true;
          mockAgentService.errorMessage = 'Save failed';

          final result = await notifier.saveAgent();

          expect(result, isFalse);
          expect(notifier.state.errorMessage, contains('Save failed'));
          expect(notifier.state.isLoading, isFalse);
        });

        test('should create agent with both tools and files', () async {
          final codeFiles = [UploadedFileInfo(
            fileId: 'code-file-1',
            fileName: 'test.py',
            fileSize: 1024,
            uploadedAt: DateTime.now(),
          )];
          final searchFiles = [UploadedFileInfo(
            fileId: 'search-file-1',
            fileName: 'data.csv',
            fileSize: 2048,
            uploadedAt: DateTime.now(),
          )];

          notifier.setName('Full Featured Agent');
          notifier.setInstructions('Test Instructions');
          notifier.setEnableCodeInterpreter(true);
          notifier.setEnableFileSearch(true);
          notifier.state = notifier.state.copyWith(
            codeInterpreterFiles: codeFiles,
            fileSearchFiles: searchFiles,
          );

          final result = await notifier.saveAgent();

          expect(result, isTrue);
          final savedAgent = mockAgentService.lastCreatedAgent!;
          expect(savedAgent.tools, hasLength(2));
          expect(savedAgent.tools.any((tool) => tool['type'] == 'code_interpreter'), isTrue);
          expect(savedAgent.tools.any((tool) => tool['type'] == 'file_search'), isTrue);
          expect(savedAgent.toolResources?.codeInterpreter?.fileIds, contains('code-file-1'));
          expect(savedAgent.toolResources?.fileSearch?.fileIds, contains('search-file-1'));
        });

        test('should handle empty description gracefully', () async {
          notifier.setName('Agent Name');
          notifier.setInstructions('Valid Instructions');
          notifier.setDescription('');

          final result = await notifier.saveAgent();

          expect(result, isTrue);
          expect(mockAgentService.lastCreatedAgent?.description, isNull);
        });

        test('should handle whitespace validation', () async {
          notifier.setName('   ');
          notifier.setInstructions('Valid Instructions');

          final result = await notifier.saveAgent();

          expect(result, isFalse);
          expect(notifier.state.errorMessage, contains('name cannot be empty'));
        });
      });

      group('File Upload', () {
        test('should not upload when already uploading', () async {
          notifier.state = notifier.state.copyWith(isUploadingFile: true);

          await notifier.uploadFileForTool('code_interpreter');

          expect(mockAgentService.uploadFileCalled, isFalse);
        });

        test('should handle upload error gracefully', () async {
          mockAgentService.shouldThrowError = true;
          mockAgentService.errorMessage = 'Upload failed';
          mockAgentService.mockUploadResponse = FileUploadResponseModel(
            providerFileId: 'provider-id',
            fileName: 'test.txt',
            message: 'Upload test failed',
          );

          await notifier.uploadFileForTool('code_interpreter');

          expect(notifier.state.isUploadingFile, isFalse);
          expect(notifier.state.errorMessage, contains('Upload failed'));
        });
      });
    });

    group('Provider Integration', () {
      test('should provide CreateAgentFormNotifier instance', () {
        final notifier = container.read(createAgentFormProvider.notifier);
        expect(notifier, isA<CreateAgentFormNotifier>());
      });

      test('should provide CreateAgentFormState', () {
        final state = container.read(createAgentFormProvider);
        expect(state, isA<CreateAgentFormState>());
      });

      test('should update state through provider', () {
        final notifier = container.read(createAgentFormProvider.notifier);
        notifier.setName('Provider Test');

        final state = container.read(createAgentFormProvider);
        expect(state.name, equals('Provider Test'));
      });

      test('should handle provider refresh', () {
        final initialNotifier = container.read(createAgentFormProvider.notifier);
        initialNotifier.setName('Initial Name');

        container.invalidate(createAgentFormProvider);

        final newNotifier = container.read(createAgentFormProvider.notifier);
        final newState = container.read(createAgentFormProvider);

        expect(newNotifier, isNot(same(initialNotifier)));
        expect(newState.name, isEmpty);
      });
    });

    group('Edge Cases', () {
      test('should handle very long text values', () {
        final longText = 'Very long text ' * 1000;
        final notifier = container.read(createAgentFormProvider.notifier);

        notifier.setName(longText);
        notifier.setDescription(longText);
        notifier.setInstructions(longText);

        expect(notifier.state.name, equals(longText));
        expect(notifier.state.description, equals(longText));
        expect(notifier.state.instructions, equals(longText));
      });

      test('should handle rapid state changes', () {
        final notifier = container.read(createAgentFormProvider.notifier);

        for (int i = 0; i < 100; i++) {
          notifier.setName('Name $i');
          notifier.setEnableCodeInterpreter(i.isEven);
        }

        expect(notifier.state.name, equals('Name 99'));
        expect(notifier.state.enableCodeInterpreter, isFalse);
      });

      test('should handle concurrent operations', () async {
        final notifier = container.read(createAgentFormProvider.notifier);
        notifier.setName('Concurrent Test');
        notifier.setInstructions('Concurrent Instructions');

        final futures = <Future>[];
        for (int i = 0; i < 5; i++) {
          futures.add(notifier.saveAgent());
        }

        final results = await Future.wait(futures);
        expect(results.every((result) => result == true), isTrue);
      });

      test('should handle special characters in file operations', () {
        final notifier = container.read(createAgentFormProvider.notifier);
        const specialFileName = 'file with émojis 🚀.txt';

        final fileInfo = UploadedFileInfo(
          fileId: 'special-file-id',
          fileName: specialFileName,
          fileSize: 1024,
          uploadedAt: DateTime.now(),
        );

        notifier.state = notifier.state.copyWith(
          codeInterpreterFiles: [fileInfo],
        );

        expect(notifier.state.codeInterpreterFiles.first.fileName, equals(specialFileName));

        notifier.removeFileFromTool('code_interpreter', 'special-file-id');
        expect(notifier.state.codeInterpreterFiles, isEmpty);
      });

      test('should maintain consistency across multiple updates', () async {
        final notifier = container.read(createAgentFormProvider.notifier);

        notifier.setName('Consistency Test');
        notifier.setDescription('Test Description');
        notifier.setInstructions('Test Instructions');
        notifier.setEnableCodeInterpreter(true);
        notifier.setEnableFileSearch(true);

        final beforeSave = notifier.state;
        final result = await notifier.saveAgent();
        final afterSave = notifier.state;

        expect(result, isTrue);
        expect(beforeSave.name, equals(afterSave.name));
        expect(beforeSave.description, equals(afterSave.description));
        expect(beforeSave.instructions, equals(afterSave.instructions));
        expect(beforeSave.enableCodeInterpreter, equals(afterSave.enableCodeInterpreter));
        expect(beforeSave.enableFileSearch, equals(afterSave.enableFileSearch));
        expect(afterSave.isLoading, isFalse);
      });
    });
  });
}