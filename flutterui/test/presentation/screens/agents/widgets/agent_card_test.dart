import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mockito/mockito.dart';

import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/data/models/user_model.dart';
import 'package:flutterui/data/services/auth_service.dart';
import 'package:flutterui/presentation/screens/agents/widgets/agent_card.dart';
import 'package:flutterui/providers/auth_provider.dart';

class MockNavigatorObserver extends Mock implements NavigatorObserver {}

void main() {
  group('AgentCard Widget Tests', () {
    late ProviderContainer container;
    late MockNavigatorObserver mockNavigatorObserver;

    setUp(() {
      mockNavigatorObserver = MockNavigatorObserver();
      container = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => MockAuthNotifier()),
        ],
      );
    });

    tearDown(() {
      container.dispose();
    });

    testWidgets('should display agent information correctly', (tester) async {
      const agent = AgentListItemModel(
        name: 'Test Agent',
        description: 'Test Description',
        id: 'agent-123',
        createdAtDisplay: '2023-01-01',
        metadata: null,
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: const Scaffold(
              body: AgentCard(agent: agent),
            ),
          ),
        ),
      );

      expect(find.text('Test Agent'), findsOneWidget);
      expect(find.text('Test Description'), findsOneWidget);
      expect(find.text('Tap to chat'), findsOneWidget);
      expect(find.text('2023-01-01'), findsOneWidget);
      expect(find.byIcon(Icons.smart_toy_outlined), findsOneWidget);
      expect(find.byIcon(Icons.calendar_today_outlined), findsOneWidget);
    });

    testWidgets('should display agent without description', (tester) async {
      const agent = AgentListItemModel(
        name: 'Test Agent',
        description: null,
        id: 'agent-123',
        createdAtDisplay: '2023-01-01',
        metadata: null,
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: const Scaffold(
              body: AgentCard(agent: agent),
            ),
          ),
        ),
      );

      expect(find.text('Test Agent'), findsOneWidget);
      expect(find.text('Tap to chat'), findsOneWidget);
      expect(find.text('2023-01-01'), findsOneWidget);
      expect(find.byIcon(Icons.smart_toy_outlined), findsOneWidget);
    });

    testWidgets('should display agent without created date', (tester) async {
      const agent = AgentListItemModel(
        name: 'Test Agent',
        description: 'Test Description',
        id: 'agent-123',
        createdAtDisplay: null,
        metadata: null,
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: const Scaffold(
              body: AgentCard(agent: agent),
            ),
          ),
        ),
      );

      expect(find.text('Test Agent'), findsOneWidget);
      expect(find.text('Test Description'), findsOneWidget);
      expect(find.text('Tap to chat'), findsOneWidget);
      expect(find.byIcon(Icons.calendar_today_outlined), findsNothing);
    });

    testWidgets('should display minimal agent information', (tester) async {
      const agent = AgentListItemModel(
        name: 'Test Agent',
        description: null,
        id: 'agent-123',
        createdAtDisplay: null,
        metadata: null,
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: const Scaffold(
              body: AgentCard(agent: agent),
            ),
          ),
        ),
      );

      expect(find.text('Test Agent'), findsOneWidget);
      expect(find.text('Tap to chat'), findsOneWidget);
      expect(find.byIcon(Icons.smart_toy_outlined), findsOneWidget);
    });

    testWidgets('should show edit icon for owner with owner_user_id', (tester) async {
      const userEmail = 'test@example.com';
      const agent = AgentListItemModel(
        name: 'Test Agent',
        description: 'Test Description',
        id: 'agent-123',
        createdAtDisplay: '2023-01-01',
        metadata: {'owner_user_id': userEmail},
      );

      final authContainer = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => MockAuthNotifierAuthenticated(userEmail)),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: authContainer,
          child: MaterialApp(
            home: const Scaffold(
              body: AgentCard(agent: agent),
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.edit), findsOneWidget);
      authContainer.dispose();
    });

    testWidgets('should show edit icon for owner with legacy user_id', (tester) async {
      const userEmail = 'test@example.com';
      const agent = AgentListItemModel(
        name: 'Test Agent',
        description: 'Test Description',
        id: 'agent-123',
        createdAtDisplay: '2023-01-01',
        metadata: {'user_id': userEmail},
      );

      final authContainer = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => MockAuthNotifierAuthenticated(userEmail)),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: authContainer,
          child: MaterialApp(
            home: const Scaffold(
              body: AgentCard(agent: agent),
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.edit), findsOneWidget);
      authContainer.dispose();
    });

    testWidgets('should not show edit icon for non-owner', (tester) async {
      const userEmail = 'test@example.com';
      const agent = AgentListItemModel(
        name: 'Test Agent',
        description: 'Test Description',
        id: 'agent-123',
        createdAtDisplay: '2023-01-01',
        metadata: {'owner_user_id': 'other@example.com'},
      );

      final authContainer = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => MockAuthNotifierAuthenticated(userEmail)),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: authContainer,
          child: MaterialApp(
            home: const Scaffold(
              body: AgentCard(agent: agent),
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.edit), findsNothing);
      authContainer.dispose();
    });

    testWidgets('should not show edit icon when not authenticated', (tester) async {
      const agent = AgentListItemModel(
        name: 'Test Agent',
        description: 'Test Description',
        id: 'agent-123',
        createdAtDisplay: '2023-01-01',
        metadata: {'owner_user_id': 'test@example.com'},
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: const Scaffold(
              body: AgentCard(agent: agent),
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.edit), findsNothing);
    });

    testWidgets('should navigate to chat when tapped', (tester) async {
      const agent = AgentListItemModel(
        name: 'Test Agent',
        description: 'Test Description',
        id: 'agent-123',
        createdAtDisplay: '2023-01-01',
        metadata: null,
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            navigatorObservers: [mockNavigatorObserver],
            routes: {
              '/chat/agent-123': (context) => const Scaffold(body: Text('Chat Screen')),
            },
            home: const Scaffold(
              body: AgentCard(agent: agent),
            ),
          ),
        ),
      );

      await tester.tap(find.byType(InkWell).first);
      await tester.pumpAndSettle();

      expect(find.text('Chat Screen'), findsOneWidget);
    });

    testWidgets('should navigate to edit when edit icon tapped', (tester) async {
      const userEmail = 'test@example.com';
      const agent = AgentListItemModel(
        name: 'Test Agent',
        description: 'Test Description',
        id: 'agent-123',
        createdAtDisplay: '2023-01-01',
        metadata: {'owner_user_id': userEmail},
      );

      final authContainer = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => MockAuthNotifierAuthenticated(userEmail)),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: authContainer,
          child: MaterialApp(
            navigatorObservers: [mockNavigatorObserver],
            routes: {
              '/edit-agent/agent-123': (context) => const Scaffold(body: Text('Edit Screen')),
            },
            home: const Scaffold(
              body: AgentCard(agent: agent),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.edit));
      await tester.pumpAndSettle();

      expect(find.text('Edit Screen'), findsOneWidget);
      authContainer.dispose();
    });

    testWidgets('should handle long agent names with ellipsis', (tester) async {
      const agent = AgentListItemModel(
        name: 'This is a very long agent name that should be truncated with ellipsis when displayed',
        description: 'Test Description',
        id: 'agent-123',
        createdAtDisplay: '2023-01-01',
        metadata: null,
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: SizedBox(
                width: 200,
                child: AgentCard(agent: agent),
              ),
            ),
          ),
        ),
      );

      final nameTextWidget = tester.widget<Text>(find.text(agent.name));
      expect(nameTextWidget.maxLines, equals(2));
      expect(nameTextWidget.overflow, equals(TextOverflow.ellipsis));
    });

    testWidgets('should handle long descriptions with ellipsis', (tester) async {
      const agent = AgentListItemModel(
        name: 'Test Agent',
        description: 'This is a very long description that should be truncated with ellipsis when displayed in the agent card to maintain proper layout',
        id: 'agent-123',
        createdAtDisplay: '2023-01-01',
        metadata: null,
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: SizedBox(
                width: 200,
                child: AgentCard(agent: agent),
              ),
            ),
          ),
        ),
      );

      final descriptionTextWidget = tester.widget<Text>(find.text(agent.description!));
      expect(descriptionTextWidget.maxLines, equals(2));
      expect(descriptionTextWidget.overflow, equals(TextOverflow.ellipsis));
    });

    testWidgets('should handle empty strings gracefully', (tester) async {
      const agent = AgentListItemModel(
        name: 'Test Agent',
        description: '',
        id: 'agent-123',
        createdAtDisplay: '',
        metadata: null,
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: const Scaffold(
              body: AgentCard(agent: agent),
            ),
          ),
        ),
      );

      expect(find.text('Test Agent'), findsOneWidget);
      expect(find.text('Tap to chat'), findsOneWidget);
      expect(find.byIcon(Icons.smart_toy_outlined), findsOneWidget);
    });

    testWidgets('should apply correct theme styling', (tester) async {
      const agent = AgentListItemModel(
        name: 'Test Agent',
        description: 'Test Description',
        id: 'agent-123',
        createdAtDisplay: '2023-01-01',
        metadata: null,
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            theme: ThemeData.light(),
            home: const Scaffold(
              body: AgentCard(agent: agent),
            ),
          ),
        ),
      );

      final cardWidget = tester.widget<Card>(find.byType(Card));
      expect(cardWidget.elevation, equals(2.0));
      expect(cardWidget.shape, isA<RoundedRectangleBorder>());
      
      final circleAvatar = tester.widget<CircleAvatar>(find.byType(CircleAvatar));
      expect(circleAvatar.radius, equals(24));
      expect(circleAvatar.child, isA<Icon>());
    });

    testWidgets('should handle special characters in text fields', (tester) async {
      const agent = AgentListItemModel(
        name: 'Agent with émojis 🤖 and spëcial chars',
        description: 'Description with unicode: café ☕ and symbols @#\$%',
        id: 'agent-123',
        createdAtDisplay: '2023-01-01',
        metadata: null,
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: const Scaffold(
              body: AgentCard(agent: agent),
            ),
          ),
        ),
      );

      expect(find.text('Agent with émojis 🤖 and spëcial chars'), findsOneWidget);
      expect(find.text('Description with unicode: café ☕ and symbols @#\$%'), findsOneWidget);
    });

    testWidgets('should handle null metadata gracefully', (tester) async {
      const agent = AgentListItemModel(
        name: 'Test Agent',
        description: 'Test Description',
        id: 'agent-123',
        createdAtDisplay: '2023-01-01',
        metadata: null,
      );

      const userEmail = 'test@example.com';
      final authContainer = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => MockAuthNotifierAuthenticated(userEmail)),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: authContainer,
          child: MaterialApp(
            home: const Scaffold(
              body: AgentCard(agent: agent),
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.edit), findsNothing);
      authContainer.dispose();
    });

    testWidgets('should render properly in different screen sizes', (tester) async {
      const agent = AgentListItemModel(
        name: 'Test Agent',
        description: 'Test Description',
        id: 'agent-123',
        createdAtDisplay: '2023-01-01',
        metadata: null,
      );

      await tester.binding.setSurfaceSize(const Size(400, 800));
      
      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: const Scaffold(
              body: AgentCard(agent: agent),
            ),
          ),
        ),
      );

      expect(find.text('Test Agent'), findsOneWidget);
      expect(find.text('Test Description'), findsOneWidget);
      
      await tester.binding.setSurfaceSize(const Size(200, 400));
      await tester.pump();

      expect(find.text('Test Agent'), findsOneWidget);
      expect(find.text('Test Description'), findsOneWidget);
      
      addTearDown(() => tester.binding.setSurfaceSize(null));
    });
  });
}

// ignore: must_be_immutable
class MockAuthService extends Mock implements AuthService {}

class MockAuthNotifier extends AuthNotifier {
  MockAuthNotifier() : super(MockAuthService()) {
    state = const Unauthenticated();
  }
}

class MockAuthNotifierAuthenticated extends AuthNotifier {
  final String userEmail;

  MockAuthNotifierAuthenticated(this.userEmail) : super(MockAuthService()) {
    state = Authenticated(
      User(
        email: userEmail,
        name: 'Test User',
      ),
    );
  }
}