@TestOn('browser')
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/presentation/screens/agents/widgets/agent_error_banner.dart';

Widget _wrap(Widget child) {
  return MaterialApp(home: Scaffold(body: child));
}

void main() {
  group('AgentErrorBanner', () {
    group('visibility', () {
      testWidgets('renders nothing when errorMessage is null', (tester) async {
        await tester.pumpWidget(_wrap(
          const AgentErrorBanner(errorMessage: null),
        ));

        expect(find.byType(SizedBox), findsOneWidget);
        expect(find.text('error'), findsNothing);
        expect(find.byIcon(Icons.error_outline), findsNothing);
      });

      testWidgets('renders error text when errorMessage is set',
          (tester) async {
        await tester.pumpWidget(_wrap(
          const AgentErrorBanner(errorMessage: 'Something went wrong'),
        ));
        await tester.pumpAndSettle();

        expect(find.text('Something went wrong'), findsOneWidget);
        expect(find.byIcon(Icons.error_outline), findsOneWidget);
      });
    });

    group('dismiss button', () {
      testWidgets('shows close button when onDismiss is provided',
          (tester) async {
        await tester.pumpWidget(_wrap(
          AgentErrorBanner(
            errorMessage: 'Error occurred',
            onDismiss: () {},
          ),
        ));
        await tester.pumpAndSettle();

        expect(find.byIcon(Icons.close), findsOneWidget);
      });

      testWidgets('does not show close button when onDismiss is null',
          (tester) async {
        await tester.pumpWidget(_wrap(
          const AgentErrorBanner(errorMessage: 'Error occurred'),
        ));
        await tester.pumpAndSettle();

        expect(find.byIcon(Icons.close), findsNothing);
      });

      testWidgets('calls onDismiss when close button is tapped',
          (tester) async {
        var dismissed = false;

        await tester.pumpWidget(_wrap(
          AgentErrorBanner(
            errorMessage: 'Error occurred',
            onDismiss: () => dismissed = true,
          ),
        ));
        await tester.pumpAndSettle();

        await tester.tap(find.byIcon(Icons.close));
        expect(dismissed, isTrue);
      });
    });

    group('content', () {
      testWidgets('displays the full error message text', (tester) async {
        const message =
            'An agent with this name already exists. Please choose a different name.';
        await tester.pumpWidget(_wrap(
          const AgentErrorBanner(errorMessage: message),
        ));
        await tester.pumpAndSettle();

        expect(find.text(message), findsOneWidget);
      });

      testWidgets('error icon is present', (tester) async {
        await tester.pumpWidget(_wrap(
          const AgentErrorBanner(errorMessage: 'Error'),
        ));
        await tester.pumpAndSettle();

        expect(find.byIcon(Icons.error_outline), findsOneWidget);
      });
    });
  });
}
