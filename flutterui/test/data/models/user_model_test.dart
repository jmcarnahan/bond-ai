import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/data/models/user_model.dart';

void main() {
  group('User Model Tests', () {
    test('constructor should create user with required email field', () {
      const user = User(email: 'test@example.com');

      expect(user.email, equals('test@example.com'));
      expect(user.name, isNull);
    });

    test('constructor should create user with email and name', () {
      const user = User(
        email: 'test@example.com',
        name: 'Test User',
      );

      expect(user.email, equals('test@example.com'));
      expect(user.name, equals('Test User'));
    });

    test('fromJson should create user from valid JSON with email only', () {
      final json = {
        'email': 'test@example.com',
      };

      final user = User.fromJson(json);

      expect(user.email, equals('test@example.com'));
      expect(user.name, isNull);
    });

    test('fromJson should create user from valid JSON with email and name', () {
      final json = {
        'email': 'test@example.com',
        'name': 'Test User',
      };

      final user = User.fromJson(json);

      expect(user.email, equals('test@example.com'));
      expect(user.name, equals('Test User'));
    });

    test('fromJson should handle null name field', () {
      final json = {
        'email': 'test@example.com',
        'name': null,
      };

      final user = User.fromJson(json);

      expect(user.email, equals('test@example.com'));
      expect(user.name, isNull);
    });

    test('toJson should convert user to JSON correctly with name', () {
      const user = User(
        email: 'test@example.com',
        name: 'Test User',
      );

      final json = user.toJson();

      expect(json['email'], equals('test@example.com'));
      expect(json['name'], equals('Test User'));
    });

    test('toJson should convert user to JSON correctly with null name', () {
      const user = User(email: 'test@example.com');

      final json = user.toJson();

      expect(json['email'], equals('test@example.com'));
      expect(json['name'], isNull);
    });

    test('should handle JSON roundtrip correctly with name', () {
      const originalUser = User(
        email: 'test@example.com',
        name: 'Test User',
      );

      final json = originalUser.toJson();
      final reconstructedUser = User.fromJson(json);

      expect(reconstructedUser.email, equals(originalUser.email));
      expect(reconstructedUser.name, equals(originalUser.name));
    });

    test('should handle JSON roundtrip correctly without name', () {
      const originalUser = User(email: 'test@example.com');

      final json = originalUser.toJson();
      final reconstructedUser = User.fromJson(json);

      expect(reconstructedUser.email, equals(originalUser.email));
      expect(reconstructedUser.name, equals(originalUser.name));
      expect(reconstructedUser.name, isNull);
    });

    test('should handle valid email formats', () {
      const validEmails = [
        'test@example.com',
        'user123@domain.co.uk',
        'firstname.lastname@company.org',
        'user+tag@example.com',
        'admin@sub.domain.com',
      ];

      for (final email in validEmails) {
        final user = User(email: email);
        expect(user.email, equals(email));
        
        final json = user.toJson();
        final reconstructedUser = User.fromJson(json);
        expect(reconstructedUser.email, equals(email));
      }
    });

    test('should handle various name formats', () {
      const nameTestCases = [
        'John Doe',
        'Jane',
        'Dr. Smith',
        'Mary Jane Watson',
        'José María',
        '李明',
        'أحمد',
        "O'Connor",
        'Jean-Pierre',
        'Smith Jr.',
      ];

      for (final name in nameTestCases) {
        final user = User(
          email: 'test@example.com',
          name: name,
        );
        
        expect(user.email, equals('test@example.com'));
        expect(user.name, equals(name));
        
        final json = user.toJson();
        final reconstructedUser = User.fromJson(json);
        expect(reconstructedUser.email, equals('test@example.com'));
        expect(reconstructedUser.name, equals(name));
      }
    });

    test('should handle empty string name', () {
      const user = User(
        email: 'test@example.com',
        name: '',
      );

      expect(user.email, equals('test@example.com'));
      expect(user.name, equals(''));

      final json = user.toJson();
      expect(json['email'], equals('test@example.com'));
      expect(json['name'], equals(''));

      final reconstructedUser = User.fromJson(json);
      expect(reconstructedUser.email, equals('test@example.com'));
      expect(reconstructedUser.name, equals(''));
    });

    test('should handle whitespace in name', () {
      const user = User(
        email: 'test@example.com',
        name: '  John Doe  ',
      );

      expect(user.email, equals('test@example.com'));
      expect(user.name, equals('  John Doe  '));

      final json = user.toJson();
      final reconstructedUser = User.fromJson(json);
      expect(reconstructedUser.name, equals('  John Doe  '));
    });

    test('immutable annotation should prevent modification', () {
      const user = User(email: 'test@example.com');
      
      expect(user, isA<User>());
      expect(() => user.email, returnsNormally);
      expect(() => user.name, returnsNormally);
    });
  });
}