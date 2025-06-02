import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/data/models/agent_model.dart';

void main() {
  group('AgentListItemModel Tests', () {
    test('constructor should create agent with required fields', () {
      const agent = AgentListItemModel(
        id: 'test-id',
        name: 'Test Agent',
      );

      expect(agent.id, equals('test-id'));
      expect(agent.name, equals('Test Agent'));
      expect(agent.description, isNull);
      expect(agent.model, isNull);
      expect(agent.tool_types, isNull);
      expect(agent.createdAtDisplay, isNull);
      expect(agent.samplePrompt, isNull);
      expect(agent.metadata, isNull);
    });

    test('constructor should create agent with all fields', () {
      const agent = AgentListItemModel(
        id: 'test-id',
        name: 'Test Agent',
        description: 'Test description',
        model: 'gpt-4',
        tool_types: ['code_interpreter', 'file_search'],
        createdAtDisplay: '2024-01-01',
        samplePrompt: 'Hello',
        metadata: {'key': 'value'},
      );

      expect(agent.id, equals('test-id'));
      expect(agent.name, equals('Test Agent'));
      expect(agent.description, equals('Test description'));
      expect(agent.model, equals('gpt-4'));
      expect(agent.tool_types, equals(['code_interpreter', 'file_search']));
      expect(agent.createdAtDisplay, equals('2024-01-01'));
      expect(agent.samplePrompt, equals('Hello'));
      expect(agent.metadata, equals({'key': 'value'}));
    });

    test('fromJson should create agent from valid JSON', () {
      final json = {
        'id': 'test-id',
        'name': 'Test Agent',
        'description': 'Test description',
        'model': 'gpt-4',
        'tool_types': ['code_interpreter'],
        'created_at_display': '2024-01-01',
        'sample_prompt': 'Hello',
        'metadata': {'key': 'value'},
      };

      final agent = AgentListItemModel.fromJson(json);

      expect(agent.id, equals('test-id'));
      expect(agent.name, equals('Test Agent'));
      expect(agent.description, equals('Test description'));
      expect(agent.model, equals('gpt-4'));
      expect(agent.tool_types, equals(['code_interpreter']));
      expect(agent.createdAtDisplay, equals('2024-01-01'));
      expect(agent.samplePrompt, equals('Hello'));
      expect(agent.metadata, equals({'key': 'value'}));
    });

    test('fromJson should handle missing optional fields', () {
      final json = {
        'id': 'test-id',
        'name': 'Test Agent',
      };

      final agent = AgentListItemModel.fromJson(json);

      expect(agent.id, equals('test-id'));
      expect(agent.name, equals('Test Agent'));
      expect(agent.description, isNull);
      expect(agent.model, isNull);
      expect(agent.tool_types, isNull);
      expect(agent.createdAtDisplay, isNull);
      expect(agent.samplePrompt, isNull);
      expect(agent.metadata, isNull);
    });

    test('toJson should convert agent to JSON correctly', () {
      const agent = AgentListItemModel(
        id: 'test-id',
        name: 'Test Agent',
        description: 'Test description',
        model: 'gpt-4',
        tool_types: ['code_interpreter'],
        createdAtDisplay: '2024-01-01',
        samplePrompt: 'Hello',
        metadata: {'key': 'value'},
      );

      final json = agent.toJson();

      expect(json['id'], equals('test-id'));
      expect(json['name'], equals('Test Agent'));
      expect(json['description'], equals('Test description'));
      expect(json['model'], equals('gpt-4'));
      expect(json['tool_types'], equals(['code_interpreter']));
      expect(json['created_at_display'], equals('2024-01-01'));
      expect(json['sample_prompt'], equals('Hello'));
      expect(json['metadata'], equals({'key': 'value'}));
    });

    test('equality should work correctly', () {
      const agent1 = AgentListItemModel(
        id: 'test-id',
        name: 'Test Agent',
      );

      const agent2 = AgentListItemModel(
        id: 'test-id',
        name: 'Test Agent',
      );

      const agent3 = AgentListItemModel(
        id: 'different-id',
        name: 'Test Agent',
      );

      expect(agent1, equals(agent2));
      expect(agent1, isNot(equals(agent3)));
    });

    test('hashCode should be consistent', () {
      const agent1 = AgentListItemModel(
        id: 'test-id',
        name: 'Test Agent',
      );

      const agent2 = AgentListItemModel(
        id: 'test-id',
        name: 'Test Agent',
      );

      expect(agent1.hashCode, equals(agent2.hashCode));
    });
  });

  group('AgentFileDetailModel Tests', () {
    test('constructor should create file detail with required fields', () {
      const fileDetail = AgentFileDetailModel(
        fileId: 'file-123',
        fileName: 'test.txt',
      );

      expect(fileDetail.fileId, equals('file-123'));
      expect(fileDetail.fileName, equals('test.txt'));
    });

    test('fromJson should create file detail from valid JSON', () {
      final json = {
        'file_id': 'file-123',
        'file_name': 'test.txt',
      };

      final fileDetail = AgentFileDetailModel.fromJson(json);

      expect(fileDetail.fileId, equals('file-123'));
      expect(fileDetail.fileName, equals('test.txt'));
    });

    test('toJson should convert file detail to JSON correctly', () {
      const fileDetail = AgentFileDetailModel(
        fileId: 'file-123',
        fileName: 'test.txt',
      );

      final json = fileDetail.toJson();

      expect(json['file_id'], equals('file-123'));
      expect(json['file_name'], equals('test.txt'));
    });
  });

  group('ToolResourceFilesListModel Tests', () {
    test('constructor should create tool resource with required fields', () {
      const toolResource = ToolResourceFilesListModel(
        fileIds: ['file-1', 'file-2'],
      );

      expect(toolResource.fileIds, equals(['file-1', 'file-2']));
      expect(toolResource.files, isNull);
    });

    test('constructor should create tool resource with all fields', () {
      const fileDetails = [
        AgentFileDetailModel(fileId: 'file-1', fileName: 'test1.txt'),
        AgentFileDetailModel(fileId: 'file-2', fileName: 'test2.txt'),
      ];

      const toolResource = ToolResourceFilesListModel(
        fileIds: ['file-1', 'file-2'],
        files: fileDetails,
      );

      expect(toolResource.fileIds, equals(['file-1', 'file-2']));
      expect(toolResource.files, equals(fileDetails));
    });

    test('fromJson should create tool resource from valid JSON', () {
      final json = {
        'file_ids': ['file-1', 'file-2'],
        'files': [
          {'file_id': 'file-1', 'file_name': 'test1.txt'},
          {'file_id': 'file-2', 'file_name': 'test2.txt'},
        ],
      };

      final toolResource = ToolResourceFilesListModel.fromJson(json);

      expect(toolResource.fileIds, equals(['file-1', 'file-2']));
      expect(toolResource.files, hasLength(2));
      expect(toolResource.files![0].fileId, equals('file-1'));
      expect(toolResource.files![0].fileName, equals('test1.txt'));
    });

    test('fromJson should handle missing files field', () {
      final json = {
        'file_ids': ['file-1', 'file-2'],
      };

      final toolResource = ToolResourceFilesListModel.fromJson(json);

      expect(toolResource.fileIds, equals(['file-1', 'file-2']));
      expect(toolResource.files, isNull);
    });

    test('toJson should convert tool resource to JSON correctly', () {
      const fileDetails = [
        AgentFileDetailModel(fileId: 'file-1', fileName: 'test1.txt'),
      ];

      const toolResource = ToolResourceFilesListModel(
        fileIds: ['file-1'],
        files: fileDetails,
      );

      final json = toolResource.toJson();

      expect(json['file_ids'], equals(['file-1']));
      expect(json['files'], hasLength(1));
      expect(json['files'][0]['file_id'], equals('file-1'));
    });
  });

  group('AgentToolResourcesModel Tests', () {
    test('constructor should create tool resources with null fields', () {
      const toolResources = AgentToolResourcesModel();

      expect(toolResources.codeInterpreter, isNull);
      expect(toolResources.fileSearch, isNull);
    });

    test('constructor should create tool resources with all fields', () {
      const codeInterpreter = ToolResourceFilesListModel(fileIds: ['file-1']);
      const fileSearch = ToolResourceFilesListModel(fileIds: ['file-2']);

      const toolResources = AgentToolResourcesModel(
        codeInterpreter: codeInterpreter,
        fileSearch: fileSearch,
      );

      expect(toolResources.codeInterpreter, equals(codeInterpreter));
      expect(toolResources.fileSearch, equals(fileSearch));
    });

    test('fromJson should create tool resources from valid JSON', () {
      final json = {
        'code_interpreter': {
          'file_ids': ['file-1'],
        },
        'file_search': {
          'file_ids': ['file-2'],
        },
      };

      final toolResources = AgentToolResourcesModel.fromJson(json);

      expect(toolResources.codeInterpreter, isNotNull);
      expect(toolResources.codeInterpreter!.fileIds, equals(['file-1']));
      expect(toolResources.fileSearch, isNotNull);
      expect(toolResources.fileSearch!.fileIds, equals(['file-2']));
    });

    test('toJson should convert tool resources to JSON correctly', () {
      const codeInterpreter = ToolResourceFilesListModel(fileIds: ['file-1']);
      const fileSearch = ToolResourceFilesListModel(fileIds: ['file-2']);

      const toolResources = AgentToolResourcesModel(
        codeInterpreter: codeInterpreter,
        fileSearch: fileSearch,
      );

      final json = toolResources.toJson();

      expect(json['code_interpreter']['file_ids'], equals(['file-1']));
      expect(json['file_search']['file_ids'], equals(['file-2']));
    });
  });

  group('AgentDetailModel Tests', () {
    test('constructor should create agent detail with required fields', () {
      const agentDetail = AgentDetailModel(
        id: 'test-id',
        name: 'Test Agent',
        tools: [], files: [],
      );

      expect(agentDetail.id, equals('test-id'));
      expect(agentDetail.name, equals('Test Agent'));
      expect(agentDetail.tools, isEmpty);
      expect(agentDetail.description, isNull);
      expect(agentDetail.instructions, isNull);
      expect(agentDetail.model, isNull);
      expect(agentDetail.toolResources, isNull);
      expect(agentDetail.metadata, isNull);
    });

    test('fromJson should create agent detail from valid JSON', () {
      final json = {
        'id': 'test-id',
        'name': 'Test Agent',
        'description': 'Test description',
        'instructions': 'Test instructions',
        'model': 'gpt-4',
        'tools': [
          {'type': 'code_interpreter'},
          {'type': 'file_search'},
        ],
        'tool_resources': {
          'code_interpreter': {'file_ids': ['file-1']},
        },
        'metadata': {'key': 'value'},
      };

      final agentDetail = AgentDetailModel.fromJson(json);

      expect(agentDetail.id, equals('test-id'));
      expect(agentDetail.name, equals('Test Agent'));
      expect(agentDetail.description, equals('Test description'));
      expect(agentDetail.instructions, equals('Test instructions'));
      expect(agentDetail.model, equals('gpt-4'));
      expect(agentDetail.tools, hasLength(2));
      expect(agentDetail.toolResources, isNotNull);
      expect(agentDetail.metadata, equals({'key': 'value'}));
    });

    test('toJson should convert agent detail to JSON correctly', () {
      const toolResources = AgentToolResourcesModel(
        codeInterpreter: ToolResourceFilesListModel(fileIds: ['file-1']),
      );

      const agentDetail = AgentDetailModel(
        id: 'test-id',
        name: 'Test Agent',
        description: 'Test description',
        instructions: 'Test instructions',
        model: 'gpt-4',
        tools: [
          {'type': 'code_interpreter'},
        ],
        toolResources: toolResources,
        metadata: {'key': 'value'}, files: [],
      );

      final json = agentDetail.toJson();

      expect(json['id'], equals('test-id'));
      expect(json['name'], equals('Test Agent'));
      expect(json['description'], equals('Test description'));
      expect(json['instructions'], equals('Test instructions'));
      expect(json['model'], equals('gpt-4'));
      expect(json['tools'], hasLength(1));
      expect(json['tool_resources'], isNotNull);
      expect(json['metadata'], equals({'key': 'value'}));
    });

    test('toJson should handle null optional fields', () {
      const agentDetail = AgentDetailModel(
        id: 'test-id',
        name: 'Test Agent',
        tools: [], files: [],
      );

      final json = agentDetail.toJson();

      expect(json['id'], equals('test-id'));
      expect(json['name'], equals('Test Agent'));
      expect(json['tools'], isEmpty);
      expect(json.containsKey('description'), isFalse);
      expect(json.containsKey('instructions'), isFalse);
      expect(json.containsKey('model'), isFalse);
      expect(json.containsKey('tool_resources'), isFalse);
      expect(json.containsKey('metadata'), isFalse);
    });
  });
}