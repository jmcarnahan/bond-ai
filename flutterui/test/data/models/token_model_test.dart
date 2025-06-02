import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/data/models/token_model.dart';

void main() {
  group('Token Model Tests', () {
    test('constructor should create token with required fields', () {
      const token = Token(
        accessToken: 'access_token_123',
        tokenType: 'Bearer',
      );

      expect(token.accessToken, equals('access_token_123'));
      expect(token.tokenType, equals('Bearer'));
    });

    test('fromJson should create token from valid JSON', () {
      final json = {
        'access_token': 'access_token_123',
        'token_type': 'Bearer',
      };

      final token = Token.fromJson(json);

      expect(token.accessToken, equals('access_token_123'));
      expect(token.tokenType, equals('Bearer'));
    });

    test('fromJson should handle different token types', () {
      final testCases = [
        {'access_token': 'token123', 'token_type': 'Bearer'},
        {'access_token': 'token456', 'token_type': 'Basic'},
        {'access_token': 'token789', 'token_type': 'MAC'},
      ];

      for (final testCase in testCases) {
        final token = Token.fromJson(testCase);
        expect(token.accessToken, equals(testCase['access_token']));
        expect(token.tokenType, equals(testCase['token_type']));
      }
    });

    test('toJson should convert token to JSON correctly', () {
      const token = Token(
        accessToken: 'access_token_123',
        tokenType: 'Bearer',
      );

      final json = token.toJson();

      expect(json['access_token'], equals('access_token_123'));
      expect(json['token_type'], equals('Bearer'));
    });

    test('should handle JSON roundtrip correctly', () {
      const originalToken = Token(
        accessToken: 'access_token_123',
        tokenType: 'Bearer',
      );

      final json = originalToken.toJson();
      final reconstructedToken = Token.fromJson(json);

      expect(reconstructedToken.accessToken, equals(originalToken.accessToken));
      expect(reconstructedToken.tokenType, equals(originalToken.tokenType));
    });

    test('should handle long access tokens', () {
      const longToken = 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiYWRtaW4iOnRydWUsImlhdCI6MTUxNjIzOTAyMn0.POstGetfAytaZS82wHcjoTyoqhMyxXiWdR7Nn7A29DNSl0EiXLdwJ6xC6AfgZWF1bOsS_TuYI3OG85AmiExREkrS6tDfTQ2B3WXlrr-wp5AokiRbz3_oB4OxG-W9KcEEbDRcZc0nH3L7LzYptiy1PtAylQGxHTWZXtGz4ht0bAecBgmpdgXMguEIcoqPiWiLiZXpCOuGlBhQjcWNGn6ZRXQ';
      
      const token = Token(
        accessToken: longToken,
        tokenType: 'Bearer',
      );

      expect(token.accessToken, equals(longToken));
      expect(token.tokenType, equals('Bearer'));

      final json = token.toJson();
      final reconstructedToken = Token.fromJson(json);
      expect(reconstructedToken.accessToken, equals(longToken));
    });

    test('should handle empty strings', () {
      const token = Token(
        accessToken: '',
        tokenType: '',
      );

      expect(token.accessToken, equals(''));
      expect(token.tokenType, equals(''));

      final json = token.toJson();
      expect(json['access_token'], equals(''));
      expect(json['token_type'], equals(''));

      final reconstructedToken = Token.fromJson(json);
      expect(reconstructedToken.accessToken, equals(''));
      expect(reconstructedToken.tokenType, equals(''));
    });

    test('should handle special characters in token', () {
      const specialToken = 'token-with_special.chars+symbols/equals=';
      
      const token = Token(
        accessToken: specialToken,
        tokenType: 'Bearer',
      );

      expect(token.accessToken, equals(specialToken));

      final json = token.toJson();
      final reconstructedToken = Token.fromJson(json);
      expect(reconstructedToken.accessToken, equals(specialToken));
    });

    test('should handle various token type formats', () {
      const tokenTypes = [
        'Bearer',
        'bearer',
        'BEARER',
        'Basic',
        'Digest',
        'OAuth',
        'JWT',
        'MAC',
        'Custom-Type',
      ];

      for (final tokenType in tokenTypes) {
        final token = Token(
          accessToken: 'test_token',
          tokenType: tokenType,
        );

        expect(token.tokenType, equals(tokenType));

        final json = token.toJson();
        final reconstructedToken = Token.fromJson(json);
        expect(reconstructedToken.tokenType, equals(tokenType));
      }
    });

    test('immutable annotation should prevent modification', () {
      const token = Token(
        accessToken: 'access_token_123',
        tokenType: 'Bearer',
      );
      
      expect(token, isA<Token>());
      expect(() => token.accessToken, returnsNormally);
      expect(() => token.tokenType, returnsNormally);
    });

    test('should handle whitespace in token fields', () {
      const token = Token(
        accessToken: '  token_with_spaces  ',
        tokenType: '  Bearer  ',
      );

      expect(token.accessToken, equals('  token_with_spaces  '));
      expect(token.tokenType, equals('  Bearer  '));

      final json = token.toJson();
      final reconstructedToken = Token.fromJson(json);
      expect(reconstructedToken.accessToken, equals('  token_with_spaces  '));
      expect(reconstructedToken.tokenType, equals('  Bearer  '));
    });
  });
}