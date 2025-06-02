import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutterui/data/services/auth_service.dart';
import 'package:flutterui/core/constants/api_constants.dart';

class MockHttpClient extends http.BaseClient {
  final Map<String, http.Response> _responses = {};
  final List<http.BaseRequest> _requests = [];

  void setResponse(String url, http.Response response) {
    _responses[url] = response;
  }

  List<http.BaseRequest> get requests => _requests;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    _requests.add(request);
    final response = _responses[request.url.toString()];
    
    if (response != null) {
      return http.StreamedResponse(
        Stream.value(response.bodyBytes),
        response.statusCode,
        headers: response.headers,
      );
    }
    
    return http.StreamedResponse(
      Stream.value([]),
      404,
    );
  }
}

void main() {
  group('AuthService Tests', () {
    late MockHttpClient mockHttpClient;
    late SharedPreferences sharedPreferences;
    late AuthService authService;

    setUp(() async {
      mockHttpClient = MockHttpClient();
      SharedPreferences.setMockInitialValues({});
      sharedPreferences = await SharedPreferences.getInstance();
      authService = AuthService(
        httpClient: mockHttpClient,
        sharedPreferences: sharedPreferences,
      );
    });

    group('Token Management', () {
      test('storeToken should store token in SharedPreferences', () async {
        const testToken = 'test_access_token_123';
        
        await authService.storeToken(testToken);
        
        final storedToken = sharedPreferences.getString('bondai_auth_token');
        expect(storedToken, equals(testToken));
      });

      test('retrieveToken should return stored token', () async {
        const testToken = 'test_access_token_123';
        await sharedPreferences.setString('bondai_auth_token', testToken);
        
        final retrievedToken = await authService.retrieveToken();
        
        expect(retrievedToken, equals(testToken));
      });

      test('retrieveToken should return null when no token stored', () async {
        final retrievedToken = await authService.retrieveToken();
        
        expect(retrievedToken, isNull);
      });

      test('clearToken should remove token from SharedPreferences', () async {
        const testToken = 'test_access_token_123';
        await sharedPreferences.setString('bondai_auth_token', testToken);
        
        await authService.clearToken();
        
        final retrievedToken = sharedPreferences.getString('bondai_auth_token');
        expect(retrievedToken, isNull);
      });
    });

    group('getCurrentUser', () {
      test('should return user when token exists and API call succeeds', () async {
        const testToken = 'test_access_token_123';
        const userJson = {
          'email': 'test@example.com',
          'name': 'Test User',
        };
        
        await sharedPreferences.setString('bondai_auth_token', testToken);
        mockHttpClient.setResponse(
          '${ApiConstants.baseUrl}${ApiConstants.usersMeEndpoint}',
          http.Response(jsonEncode(userJson), 200),
        );
        
        final user = await authService.getCurrentUser();
        
        expect(user.email, equals('test@example.com'));
        expect(user.name, equals('Test User'));
        expect(mockHttpClient.requests, hasLength(1));
        expect(mockHttpClient.requests[0].headers['Authorization'], equals('Bearer $testToken'));
      });

      test('should throw exception when no token exists', () async {
        expect(
          () => authService.getCurrentUser(),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Not authenticated: No token found.'),
          )),
        );
      });

      test('should clear token and throw exception on 401 response', () async {
        const testToken = 'invalid_token';
        
        await sharedPreferences.setString('bondai_auth_token', testToken);
        mockHttpClient.setResponse(
          '${ApiConstants.baseUrl}${ApiConstants.usersMeEndpoint}',
          http.Response('Unauthorized', 401),
        );
        
        expect(
          () => authService.getCurrentUser(),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Unauthorized: Token may be invalid or expired.'),
          )),
        );
        
        final tokenAfterError = sharedPreferences.getString('bondai_auth_token');
        expect(tokenAfterError, isNull);
      });

      test('should throw exception on non-200/401 response', () async {
        const testToken = 'test_access_token_123';
        
        await sharedPreferences.setString('bondai_auth_token', testToken);
        mockHttpClient.setResponse(
          '${ApiConstants.baseUrl}${ApiConstants.usersMeEndpoint}',
          http.Response('Server Error', 500),
        );
        
        expect(
          () => authService.getCurrentUser(),
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Failed to load user data: 500'),
          )),
        );
      });
    });

    group('authenticatedHeaders', () {
      test('should return headers with authorization when token exists', () async {
        const testToken = 'test_access_token_123';
        await sharedPreferences.setString('bondai_auth_token', testToken);
        
        final headers = await authService.authenticatedHeaders;
        
        expect(headers['Authorization'], equals('Bearer $testToken'));
        expect(headers['Content-Type'], equals('application/json'));
      });

      test('should throw exception when no token exists', () async {
        expect(
          () => authService.authenticatedHeaders,
          throwsA(isA<Exception>().having(
            (e) => e.toString(),
            'message',
            contains('Not authenticated for this request.'),
          )),
        );
      });
    });

    group('launchLoginUrl', () {
      test('should construct correct login URL', () async {
        expect(
          () => authService.launchLoginUrl(),
          throwsA(isA<Exception>()),
        );
      });
    });

    group('Constructor', () {
      test('should use provided httpClient', () {
        final customClient = MockHttpClient();
        final service = AuthService(
          httpClient: customClient,
          sharedPreferences: sharedPreferences,
        );
        
        expect(service, isA<AuthService>());
      });

      test('should use default httpClient when not provided', () {
        final service = AuthService(
          sharedPreferences: sharedPreferences,
        );
        
        expect(service, isA<AuthService>());
      });
    });

    group('Edge Cases', () {
      test('should handle malformed JSON response gracefully', () async {
        const testToken = 'test_access_token_123';
        
        await sharedPreferences.setString('bondai_auth_token', testToken);
        mockHttpClient.setResponse(
          '${ApiConstants.baseUrl}${ApiConstants.usersMeEndpoint}',
          http.Response('invalid json', 200),
        );
        
        expect(
          () => authService.getCurrentUser(),
          throwsA(isA<Exception>()),
        );
      });

      test('should handle empty response body', () async {
        const testToken = 'test_access_token_123';
        
        await sharedPreferences.setString('bondai_auth_token', testToken);
        mockHttpClient.setResponse(
          '${ApiConstants.baseUrl}${ApiConstants.usersMeEndpoint}',
          http.Response('', 200),
        );
        
        expect(
          () => authService.getCurrentUser(),
          throwsA(isA<Exception>()),
        );
      });

      test('should handle network errors', () async {
        const testToken = 'test_access_token_123';
        await sharedPreferences.setString('bondai_auth_token', testToken);
        
        expect(
          () => authService.getCurrentUser(),
          throwsA(isA<Exception>()),
        );
      });
    });
  });
}