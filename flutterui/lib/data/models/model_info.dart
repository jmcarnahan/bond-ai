class ModelInfo {
  final String name;
  final String description;
  final bool isDefault;

  const ModelInfo({
    required this.name,
    required this.description,
    required this.isDefault,
  });

  factory ModelInfo.fromJson(Map<String, dynamic> json) {
    return ModelInfo(
      name: json['name'] as String,
      description: json['description'] as String,
      isDefault: json['is_default'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'name': name,
      'description': description,
      'is_default': isDefault,
    };
  }

  @override
  String toString() => 'ModelInfo(name: $name, isDefault: $isDefault)';
}
