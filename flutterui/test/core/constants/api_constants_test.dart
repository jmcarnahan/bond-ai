import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/core/constants/api_constants.dart';

void main() {
  group('ApiConstants Tests', () {
    test('should have correct base URL', () {
      expect(ApiConstants.baseUrl, equals('http://localhost:8000'));
    });

    test('should have correct endpoint paths', () {
      expect(ApiConstants.loginEndpoint, equals('/login'));
      expect(ApiConstants.googleCallbackEndpoint, equals('/auth/google/callback'));
      expect(ApiConstants.usersMeEndpoint, equals('/users/me'));
      expect(ApiConstants.agentsEndpoint, equals('/agents'));
      expect(ApiConstants.threadsEndpoint, equals('/threads'));
      expect(ApiConstants.chatEndpoint, equals('/chat'));
      expect(ApiConstants.filesEndpoint, equals('/files'));
    });

    test('endpoints should start with forward slash', () {
      expect(ApiConstants.loginEndpoint, startsWith('/'));
      expect(ApiConstants.googleCallbackEndpoint, startsWith('/'));
      expect(ApiConstants.usersMeEndpoint, startsWith('/'));
      expect(ApiConstants.agentsEndpoint, startsWith('/'));
      expect(ApiConstants.threadsEndpoint, startsWith('/'));
      expect(ApiConstants.chatEndpoint, startsWith('/'));
      expect(ApiConstants.filesEndpoint, startsWith('/'));
    });

    test('should construct full URLs correctly', () {
      expect('${ApiConstants.baseUrl}${ApiConstants.loginEndpoint}', 
             equals('http://localhost:8000/login'));
      expect('${ApiConstants.baseUrl}${ApiConstants.agentsEndpoint}', 
             equals('http://localhost:8000/agents'));
      expect('${ApiConstants.baseUrl}${ApiConstants.threadsEndpoint}', 
             equals('http://localhost:8000/threads'));
      expect('${ApiConstants.baseUrl}${ApiConstants.chatEndpoint}', 
             equals('http://localhost:8000/chat'));
    });

    test('base URL should not end with slash', () {
      expect(ApiConstants.baseUrl, isNot(endsWith('/')));
    });

    test('endpoints should not be empty', () {
      expect(ApiConstants.loginEndpoint, isNotEmpty);
      expect(ApiConstants.googleCallbackEndpoint, isNotEmpty);
      expect(ApiConstants.usersMeEndpoint, isNotEmpty);
      expect(ApiConstants.agentsEndpoint, isNotEmpty);
      expect(ApiConstants.threadsEndpoint, isNotEmpty);
      expect(ApiConstants.chatEndpoint, isNotEmpty);
      expect(ApiConstants.filesEndpoint, isNotEmpty);
    });
  });
}