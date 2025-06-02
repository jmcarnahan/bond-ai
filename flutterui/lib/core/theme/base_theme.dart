import 'package:flutter/material.dart';
import 'package:flutterui/core/theme/app_theme.dart';
class BaseTheme implements AppTheme {
  const BaseTheme();

  static const Color baseDarkBrandingSurface = Color(0xFF424242);
  static const Color baseCyan = Color(0xFF00BCD4);
  static const Color baseDarkGrey = Color(0xFF616161);
  static const Color baseLightGrey = Color(0xFFF5F5F5);
  static const Color baseTextPrimary = Color(0xFF212121);
  static const Color baseTextSecondary = Color(0xFF757575);

  @override
  String get name => 'Bond AI';

  @override
  String get brandingMessage => 'Your Enterprise Space For Managing AI Agents';

  @override
  String get logo => 'assets/bond_logo.png';

  @override
  String get logoIcon => 'assets/bond_logo_icon.png';

  @override
  ThemeData get themeData {
    return ThemeData(
      brightness: Brightness.light,
      primaryColor: Color(0xFF1A2E5C),
      colorScheme: ColorScheme(
        brightness: Brightness.light,
        primary: Color(0xFF1A2E5C),
        onPrimary: Colors.white,
        secondary: Color(0xFF8A96A3),
        onSecondary: Colors.white,
        error: Color(0xFFB00020),
        onError: Colors.white,
        surface: Color(0xFFF5F6F8),
        onSurface: Color(0xFF1A2E5C),
      ),
      scaffoldBackgroundColor: Color(0xFFF5F6F8),
      fontFamily: 'Roboto',

      textTheme: TextTheme(
        displayLarge: TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: Color(0xFF1A2E5C)),
        displayMedium: TextStyle(fontSize: 28, fontWeight: FontWeight.w600, color: Color(0xFF1A2E5C)),
        displaySmall: TextStyle(fontSize: 24, fontWeight: FontWeight.w500, color: Color(0xFF1A2E5C)),
        headlineMedium: TextStyle(fontSize: 20, fontWeight: FontWeight.w600, color: Color(0xFF1A2E5C)),
        headlineSmall: TextStyle(fontSize: 18, fontWeight: FontWeight.w500, color: Color(0xFF1A2E5C)),
        bodyLarge: TextStyle(fontSize: 16, color: Color(0xFF1A2E5C)),
        bodyMedium: TextStyle(fontSize: 14, color: Color(0xFF1A2E5C)),
        bodySmall: TextStyle(fontSize: 12, color: Color(0xFF8A96A3)),
        labelLarge: TextStyle(fontSize: 14, fontWeight: FontWeight.w500, color: Color(0xFF1A2E5C)),
        labelSmall: TextStyle(fontSize: 12, color: Color(0xFF8A96A3)),
      ),

      appBarTheme: AppBarTheme(
        backgroundColor: Color(0xFF1A2E5C),
        foregroundColor: Colors.white,
        elevation: 2,
        centerTitle: true,
        titleTextStyle: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white),
      ),

      cardTheme: CardThemeData(
        color: Colors.white,
        elevation: 4,
        margin: EdgeInsets.all(12),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(12))),
      ),

      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ButtonStyle(
          foregroundColor: WidgetStatePropertyAll<Color>(Colors.white),
          backgroundColor: WidgetStatePropertyAll<Color>(Color(0xFF1A2E5C)),
          padding: WidgetStatePropertyAll<EdgeInsets>(EdgeInsets.symmetric(horizontal: 24, vertical: 12)),
          shape: WidgetStatePropertyAll<RoundedRectangleBorder>(
            RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(8))),
          ),
        ),
      ),

      textButtonTheme: TextButtonThemeData(
        style: ButtonStyle(
          foregroundColor: WidgetStatePropertyAll<Color>(Color(0xFF1A2E5C)),
          textStyle: WidgetStatePropertyAll<TextStyle>(
            TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
          ),
        ),
      ),

      outlinedButtonTheme: OutlinedButtonThemeData(
        style: ButtonStyle(
          foregroundColor: WidgetStatePropertyAll<Color>(Color(0xFF1A2E5C)),
          side: WidgetStatePropertyAll<BorderSide>(BorderSide(color: Color(0xFF1A2E5C))),
          shape: WidgetStatePropertyAll<RoundedRectangleBorder>(
            RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(8))),
          ),
        ),
      ),

      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(8))),
        focusedBorder: OutlineInputBorder(
          borderSide: BorderSide(color: Color(0xFF1A2E5C), width: 2),
          borderRadius: BorderRadius.all(Radius.circular(8)),
        ),
        labelStyle: TextStyle(color: Color(0xFF1A2E5C)),
      ),

      dialogTheme: DialogThemeData(
        backgroundColor: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(12))),
        titleTextStyle: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Color(0xFF1A2E5C)),
        contentTextStyle: TextStyle(fontSize: 16, color: Color(0xFF1A2E5C)),
      ),

      snackBarTheme: SnackBarThemeData(
        backgroundColor: Color(0xFF1A2E5C),
        contentTextStyle: TextStyle(color: Colors.white),
        behavior: SnackBarBehavior.floating,
      ),

      iconTheme: IconThemeData(
        color: Color(0xFF1A2E5C),
      ),

      dividerTheme: DividerThemeData(
        color: Color(0xFF8A96A3),
        thickness: 1,
        space: 32,
      ),

      useMaterial3: true,
    );
  }
}
