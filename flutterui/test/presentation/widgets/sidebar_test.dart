import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mockito/mockito.dart';

import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/presentation/widgets/sidebar.dart';
import 'package:flutterui/providers/agent_provider.dart';
import 'package:flutterui/providers/auth_provider.dart';

// MockAgentsNotifier removed - using AsyncValue directly
class MockAuthNotifier extends Mock implements AuthNotifier {}

void main() {
  group('AppSidebar Widget Tests', () {
    late ProviderContainer container;
    late MockAuthNotifier mockAuthNotifier;

    setUp(() {
      mockAuthNotifier = MockAuthNotifier();
    });

    tearDown(() {
      container.dispose();
    });

    testWidgets('should render sidebar with drawer header', (tester) async {
      container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => []),
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              drawer: const AppSidebar(),
              body: Container(),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.menu));
      await tester.pumpAndSettle();

      expect(find.byType(DrawerHeader), findsOneWidget);
      expect(find.text('My Agents'), findsOneWidget);
      expect(find.byType(Image), findsOneWidget);
    });

    testWidgets('should render main navigation items', (tester) async {
      container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => []),
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              drawer: const AppSidebar(),
              body: Container(),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.menu));
      await tester.pumpAndSettle();

      expect(find.text('Home'), findsOneWidget);
      expect(find.text('Threads'), findsOneWidget);
      expect(find.text('Create Agent'), findsOneWidget);
      expect(find.text('Logout'), findsOneWidget);
      expect(find.byIcon(Icons.home), findsOneWidget);
      expect(find.byIcon(Icons.forum_outlined), findsOneWidget);
      expect(find.byIcon(Icons.add_circle_outline), findsOneWidget);
      expect(find.byIcon(Icons.logout), findsOneWidget);
    });

    testWidgets('should display agents when loaded', (tester) async {
      const agents = [
        AgentListItemModel(
          name: 'Test Agent 1',
          description: 'Description 1',
          id: 'agent-1',
          createdAtDisplay: '2023-01-01',
          metadata: null,
        ),
        AgentListItemModel(
          name: 'Test Agent 2',
          description: 'Description 2',
          id: 'agent-2',
          createdAtDisplay: '2023-01-02',
          metadata: null,
        ),
      ];

      container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => agents),
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            routes: {
              '/chat/agent-1': (context) => const Scaffold(body: Text('Chat 1')),
              '/chat/agent-2': (context) => const Scaffold(body: Text('Chat 2')),
            },
            home: Scaffold(
              drawer: const AppSidebar(),
              body: Container(),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.menu));
      await tester.pumpAndSettle();

      expect(find.text('Agents'), findsOneWidget);
      expect(find.text('Test Agent 1'), findsOneWidget);
      expect(find.text('Test Agent 2'), findsOneWidget);
      expect(find.byIcon(Icons.person), findsNWidgets(2));
    });

    testWidgets('should display loading state', (tester) async {
      container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => Future<List<AgentListItemModel>>.value([])),
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              drawer: const AppSidebar(),
              body: Container(),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.menu));
      await tester.pumpAndSettle();

      expect(find.text('Loading agents...'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('should display error state', (tester) async {
      const errorMessage = 'Failed to load agents';
      
      container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => Future<List<AgentListItemModel>>.error(Exception(errorMessage))),
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              drawer: const AppSidebar(),
              body: Container(),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.menu));
      await tester.pumpAndSettle();

      expect(find.textContaining('Error loading agents:'), findsOneWidget);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });

    testWidgets('should display no agents message when empty', (tester) async {
      container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => []),
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              drawer: const AppSidebar(),
              body: Container(),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.menu));
      await tester.pumpAndSettle();

      expect(find.text('No agents found.'), findsOneWidget);
      expect(find.byIcon(Icons.info_outline), findsOneWidget);
    });

    testWidgets('should navigate to home when home item tapped', (tester) async {
      container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => []),
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            routes: {
              '/home': (context) => const Scaffold(body: Text('Home Screen')),
            },
            home: Scaffold(
              drawer: const AppSidebar(),
              body: Container(),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.menu));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Home'));
      await tester.pumpAndSettle();

      expect(find.text('Home Screen'), findsOneWidget);
    });

    testWidgets('should navigate to threads when threads item tapped', (tester) async {
      container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => []),
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            routes: {
              '/threads': (context) => const Scaffold(body: Text('Threads Screen')),
            },
            home: Scaffold(
              drawer: const AppSidebar(),
              body: Container(),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.menu));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Threads'));
      await tester.pumpAndSettle();

      expect(find.text('Threads Screen'), findsOneWidget);
    });

    testWidgets('should navigate to create agent when create agent item tapped', (tester) async {
      container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => []),
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            routes: {
              '/create-agent': (context) => const Scaffold(body: Text('Create Agent Screen')),
            },
            home: Scaffold(
              drawer: const AppSidebar(),
              body: Container(),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.menu));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Create Agent'));
      await tester.pumpAndSettle();

      expect(find.text('Create Agent Screen'), findsOneWidget);
    });

    testWidgets('should navigate to agent chat when agent tapped', (tester) async {
      const agent = AgentListItemModel(
        name: 'Test Agent',
        description: 'Description',
        id: 'agent-1',
        createdAtDisplay: '2023-01-01',
        metadata: null,
      );

      container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => [agent]),
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            routes: {
              '/chat/agent-1': (context) => const Scaffold(body: Text('Agent Chat')),
            },
            home: Scaffold(
              drawer: const AppSidebar(),
              body: Container(),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.menu));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Test Agent'));
      await tester.pumpAndSettle();

      expect(find.text('Agent Chat'), findsOneWidget);
    });

    testWidgets('should call logout when logout item tapped', (tester) async {
      container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => []),
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              drawer: const AppSidebar(),
              body: Container(),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.menu));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Logout'));
      await tester.pump();

      verify(mockAuthNotifier.logout()).called(1);
    });

    testWidgets('should handle agents with null values', (tester) async {
      const agents = [
        AgentListItemModel(
          name: 'Valid Agent',
          description: 'Description',
          id: 'agent-1',
          createdAtDisplay: '2023-01-01',
          metadata: null,
        ),
      ];

      container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => agents),
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              drawer: const AppSidebar(),
              body: Container(),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.menu));
      await tester.pumpAndSettle();

      expect(find.text('Valid Agent'), findsOneWidget);
    });

    testWidgets('should display dividers correctly', (tester) async {
      container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => []),
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              drawer: const AppSidebar(),
              body: Container(),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.menu));
      await tester.pumpAndSettle();

      expect(find.byType(Divider), findsNWidgets(2));
    });

    testWidgets('should apply correct theme colors', (tester) async {
      container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => []),
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            theme: ThemeData(
              primaryColor: Colors.blue,
              colorScheme: const ColorScheme.light(
                primary: Colors.blue,
                onPrimary: Colors.white,
                surface: Colors.grey,
                onSurface: Colors.black,
              ),
            ),
            home: Scaffold(
              drawer: const AppSidebar(),
              body: Container(),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.menu));
      await tester.pumpAndSettle();

      final drawer = tester.widget<Drawer>(find.byType(Drawer));
      expect(drawer.backgroundColor, equals(Colors.grey));
    });

    testWidgets('should handle long agent names gracefully', (tester) async {
      const agents = [
        AgentListItemModel(
          name: 'This is a very long agent name that might overflow in the sidebar',
          description: 'Description',
          id: 'agent-1',
          createdAtDisplay: '2023-01-01',
          metadata: null,
        ),
      ];

      container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => agents),
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              drawer: const AppSidebar(),
              body: Container(),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.menu));
      await tester.pumpAndSettle();

      expect(find.textContaining('This is a very long agent name'), findsOneWidget);
    });

    testWidgets('should handle special characters in agent names', (tester) async {
      const agents = [
        AgentListItemModel(
          name: 'Agent with émojis 🤖 and spëcial chars @#\$%',
          description: 'Description',
          id: 'agent-1',
          createdAtDisplay: '2023-01-01',
          metadata: null,
        ),
      ];

      container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => agents),
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              drawer: const AppSidebar(),
              body: Container(),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.menu));
      await tester.pumpAndSettle();

      expect(find.text('Agent with émojis 🤖 and spëcial chars @#\$%'), findsOneWidget);
    });

    testWidgets('should handle empty agent IDs', (tester) async {
      const agents = [
        AgentListItemModel(
          name: 'Agent with empty ID',
          description: 'Description',
          id: '',
          createdAtDisplay: '2023-01-01',
          metadata: null,
        ),
      ];

      container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => agents),
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            routes: {
              '/chat/': (context) => const Scaffold(body: Text('Empty ID Chat')),
            },
            home: Scaffold(
              drawer: const AppSidebar(),
              body: Container(),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.menu));
      await tester.pumpAndSettle();

      expect(find.text('Agent with empty ID'), findsOneWidget);
    });

    testWidgets('should work with different screen sizes', (tester) async {
      container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => []),
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
        ],
      );

      await tester.binding.setSurfaceSize(const Size(400, 800));

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              drawer: const AppSidebar(),
              body: Container(),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.menu));
      await tester.pumpAndSettle();

      expect(find.text('My Agents'), findsOneWidget);

      await tester.binding.setSurfaceSize(const Size(200, 400));
      await tester.pump();

      expect(find.text('My Agents'), findsOneWidget);

      addTearDown(() => tester.binding.setSurfaceSize(null));
    });

    testWidgets('should close drawer when navigation items are tapped', (tester) async {
      container = ProviderContainer(
        overrides: [
          agentsProvider.overrideWith((ref) => []),
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              drawer: const AppSidebar(),
              body: Container(),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.menu));
      await tester.pumpAndSettle();

      expect(find.text('My Agents'), findsOneWidget);

      await tester.tap(find.text('Home'));
      await tester.pumpAndSettle();

      expect(find.text('My Agents'), findsNothing);
    });
  });
}