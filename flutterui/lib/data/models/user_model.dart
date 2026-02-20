import 'package:flutter/foundation.dart' show immutable;

@immutable
class User {
  final String email;
  final String? name;
  final String userId;
  final String provider;
  final bool isAdmin;

  const User({
    required this.email,
    this.name,
    required this.userId,
    required this.provider,
    this.isAdmin = false,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      email: json['email'] as String,
      name: json['name'] as String?,
      userId: json['user_id'] as String,
      provider: json['provider'] as String,
      isAdmin: json['is_admin'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'email': email,
      'name': name,
      'user_id': userId,
      'provider': provider,
      'is_admin': isAdmin,
    };
  }
}
