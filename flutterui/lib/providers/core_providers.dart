import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutterui/core/theme/app_theme.dart';
import 'package:flutterui/core/theme/generated_theme.dart';

/// Provider for SharedPreferences instance
/// This must be overridden with the actual instance during app initialization
final sharedPreferencesProvider = Provider<SharedPreferences>((ref) {
  throw UnimplementedError('SharedPreferences not initialized');
});

/// Provider for the application theme
/// Returns the generated theme configuration
final appThemeProvider = Provider<AppTheme>((ref) {
  return AppGeneratedTheme();
});
