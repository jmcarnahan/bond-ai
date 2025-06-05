import 'package:flutter/foundation.dart' show immutable;

@immutable
class Thread {
  final String id;
  final String name;
  final String? description;

  const Thread({
    required this.id,
    required this.name,
    this.description,
  });

  factory Thread.fromJson(Map<String, dynamic> json) {
    return Thread(
      id: json['id'] as String,
      name: json['name'] as String,
      description: json['description'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'description': description,
    };
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;

    return other is Thread &&
        other.id == id &&
        other.name == name &&
        other.description == description;
  }

  @override
  int get hashCode => id.hashCode ^ name.hashCode ^ description.hashCode;
}
