import 'package:flutter/foundation.dart' show immutable;

@immutable
class FolderModel {
  final String id;
  final String name;
  final int agentCount;
  final int sortOrder;

  const FolderModel({
    required this.id,
    required this.name,
    this.agentCount = 0,
    this.sortOrder = 0,
  });

  factory FolderModel.fromJson(Map<String, dynamic> json) {
    return FolderModel(
      id: json['id'] as String,
      name: json['name'] as String,
      agentCount: json['agent_count'] as int? ?? 0,
      sortOrder: json['sort_order'] as int? ?? 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'agent_count': agentCount,
      'sort_order': sortOrder,
    };
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is FolderModel &&
        other.id == id &&
        other.name == name &&
        other.agentCount == agentCount &&
        other.sortOrder == sortOrder;
  }

  @override
  int get hashCode =>
      id.hashCode ^ name.hashCode ^ agentCount.hashCode ^ sortOrder.hashCode;
}
