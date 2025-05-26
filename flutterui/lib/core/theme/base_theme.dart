import 'package:flutter/material.dart';
import 'package:flutterui/core/theme/app_theme.dart'; // Imports AppTheme and CustomColors

/// Base theme implementation.
class BaseTheme implements AppTheme {
  static const Color baseDarkBrandingSurface = Color(0xFF424242); // Darker Grey (Colors.grey[800])
  static const Color baseCyan = Color(0xFF00BCD4); // Cyan
  static const Color baseDarkGrey = Color(0xFF616161); // Dark Grey (Colors.grey[700])
  static const Color baseLightGrey = Color(0xFFF5F5F5); // Light Grey (Colors.grey[100])
  static const Color baseTextPrimary = Color(0xFF212121); // Nearly Black
  static const Color baseTextSecondary = Color(0xFF757575); // Grey

  @override
  String get name => 'BaseTheme';

  @override
  String get brandingMessage => 'Powered by BondAI';

  @override
  String get logo => 'assets/bond_logo_logo.png'; // Placeholder, user might need to add this

  @override
  String get logoIcon => 'assets/bond_logo_icon.png'; // Placeholder, user might need to add this

  @override
  ThemeData get themeData {
    return ThemeData(
      brightness: Brightness.light,
      primaryColor: baseCyan,

      colorScheme: ColorScheme(
        brightness: Brightness.light,
        primary: baseCyan,
        onPrimary: Colors.white,
        secondary: baseDarkGrey, 
        onSecondary: Colors.white,
        error: Color(0xFFD32F2F), // Standard Red for errors
        onError: Colors.white,
        background: Colors.white, // White background
        onBackground: baseTextPrimary,
        surface: baseLightGrey, // Light grey surface
        onSurface: baseTextPrimary,
      ),
      extensions: const <ThemeExtension<dynamic>>[
        CustomColors(brandingSurface: baseDarkBrandingSurface),
      ],
      scaffoldBackgroundColor: Colors.white,
      fontFamily: 'Poppins', // Keeping Poppins for now, can be changed

      textTheme: TextTheme(
        displayLarge: TextStyle(fontSize: 32, fontWeight: FontWeight.w600, color: baseTextPrimary),
        displayMedium: TextStyle(fontSize: 28.8, fontWeight: FontWeight.w600, color: baseTextPrimary),
        displaySmall: TextStyle(fontSize: 28, fontWeight: FontWeight.w600, color: baseTextPrimary),
        headlineMedium: TextStyle(fontSize: 20, fontWeight: FontWeight.w600, color: baseTextPrimary),
        headlineSmall: TextStyle(fontSize: 18, fontWeight: FontWeight.w500, color: baseTextSecondary),
        bodyLarge: TextStyle(fontSize: 16.2, color: baseTextSecondary),
        bodyMedium: TextStyle(fontSize: 14, color: baseTextSecondary),
        bodySmall: TextStyle(fontSize: 12, color: baseTextSecondary),
        labelLarge: TextStyle(fontSize: 14, fontWeight: FontWeight.w500, color: baseCyan), // Links
        labelSmall: TextStyle(fontSize: 12, color: baseTextSecondary),
      ),

      appBarTheme: AppBarTheme(
        backgroundColor: Colors.white,
        foregroundColor: baseTextPrimary,
        elevation: 0.5,
        centerTitle: true,
        titleTextStyle: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: baseTextPrimary),
      ),

      cardTheme: CardThemeData(
        color: Colors.white,
        elevation: 1,
        margin: EdgeInsets.all(12),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),

      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ButtonStyle(
          foregroundColor: WidgetStateProperty.all<Color>(Colors.white),
          backgroundColor: WidgetStateProperty.all<Color>(baseCyan),
          padding: WidgetStateProperty.all<EdgeInsets>(EdgeInsets.symmetric(horizontal: 20, vertical: 12)),
          shape: WidgetStateProperty.all<RoundedRectangleBorder>(
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
          ),
        ),
      ),

      textButtonTheme: TextButtonThemeData(
        style: ButtonStyle(
          foregroundColor: WidgetStateProperty.all<Color>(baseCyan),
          textStyle: WidgetStateProperty.all<TextStyle>(
            TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
          ),
        ),
      ),

      outlinedButtonTheme: OutlinedButtonThemeData(
        style: ButtonStyle(
          foregroundColor: WidgetStateProperty.all<Color>(baseCyan),
          side: WidgetStateProperty.all<BorderSide>(
            BorderSide(color: baseCyan),
          ),
          shape: WidgetStateProperty.all<RoundedRectangleBorder>(
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
          ),
        ),
      ),

      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
          borderSide: BorderSide(color: Color(0xFFDBDBDB), width: 0.5),
          borderRadius: BorderRadius.circular(7.3),
        ),
        focusedBorder: OutlineInputBorder(
          borderSide: BorderSide(color: baseCyan, width: 1.5),
          borderRadius: BorderRadius.circular(7.3),
        ),
        labelStyle: TextStyle(color: baseTextSecondary),
      ),

      dialogTheme: DialogThemeData(
        backgroundColor: Colors.white,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
        ),
        titleTextStyle: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: baseTextPrimary),
        contentTextStyle: TextStyle(fontSize: 16, color: baseTextSecondary),
      ),

      snackBarTheme: SnackBarThemeData(
        backgroundColor: Color(0xFFD32F2F), // Standard Red
        contentTextStyle: TextStyle(color: Colors.white),
        behavior: SnackBarBehavior.floating,
      ),

      iconTheme: IconThemeData(
        color: baseCyan,
      ),

      dividerTheme: DividerThemeData(
        color: Color(0xFFDBDBDB),
        thickness: 1,
        space: 16,
      ),

      useMaterial3: true,
    );
  }
}
