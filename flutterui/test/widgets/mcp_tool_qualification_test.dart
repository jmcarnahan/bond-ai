@TestOn('browser')
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/data/models/mcp_model.dart';

/// Test the tool qualification logic that is used by McpSelectionSection.
/// These tests validate the core data manipulation without requiring
/// the full widget tree with Riverpod providers.

// Helper functions that mirror the logic in mcp_selection_section.dart

bool isToolSelected(Set<String> selectedToolNames, String serverName, String toolName) {
  // Check qualified name first (new format)
  if (selectedToolNames.contains('$serverName:$toolName')) return true;
  // Backward compat: check bare name (legacy agents)
  if (selectedToolNames.contains(toolName)) return true;
  return false;
}

Set<String> upgradeToolNames(
  Set<String> current,
  McpToolsGroupedResponse grouped,
) {
  final upgraded = <String>{};
  for (final name in current) {
    if (name.contains(':')) {
      upgraded.add(name);
    } else {
      bool found = false;
      for (final server in grouped.servers) {
        final matchingTool = server.tools.cast<McpToolModel?>().firstWhere(
          (t) => t!.name == name || t.displayName == name,
          orElse: () => null,
        );
        if (matchingTool != null) {
          upgraded.add('${server.serverName}:${matchingTool.name}');
          found = true;
          break;
        }
      }
      if (!found) upgraded.add(name);
    }
  }
  return upgraded;
}

Set<String> onToolSelectionChanged(
  Set<String> currentSelection,
  String serverName,
  String toolName,
  bool selected,
) {
  final qualifiedName = '$serverName:$toolName';
  final updatedSelection = Set<String>.from(currentSelection);
  if (selected) {
    updatedSelection.add(qualifiedName);
  } else {
    updatedSelection.remove(qualifiedName);
    updatedSelection.remove(toolName);
  }
  return updatedSelection;
}

Set<String> selectAllToolsInServer(
  Set<String> currentSelection,
  McpServerWithTools server,
  bool select,
) {
  final updatedSelection = Set<String>.from(currentSelection);
  for (final tool in server.tools) {
    final qualifiedName = '${server.serverName}:${tool.name}';
    if (select) {
      updatedSelection.add(qualifiedName);
    } else {
      updatedSelection.remove(qualifiedName);
      updatedSelection.remove(tool.name);
    }
  }
  return updatedSelection;
}

// Test data helpers

McpToolModel _tool(String name, [String description = 'A tool']) {
  return McpToolModel(name: name, description: description, inputSchema: const {});
}

McpServerWithTools _server(String name, List<McpToolModel> tools,
    {String? displayName}) {
  return McpServerWithTools(
    serverName: name,
    displayName: displayName ?? name.replaceAll('_', ' ').toUpperCase(),
    tools: tools,
    toolCount: tools.length,
    connectionStatus: const McpConnectionStatusInfo(connected: true, valid: true),
  );
}

McpToolsGroupedResponse _grouped(List<McpServerWithTools> servers) {
  final totalTools = servers.fold<int>(0, (sum, s) => sum + s.tools.length);
  return McpToolsGroupedResponse(
    servers: servers,
    totalServers: servers.length,
    totalTools: totalTools,
  );
}

void main() {
  group('isToolSelected', () {
    test('qualified name matches correct server', () {
      final selected = {'microsoft:get_user_profile'};
      expect(isToolSelected(selected, 'microsoft', 'get_user_profile'), isTrue);
      expect(isToolSelected(selected, 'my_client', 'get_user_profile'), isFalse);
    });

    test('bare name matches any server (backward compat)', () {
      final selected = {'get_user_profile'};
      expect(isToolSelected(selected, 'microsoft', 'get_user_profile'), isTrue);
      expect(isToolSelected(selected, 'my_client', 'get_user_profile'), isTrue);
    });

    test('unrelated tool not selected', () {
      final selected = {'microsoft:read_emails'};
      expect(isToolSelected(selected, 'microsoft', 'get_user_profile'), isFalse);
    });

    test('empty selection matches nothing', () {
      final selected = <String>{};
      expect(isToolSelected(selected, 'microsoft', 'get_user_profile'), isFalse);
    });

    test('qualified and bare names for different tools', () {
      final selected = {'microsoft:read_emails', 'list_files'};
      expect(isToolSelected(selected, 'microsoft', 'read_emails'), isTrue);
      expect(isToolSelected(selected, 'my_client', 'read_emails'), isFalse);
      // bare name matches any server
      expect(isToolSelected(selected, 'my_client', 'list_files'), isTrue);
      expect(isToolSelected(selected, 'microsoft', 'list_files'), isTrue);
    });
  });

  group('upgradeToolNames', () {
    late McpToolsGroupedResponse grouped;

    setUp(() {
      grouped = _grouped([
        _server('my_client', [_tool('get_user_profile'), _tool('list_files')]),
        _server('microsoft', [_tool('get_user_profile'), _tool('read_emails')]),
      ]);
    });

    test('bare names upgrade to first matching server', () {
      final result = upgradeToolNames({'get_user_profile'}, grouped);
      expect(result, {'my_client:get_user_profile'});
    });

    test('already qualified names pass through unchanged', () {
      final result = upgradeToolNames({'microsoft:get_user_profile'}, grouped);
      expect(result, {'microsoft:get_user_profile'});
    });

    test('unknown bare names kept as-is', () {
      final result = upgradeToolNames({'unknown_tool'}, grouped);
      expect(result, {'unknown_tool'});
    });

    test('mix of qualified and bare names handled correctly', () {
      final result = upgradeToolNames(
        {'microsoft:read_emails', 'list_files'},
        grouped,
      );
      expect(result, {'microsoft:read_emails', 'my_client:list_files'});
    });

    test('bare name matching via displayName uses actual tool name', () {
      // Regression test: when a tool has a hashed name like b.{hash}.{name},
      // the upgrade should use the actual tool name (with hash), not the bare displayName
      final hashedGrouped = _grouped([
        _server('my_client', [
          McpToolModel(
            name: 'b.a1b2c3.get_user_profile',
            description: 'test',
            inputSchema: const {},
          ),
        ]),
      ]);
      final result = upgradeToolNames({'get_user_profile'}, hashedGrouped);
      // Should qualify with the actual hashed tool name, not the bare displayName
      expect(result, {'my_client:b.a1b2c3.get_user_profile'});
    });

    test('idempotent - already upgraded names stay the same', () {
      final first = upgradeToolNames({'get_user_profile'}, grouped);
      final second = upgradeToolNames(first, grouped);
      expect(second, first);
    });

    test('empty set returns empty', () {
      final result = upgradeToolNames(<String>{}, grouped);
      expect(result, isEmpty);
    });
  });

  group('onToolSelectionChanged', () {
    test('selecting produces qualified name', () {
      final result = onToolSelectionChanged(
        <String>{},
        'microsoft',
        'get_user_profile',
        true,
      );
      expect(result, {'microsoft:get_user_profile'});
    });

    test('deselecting removes qualified name', () {
      final result = onToolSelectionChanged(
        {'microsoft:get_user_profile'},
        'microsoft',
        'get_user_profile',
        false,
      );
      expect(result, isEmpty);
    });

    test('deselecting also removes bare name', () {
      // Legacy state with bare name
      final result = onToolSelectionChanged(
        {'get_user_profile'},
        'microsoft',
        'get_user_profile',
        false,
      );
      expect(result, isEmpty);
    });

    test('selecting same tool from different server adds both', () {
      var selection = onToolSelectionChanged(
        <String>{},
        'my_client',
        'get_user_profile',
        true,
      );
      selection = onToolSelectionChanged(
        selection,
        'microsoft',
        'get_user_profile',
        true,
      );
      expect(selection, {
        'my_client:get_user_profile',
        'microsoft:get_user_profile',
      });
    });

    test('deselecting one server does not affect other server', () {
      final selection = {
        'my_client:get_user_profile',
        'microsoft:get_user_profile',
      };
      final result = onToolSelectionChanged(
        selection,
        'microsoft',
        'get_user_profile',
        false,
      );
      expect(result, {'my_client:get_user_profile'});
    });
  });

  group('selectAllToolsInServer', () {
    test('select all adds qualified names for server', () {
      final server = _server('microsoft', [
        _tool('read_emails'),
        _tool('send_email'),
      ]);
      final result = selectAllToolsInServer(<String>{}, server, true);
      expect(result, {
        'microsoft:read_emails',
        'microsoft:send_email',
      });
    });

    test('deselect all removes qualified and bare names', () {
      final server = _server('microsoft', [
        _tool('read_emails'),
        _tool('send_email'),
      ]);
      // Mix of legacy bare and new qualified
      final selection = {
        'microsoft:read_emails',
        'send_email', // legacy bare name
      };
      final result = selectAllToolsInServer(selection, server, false);
      expect(result, isEmpty);
    });

    test('select all does not affect other servers', () {
      final server = _server('microsoft', [_tool('read_emails')]);
      final selection = {'my_client:list_files'};
      final result = selectAllToolsInServer(selection, server, true);
      expect(result, {
        'my_client:list_files',
        'microsoft:read_emails',
      });
    });
  });

  group('McpToolModel.displayName with qualification', () {
    test('bare tool name returned as-is', () {
      final tool = _tool('get_user_profile');
      expect(tool.displayName, 'get_user_profile');
    });

    test('hashed tool name strips prefix', () {
      final tool = McpToolModel(
        name: 'b.a1b2c3.get_user_profile',
        description: 'test',
        inputSchema: const {},
      );
      expect(tool.displayName, 'get_user_profile');
    });
  });
}
