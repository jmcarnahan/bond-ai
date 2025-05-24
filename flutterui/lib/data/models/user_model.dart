import 'package:flutter/foundation.dart' show immutable;

@immutable
class User {
  final String email;
  final String? name; // Name is optional as per the Pydantic model in backend

  const User({required this.email, this.name});

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      email: json['email'] as String,
      name: json['name'] as String?, // Handle nullable name
    );
  }

  Map<String, dynamic> toJson() {
    return {'email': email, 'name': name};
  }
}
