@TestOn('browser')
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/data/models/mcp_model.dart';

void main() {
  group('McpServerWithTools - isUserDefined', () {
    test('defaults to false', () {
      final json = {
        'server_name': 'global_server',
        'display_name': 'Global Server',
        'auth_type': 'bond_jwt',
        'connection_status': {'connected': true, 'valid': true},
        'tools': [],
        'tool_count': 0,
      };

      final server = McpServerWithTools.fromJson(json);
      expect(server.isUserDefined, false);
      expect(server.userServerId, isNull);
    });

    test('parses isUserDefined=true', () {
      final json = {
        'server_name': 'user_abc12345_my_server',
        'display_name': 'My Custom Server',
        'auth_type': 'none',
        'connection_status': {'connected': true, 'valid': true},
        'tools': [
          {'name': 'my_tool', 'description': 'A tool', 'input_schema': <String, dynamic>{}},
        ],
        'tool_count': 1,
        'is_user_defined': true,
        'user_server_id': 'uuid-123',
      };

      final server = McpServerWithTools.fromJson(json);
      expect(server.isUserDefined, true);
      expect(server.userServerId, 'uuid-123');
      expect(server.toolCount, 1);
      expect(server.tools.first.name, 'my_tool');
    });

    test('toJson includes isUserDefined fields', () {
      final server = McpServerWithTools(
        serverName: 'test',
        displayName: 'Test',
        connectionStatus: const McpConnectionStatusInfo(connected: true),
        tools: const [],
        toolCount: 0,
        isUserDefined: true,
        userServerId: 'uid-1',
      );

      final json = server.toJson();
      expect(json['is_user_defined'], true);
      expect(json['user_server_id'], 'uid-1');
    });

    test('global server has isUserDefined=false in toJson', () {
      final server = McpServerWithTools(
        serverName: 'global',
        displayName: 'Global',
        connectionStatus: const McpConnectionStatusInfo(connected: true),
        tools: const [],
        toolCount: 0,
      );

      final json = server.toJson();
      expect(json['is_user_defined'], false);
      expect(json['user_server_id'], isNull);
    });
  });

  group('McpToolsGroupedResponse with user-defined servers', () {
    test('mixed global and user-defined servers', () {
      final json = {
        'servers': [
          {
            'server_name': 'atlassian',
            'display_name': 'Atlassian',
            'auth_type': 'oauth2',
            'connection_status': {'connected': true, 'valid': true},
            'tools': [
              {'name': 'search_issues', 'description': 'Search Jira', 'input_schema': <String, dynamic>{}},
            ],
            'tool_count': 1,
            'is_user_defined': false,
          },
          {
            'server_name': 'user_abc_custom',
            'display_name': 'My Custom',
            'auth_type': 'none',
            'connection_status': {'connected': true, 'valid': true},
            'tools': [
              {'name': 'custom_tool', 'description': 'Custom', 'input_schema': <String, dynamic>{}},
            ],
            'tool_count': 1,
            'is_user_defined': true,
            'user_server_id': 'uid-abc',
          },
        ],
        'total_servers': 2,
        'total_tools': 2,
      };

      final response = McpToolsGroupedResponse.fromJson(json);
      expect(response.totalServers, 2);

      final globalServers = response.servers.where((s) => !s.isUserDefined).toList();
      final userServers = response.servers.where((s) => s.isUserDefined).toList();

      expect(globalServers.length, 1);
      expect(userServers.length, 1);
      expect(userServers.first.userServerId, 'uid-abc');
    });
  });
}
