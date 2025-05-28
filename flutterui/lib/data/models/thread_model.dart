import 'package:flutter/foundation.dart' show immutable;

@immutable
class Thread {
  final String id;
  final String name;
  final String? description;
  // final DateTime? createdAt; // Optional: if you add timestamps
  // final DateTime? updatedAt; // Optional: if you add timestamps

  const Thread({
    required this.id,
    required this.name,
    this.description,
    // this.createdAt,
    // this.updatedAt,
  });

  factory Thread.fromJson(Map<String, dynamic> json) {
    return Thread(
      id: json['id'] as String,
      name: json['name'] as String,
      description: json['description'] as String?,
      // createdAt: json['created_at'] != null
      //     ? DateTime.parse(json['created_at'] as String)
      //     : null,
      // updatedAt: json['updated_at'] != null
      //     ? DateTime.parse(json['updated_at'] as String)
      //     : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'description': description,
      // 'created_at': createdAt?.toIso8601String(),
      // 'updated_at': updatedAt?.toIso8601String(),
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
