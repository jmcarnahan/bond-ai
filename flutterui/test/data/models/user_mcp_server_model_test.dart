@TestOn('browser')
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/data/models/user_mcp_server_model.dart';

void main() {
  group('UserMcpServerModel', () {
    test('fromJson parses basic server', () {
      final json = {
        'id': 'abc-123',
        'server_name': 'my_server',
        'display_name': 'My Server',
        'description': 'A test server',
        'url': 'http://localhost:5555/mcp',
        'transport': 'streamable-http',
        'auth_type': 'none',
        'has_headers': false,
        'has_oauth_config': false,
        'oauth_config': null,
        'extra_config': null,
        'is_active': true,
        'created_at': '2026-04-08T12:00:00',
        'updated_at': '2026-04-08T12:00:00',
      };

      final model = UserMcpServerModel.fromJson(json);
      expect(model.id, 'abc-123');
      expect(model.serverName, 'my_server');
      expect(model.displayName, 'My Server');
      expect(model.description, 'A test server');
      expect(model.url, 'http://localhost:5555/mcp');
      expect(model.transport, 'streamable-http');
      expect(model.authType, 'none');
      expect(model.hasHeaders, false);
      expect(model.hasOauthConfig, false);
      expect(model.isActive, true);
    });

    test('fromJson parses server with oauth config', () {
      final json = {
        'id': 'def-456',
        'server_name': 'oauth_server',
        'display_name': 'OAuth Server',
        'url': 'https://oauth.example.com/mcp',
        'transport': 'streamable-http',
        'auth_type': 'oauth2',
        'has_headers': false,
        'has_oauth_config': true,
        'oauth_config': {
          'client_id': 'test-client',
          'authorize_url': 'https://auth.example.com/authorize',
          'token_url': 'https://auth.example.com/token',
          'scopes': 'read write',
          'redirect_uri': 'http://localhost:8000/cb',
          'provider': 'microsoft',
        },
        'extra_config': {'cloud_id': 'abc123', 'site_url': 'https://example.com'},
        'is_active': true,
      };

      final model = UserMcpServerModel.fromJson(json);
      expect(model.authType, 'oauth2');
      expect(model.hasOauthConfig, true);
      expect(model.oauthConfig, isNotNull);
      expect(model.oauthConfig!.clientId, 'test-client');
      expect(model.oauthConfig!.provider, 'microsoft');
      expect(model.oauthConfig!.scopes, 'read write');
      expect(model.extraConfig, isNotNull);
      expect(model.extraConfig!['cloud_id'], 'abc123');
      expect(model.extraConfig!['site_url'], 'https://example.com');
    });

    test('fromJson handles missing optional fields', () {
      final json = {
        'id': 'min-1',
        'server_name': 'minimal',
        'display_name': 'Minimal',
        'url': 'http://localhost/mcp',
      };

      final model = UserMcpServerModel.fromJson(json);
      expect(model.transport, 'streamable-http'); // default
      expect(model.authType, 'none'); // default
      expect(model.hasHeaders, false);
      expect(model.hasOauthConfig, false);
      expect(model.oauthConfig, isNull);
      expect(model.extraConfig, isNull);
      expect(model.isActive, true); // default
      expect(model.description, isNull);
    });

    test('toJson produces correct output', () {
      final model = UserMcpServerModel(
        id: 'test-1',
        serverName: 'test_server',
        displayName: 'Test Server',
        description: 'Desc',
        url: 'http://localhost/mcp',
        transport: 'sse',
        authType: 'header',
        hasHeaders: true,
        extraConfig: {'cloud_id': 'xyz'},
      );

      final json = model.toJson();
      expect(json['id'], 'test-1');
      expect(json['server_name'], 'test_server');
      expect(json['transport'], 'sse');
      expect(json['auth_type'], 'header');
      expect(json['has_headers'], true);
      expect(json['extra_config'], {'cloud_id': 'xyz'});
    });

    test('equality based on id', () {
      final a = UserMcpServerModel(id: 'same', serverName: 'a', displayName: 'A', url: 'http://a/mcp');
      final b = UserMcpServerModel(id: 'same', serverName: 'b', displayName: 'B', url: 'http://b/mcp');
      final c = UserMcpServerModel(id: 'diff', serverName: 'a', displayName: 'A', url: 'http://a/mcp');

      expect(a, equals(b)); // Same ID
      expect(a, isNot(equals(c))); // Different ID
    });
  });

  group('OAuthConfigDisplay', () {
    test('fromJson parses correctly', () {
      final json = {
        'client_id': 'cid',
        'authorize_url': 'https://auth.com/auth',
        'token_url': 'https://auth.com/token',
        'scopes': 'read write',
        'redirect_uri': 'http://localhost/cb',
        'provider': 'github',
      };

      final config = OAuthConfigDisplay.fromJson(json);
      expect(config.clientId, 'cid');
      expect(config.authorizeUrl, 'https://auth.com/auth');
      expect(config.tokenUrl, 'https://auth.com/token');
      expect(config.scopes, 'read write');
      expect(config.redirectUri, 'http://localhost/cb');
      expect(config.provider, 'github');
    });

    test('toJson roundtrips', () {
      final config = OAuthConfigDisplay(
        clientId: 'c1',
        authorizeUrl: 'https://a/auth',
        tokenUrl: 'https://a/token',
        redirectUri: 'http://r/cb',
      );
      final json = config.toJson();
      final roundtripped = OAuthConfigDisplay.fromJson(json);
      expect(roundtripped.clientId, config.clientId);
      expect(roundtripped.scopes, isNull);
      expect(roundtripped.provider, isNull);
    });
  });

  group('UserMcpServerListResponse', () {
    test('fromJson parses server list', () {
      final json = {
        'servers': [
          {
            'id': '1',
            'server_name': 'srv1',
            'display_name': 'Server 1',
            'url': 'http://localhost/mcp',
            'is_active': true,
          },
          {
            'id': '2',
            'server_name': 'srv2',
            'display_name': 'Server 2',
            'url': 'http://localhost/mcp',
            'is_active': false,
          },
        ],
        'total': 2,
      };

      final response = UserMcpServerListResponse.fromJson(json);
      expect(response.total, 2);
      expect(response.servers.length, 2);
      expect(response.servers[0].serverName, 'srv1');
      expect(response.servers[1].isActive, false);
    });

    test('fromJson handles empty list', () {
      final json = {'servers': [], 'total': 0};
      final response = UserMcpServerListResponse.fromJson(json);
      expect(response.total, 0);
      expect(response.servers, isEmpty);
    });
  });

  group('TestConnectionResponse', () {
    test('fromJson parses success', () {
      final json = {
        'success': true,
        'tool_count': 3,
        'tools': ['tool_a', 'tool_b', 'tool_c'],
      };

      final response = TestConnectionResponse.fromJson(json);
      expect(response.success, true);
      expect(response.toolCount, 3);
      expect(response.tools, hasLength(3));
      expect(response.error, isNull);
    });

    test('fromJson parses failure', () {
      final json = {
        'success': false,
        'tool_count': 0,
        'tools': [],
        'error': 'Connection refused',
      };

      final response = TestConnectionResponse.fromJson(json);
      expect(response.success, false);
      expect(response.error, 'Connection refused');
    });
  });
}
