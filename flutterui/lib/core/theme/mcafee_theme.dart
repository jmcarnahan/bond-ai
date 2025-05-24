import 'package:flutter/material.dart';
import 'package:flutterui/core/theme/app_theme.dart';

// Define a custom ThemeExtension for additional colors
@immutable
class CustomColors extends ThemeExtension<CustomColors> {
  const CustomColors({
    required this.brandingSurface,
  });

  final Color? brandingSurface;

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
      brandingSurface: Color.lerp(brandingSurface, other.brandingSurface, t),
    );
  }

  // Optional: A helper to easily access from Theme.of(context)
  static CustomColors? of(BuildContext context) {
    return Theme.of(context).extension<CustomColors>();
  }
}

/// McAfee specific theme implementation.
class McAfeeTheme implements AppTheme {
  static const Color mcafeeDarkBrandingSurface = Color(0xFF303030); // Colors.grey[850]

  @override
  String get name => 'McAfee';

  @override
  String get brandingMessage => 'Protecting Your Digital Life';

  @override
  String get logo => 'assets/mcafee_logo.png';

  @override
  String get logoIcon => 'assets/mcafee_shield_logo.png';

  @override
  ThemeData get themeData {
    return ThemeData(
      brightness: Brightness.light,
      primaryColor: Color(0xFFFF1C1C), // McAfee's red

      colorScheme: ColorScheme(
        brightness: Brightness.light,
        primary: Color(0xFFFF1C1C), // Accent red
        onPrimary: Colors.white,
        secondary: Color(0xFF0C63E4), // Blue accent for contrast
        onSecondary: Colors.white,
        error: Color(0xFFAF0707), // Deep red for error
        onError: Colors.white,
        background: Color(0xFFFFFFFF), // Body background
        onBackground: Color(0xFF333333), // Very close to #303030, consider using this or a variant
        surface: Color(0xFFF2F4F7), // Light grey surface
        onSurface: Color(0xFF101828),
      ),
      extensions: const <ThemeExtension<dynamic>>[
        CustomColors(brandingSurface: mcafeeDarkBrandingSurface),
      ],
      scaffoldBackgroundColor: Color(0xFFFFFFFF),
      fontFamily: 'Poppins',

      textTheme: TextTheme(
        displayLarge: TextStyle(fontSize: 32, fontWeight: FontWeight.w600, color: Color(0xFF53565A)), // H2
        displayMedium: TextStyle(fontSize: 28.8, fontWeight: FontWeight.w600, color: Color(0xFF333333)), // H1
        displaySmall: TextStyle(fontSize: 28, fontWeight: FontWeight.w600, color: Color(0xFF000000)), // H3
        headlineMedium: TextStyle(fontSize: 20, fontWeight: FontWeight.w600, color: Color(0xFF383434)), // custom header
        headlineSmall: TextStyle(fontSize: 18, fontWeight: FontWeight.w500, color: Color(0xFF475467)),
        bodyLarge: TextStyle(fontSize: 16.2, color: Color(0xFF667085)), // paragraph
        bodyMedium: TextStyle(fontSize: 14, color: Color(0xFF6E6E6E)),
        bodySmall: TextStyle(fontSize: 12, color: Color(0xFF959595)),
        labelLarge: TextStyle(fontSize: 14, fontWeight: FontWeight.w500, color: Color(0xFFFF1C1C)), // links
        labelSmall: TextStyle(fontSize: 12, color: Color(0xFFB2B2B2)),
      ),

      appBarTheme: AppBarTheme(
        backgroundColor: Colors.white,
        foregroundColor: Color(0xFF333333),
        elevation: 0.5,
        centerTitle: true,
        titleTextStyle: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Color(0xFF333333)),
      ),

      cardTheme: CardThemeData(
        color: Color(0xFFFFFFFF),
        elevation: 1,
        margin: EdgeInsets.all(12),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),

      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ButtonStyle(
          foregroundColor: WidgetStateProperty.all<Color>(Colors.white),
          backgroundColor: WidgetStateProperty.all<Color>(Color(0xFFFF1C1C)),
          padding: WidgetStateProperty.all<EdgeInsets>(EdgeInsets.symmetric(horizontal: 20, vertical: 12)),
          shape: WidgetStateProperty.all<RoundedRectangleBorder>(
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
          ),
        ),
      ),

      textButtonTheme: TextButtonThemeData(
        style: ButtonStyle(
          foregroundColor: WidgetStateProperty.all<Color>(Color(0xFFFF1C1C)),
          textStyle: WidgetStateProperty.all<TextStyle>(
            TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
          ),
        ),
      ),

      outlinedButtonTheme: OutlinedButtonThemeData(
        style: ButtonStyle(
          foregroundColor: WidgetStateProperty.all<Color>(Color(0xFF0C63E4)),
          side: WidgetStateProperty.all<BorderSide>(
            BorderSide(color: Color(0xFF0C63E4)),
          ),
          shape: WidgetStateProperty.all<RoundedRectangleBorder>(
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
          ),
        ),
      ),

      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Color(0xFFFFFFFF),
        border: OutlineInputBorder(
          borderSide: BorderSide(color: Color(0xFFDBDBDB), width: 0.5),
          borderRadius: BorderRadius.circular(7.3),
        ),
        focusedBorder: OutlineInputBorder(
          borderSide: BorderSide(color: Color(0xFF0C63E4), width: 1.5),
          borderRadius: BorderRadius.circular(7.3),
        ),
        labelStyle: TextStyle(color: Color(0xFF53565A)),
      ),

      dialogTheme: DialogThemeData(
        backgroundColor: Color(0xFFFFFFFF),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
        ),
        titleTextStyle: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Color(0xFF333333)),
        contentTextStyle: TextStyle(fontSize: 16, color: Color(0xFF667085)),
      ),

      snackBarTheme: SnackBarThemeData(
        backgroundColor: Color(0xFFAF0707),
        contentTextStyle: TextStyle(color: Colors.white),
        behavior: SnackBarBehavior.floating,
      ),

      iconTheme: IconThemeData(
        color: Color(0xFF0C63E4),
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
