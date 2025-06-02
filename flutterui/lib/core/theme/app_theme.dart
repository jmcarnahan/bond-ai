import 'package:flutter/material.dart';

@immutable
class CustomColors extends ThemeExtension<CustomColors> {
  const CustomColors({
    required this.brandingSurface,
  });

  final Color brandingSurface;

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
      brandingSurface: Color.lerp(brandingSurface, other.brandingSurface, t) ?? brandingSurface,
    );
  }

  static CustomColors? of(BuildContext context) {
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
