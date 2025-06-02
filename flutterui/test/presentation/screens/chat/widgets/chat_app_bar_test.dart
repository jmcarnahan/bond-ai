import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutterui/presentation/screens/chat/widgets/chat_app_bar.dart';

void main() {
  group('ChatAppBar Widget Tests', () {
    late bool onStartNewThreadCalled;
    late bool onViewThreadsCalled;

    setUp(() {
      onStartNewThreadCalled = false;
      onViewThreadsCalled = false;
    });

    testWidgets('should display app bar with agent name', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              appBar: ChatAppBar(
                agentName: 'Test Agent',
                onStartNewThread: () => onStartNewThreadCalled = true,
                onViewThreads: () => onViewThreadsCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.text('Chat with Test Agent'), findsOneWidget);
      expect(find.byType(AppBar), findsOneWidget);
      expect(find.byType(Image), findsOneWidget);
    });

    testWidgets('should display back button', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              appBar: ChatAppBar(
                agentName: 'Test Agent',
                onStartNewThread: () => onStartNewThreadCalled = true,
                onViewThreads: () => onViewThreadsCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.arrow_back), findsOneWidget);
      
      final backIcon = tester.widget<Icon>(find.byIcon(Icons.arrow_back));
      expect(backIcon.color, equals(Colors.white));
    });

    testWidgets('should display action buttons with correct icons', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              appBar: ChatAppBar(
                agentName: 'Test Agent',
                onStartNewThread: () => onStartNewThreadCalled = true,
                onViewThreads: () => onViewThreadsCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.forum), findsOneWidget);
      expect(find.byIcon(Icons.add_comment), findsOneWidget);

      final forumIcon = tester.widget<Icon>(find.byIcon(Icons.forum));
      expect(forumIcon.color, equals(Colors.white));

      final addCommentIcon = tester.widget<Icon>(find.byIcon(Icons.add_comment));
      expect(addCommentIcon.color, equals(Colors.white));
    });

    testWidgets('should call onViewThreads when forum button pressed', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              appBar: ChatAppBar(
                agentName: 'Test Agent',
                onStartNewThread: () => onStartNewThreadCalled = true,
                onViewThreads: () => onViewThreadsCalled = true,
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.forum));
      expect(onViewThreadsCalled, isTrue);
      expect(onStartNewThreadCalled, isFalse);
    });

    testWidgets('should call onStartNewThread when add comment button pressed', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              appBar: ChatAppBar(
                agentName: 'Test Agent',
                onStartNewThread: () => onStartNewThreadCalled = true,
                onViewThreads: () => onViewThreadsCalled = true,
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.add_comment));
      expect(onStartNewThreadCalled, isTrue);
      expect(onViewThreadsCalled, isFalse);
    });

    testWidgets('should navigate back when back button pressed', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              body: const Text('Home'),
            ),
            routes: {
              '/chat': (context) => Scaffold(
                appBar: ChatAppBar(
                  agentName: 'Test Agent',
                  onStartNewThread: () => onStartNewThreadCalled = true,
                  onViewThreads: () => onViewThreadsCalled = true,
                ),
                body: const Text('Chat Screen'),
              ),
            },
          ),
        ),
      );

      await tester.tap(find.text('Home'));
      await tester.pump();

      Navigator.of(tester.element(find.text('Home'))).pushNamed('/chat');
      await tester.pumpAndSettle();

      expect(find.text('Chat Screen'), findsOneWidget);

      await tester.tap(find.byIcon(Icons.arrow_back));
      await tester.pumpAndSettle();

      expect(find.text('Home'), findsOneWidget);
    });

    testWidgets('should display correct tooltips', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              appBar: ChatAppBar(
                agentName: 'Test Agent',
                onStartNewThread: () => onStartNewThreadCalled = true,
                onViewThreads: () => onViewThreadsCalled = true,
              ),
            ),
          ),
        ),
      );

      final forumButton = tester.widget<IconButton>(find.ancestor(
        of: find.byIcon(Icons.forum),
        matching: find.byType(IconButton),
      ));
      expect(forumButton.tooltip, equals('View/Change Threads'));

      final addCommentButton = tester.widget<IconButton>(find.ancestor(
        of: find.byIcon(Icons.add_comment),
        matching: find.byType(IconButton),
      ));
      expect(addCommentButton.tooltip, equals('Start New Thread'));
    });

    testWidgets('should have correct preferred size', (tester) async {
      final chatAppBar = ChatAppBar(
        agentName: 'Test Agent',
        onStartNewThread: () {},
        onViewThreads: () {},
      );

      expect(chatAppBar.preferredSize, equals(const Size.fromHeight(kToolbarHeight)));
    });

    testWidgets('should handle long agent names with ellipsis', (tester) async {
      const longAgentName = 'This is a very long agent name that might overflow in the app bar title area';
      
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              appBar: ChatAppBar(
                agentName: longAgentName,
                onStartNewThread: () => onStartNewThreadCalled = true,
                onViewThreads: () => onViewThreadsCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.textContaining('Chat with'), findsOneWidget);
      expect(find.textContaining(longAgentName), findsOneWidget);
    });

    testWidgets('should handle special characters in agent name', (tester) async {
      const specialAgentName = 'Agent with émojis 🤖 and spëcial chars @#\$%';
      
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              appBar: ChatAppBar(
                agentName: specialAgentName,
                onStartNewThread: () => onStartNewThreadCalled = true,
                onViewThreads: () => onViewThreadsCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.text('Chat with $specialAgentName'), findsOneWidget);
    });

    testWidgets('should handle empty agent name', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              appBar: ChatAppBar(
                agentName: '',
                onStartNewThread: () => onStartNewThreadCalled = true,
                onViewThreads: () => onViewThreadsCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.text('Chat with '), findsOneWidget);
    });

    testWidgets('should apply correct theme colors', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: ThemeData(
              appBarTheme: const AppBarTheme(
                backgroundColor: Colors.blue,
              ),
            ),
            home: Scaffold(
              appBar: ChatAppBar(
                agentName: 'Test Agent',
                onStartNewThread: () => onStartNewThreadCalled = true,
                onViewThreads: () => onViewThreadsCalled = true,
              ),
            ),
          ),
        ),
      );

      final appBar = tester.widget<AppBar>(find.byType(AppBar));
      expect(appBar.backgroundColor, equals(Colors.blue));
    });

    testWidgets('should display title with correct text style', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: ThemeData(
              textTheme: const TextTheme(
                titleLarge: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              ),
            ),
            home: Scaffold(
              appBar: ChatAppBar(
                agentName: 'Test Agent',
                onStartNewThread: () => onStartNewThreadCalled = true,
                onViewThreads: () => onViewThreadsCalled = true,
              ),
            ),
          ),
        ),
      );

      final titleText = tester.widget<Text>(find.text('Chat with Test Agent'));
      expect(titleText.style?.color, equals(Colors.white));
    });

    testWidgets('should maintain row layout for title', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              appBar: ChatAppBar(
                agentName: 'Test Agent',
                onStartNewThread: () => onStartNewThreadCalled = true,
                onViewThreads: () => onViewThreadsCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.byType(Row), findsOneWidget);
      
      final row = tester.widget<Row>(find.byType(Row));
      expect(row.mainAxisSize, equals(MainAxisSize.min));
      expect(row.children, hasLength(3));
    });

    testWidgets('should display logo icon with correct size', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              appBar: ChatAppBar(
                agentName: 'Test Agent',
                onStartNewThread: () => onStartNewThreadCalled = true,
                onViewThreads: () => onViewThreadsCalled = true,
              ),
            ),
          ),
        ),
      );

      final image = tester.widget<Image>(find.byType(Image));
      expect(image.height, equals(24));
      expect(image.width, equals(24));
    });

    testWidgets('should handle rapid button presses', (tester) async {
      int startNewThreadCount = 0;
      int viewThreadsCount = 0;

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              appBar: ChatAppBar(
                agentName: 'Test Agent',
                onStartNewThread: () => startNewThreadCount++,
                onViewThreads: () => viewThreadsCount++,
              ),
            ),
          ),
        ),
      );

      for (int i = 0; i < 5; i++) {
        await tester.tap(find.byIcon(Icons.add_comment));
        await tester.pump(const Duration(milliseconds: 10));
      }

      for (int i = 0; i < 3; i++) {
        await tester.tap(find.byIcon(Icons.forum));
        await tester.pump(const Duration(milliseconds: 10));
      }

      expect(startNewThreadCount, equals(5));
      expect(viewThreadsCount, equals(3));
    });

    testWidgets('should work with different screen sizes', (tester) async {
      await tester.binding.setSurfaceSize(const Size(400, 800));

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              appBar: ChatAppBar(
                agentName: 'Test Agent',
                onStartNewThread: () => onStartNewThreadCalled = true,
                onViewThreads: () => onViewThreadsCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.text('Chat with Test Agent'), findsOneWidget);

      await tester.binding.setSurfaceSize(const Size(800, 600));
      await tester.pump();

      expect(find.text('Chat with Test Agent'), findsOneWidget);

      addTearDown(() => tester.binding.setSurfaceSize(null));
    });

    testWidgets('should handle null callbacks gracefully', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              appBar: ChatAppBar(
                agentName: 'Test Agent',
                onStartNewThread: () {},
                onViewThreads: () {},
              ),
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.forum), findsOneWidget);
      expect(find.byIcon(Icons.add_comment), findsOneWidget);
    });

    testWidgets('should maintain consistent spacing', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              appBar: ChatAppBar(
                agentName: 'Test Agent',
                onStartNewThread: () => onStartNewThreadCalled = true,
                onViewThreads: () => onViewThreadsCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.byType(SizedBox), findsOneWidget);
      
      final sizedBox = tester.widget<SizedBox>(find.byType(SizedBox));
      expect(sizedBox.width, equals(8));
    });

    testWidgets('should handle dark theme correctly', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: ThemeData.dark(),
            home: Scaffold(
              appBar: ChatAppBar(
                agentName: 'Test Agent',
                onStartNewThread: () => onStartNewThreadCalled = true,
                onViewThreads: () => onViewThreadsCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.text('Chat with Test Agent'), findsOneWidget);
      expect(find.byIcon(Icons.arrow_back), findsOneWidget);
    });

    testWidgets('should display correct number of actions', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: Scaffold(
              appBar: ChatAppBar(
                agentName: 'Test Agent',
                onStartNewThread: () => onStartNewThreadCalled = true,
                onViewThreads: () => onViewThreadsCalled = true,
              ),
            ),
          ),
        ),
      );

      final appBar = tester.widget<AppBar>(find.byType(AppBar));
      expect(appBar.actions, hasLength(2));
    });

    testWidgets('should work as PreferredSizeWidget', (tester) async {
      final chatAppBar = ChatAppBar(
        agentName: 'Test Agent',
        onStartNewThread: () {},
        onViewThreads: () {},
      );

      expect(chatAppBar, isA<PreferredSizeWidget>());
      expect(chatAppBar.preferredSize.height, equals(kToolbarHeight));
    });
  });
}