import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/presentation/screens/home/home_screen.dart';
import 'package:flutterui/presentation/screens/agents/widgets/agent_card.dart';
import 'package:flutterui/presentation/widgets/sidebar.dart';
import 'package:flutterui/providers/agent_provider.dart';

void main() {
  group('HomeScreen Widget Tests', () {
    late ProviderContainer container;

    tearDown(() {
      container.dispose();
    });

    Widget createHomeWidget({
      required List<AgentListItemModel> agents,
      bool isLoading = false,
      String? error,
    }) {
      late final Override override;
      
      if (error != null) {
        override = agentsProvider.overrideWith((ref) => throw Exception(error));
      } else if (isLoading) {
        override = agentsProvider.overrideWith((ref) async {
          await Future.delayed(const Duration(seconds: 10));
          return agents;
        });
      } else {
        override = agentsProvider.overrideWith((ref) => Future.value(agents));
      }

      container = ProviderContainer(overrides: [override]);

      return UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          theme: ThemeData(
            appBarTheme: const AppBarTheme(
              iconTheme: IconThemeData(color: Colors.white),
            ),
          ),
          home: const HomeScreen(),
        ),
      );
    }

    testWidgets('should display home screen with app bar and sidebar', (tester) async {
      await tester.pumpWidget(createHomeWidget(agents: []));
      await tester.pump();

      expect(find.byType(AppBar), findsOneWidget);
      expect(find.byType(AppSidebar), findsOneWidget);
      expect(find.text('Bond AI Agents'), findsOneWidget);
      expect(find.text('Your AI Agents'), findsOneWidget);
      expect(find.text('Manage and interact with your configured agents.'), findsOneWidget);
    });

    testWidgets('should display empty state when no agents', (tester) async {
      await tester.pumpWidget(createHomeWidget(agents: []));
      await tester.pump();

      expect(find.text('No Agents Yet'), findsOneWidget);
      expect(find.text('Tap the menu and select "Create Agent" to build your first AI assistant.'), findsOneWidget);
      expect(find.byIcon(Icons.person_search_outlined), findsOneWidget);
    });

    testWidgets('should display loading state', (tester) async {
      await tester.pumpWidget(createHomeWidget(agents: [], isLoading: true));

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Loading Agents...'), findsOneWidget);
    });

    testWidgets('should display error state with retry button', (tester) async {
      const errorMessage = 'Failed to load agents';
      await tester.pumpWidget(createHomeWidget(agents: [], error: errorMessage));
      await tester.pump();

      expect(find.text('Error Loading Agents'), findsOneWidget);
      expect(find.textContaining(errorMessage), findsOneWidget);
      expect(find.byIcon(Icons.error_outline_rounded), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
      expect(find.byIcon(Icons.refresh), findsOneWidget);
    });

    testWidgets('should display agents in grid when loaded', (tester) async {
      const agents = [
        AgentListItemModel(
          id: 'agent-1',
          name: 'Test Agent 1',
          description: 'Description 1',
          createdAtDisplay: '2023-01-01',
          metadata: null,
        ),
        AgentListItemModel(
          id: 'agent-2',
          name: 'Test Agent 2',
          description: 'Description 2',
          createdAtDisplay: '2023-01-02',
          metadata: null,
        ),
      ];

      await tester.pumpWidget(createHomeWidget(agents: agents));
      await tester.pump();

      expect(find.byType(GridView), findsOneWidget);
      expect(find.byType(AgentCard), findsNWidgets(2));
      expect(find.text('Test Agent 1'), findsOneWidget);
      expect(find.text('Test Agent 2'), findsOneWidget);
    });

    testWidgets('should adapt grid columns based on screen width - mobile', (tester) async {
      const agents = [
        AgentListItemModel(
          id: 'agent-1',
          name: 'Test Agent 1',
          description: 'Description 1',
          createdAtDisplay: '2023-01-01',
          metadata: null,
        ),
      ];

      await tester.binding.setSurfaceSize(const Size(400, 800));

      await tester.pumpWidget(createHomeWidget(agents: agents));
      await tester.pump();

      final gridView = tester.widget<GridView>(find.byType(GridView));
      final delegate = gridView.gridDelegate as SliverGridDelegateWithFixedCrossAxisCount;
      expect(delegate.crossAxisCount, equals(1));

      addTearDown(() {
        tester.binding.setSurfaceSize(const Size(800, 600));
      });
    });

    testWidgets('should adapt grid columns based on screen width - tablet', (tester) async {
      const agents = [
        AgentListItemModel(
          id: 'agent-1',
          name: 'Test Agent 1',
          description: 'Description 1',
          createdAtDisplay: '2023-01-01',
          metadata: null,
        ),
      ];

      await tester.binding.setSurfaceSize(const Size(700, 800));

      await tester.pumpWidget(createHomeWidget(agents: agents));
      await tester.pump();

      final gridView = tester.widget<GridView>(find.byType(GridView));
      final delegate = gridView.gridDelegate as SliverGridDelegateWithFixedCrossAxisCount;
      expect(delegate.crossAxisCount, equals(2));

      addTearDown(() {
        tester.binding.setSurfaceSize(const Size(800, 600));
      });
    });

    testWidgets('should adapt grid columns based on screen width - desktop', (tester) async {
      const agents = [
        AgentListItemModel(
          id: 'agent-1',
          name: 'Test Agent 1',
          description: 'Description 1',
          createdAtDisplay: '2023-01-01',
          metadata: null,
        ),
      ];

      await tester.binding.setSurfaceSize(const Size(1000, 800));

      await tester.pumpWidget(createHomeWidget(agents: agents));
      await tester.pump();

      final gridView = tester.widget<GridView>(find.byType(GridView));
      final delegate = gridView.gridDelegate as SliverGridDelegateWithFixedCrossAxisCount;
      expect(delegate.crossAxisCount, equals(3));

      addTearDown(() {
        tester.binding.setSurfaceSize(const Size(800, 600));
      });
    });

    testWidgets('should adapt grid columns based on screen width - large desktop', (tester) async {
      const agents = [
        AgentListItemModel(
          id: 'agent-1',
          name: 'Test Agent 1',
          description: 'Description 1',
          createdAtDisplay: '2023-01-01',
          metadata: null,
        ),
      ];

      await tester.binding.setSurfaceSize(const Size(1500, 800));

      await tester.pumpWidget(createHomeWidget(agents: agents));
      await tester.pump();

      final gridView = tester.widget<GridView>(find.byType(GridView));
      final delegate = gridView.gridDelegate as SliverGridDelegateWithFixedCrossAxisCount;
      expect(delegate.crossAxisCount, equals(5));

      addTearDown(() {
        tester.binding.setSurfaceSize(const Size(800, 600));
      });
    });

    testWidgets('should handle large number of agents', (tester) async {
      final agents = List.generate(20, (index) => AgentListItemModel(
        id: 'agent-$index',
        name: 'Test Agent $index',
        description: 'Description $index',
        createdAtDisplay: '2023-01-01',
        metadata: null,
      ));

      await tester.pumpWidget(createHomeWidget(agents: agents));
      await tester.pump();

      expect(find.byType(GridView), findsOneWidget);
      expect(find.byType(AgentCard), findsAtLeastNWidgets(1));
    });

    testWidgets('should apply correct theme colors', (tester) async {
      container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => Future.value(<AgentListItemModel>[])),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            theme: ThemeData(
              colorScheme: const ColorScheme.light(
                surface: Colors.blue,
                onSurface: Colors.white,
                primary: Colors.red,
              ),
            ),
            home: const HomeScreen(),
          ),
        ),
      );
      await tester.pump();

      final scaffold = tester.widget<Scaffold>(find.byType(Scaffold));
      expect(scaffold.backgroundColor, equals(Colors.blue));
    });

    testWidgets('should display divider between header and content', (tester) async {
      await tester.pumpWidget(createHomeWidget(agents: []));
      await tester.pump();

      expect(find.byType(Divider), findsOneWidget);
    });

    testWidgets('should handle app bar icon theme correctly', (tester) async {
      await tester.pumpWidget(createHomeWidget(agents: []));
      await tester.pump();

      final appBar = tester.widget<AppBar>(find.byType(AppBar));
      expect(appBar.iconTheme?.color, equals(Colors.white));
    });

    testWidgets('should handle different aspect ratios for grid items', (tester) async {
      const agents = [
        AgentListItemModel(
          id: 'agent-1',
          name: 'Test Agent 1',
          description: 'Description 1',
          createdAtDisplay: '2023-01-01',
          metadata: null,
        ),
      ];

      await tester.binding.setSurfaceSize(const Size(400, 800));

      await tester.pumpWidget(createHomeWidget(agents: agents));
      await tester.pump();

      final gridView = tester.widget<GridView>(find.byType(GridView));
      final delegate = gridView.gridDelegate as SliverGridDelegateWithFixedCrossAxisCount;
      expect(delegate.childAspectRatio, equals(16 / 10));

      await tester.binding.setSurfaceSize(const Size(800, 800));
      await tester.pump();

      final gridView2 = tester.widget<GridView>(find.byType(GridView));
      final delegate2 = gridView2.gridDelegate as SliverGridDelegateWithFixedCrossAxisCount;
      expect(delegate2.childAspectRatio, equals(4 / 2.8));

      addTearDown(() {
        tester.binding.setSurfaceSize(const Size(800, 600));
      });
    });

    testWidgets('should handle empty error message', (tester) async {
      await tester.pumpWidget(createHomeWidget(agents: [], error: ''));
      await tester.pump();

      expect(find.text('Error Loading Agents'), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
    });

    testWidgets('should handle null agents gracefully', (tester) async {
      await tester.pumpWidget(createHomeWidget(agents: []));
      await tester.pump();

      expect(find.text('No Agents Yet'), findsOneWidget);
    });

    testWidgets('should scroll when many agents are present', (tester) async {
      final agents = List.generate(50, (index) => AgentListItemModel(
        id: 'agent-$index',
        name: 'Test Agent $index',
        description: 'Description $index',
        createdAtDisplay: '2023-01-01',
        metadata: null,
      ));

      await tester.pumpWidget(createHomeWidget(agents: agents));
      await tester.pump();

      expect(find.byType(GridView), findsOneWidget);
      
      final gridView = tester.widget<GridView>(find.byType(GridView));
      expect(gridView.physics, isNotNull);
    });

    testWidgets('should maintain padding and spacing consistency', (tester) async {
      await tester.pumpWidget(createHomeWidget(agents: []));
      await tester.pump();

      final padding = tester.widget<Padding>(find.byType(Padding).first);
      expect(padding.padding, equals(const EdgeInsets.only(top: 24.0, left: 24.0, right: 24.0)));

      expect(find.byType(SizedBox), findsAtLeastNWidgets(3));
    });

    testWidgets('should render all required UI elements', (tester) async {
      await tester.pumpWidget(createHomeWidget(agents: []));
      await tester.pump();

      expect(find.byType(Scaffold), findsOneWidget);
      expect(find.byType(AppBar), findsOneWidget);
      expect(find.byType(Drawer), findsOneWidget);
      expect(find.byType(Column), findsAtLeastNWidgets(1));
      expect(find.byType(Expanded), findsOneWidget);
    });

    testWidgets('should handle retry button tap', (tester) async {
      await tester.pumpWidget(createHomeWidget(agents: [], error: 'Network error'));
      await tester.pump();

      expect(find.text('Retry'), findsOneWidget);
      
      await tester.tap(find.text('Retry'));
      await tester.pump();

      expect(find.text('Error Loading Agents'), findsOneWidget);
    });

    testWidgets('should handle agents with missing descriptions', (tester) async {
      const agents = [
        AgentListItemModel(
          id: 'agent-1',
          name: 'Test Agent 1',
          description: null,
          createdAtDisplay: '2023-01-01',
          metadata: null,
        ),
      ];

      await tester.pumpWidget(createHomeWidget(agents: agents));
      await tester.pump();

      expect(find.byType(AgentCard), findsOneWidget);
      expect(find.text('Test Agent 1'), findsOneWidget);
    });

    testWidgets('should handle different screen orientations', (tester) async {
      const agents = [
        AgentListItemModel(
          id: 'agent-1',
          name: 'Test Agent 1',
          description: 'Description 1',
          createdAtDisplay: '2023-01-01',
          metadata: null,
        ),
      ];

      await tester.binding.setSurfaceSize(const Size(800, 400));

      await tester.pumpWidget(createHomeWidget(agents: agents));
      await tester.pump();

      expect(find.byType(GridView), findsOneWidget);
      expect(find.text('Test Agent 1'), findsOneWidget);

      addTearDown(() {
        tester.binding.setSurfaceSize(const Size(800, 600));
      });
    });

    testWidgets('should handle edge case with single agent', (tester) async {
      const agents = [
        AgentListItemModel(
          id: 'single-agent',
          name: 'Single Agent',
          description: 'Only agent',
          createdAtDisplay: '2023-01-01',
          metadata: null,
        ),
      ];

      await tester.pumpWidget(createHomeWidget(agents: agents));
      await tester.pump();

      expect(find.byType(GridView), findsOneWidget);
      expect(find.byType(AgentCard), findsOneWidget);
      expect(find.text('Single Agent'), findsOneWidget);
    });

    testWidgets('should apply consistent card spacing in grid', (tester) async {
      const agents = [
        AgentListItemModel(
          id: 'agent-1',
          name: 'Agent 1',
          description: 'Desc 1',
          createdAtDisplay: '2023-01-01',
        ),
        AgentListItemModel(
          id: 'agent-2',
          name: 'Agent 2',
          description: 'Desc 2',
          createdAtDisplay: '2023-01-02',
        ),
      ];

      await tester.pumpWidget(createHomeWidget(agents: agents));
      await tester.pump();

      final gridView = tester.widget<GridView>(find.byType(GridView));
      final delegate = gridView.gridDelegate as SliverGridDelegateWithFixedCrossAxisCount;
      expect(delegate.crossAxisSpacing, equals(16.0));
      expect(delegate.mainAxisSpacing, equals(16.0));
    });
  });
}