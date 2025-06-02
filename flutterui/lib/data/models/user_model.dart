import 'package:flutter/foundation.dart' show immutable;

@immutable
class User {
  final String email;
  final String? name;

  const User({required this.email, this.name});

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      email: json['email'] as String,
      name: json['name'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {'email': email, 'name': name};
  }
}
