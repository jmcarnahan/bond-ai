@TestOn('browser')
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/providers/create_agent_form_provider.dart';
import 'package:flutterui/data/services/agent_service/agent_service.dart';
import 'package:flutterui/data/services/file_service.dart';
import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/data/models/api_response_models.dart';
import 'package:file_picker/file_picker.dart';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

class MockAgentService implements AgentService {
  Future<AgentResponseModel> Function(AgentDetailModel)? createAgentStub;
  Future<AgentResponseModel> Function(String, AgentDetailModel)?
      updateAgentStub;
  Future<void> Function(String)? deleteAgentStub;

  @override
  Future<AgentResponseModel> createAgent(AgentDetailModel agentData) {
    if (createAgentStub != null) return createAgentStub!(agentData);
    return Future.value(
        AgentResponseModel(agentId: 'agent-1', name: agentData.name));
  }

  @override
  Future<AgentResponseModel> updateAgent(
      String agentId, AgentDetailModel agentData) {
    if (updateAgentStub != null) return updateAgentStub!(agentId, agentData);
    return Future.value(
        AgentResponseModel(agentId: agentId, name: agentData.name));
  }

  @override
  Future<void> deleteAgent(String agentId) {
    if (deleteAgentStub != null) return deleteAgentStub!(agentId);
    return Future.value();
  }

  // Stubs for other methods not relevant to these tests
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class MockFileService implements FileService {
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

({CreateAgentFormNotifier notifier, MockAgentService mockAgent})
    _createNotifier({MockAgentService? mockAgent}) {
  final agent = mockAgent ?? MockAgentService();
  final notifier = CreateAgentFormNotifier(
    agentService: agent,
    fileService: MockFileService(),
    getDefaultModel: () => 'gpt-4',
  );
  return (notifier: notifier, mockAgent: agent);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  group('CreateAgentFormNotifier', () {
    group('clearError', () {
      test('clears errorMessage from state', () async {
        final setup = _createNotifier();

        // Set an error first via setName + saveAgent with empty instructions
        setup.notifier.setName('Test');
        // Manually set an error by trying to save with empty instructions
        // which sets errorMessage = "Instructions cannot be empty."

        // Directly test clearError by setting error state first
        setup.notifier.setName(''); // clear name so save would fail
        await setup.notifier.saveAgent(); // will set error: "Agent name cannot be empty."

        // Verify error is set
        expect(setup.notifier.state.errorMessage, isNotNull);

        // Now clear it
        setup.notifier.clearError();
        expect(setup.notifier.state.errorMessage, isNull);
      });

      test('clearError when no error is a no-op', () {
        final setup = _createNotifier();
        expect(setup.notifier.state.errorMessage, isNull);

        setup.notifier.clearError();
        expect(setup.notifier.state.errorMessage, isNull);
      });
    });

    group('validation errors', () {
      test('empty name sets validation error', () async {
        final setup = _createNotifier();
        setup.notifier.setInstructions('Do something');

        final result = await setup.notifier.saveAgent();

        expect(result, isFalse);
        expect(setup.notifier.state.errorMessage,
            'Agent name cannot be empty.');
      });

      test('empty instructions sets validation error', () async {
        final setup = _createNotifier();
        setup.notifier.setName('Test Agent');

        final result = await setup.notifier.saveAgent();

        expect(result, isFalse);
        expect(setup.notifier.state.errorMessage,
            'Instructions cannot be empty.');
      });
    });

    group('saveAgent error handling', () {
      test('humanizes 409 conflict error from API', () async {
        final setup = _createNotifier();
        setup.notifier.setName('Test Agent');
        setup.notifier.setInstructions('Do something');

        setup.mockAgent.createAgentStub = (_) =>
            throw Exception(
                'Failed to create agent: 409 {"detail": "Agent already exists"}');

        final result = await setup.notifier.saveAgent();

        expect(result, isFalse);
        expect(
          setup.notifier.state.errorMessage,
          'An agent with this name already exists. Please choose a different name.',
        );
      });

      test('humanizes 403 permission error from API', () async {
        final setup = _createNotifier();
        setup.notifier.setName('Test Agent');
        setup.notifier.setInstructions('Do something');

        setup.mockAgent.updateAgentStub = (_, __) =>
            throw Exception(
                'Failed to update agent: 403 {"detail": "You do not have permission to edit this agent."}');

        final result =
            await setup.notifier.saveAgent(agentId: 'existing-agent');

        expect(result, isFalse);
        expect(
          setup.notifier.state.errorMessage,
          'You do not have permission to perform this action.',
        );
      });

      test('humanizes 500 server error', () async {
        final setup = _createNotifier();
        setup.notifier.setName('Test Agent');
        setup.notifier.setInstructions('Do something');

        setup.mockAgent.createAgentStub = (_) =>
            throw Exception('Failed to create agent: 500 Internal Server Error');

        final result = await setup.notifier.saveAgent();

        expect(result, isFalse);
        expect(
          setup.notifier.state.errorMessage,
          'A server error occurred. Please try again later.',
        );
      });
    });

    group('deleteAgent error handling', () {
      test('humanizes delete error', () async {
        final setup = _createNotifier();

        setup.mockAgent.deleteAgentStub = (_) =>
            throw Exception(
                'Failed to delete agent: 403 {"detail": "You do not have permission"}');

        final result = await setup.notifier.deleteAgent('agent-1');

        expect(result, isFalse);
        expect(
          setup.notifier.state.errorMessage,
          'You do not have permission to perform this action.',
        );
      });
    });
  });
}
