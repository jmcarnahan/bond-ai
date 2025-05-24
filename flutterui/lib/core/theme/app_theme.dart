import 'package:flutter/material.dart';

/// Abstract base class for application themes.
///
/// This class provides a common structure for defining themes,
/// allowing for easy swapping of different theme implementations
/// throughout the application.
abstract class AppTheme {
  /// Gets the [ThemeData] for the current theme.
  ThemeData get themeData;

  /// Gets the name of the application.
  String get name;

  /// Gets the logo widget of the application.
  Widget get logo;
}
