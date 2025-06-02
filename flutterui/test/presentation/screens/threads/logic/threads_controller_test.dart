import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';

import 'package:flutterui/presentation/screens/threads/logic/threads_controller.dart';
import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/providers/thread_provider.dart';

class MockWidgetRef extends Mock implements WidgetRef {}

class MockThreadsNotifier extends ThreadsNotifier {
  bool fetchThreadsCalled = false;
  bool selectThreadCalled = false;
  String? lastSelectedThreadId;
  bool shouldThrowError = false;

  MockThreadsNotifier(super.ref);

  @override
  Future<void> fetchThreads() async {
    fetchThreadsCalled = true;
    if (shouldThrowError) {
      throw Exception('Mock fetch error');
    }
  }

  @override
  void selectThread(String threadId) {
    selectThreadCalled = true;
    lastSelectedThreadId = threadId;
  }
}

void main() {
  group('ThreadsController Tests', () {
    late MockThreadsNotifier mockNotifier;
    late ProviderContainer container;
    late GlobalKey<NavigatorState> navigatorKey;

    setUp(() {
      navigatorKey = GlobalKey<NavigatorState>();
      
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) {
            mockNotifier = MockThreadsNotifier(ref);
            return mockNotifier;
          }),
        ],
      );
    });

    tearDown(() {
      container.dispose();
    });

    Widget createTestWidget({required Widget child}) {
      return UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          navigatorKey: navigatorKey,
          home: Scaffold(
            body: child,
          ),
        ),
      );
    }

    ThreadsController createController(BuildContext context) {
      final mockRef = MockWidgetRef();
      when(mockRef.read(threadsProvider.notifier)).thenReturn(mockNotifier);
      return ThreadsController(
        ref: mockRef,
        context: context,
      );
    }

    group('Constructor', () {
      testWidgets('should create controller with required parameters', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            child: Builder(
              builder: (context) {
                final testController = createController(context);
                
                expect(testController.ref, equals(container));
                expect(testController.context, equals(context));
                
                return const SizedBox();
              },
            ),
          ),
        );
      });
    });

    group('initializeThreads', () {
      testWidgets('should complete without errors', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            child: Builder(
              builder: (context) {
                final testController = createController(context);
                
                expect(() => testController.initializeThreads(), returnsNormally);
                
                return const SizedBox();
              },
            ),
          ),
        );
      });
    });

    group('showErrorSnackBar', () {
      testWidgets('should display error message in snackbar', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            child: Builder(
              builder: (context) {
                final testController = createController(context);
                
                testController.showErrorSnackBar('Test error message');
                
                return const SizedBox();
              },
            ),
          ),
        );

        await tester.pumpAndSettle();

        expect(find.text('Test error message'), findsOneWidget);
        expect(find.byType(SnackBar), findsOneWidget);
      });

      testWidgets('should remove current snackbar before showing new one', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            child: Builder(
              builder: (context) {
                final testController = createController(context);
                
                testController.showErrorSnackBar('First error');
                testController.showErrorSnackBar('Second error');
                
                return const SizedBox();
              },
            ),
          ),
        );

        await tester.pumpAndSettle();

        expect(find.text('Second error'), findsOneWidget);
        expect(find.text('First error'), findsNothing);
      });

      testWidgets('should apply error color scheme to snackbar', (tester) async {
        await tester.pumpWidget(
          MaterialApp(
            theme: ThemeData(
              colorScheme: const ColorScheme.light(
                error: Colors.red,
              ),
            ),
            home: UncontrolledProviderScope(
              container: container,
              child: Scaffold(
                body: Builder(
                  builder: (context) {
                    final testController = createController(context);
                    
                    testController.showErrorSnackBar('Error with theme');
                    
                    return const SizedBox();
                  },
                ),
              ),
            ),
          ),
        );

        await tester.pumpAndSettle();

        final snackBar = tester.widget<SnackBar>(find.byType(SnackBar));
        expect(snackBar.backgroundColor, equals(Colors.red));
      });

      testWidgets('should set correct duration for snackbar', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            child: Builder(
              builder: (context) {
                final testController = createController(context);
                
                testController.showErrorSnackBar('Timed error');
                
                return const SizedBox();
              },
            ),
          ),
        );

        await tester.pumpAndSettle();

        final snackBar = tester.widget<SnackBar>(find.byType(SnackBar));
        expect(snackBar.duration, equals(const Duration(seconds: 3)));
      });
    });

    group('refreshThreads', () {
      testWidgets('should call fetchThreads on notifier', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            child: Builder(
              builder: (context) {
                final testController = createController(context);
                
                testController.refreshThreads();
                
                return const SizedBox();
              },
            ),
          ),
        );

        await tester.pump();

        expect(mockNotifier.fetchThreadsCalled, isTrue);
      });

      testWidgets('should handle fetch error gracefully', (tester) async {
        mockNotifier.shouldThrowError = true;

        await tester.pumpWidget(
          createTestWidget(
            child: Builder(
              builder: (context) {
                final testController = createController(context);
                
                expect(() => testController.refreshThreads(), returnsNormally);
                
                return const SizedBox();
              },
            ),
          ),
        );

        await tester.pump();

        expect(mockNotifier.fetchThreadsCalled, isTrue);
      });
    });

    group('selectThread', () {
      testWidgets('should call selectThread on notifier and navigate back', (tester) async {
        final testThread = Thread(
            id: 'test-thread-id',
            name: 'Test Thread',
          );

        await tester.pumpWidget(
          createTestWidget(
            child: Builder(
              builder: (context) {
                final testController = createController(context);
                
                testController.selectThread(testThread);
                
                return const SizedBox();
              },
            ),
          ),
        );

        await tester.pumpAndSettle();

        expect(mockNotifier.selectThreadCalled, isTrue);
        expect(mockNotifier.lastSelectedThreadId, equals('test-thread-id'));
      });

      testWidgets('should handle thread with empty name', (tester) async {
        final testThread = Thread(
            id: 'test-thread-id',
            name: '',
          );

        await tester.pumpWidget(
          createTestWidget(
            child: Builder(
              builder: (context) {
                final testController = createController(context);
                
                expect(() => testController.selectThread(testThread), returnsNormally);
                
                return const SizedBox();
              },
            ),
          ),
        );

        expect(mockNotifier.selectThreadCalled, isTrue);
        expect(mockNotifier.lastSelectedThreadId, equals('test-thread-id'));
      });

      testWidgets('should handle thread with special characters in name', (tester) async {
        final testThread = Thread(
            id: 'special-thread-id',
            name: 'Thread with émojis 🚀 and spëcial chars',
          );

        await tester.pumpWidget(
          createTestWidget(
            child: Builder(
              builder: (context) {
                final testController = createController(context);
                
                testController.selectThread(testThread);
                
                return const SizedBox();
              },
            ),
          ),
        );

        expect(mockNotifier.selectThreadCalled, isTrue);
        expect(mockNotifier.lastSelectedThreadId, equals('special-thread-id'));
      });
    });

    group('showCreateThreadDialog', () {
      testWidgets('should complete without errors', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            child: Builder(
              builder: (context) {
                final testController = createController(context);
                
                expect(() => testController.showCreateThreadDialog(), returnsNormally);
                
                return const SizedBox();
              },
            ),
          ),
        );
      });
    });

    group('navigateBack', () {
      testWidgets('should call Navigator.pop', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            child: Builder(
              builder: (context) {
                final testController = createController(context);
                
                testController.navigateBack();
                
                return const SizedBox();
              },
            ),
          ),
        );

        await tester.pumpAndSettle();
      });
    });

    group('Provider Integration', () {
      testWidgets('should access threads notifier correctly', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            child: Builder(
              builder: (context) {
                final testController = createController(context);
                
                expect(testController, isA<ThreadsController>());
                
                return const SizedBox();
              },
            ),
          ),
        );
      });
    });

    group('Error Handling', () {
      testWidgets('should handle empty error messages', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            child: Builder(
              builder: (context) {
                final testController = createController(context);
                
                testController.showErrorSnackBar('');
                
                return const SizedBox();
              },
            ),
          ),
        );

        await tester.pumpAndSettle();

        expect(find.text(''), findsOneWidget);
        expect(find.byType(SnackBar), findsOneWidget);
      });

      testWidgets('should handle long error messages', (tester) async {
        const longError = 'This is a very long error message that should still be displayed properly in the snackbar without causing any layout issues or overflow problems in the user interface.';

        await tester.pumpWidget(
          createTestWidget(
            child: Builder(
              builder: (context) {
                final testController = createController(context);
                
                testController.showErrorSnackBar(longError);
                
                return const SizedBox();
              },
            ),
          ),
        );

        await tester.pumpAndSettle();

        expect(find.textContaining('This is a very long error'), findsOneWidget);
      });

      testWidgets('should handle special characters in error messages', (tester) async {
        const specialError = 'Error with émojis 💥 and spëcial chars @#\$%^&*()';

        await tester.pumpWidget(
          createTestWidget(
            child: Builder(
              builder: (context) {
                final testController = createController(context);
                
                testController.showErrorSnackBar(specialError);
                
                return const SizedBox();
              },
            ),
          ),
        );

        await tester.pumpAndSettle();

        expect(find.text(specialError), findsOneWidget);
      });
    });

    group('Multiple Operations', () {
      testWidgets('should handle multiple thread selections', (tester) async {
        final threads = [
          Thread(
            id: 'thread-1',
            name: 'Thread 1',
          ),
          Thread(
            id: 'thread-2',
            name: 'Thread 2',
          ),
        ];

        await tester.pumpWidget(
          createTestWidget(
            child: Builder(
              builder: (context) {
                final testController = createController(context);
                
                testController.selectThread(threads[0]);
                testController.selectThread(threads[1]);
                
                return const SizedBox();
              },
            ),
          ),
        );

        expect(mockNotifier.lastSelectedThreadId, equals('thread-2'));
      });

      testWidgets('should handle multiple refresh calls', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            child: Builder(
              builder: (context) {
                final testController = createController(context);
                
                testController.refreshThreads();
                testController.refreshThreads();
                testController.refreshThreads();
                
                return const SizedBox();
              },
            ),
          ),
        );

        await tester.pump();

        expect(mockNotifier.fetchThreadsCalled, isTrue);
      });

      testWidgets('should handle rapid error messages', (tester) async {
        await tester.pumpWidget(
          createTestWidget(
            child: Builder(
              builder: (context) {
                final testController = createController(context);
                
                for (int i = 0; i < 5; i++) {
                  testController.showErrorSnackBar('Error $i');
                }
                
                return const SizedBox();
              },
            ),
          ),
        );

        await tester.pumpAndSettle();

        expect(find.text('Error 4'), findsOneWidget);
      });
    });

    group('Context Handling', () {
      testWidgets('should work with different scaffold contexts', (tester) async {
        await tester.pumpWidget(
          MaterialApp(
            home: UncontrolledProviderScope(
              container: container,
              child: Scaffold(
                body: Builder(
                  builder: (context) {
                    final testController = createController(context);
                    
                    testController.showErrorSnackBar('Context test');
                    
                    return const SizedBox();
                  },
                ),
              ),
            ),
          ),
        );

        await tester.pumpAndSettle();

        expect(find.text('Context test'), findsOneWidget);
      });

      testWidgets('should work with nested navigation contexts', (tester) async {
        await tester.pumpWidget(
          MaterialApp(
            home: UncontrolledProviderScope(
              container: container,
              child: Navigator(
                onGenerateRoute: (settings) => MaterialPageRoute(
                  builder: (context) => Scaffold(
                    body: Builder(
                      builder: (nestedContext) {
                        final testController = createController(nestedContext);
                        
                        expect(() => testController.navigateBack(), returnsNormally);
                        
                        return const SizedBox();
                      },
                    ),
                  ),
                ),
              ),
            ),
          ),
        );

        await tester.pumpAndSettle();
      });
    });

    group('Thread Model Validation', () {
      testWidgets('should handle thread with all properties populated', (tester) async {
        final completeThread = Thread(
            id: 'complete-id',
            name: 'Complete Thread Title',
          );

        await tester.pumpWidget(
          createTestWidget(
            child: Builder(
              builder: (context) {
                final testController = createController(context);
                
                testController.selectThread(completeThread);
                
                return const SizedBox();
              },
            ),
          ),
        );

        expect(mockNotifier.selectThreadCalled, isTrue);
        expect(mockNotifier.lastSelectedThreadId, equals('complete-id'));
      });

      testWidgets('should handle thread with minimal properties', (tester) async {
        final minimalThread = Thread(
            id: 'minimal-id',
            name: '',
          );

        await tester.pumpWidget(
          createTestWidget(
            child: Builder(
              builder: (context) {
                final testController = createController(context);
                
                testController.selectThread(minimalThread);
                
                return const SizedBox();
              },
            ),
          ),
        );

        expect(mockNotifier.selectThreadCalled, isTrue);
        expect(mockNotifier.lastSelectedThreadId, equals('minimal-id'));
      });
    });

    group('Theme Integration', () {
      testWidgets('should work with dark theme', (tester) async {
        await tester.pumpWidget(
          MaterialApp(
            theme: ThemeData.dark(),
            home: UncontrolledProviderScope(
              container: container,
              child: Scaffold(
                body: Builder(
                  builder: (context) {
                    final testController = createController(context);
                    
                    testController.showErrorSnackBar('Dark theme error');
                    
                    return const SizedBox();
                  },
                ),
              ),
            ),
          ),
        );

        await tester.pumpAndSettle();

        expect(find.text('Dark theme error'), findsOneWidget);
      });

      testWidgets('should work with custom color scheme', (tester) async {
        await tester.pumpWidget(
          MaterialApp(
            theme: ThemeData(
              colorScheme: ColorScheme.fromSeed(
                seedColor: Colors.purple,
                error: Colors.orange,
              ),
            ),
            home: UncontrolledProviderScope(
              container: container,
              child: Scaffold(
                body: Builder(
                  builder: (context) {
                    final testController = createController(context);
                    
                    testController.showErrorSnackBar('Custom theme error');
                    
                    return const SizedBox();
                  },
                ),
              ),
            ),
          ),
        );

        await tester.pumpAndSettle();

        final snackBar = tester.widget<SnackBar>(find.byType(SnackBar));
        expect(snackBar.backgroundColor, equals(Colors.orange));
      });
    });
  });
}