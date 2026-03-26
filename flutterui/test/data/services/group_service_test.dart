@TestOn('browser')
import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:flutterui/core/constants/api_constants.dart';
import 'package:flutterui/data/models/group_model.dart';
import 'package:flutterui/data/services/auth_service.dart';
import 'package:flutterui/data/services/group_service.dart';

// ---------------------------------------------------------------------------
// Manual mock for AuthService
// ---------------------------------------------------------------------------
class MockAuthService implements AuthService {
  Future<Map<String, String>> Function()? authenticatedHeadersStub;

  @override
  Future<Map<String, String>> get authenticatedHeaders async {
    if (authenticatedHeadersStub != null) {
      return authenticatedHeadersStub!();
    }
    return {
      'Authorization': 'Bearer test-token',
      'Content-Type': 'application/json',
    };
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------
final testGroupJson = {
  'id': 'group-1',
  'name': 'Test Group',
  'description': 'A test group',
  'owner_user_id': 'user-1',
  'created_at': '2024-01-01T00:00:00.000Z',
  'updated_at': '2024-01-01T00:00:00.000Z',
};

final testGroupJson2 = {
  'id': 'group-2',
  'name': 'Second Group',
  'description': null,
  'owner_user_id': 'user-2',
  'created_at': '2024-02-01T00:00:00.000Z',
  'updated_at': '2024-02-01T00:00:00.000Z',
};

final testMemberJson = {
  'user_id': 'user-1',
  'email': 'alice@example.com',
  'name': 'Alice',
};

final testMemberJson2 = {
  'user_id': 'user-2',
  'email': 'bob@example.com',
  'name': null,
};

final testGroupWithMembersJson = {
  ...testGroupJson,
  'members': [testMemberJson, testMemberJson2],
};

void main() {
  late MockAuthService mockAuthService;

  setUp(() {
    ApiConstants.baseUrl = 'http://localhost:8000';
    mockAuthService = MockAuthService();
  });

  // -------------------------------------------------------------------------
  // getUserGroups
  // -------------------------------------------------------------------------
  group('getUserGroups', () {
    test('200 with list of groups returns correct List<Group>', () async {
      final client = MockClient((request) async {
        return http.Response(json.encode([testGroupJson, testGroupJson2]), 200);
      });
      final service =
          GroupService(httpClient: client, authService: mockAuthService);

      final groups = await service.getUserGroups();

      expect(groups, hasLength(2));
      expect(groups[0].id, 'group-1');
      expect(groups[0].name, 'Test Group');
      expect(groups[0].description, 'A test group');
      expect(groups[0].ownerUserId, 'user-1');
      expect(groups[1].id, 'group-2');
      expect(groups[1].description, isNull);
    });

    test('200 with empty list returns empty List<Group>', () async {
      final client = MockClient((request) async {
        return http.Response(json.encode([]), 200);
      });
      final service =
          GroupService(httpClient: client, authService: mockAuthService);

      final groups = await service.getUserGroups();

      expect(groups, isEmpty);
    });

    test('500 response throws Exception', () async {
      final client = MockClient((request) async {
        return http.Response('Internal Server Error', 500);
      });
      final service =
          GroupService(httpClient: client, authService: mockAuthService);

      expect(() => service.getUserGroups(), throwsException);
    });

    test('sends correct URL and headers', () async {
      Uri? capturedUri;
      Map<String, String>? capturedHeaders;

      final client = MockClient((request) async {
        capturedUri = request.url;
        capturedHeaders = request.headers;
        return http.Response(json.encode([]), 200);
      });
      final service =
          GroupService(httpClient: client, authService: mockAuthService);

      await service.getUserGroups();

      expect(capturedUri.toString(), contains('/groups'));
      expect(capturedHeaders?['Authorization'], 'Bearer test-token');
    });
  });

  // -------------------------------------------------------------------------
  // createGroup
  // -------------------------------------------------------------------------
  group('createGroup', () {
    test('201 returns Group with correct fields', () async {
      final client = MockClient((request) async {
        return http.Response(json.encode(testGroupJson), 201);
      });
      final service =
          GroupService(httpClient: client, authService: mockAuthService);

      final group =
          await service.createGroup(name: 'Test Group', description: 'A test group');

      expect(group.id, 'group-1');
      expect(group.name, 'Test Group');
      expect(group.description, 'A test group');
      expect(group.ownerUserId, 'user-1');
    });

    test('400 response throws Exception', () async {
      final client = MockClient((request) async {
        return http.Response('Bad Request', 400);
      });
      final service =
          GroupService(httpClient: client, authService: mockAuthService);

      expect(
        () => service.createGroup(name: 'Test'),
        throwsException,
      );
    });

    test('POST body contains name and description', () async {
      Map<String, dynamic>? capturedBody;

      final client = MockClient((request) async {
        capturedBody = json.decode(request.body) as Map<String, dynamic>;
        return http.Response(json.encode(testGroupJson), 201);
      });
      final service =
          GroupService(httpClient: client, authService: mockAuthService);

      await service.createGroup(name: 'Test Group', description: 'A test group');

      expect(capturedBody?['name'], 'Test Group');
      expect(capturedBody?['description'], 'A test group');
    });

    test('POST body handles null description', () async {
      Map<String, dynamic>? capturedBody;

      final client = MockClient((request) async {
        capturedBody = json.decode(request.body) as Map<String, dynamic>;
        return http.Response(json.encode(testGroupJson), 201);
      });
      final service =
          GroupService(httpClient: client, authService: mockAuthService);

      await service.createGroup(name: 'Test Group');

      expect(capturedBody?['name'], 'Test Group');
      expect(capturedBody?['description'], isNull);
    });
  });

  // -------------------------------------------------------------------------
  // getGroup
  // -------------------------------------------------------------------------
  group('getGroup', () {
    test('200 returns GroupWithMembers with members', () async {
      final client = MockClient((request) async {
        return http.Response(json.encode(testGroupWithMembersJson), 200);
      });
      final service =
          GroupService(httpClient: client, authService: mockAuthService);

      final group = await service.getGroup('group-1');

      expect(group.id, 'group-1');
      expect(group.name, 'Test Group');
      expect(group.members, hasLength(2));
      expect(group.members[0].userId, 'user-1');
      expect(group.members[0].email, 'alice@example.com');
      expect(group.members[0].name, 'Alice');
      expect(group.members[1].userId, 'user-2');
      expect(group.members[1].name, isNull);
    });

    test('404 response throws Exception', () async {
      final client = MockClient((request) async {
        return http.Response('Not Found', 404);
      });
      final service =
          GroupService(httpClient: client, authService: mockAuthService);

      expect(() => service.getGroup('nonexistent'), throwsException);
    });
  });

  // -------------------------------------------------------------------------
  // updateGroup
  // -------------------------------------------------------------------------
  group('updateGroup', () {
    test('200 returns updated Group', () async {
      final updatedJson = {
        ...testGroupJson,
        'name': 'Updated Name',
      };
      final client = MockClient((request) async {
        return http.Response(json.encode(updatedJson), 200);
      });
      final service =
          GroupService(httpClient: client, authService: mockAuthService);

      final group = await service.updateGroup('group-1', name: 'Updated Name');

      expect(group.name, 'Updated Name');
    });

    test('403 response throws Exception', () async {
      final client = MockClient((request) async {
        return http.Response('Forbidden', 403);
      });
      final service =
          GroupService(httpClient: client, authService: mockAuthService);

      expect(
        () => service.updateGroup('group-1', name: 'New Name'),
        throwsException,
      );
    });

    test('body contains only name when description is not set', () async {
      Map<String, dynamic>? capturedBody;

      final client = MockClient((request) async {
        capturedBody = json.decode(request.body) as Map<String, dynamic>;
        return http.Response(json.encode(testGroupJson), 200);
      });
      final service =
          GroupService(httpClient: client, authService: mockAuthService);

      await service.updateGroup('group-1', name: 'Only Name');

      expect(capturedBody?['name'], 'Only Name');
      expect(capturedBody?.containsKey('description'), isFalse);
    });
  });

  // -------------------------------------------------------------------------
  // deleteGroup
  // -------------------------------------------------------------------------
  group('deleteGroup', () {
    test('204 completes successfully', () async {
      final client = MockClient((request) async {
        return http.Response('', 204);
      });
      final service =
          GroupService(httpClient: client, authService: mockAuthService);

      // Should not throw
      await service.deleteGroup('group-1');
    });

    test('403 response throws Exception', () async {
      final client = MockClient((request) async {
        return http.Response('Forbidden', 403);
      });
      final service =
          GroupService(httpClient: client, authService: mockAuthService);

      expect(() => service.deleteGroup('group-1'), throwsException);
    });
  });

  // -------------------------------------------------------------------------
  // getAllUsers
  // -------------------------------------------------------------------------
  group('getAllUsers', () {
    test('200 with users returns List<GroupMember>', () async {
      final client = MockClient((request) async {
        return http.Response(
            json.encode([testMemberJson, testMemberJson2]), 200);
      });
      final service =
          GroupService(httpClient: client, authService: mockAuthService);

      final users = await service.getAllUsers();

      expect(users, hasLength(2));
      expect(users[0].userId, 'user-1');
      expect(users[0].email, 'alice@example.com');
      expect(users[0].name, 'Alice');
      expect(users[1].userId, 'user-2');
      expect(users[1].name, isNull);
    });

    test('200 with empty list returns empty list', () async {
      final client = MockClient((request) async {
        return http.Response(json.encode([]), 200);
      });
      final service =
          GroupService(httpClient: client, authService: mockAuthService);

      final users = await service.getAllUsers();

      expect(users, isEmpty);
    });

    test('500 response throws Exception', () async {
      final client = MockClient((request) async {
        return http.Response('Internal Server Error', 500);
      });
      final service =
          GroupService(httpClient: client, authService: mockAuthService);

      expect(() => service.getAllUsers(), throwsException);
    });
  });

  // -------------------------------------------------------------------------
  // addGroupMember
  // -------------------------------------------------------------------------
  group('addGroupMember', () {
    test('201 completes successfully', () async {
      final client = MockClient((request) async {
        return http.Response('', 201);
      });
      final service =
          GroupService(httpClient: client, authService: mockAuthService);

      // Should not throw
      await service.addGroupMember('group-1', 'user-2');
    });

    test('403 response throws Exception', () async {
      final client = MockClient((request) async {
        return http.Response('Forbidden', 403);
      });
      final service =
          GroupService(httpClient: client, authService: mockAuthService);

      expect(
        () => service.addGroupMember('group-1', 'user-2'),
        throwsException,
      );
    });

    test('URL includes groupId and userId', () async {
      Uri? capturedUri;

      final client = MockClient((request) async {
        capturedUri = request.url;
        return http.Response('', 201);
      });
      final service =
          GroupService(httpClient: client, authService: mockAuthService);

      await service.addGroupMember('group-1', 'user-2');

      expect(capturedUri.toString(), contains('/groups/group-1/members/user-2'));
    });
  });

  // -------------------------------------------------------------------------
  // removeGroupMember
  // -------------------------------------------------------------------------
  group('removeGroupMember', () {
    test('204 completes successfully', () async {
      final client = MockClient((request) async {
        return http.Response('', 204);
      });
      final service =
          GroupService(httpClient: client, authService: mockAuthService);

      // Should not throw
      await service.removeGroupMember('group-1', 'user-2');
    });

    test('404 response throws Exception', () async {
      final client = MockClient((request) async {
        return http.Response('Not Found', 404);
      });
      final service =
          GroupService(httpClient: client, authService: mockAuthService);

      expect(
        () => service.removeGroupMember('group-1', 'user-2'),
        throwsException,
      );
    });
  });

  // -------------------------------------------------------------------------
  // HTTP client injection
  // -------------------------------------------------------------------------
  group('HTTP client injection', () {
    test('injected client is used for requests', () async {
      var clientWasCalled = false;

      final client = MockClient((request) async {
        clientWasCalled = true;
        return http.Response(json.encode([]), 200);
      });
      final service =
          GroupService(httpClient: client, authService: mockAuthService);

      await service.getUserGroups();

      expect(clientWasCalled, isTrue);
    });
  });
}
