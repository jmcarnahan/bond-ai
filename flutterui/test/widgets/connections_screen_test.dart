import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/connection_model.dart';
import 'package:flutterui/data/models/user_mcp_server_model.dart';
import 'package:flutterui/data/services/user_mcp_server_service.dart';
import 'package:flutterui/providers/connections_provider.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import 'package:flutterui/presentation/screens/connections/connections_screen.dart';

// ---------------------------------------------------------------------------
// Fakes
// ---------------------------------------------------------------------------

/// Seeded notifier: loadConnections is a no-op so initState never overwrites
/// the canned state.
class _FakeConnectionsNotifier extends StateNotifier<ConnectionsState>
    implements ConnectionsNotifier {
  _FakeConnectionsNotifier(ConnectionsState seeded) : super(seeded);

  @override
  Future<void> loadConnections() async {}

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _FakeUserMcpServerService implements UserMcpServerService {
  @override
  Future<UserMcpServerListResponse> listServers() async =>
      UserMcpServerListResponse(servers: const [], total: 0);

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

ConnectionStatus _connection({
  required String name,
  required String displayName,
  bool connected = false,
  bool requiresConnection = true,
}) {
  return ConnectionStatus(
    name: name,
    displayName: displayName,
    connected: connected,
    valid: true,
    authType: 'bond_jwt',
    requiresAuthorization: !connected,
    requiresConnection: requiresConnection,
  );
}

Future<void> _pumpConnectionsScreen(
  WidgetTester tester,
  List<ConnectionStatus> connections,
) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        connectionsNotifierProvider.overrideWith(
          (ref) => _FakeConnectionsNotifier(
            ConnectionsState(connections: connections),
          ),
        ),
        userMcpServerServiceProvider
            .overrideWithValue(_FakeUserMcpServerService()),
      ],
      child: const MaterialApp(home: ConnectionsScreen()),
    ),
  );
  await tester.pumpAndSettle();
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  group('ConnectionsScreen row actions', () {
    testWidgets(
        'internal connection (requiresConnection=false) renders an '
        'informational tile with no Connect/Disconnect action', (tester) async {
      await _pumpConnectionsScreen(tester, [
        _connection(
          name: 'sbelcrm',
          displayName: 'SBEL CRM',
          connected: true,
          requiresConnection: false,
        ),
      ]);

      expect(find.text('SBEL CRM'), findsOneWidget);
      expect(find.text('Connected'), findsOneWidget);
      expect(find.text('Included'), findsOneWidget);
      expect(find.text('Connect'), findsNothing);
      expect(find.text('Disconnect'), findsNothing);
    });

    testWidgets('managed connection still gets a Connect button when '
        'disconnected', (tester) async {
      await _pumpConnectionsScreen(tester, [
        _connection(name: 'github', displayName: 'GitHub'),
      ]);

      expect(find.text('GitHub'), findsOneWidget);
      expect(find.text('Not Connected'), findsOneWidget);
      expect(find.text('Connect'), findsOneWidget);
      expect(find.text('Included'), findsNothing);
    });

    testWidgets('managed connection still gets a Disconnect button when '
        'connected', (tester) async {
      await _pumpConnectionsScreen(tester, [
        _connection(name: 'microsoft', displayName: 'Microsoft', connected: true),
      ]);

      expect(find.text('Microsoft'), findsOneWidget);
      expect(find.text('Disconnect'), findsOneWidget);
      expect(find.text('Included'), findsNothing);
    });
  });
}
