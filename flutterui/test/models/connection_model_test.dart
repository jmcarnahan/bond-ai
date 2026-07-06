import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/data/models/connection_model.dart';

void main() {
  group('ConnectionStatus.requiresConnection', () {
    test('defaults to true when absent from JSON', () {
      final status = ConnectionStatus.fromJson(const {
        'name': 'atlassian',
        'display_name': 'Atlassian',
        'connected': false,
        'auth_type': 'bond_jwt',
      });
      expect(status.requiresConnection, isTrue);
      expect(status.needsAttention, isTrue);
    });

    test('parses false and round-trips through toJson', () {
      final status = ConnectionStatus.fromJson(const {
        'name': 'sbelcrm',
        'display_name': 'SBEL CRM',
        'connected': true,
        'valid': true,
        'auth_type': 'bond_jwt',
        'requires_connection': false,
      });
      expect(status.requiresConnection, isFalse);
      expect(status.toJson()['requires_connection'], isFalse);
      expect(status.statusText, 'Connected');
    });

    test('never needs attention when no connection is required', () {
      final status = ConnectionStatus.fromJson(const {
        'name': 'sbelcrm',
        'display_name': 'SBEL CRM',
        'connected': false, // even if a stale payload says disconnected
        'auth_type': 'bond_jwt',
        'requires_connection': false,
      });
      expect(status.needsAttention, isFalse);
    });
  });
}
