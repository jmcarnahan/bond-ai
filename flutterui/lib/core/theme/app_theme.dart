import 'package:flutter/material.dart';

// Define a custom ThemeExtension for additional colors
@immutable
class CustomColors extends ThemeExtension<CustomColors> {
  const CustomColors({
    required this.brandingSurface,
  });

  final Color brandingSurface; // Made non-nullable

  @override
  CustomColors copyWith({Color? brandingSurface}) {
    return CustomColors(
      brandingSurface: brandingSurface ?? this.brandingSurface,
    );
  }

  @override
  CustomColors lerp(ThemeExtension<CustomColors>? other, double t) {
    if (other is! CustomColors) {
      return this;
    }
    return CustomColors(
      brandingSurface: Color.lerp(brandingSurface, other.brandingSurface, t) ?? this.brandingSurface, // Ensure non-null result
    );
  }

  // Optional: A helper to easily access from Theme.of(context)
  static CustomColors? of(BuildContext context) { // Still can be null if theme doesn't provide it
    return Theme.of(context).extension<CustomColors>();
  }
}

abstract class AppTheme {
  ThemeData get themeData;
  String get name;
  String get brandingMessage;
  String get logo;
  String get logoIcon;
}
