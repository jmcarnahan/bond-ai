@TestOn('browser')
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/providers/create_agent_form_provider.dart';
import 'package:flutterui/data/services/agent_service/agent_service.dart';
import 'package:flutterui/data/services/file_service.dart';
import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/data/models/api_response_models.dart';
import 'package:flutterui/data/models/model_info.dart';
import 'package:flutterui/data/models/group_model.dart';
import 'package:flutterui/providers/models_provider.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import 'package:flutterui/data/services/mcp_service.dart';
import 'package:flutterui/data/models/mcp_model.dart';
import 'package:flutterui/presentation/screens/agents/create_agent_screen.dart';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

class MockAgentService implements AgentService {
  @override
  Future<AgentResponseModel> createAgent(AgentDetailModel data) =>
      Future.value(AgentResponseModel(agentId: 'a1', name: data.name));

  @override
  Future<AgentResponseModel> updateAgent(String id, AgentDetailModel data) =>
      Future.value(AgentResponseModel(agentId: id, name: data.name));

  @override
  Future<void> deleteAgent(String id) => Future.value();

  @override
  Future<List<AgentListItemModel>> getAgents() => Future.value([]);

  @override
  Future<AgentDetailModel> getAgentDetails(String id) =>
      throw UnimplementedError();

  @override
  Future<List<AvailableGroup>> getAvailableGroups([String? agentId]) =>
      Future.value([]);

  @override
  Future<List<ModelInfo>> getAvailableModels() => Future.value([
        ModelInfo(name: 'gpt-4', description: 'GPT-4 model', isDefault: true),
      ]);

  @override
  Future<AgentResponseModel> getDefaultAgent() =>
      Future.value(AgentResponseModel(agentId: 'default', name: 'Home'));

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class MockFileService implements FileService {
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class MockMcpService implements McpService {
  @override
  Future<McpToolsGroupedResponse> getToolsGrouped() =>
      Future.value(const McpToolsGroupedResponse(
        servers: [],
        totalServers: 0,
        totalTools: 0,
      ));

  @override
  Future<List<McpResourceModel>> getResources() => Future.value([]);

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

Future<ProviderContainer> _pumpCreateAgentScreen(
  WidgetTester tester,
) async {
  final mockAgent = MockAgentService();
  final mockFile = MockFileService();

  final container = ProviderContainer(
    overrides: [
      agentServiceProvider.overrideWithValue(mockAgent),
      fileServiceProvider.overrideWithValue(mockFile),
      mcpServiceProvider.overrideWithValue(MockMcpService()),
      availableModelsProvider.overrideWith(
        (ref) async => [ModelInfo(name: 'gpt-4', description: 'GPT-4 model', isDefault: true)],
      ),
      defaultModelProvider.overrideWith((ref) => 'gpt-4'),
    ],
  );

  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: const MaterialApp(
        home: CreateAgentScreen(),
      ),
    ),
  );

  await tester.pumpAndSettle();

  return container;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  group('CreateAgentScreen', () {
    group('save button hint text', () {
      testWidgets('shows hint for both missing fields when form is empty',
          (tester) async {
        await _pumpCreateAgentScreen(tester);

        expect(
          find.text('Please fill in: Agent Name, Instructions'),
          findsOneWidget,
        );
      });

      testWidgets('shows hint for missing Instructions when name is filled',
          (tester) async {
        await _pumpCreateAgentScreen(tester);

        // Type into the Agent Name field
        await tester.enterText(
          find.widgetWithText(TextFormField, '').first,
          'My Agent',
        );
        await tester.pump();

        expect(
          find.text('Please fill in: Instructions'),
          findsOneWidget,
        );
      });

      testWidgets('no hint when both fields are filled', (tester) async {
        await _pumpCreateAgentScreen(tester);

        // Find all TextFormField widgets and fill the required ones
        final textFields = find.byType(TextFormField);

        // First field is Agent Name
        await tester.enterText(textFields.first, 'My Agent');
        await tester.pump();

        // Find the Instructions field (third field - after Name and Description)
        await tester.enterText(textFields.at(2), 'Do something useful');
        await tester.pump();

        expect(find.textContaining('Please fill in'), findsNothing);
      });

      testWidgets('Create Agent button is disabled when fields are empty',
          (tester) async {
        await _pumpCreateAgentScreen(tester);

        final button = tester.widget<ElevatedButton>(
          find.widgetWithText(ElevatedButton, 'Create Agent'),
        );
        expect(button.onPressed, isNull);
      });

      testWidgets(
          'Create Agent button is enabled when required fields are filled',
          (tester) async {
        await _pumpCreateAgentScreen(tester);

        final textFields = find.byType(TextFormField);
        await tester.enterText(textFields.first, 'My Agent');
        await tester.enterText(textFields.at(2), 'Instructions here');
        await tester.pump();

        final button = tester.widget<ElevatedButton>(
          find.widgetWithText(ElevatedButton, 'Create Agent'),
        );
        expect(button.onPressed, isNotNull);
      });
    });

    group('error banner', () {
      testWidgets('no error banner text initially', (tester) async {
        await _pumpCreateAgentScreen(tester);

        expect(find.text('Agent name cannot be empty.'), findsNothing);
        expect(find.text('Instructions cannot be empty.'), findsNothing);
      });

      testWidgets('error banner appears when error is set via notifier',
          (tester) async {
        final container = await _pumpCreateAgentScreen(tester);

        // Set an error via the notifier
        final notifier = container.read(createAgentFormProvider.notifier);
        notifier.setName(''); // ensure empty
        await notifier.saveAgent(); // triggers "Agent name cannot be empty."
        await tester.pumpAndSettle();

        expect(find.text('Agent name cannot be empty.'), findsOneWidget);
      });

      testWidgets('error banner dismiss button clears the error',
          (tester) async {
        final container = await _pumpCreateAgentScreen(tester);

        // Set an error
        final notifier = container.read(createAgentFormProvider.notifier);
        await notifier.saveAgent(); // empty name
        await tester.pumpAndSettle();

        expect(find.text('Agent name cannot be empty.'), findsOneWidget);

        // Tap the dismiss close button on the error banner
        await tester.tap(find.byIcon(Icons.close));
        await tester.pumpAndSettle();

        expect(find.text('Agent name cannot be empty.'), findsNothing);
      });
    });
  });
}
