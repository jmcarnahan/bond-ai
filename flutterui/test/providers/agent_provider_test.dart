import 'dart:typed_data';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/providers/agent_provider.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/data/models/api_response_models.dart';
import 'package:flutterui/data/services/agent_service.dart';
import 'package:flutterui/data/services/agent_service/agent_file_service.dart';

class MockAgentService implements AgentService {
  List<AgentListItemModel> mockAgents = [];
  Map<String, AgentDetailModel> mockAgentDetails = {};
  bool shouldThrowError = false;
  String? errorMessage;

  @override
  Future<List<AgentListItemModel>> getAgents() async {
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock error');
    }
    return mockAgents;
  }

  @override
  Future<AgentDetailModel> getAgentDetails(String agentId) async {
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock error');
    }
    if (!mockAgentDetails.containsKey(agentId)) {
      throw Exception('Agent not found');
    }
    return mockAgentDetails[agentId]!;
  }

  @override
  Future<AgentResponseModel> createAgent(AgentDetailModel agent) async {
    throw UnimplementedError();
  }

  @override
  Future<FileUploadResponseModel> uploadFile(String fileName, Uint8List fileBytes) async {
    throw UnimplementedError();
  }

  @override
  Future<AgentResponseModel> updateAgent(String agentId, AgentDetailModel agent) async {
    throw UnimplementedError();
  }

  @override
  Future<void> deleteAgent(String agentId) async {
    throw UnimplementedError();
  }

  @override
  Future<void> deleteFile(String providerFileId) async {
    throw UnimplementedError();
  }

  @override
  void dispose() {}

  @override
  Future<FileInfoModel> getFileInfo(String providerFileId) async {
    throw UnimplementedError();
  }

  @override
  Future<List<FileInfoModel>> getFiles() async {
    throw UnimplementedError();
  }
}

void main() {
  group('Agent Provider Tests', () {
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

    group('agentsProvider', () {
      test('should return list of agents when service succeeds', () async {
        final testAgents = [
          AgentListItemModel(
            id: 'agent-1',
            name: 'Test Agent 1',
            description: 'Test Description 1',
          ),
          AgentListItemModel(
            id: 'agent-2',
            name: 'Test Agent 2',
            description: 'Test Description 2',
          ),
        ];
        mockAgentService.mockAgents = testAgents;

        final result = await container.read(agentsProvider.future);

        expect(result, equals(testAgents));
        expect(result, hasLength(2));
        expect(result[0].id, equals('agent-1'));
        expect(result[0].name, equals('Test Agent 1'));
        expect(result[1].id, equals('agent-2'));
        expect(result[1].name, equals('Test Agent 2'));
      });

      test('should return empty list when no agents exist', () async {
        mockAgentService.mockAgents = [];

        final result = await container.read(agentsProvider.future);

        expect(result, isEmpty);
      });

      test('should throw exception when service fails', () async {
        mockAgentService.shouldThrowError = true;
        mockAgentService.errorMessage = 'Network error';

        expect(
          () => container.read(agentsProvider.future),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Network error'),
          )),
        );
      });

      test('should handle service throwing generic exception', () async {
        mockAgentService.shouldThrowError = true;

        expect(
          () => container.read(agentsProvider.future),
          throwsA(isA<Exception>()),
        );
      });

      test('should refresh data when provider is invalidated', () async {
        final initialAgents = [
          AgentListItemModel(
            id: 'agent-1',
            name: 'Initial Agent',
            description: 'Initial Description',
          ),
        ];
        mockAgentService.mockAgents = initialAgents;

        final initialResult = await container.read(agentsProvider.future);
        expect(initialResult, hasLength(1));

        final updatedAgents = [
          AgentListItemModel(
            id: 'agent-1',
            name: 'Updated Agent',
            description: 'Updated Description',
          ),
          AgentListItemModel(
            id: 'agent-2',
            name: 'New Agent',
            description: 'New Description',
          ),
        ];
        mockAgentService.mockAgents = updatedAgents;

        container.invalidate(agentsProvider);

        final updatedResult = await container.read(agentsProvider.future);
        expect(updatedResult, hasLength(2));
        expect(updatedResult[0].name, equals('Updated Agent'));
        expect(updatedResult[1].name, equals('New Agent'));
      });

      test('should handle agents with special characters', () async {
        final specialAgents = [
          AgentListItemModel(
            id: 'agent-special',
            name: 'Agent with émojis 🤖',
            description: 'Description with spëcial chars @#\$%',
          ),
        ];
        mockAgentService.mockAgents = specialAgents;

        final result = await container.read(agentsProvider.future);

        expect(result, hasLength(1));
        expect(result[0].name, equals('Agent with émojis 🤖'));
        expect(result[0].description, equals('Description with spëcial chars @#\$%'));
      });

      test('should handle agents with empty properties', () async {
        final emptyAgents = [
          AgentListItemModel(
            id: '',
            name: '',
            description: '',
          ),
        ];
        mockAgentService.mockAgents = emptyAgents;

        final result = await container.read(agentsProvider.future);

        expect(result, hasLength(1));
        expect(result[0].id, equals(''));
        expect(result[0].name, equals(''));
        expect(result[0].description, equals(''));
      });
    });

    group('selectedAgentProvider', () {
      test('should start with null state', () {
        final notifier = container.read(selectedAgentProvider.notifier);
        final state = container.read(selectedAgentProvider);

        expect(state, isNull);
        expect(notifier, isA<SelectedAgentNotifier>());
      });

      test('should select agent correctly', () {
        final testAgent = AgentListItemModel(
          id: 'test-agent',
          name: 'Test Agent',
          description: 'Test Description',
        );

        final notifier = container.read(selectedAgentProvider.notifier);
        notifier.selectAgent(testAgent);

        final state = container.read(selectedAgentProvider);
        expect(state, equals(testAgent));
        expect(state?.id, equals('test-agent'));
        expect(state?.name, equals('Test Agent'));
      });

      test('should clear agent selection', () {
        final testAgent = AgentListItemModel(
          id: 'test-agent',
          name: 'Test Agent',
          description: 'Test Description',
        );

        final notifier = container.read(selectedAgentProvider.notifier);
        notifier.selectAgent(testAgent);

        expect(container.read(selectedAgentProvider), equals(testAgent));

        notifier.clearAgent();

        final state = container.read(selectedAgentProvider);
        expect(state, isNull);
      });

      test('should handle multiple agent selections', () {
        final agent1 = AgentListItemModel(
          id: 'agent-1',
          name: 'Agent 1',
          description: 'Description 1',
        );
        final agent2 = AgentListItemModel(
          id: 'agent-2',
          name: 'Agent 2',
          description: 'Description 2',
        );

        final notifier = container.read(selectedAgentProvider.notifier);
        
        notifier.selectAgent(agent1);
        expect(container.read(selectedAgentProvider), equals(agent1));

        notifier.selectAgent(agent2);
        expect(container.read(selectedAgentProvider), equals(agent2));
      });

      test('should handle selecting same agent multiple times', () {
        final testAgent = AgentListItemModel(
          id: 'test-agent',
          name: 'Test Agent',
          description: 'Test Description',
        );

        final notifier = container.read(selectedAgentProvider.notifier);
        
        notifier.selectAgent(testAgent);
        notifier.selectAgent(testAgent);
        notifier.selectAgent(testAgent);

        final state = container.read(selectedAgentProvider);
        expect(state, equals(testAgent));
      });

      test('should clear selection multiple times without error', () {
        final notifier = container.read(selectedAgentProvider.notifier);
        
        notifier.clearAgent();
        notifier.clearAgent();
        notifier.clearAgent();

        final state = container.read(selectedAgentProvider);
        expect(state, isNull);
      });

      test('should handle agent with special characters', () {
        final specialAgent = AgentListItemModel(
          id: 'special-agent-🤖',
          name: 'Agent with émojis 🚀',
          description: 'Description with spëcial chars',
        );

        final notifier = container.read(selectedAgentProvider.notifier);
        notifier.selectAgent(specialAgent);

        final state = container.read(selectedAgentProvider);
        expect(state, equals(specialAgent));
        expect(state?.name, equals('Agent with émojis 🚀'));
      });

      test('should handle agent with empty properties', () {
        final emptyAgent = AgentListItemModel(
          id: '',
          name: '',
          description: '',
        );

        final notifier = container.read(selectedAgentProvider.notifier);
        notifier.selectAgent(emptyAgent);

        final state = container.read(selectedAgentProvider);
        expect(state, equals(emptyAgent));
        expect(state?.id, equals(''));
        expect(state?.name, equals(''));
      });
    });

    group('agentDetailProvider', () {
      test('should return agent details for valid agent ID', () async {
        final testDetail = AgentDetailModel(
          id: 'agent-detail-1',
          name: 'Detailed Agent',
          description: 'Detailed Description',
          instructions: 'Test Instructions',
          model: 'gpt-4',
          tools: const [],
          files: const [],
        );
        mockAgentService.mockAgentDetails['agent-detail-1'] = testDetail;

        final result = await container.read(agentDetailProvider('agent-detail-1').future);

        expect(result, equals(testDetail));
        expect(result.id, equals('agent-detail-1'));
        expect(result.name, equals('Detailed Agent'));
        expect(result.instructions, equals('Test Instructions'));
        expect(result.model, equals('gpt-4'));
      });

      test('should throw exception for non-existent agent ID', () async {
        expect(
          () => container.read(agentDetailProvider('non-existent').future),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Agent not found'),
          )),
        );
      });

      test('should handle service error when fetching details', () async {
        mockAgentService.shouldThrowError = true;
        mockAgentService.errorMessage = 'Service unavailable';

        expect(
          () => container.read(agentDetailProvider('any-id').future),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Service unavailable'),
          )),
        );
      });

      test('should handle multiple concurrent requests for different agents', () async {
        final detail1 = AgentDetailModel(
          id: 'agent-1',
          name: 'Agent 1',
          description: 'Description 1',
          instructions: 'Instructions 1',
          model: 'gpt-4',
          tools: const [],
          files: const [],
        );
        final detail2 = AgentDetailModel(
          id: 'agent-2',
          name: 'Agent 2',
          description: 'Description 2',
          instructions: 'Instructions 2',
          model: 'gpt-3.5',
          tools: const [],
          files: const [],
        );

        mockAgentService.mockAgentDetails['agent-1'] = detail1;
        mockAgentService.mockAgentDetails['agent-2'] = detail2;

        final future1 = container.read(agentDetailProvider('agent-1').future);
        final future2 = container.read(agentDetailProvider('agent-2').future);

        final results = await Future.wait([future1, future2]);

        expect(results[0], equals(detail1));
        expect(results[1], equals(detail2));
        expect(results[0].name, equals('Agent 1'));
        expect(results[1].name, equals('Agent 2'));
      });

      test('should handle agent detail with complex data', () async {
        final complexDetail = AgentDetailModel(
          id: 'complex-agent',
          name: 'Complex Agent with émojis 🤖',
          description: 'Complex description with spëcial chars',
          instructions: 'Very long instructions with multiple lines\nand special characters @#\$%',
          model: 'gpt-4-turbo',
          tools: const [
            {'type': 'code_interpreter'},
            {'type': 'file_search'},
          ],
          files: const [
            {'id': 'file-1', 'name': 'document.pdf'},
            {'id': 'file-2', 'name': 'data.csv'},
          ],
        );

        mockAgentService.mockAgentDetails['complex-agent'] = complexDetail;

        final result = await container.read(agentDetailProvider('complex-agent').future);

        expect(result, equals(complexDetail));
        expect(result.name, contains('émojis 🤖'));
        expect(result.tools, hasLength(2));
        expect(result.files, hasLength(2));
        expect(result.instructions, contains('multiple lines\nand special'));
      });

      test('should handle agent detail with empty properties', () async {
        final emptyDetail = AgentDetailModel(
          id: '',
          name: '',
          description: '',
          instructions: '',
          model: '',
          tools: const [],
          files: const [],
        );

        mockAgentService.mockAgentDetails[''] = emptyDetail;

        final result = await container.read(agentDetailProvider('').future);

        expect(result, equals(emptyDetail));
        expect(result.id, equals(''));
        expect(result.name, equals(''));
        expect(result.tools, isEmpty);
        expect(result.files, isEmpty);
      });

      test('should cache results correctly', () async {
        final testDetail = AgentDetailModel(
          id: 'cached-agent',
          name: 'Cached Agent',
          description: 'Cached Description',
          instructions: 'Cached Instructions',
          model: 'gpt-4',
          tools: const [],
          files: const [],
        );

        mockAgentService.mockAgentDetails['cached-agent'] = testDetail;

        final result1 = await container.read(agentDetailProvider('cached-agent').future);
        final result2 = await container.read(agentDetailProvider('cached-agent').future);

        expect(result1, equals(result2));
        expect(result1, equals(testDetail));
      });

      test('should handle special character agent IDs', () async {
        const specialId = 'agent-with-special-@#%';
        final testDetail = AgentDetailModel(
          id: specialId,
          name: 'Special ID Agent',
          description: 'Description',
          instructions: 'Instructions',
          model: 'gpt-4',
          tools: const [],
          files: const [],
        );

        mockAgentService.mockAgentDetails[specialId] = testDetail;

        final result = await container.read(agentDetailProvider(specialId).future);

        expect(result, equals(testDetail));
        expect(result.id, equals(specialId));
      });
    });

    group('Provider Integration', () {
      test('should work together for complete agent workflow', () async {
        final agents = [
          AgentListItemModel(
            id: 'workflow-agent',
            name: 'Workflow Agent',
            description: 'Test Description',
          ),
        ];
        final agentDetail = AgentDetailModel(
          id: 'workflow-agent',
          name: 'Workflow Agent Detailed',
          description: 'Detailed Description',
          instructions: 'Detailed Instructions',
          model: 'gpt-4',
          tools: const [],
          files: const [],
        );

        mockAgentService.mockAgents = agents;
        mockAgentService.mockAgentDetails['workflow-agent'] = agentDetail;

        final agentsList = await container.read(agentsProvider.future);
        expect(agentsList, hasLength(1));

        final selectedNotifier = container.read(selectedAgentProvider.notifier);
        selectedNotifier.selectAgent(agentsList[0]);

        final selectedAgent = container.read(selectedAgentProvider);
        expect(selectedAgent, equals(agentsList[0]));

        final detailResult = await container.read(agentDetailProvider('workflow-agent').future);
        expect(detailResult, equals(agentDetail));
        expect(detailResult.name, equals('Workflow Agent Detailed'));
      });

      test('should handle provider refresh scenarios', () async {
        final initialAgents = [
          AgentListItemModel(
            id: 'refresh-agent',
            name: 'Initial Agent',
            description: 'Initial Description',
          ),
        ];
        mockAgentService.mockAgents = initialAgents;

        final initialResult = await container.read(agentsProvider.future);
        expect(initialResult, hasLength(1));

        final notifier = container.read(selectedAgentProvider.notifier);
        notifier.selectAgent(initialResult[0]);

        container.invalidate(agentsProvider);

        final updatedAgents = [
          AgentListItemModel(
            id: 'refresh-agent',
            name: 'Updated Agent',
            description: 'Updated Description',
          ),
        ];
        mockAgentService.mockAgents = updatedAgents;

        final updatedResult = await container.read(agentsProvider.future);
        expect(updatedResult[0].name, equals('Updated Agent'));

        final selectedAgent = container.read(selectedAgentProvider);
        expect(selectedAgent?.name, equals('Initial Agent'));
      });
    });

    group('Error Handling Edge Cases', () {
      test('should handle null values gracefully', () async {
        final notifier = container.read(selectedAgentProvider.notifier);
        
        expect(() => notifier.clearAgent(), returnsNormally);
        expect(container.read(selectedAgentProvider), isNull);
      });

      test('should handle rapid state changes', () async {
        final agents = List.generate(10, (index) => AgentListItemModel(
          id: 'agent-$index',
          name: 'Agent $index',
          description: 'Description $index',
        ));

        final notifier = container.read(selectedAgentProvider.notifier);

        for (final agent in agents) {
          notifier.selectAgent(agent);
        }

        final finalState = container.read(selectedAgentProvider);
        expect(finalState?.id, equals('agent-9'));
      });
    });
  });
}