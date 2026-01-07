import 'package:flutter/foundation.dart' show immutable;

@immutable
class AvailableGroup {
  final String id;
  final String name;
  final String? description;
  final bool isOwner;

  const AvailableGroup({
    required this.id,
    required this.name,
    this.description,
    required this.isOwner,
  });

  factory AvailableGroup.fromJson(Map<String, dynamic> json) {
    return AvailableGroup(
      id: json['id'] as String,
      name: json['name'] as String,
      description: json['description'] as String?,
      isOwner: json['is_owner'] as bool,
    );
  }
}

@immutable
class Group {
  final String id;
  final String name;
  final String? description;
  final String ownerUserId;
  final DateTime createdAt;
  final DateTime updatedAt;

  const Group({
    required this.id,
    required this.name,
    this.description,
    required this.ownerUserId,
    required this.createdAt,
    required this.updatedAt,
  });

  factory Group.fromJson(Map<String, dynamic> json) {
    return Group(
      id: json['id'] as String,
      name: json['name'] as String,
      description: json['description'] as String?,
      ownerUserId: json['owner_user_id'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'description': description,
      'owner_user_id': ownerUserId,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
    };
  }
}

@immutable
class GroupMember {
  final String userId;
  final String email;
  final String? name;

  const GroupMember({
    required this.userId,
    required this.email,
    this.name,
  });

  factory GroupMember.fromJson(Map<String, dynamic> json) {
    return GroupMember(
      userId: json['user_id'] as String,
      email: json['email'] as String,
      name: json['name'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'user_id': userId,
      'email': email,
      'name': name,
    };
  }
}

@immutable
class GroupWithMembers extends Group {
  final List<GroupMember> members;

  const GroupWithMembers({
    required super.id,
    required super.name,
    super.description,
    required super.ownerUserId,
    required super.createdAt,
    required super.updatedAt,
    required this.members,
  });

  factory GroupWithMembers.fromJson(Map<String, dynamic> json) {
    return GroupWithMembers(
      id: json['id'] as String,
      name: json['name'] as String,
      description: json['description'] as String?,
      ownerUserId: json['owner_user_id'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
      members: (json['members'] as List<dynamic>?)
              ?.map((m) => GroupMember.fromJson(m as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }

  @override
  Map<String, dynamic> toJson() {
    final json = super.toJson();
    json['members'] = members.map((m) => m.toJson()).toList();
    return json;
  }
}
