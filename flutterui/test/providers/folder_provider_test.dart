@TestOn('browser')
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/providers/agent_provider.dart';
import 'package:flutterui/providers/folder_provider.dart';

void main() {
  // Test agents: some in folders, some not
  final testAgents = [
    const AgentListItemModel(id: 'a1', name: 'Agent 1', folderId: null),
    const AgentListItemModel(id: 'a2', name: 'Agent 2', folderId: 'fld_work'),
    const AgentListItemModel(id: 'a3', name: 'Agent 3', folderId: 'fld_work'),
    const AgentListItemModel(id: 'a4', name: 'Agent 4', folderId: 'fld_personal'),
    const AgentListItemModel(id: 'a5', name: 'Agent 5', folderId: null),
  ];

  /// Helper: wait for an AsyncValue provider to emit data.
  Future<List<AgentListItemModel>> waitForAgents(
    ProviderContainer container,
    ProviderListenable<AsyncValue<List<AgentListItemModel>>> provider,
  ) async {
    // Read once to kick off the future
    final initial = container.read(provider);
    if (initial is AsyncData<List<AgentListItemModel>>) {
      return initial.value;
    }
    // Wait for data via listener
    final completer = <List<AgentListItemModel>>[];
    container.listen<AsyncValue<List<AgentListItemModel>>>(provider, (prev, next) {
      next.whenData((data) => completer.add(data));
    });
    // Pump microtasks
    await Future<void>.delayed(Duration.zero);
    await Future<void>.delayed(Duration.zero);
    final result = container.read(provider);
    return result.when(
      data: (d) => d,
      loading: () => throw StateError('Still loading'),
      error: (e, s) => throw e,
    );
  }

  group('visibleAgentsProvider', () {
    test('returns only unfiled agents when no folder is open', () async {
      final container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => Future.value(testAgents)),
          currentFolderProvider.overrideWith((ref) => null),
        ],
      );
      addTearDown(container.dispose);

      final agents = await waitForAgents(container, visibleAgentsProvider);
      expect(agents.length, 2);
      expect(agents.map((a) => a.id).toList(), ['a1', 'a5']);
    });

    test('returns only agents in the selected folder', () async {
      final container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => Future.value(testAgents)),
          currentFolderProvider.overrideWith((ref) => 'fld_work'),
        ],
      );
      addTearDown(container.dispose);

      final agents = await waitForAgents(container, visibleAgentsProvider);
      expect(agents.length, 2);
      expect(agents.map((a) => a.id).toList(), ['a2', 'a3']);
    });

    test('returns empty list for folder with no agents', () async {
      final container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => Future.value(testAgents)),
          currentFolderProvider.overrideWith((ref) => 'fld_empty'),
        ],
      );
      addTearDown(container.dispose);

      final agents = await waitForAgents(container, visibleAgentsProvider);
      expect(agents.length, 0);
    });
  });

  group('sidebarAgentsProvider', () {
    test('returns only agents not in any folder', () async {
      final container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => Future.value(testAgents)),
        ],
      );
      addTearDown(container.dispose);

      final agents = await waitForAgents(container, sidebarAgentsProvider);
      expect(agents.length, 2);
      expect(agents.map((a) => a.id).toList(), ['a1', 'a5']);
      for (final agent in agents) {
        expect(agent.folderId, isNull);
      }
    });

    test('returns all agents when none are in folders', () async {
      final unfolderedAgents = [
        const AgentListItemModel(id: 'a1', name: 'Agent 1', folderId: null),
        const AgentListItemModel(id: 'a2', name: 'Agent 2', folderId: null),
      ];

      final container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => Future.value(unfolderedAgents)),
        ],
      );
      addTearDown(container.dispose);

      final agents = await waitForAgents(container, sidebarAgentsProvider);
      expect(agents.length, 2);
    });

    test('returns empty when all agents are in folders', () async {
      final allFoldered = [
        const AgentListItemModel(id: 'a1', name: 'Agent 1', folderId: 'fld_1'),
        const AgentListItemModel(id: 'a2', name: 'Agent 2', folderId: 'fld_2'),
      ];

      final container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => Future.value(allFoldered)),
        ],
      );
      addTearDown(container.dispose);

      final agents = await waitForAgents(container, sidebarAgentsProvider);
      expect(agents.length, 0);
    });
  });

  group('visibleAgentsProvider sorting', () {
    test('sorts agents by sortOrder ascending, nulls at end', () async {
      final sortedAgents = [
        const AgentListItemModel(id: 'a1', name: 'Agent 1', folderId: null, sortOrder: 2),
        const AgentListItemModel(id: 'a2', name: 'Agent 2', folderId: null, sortOrder: 0),
        const AgentListItemModel(id: 'a3', name: 'Agent 3', folderId: null, sortOrder: 1),
        const AgentListItemModel(id: 'a4', name: 'Agent 4', folderId: null, sortOrder: null),
      ];

      final container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => Future.value(sortedAgents)),
          currentFolderProvider.overrideWith((ref) => null),
        ],
      );
      addTearDown(container.dispose);

      final agents = await waitForAgents(container, visibleAgentsProvider);
      expect(agents.map((a) => a.id).toList(), ['a2', 'a3', 'a1', 'a4']);
    });

    test('agents with all null sortOrder preserve original order', () async {
      final unsorted = [
        const AgentListItemModel(id: 'a1', name: 'Agent 1', folderId: null),
        const AgentListItemModel(id: 'a2', name: 'Agent 2', folderId: null),
        const AgentListItemModel(id: 'a3', name: 'Agent 3', folderId: null),
      ];

      final container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => Future.value(unsorted)),
          currentFolderProvider.overrideWith((ref) => null),
        ],
      );
      addTearDown(container.dispose);

      final agents = await waitForAgents(container, visibleAgentsProvider);
      expect(agents.map((a) => a.id).toList(), ['a1', 'a2', 'a3']);
    });

    test('sorts agents within a folder by sortOrder', () async {
      final folderAgents = [
        const AgentListItemModel(id: 'a1', name: 'Agent 1', folderId: 'fld_1', sortOrder: 1),
        const AgentListItemModel(id: 'a2', name: 'Agent 2', folderId: 'fld_1', sortOrder: 0),
        const AgentListItemModel(id: 'a3', name: 'Agent 3', folderId: null, sortOrder: 0),
      ];

      final container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => Future.value(folderAgents)),
          currentFolderProvider.overrideWith((ref) => 'fld_1'),
        ],
      );
      addTearDown(container.dispose);

      final agents = await waitForAgents(container, visibleAgentsProvider);
      expect(agents.length, 2);
      expect(agents.map((a) => a.id).toList(), ['a2', 'a1']);
    });
  });
}
