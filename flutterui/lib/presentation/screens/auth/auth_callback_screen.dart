import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/providers/auth_provider.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:web/web.dart' as web if (dart.library.io) 'dart:io';
import '../../../core/utils/logger.dart';

class AuthCallbackScreen extends ConsumerStatefulWidget {
  const AuthCallbackScreen({super.key});

  @override
  ConsumerState<AuthCallbackScreen> createState() => _AuthCallbackScreenState();
}

class _AuthCallbackScreenState extends ConsumerState<AuthCallbackScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _handleAuthCallback();
    });
  }

  void _handleAuthCallback() async {
    // Made async
    logger.i("[AuthCallbackScreen] _handleAuthCallback triggered.");
    if (kIsWeb) {
      // Use kIsWeb for a more robust check
      logger.i("[AuthCallbackScreen] Running on web.");
      final String fullUrl = web.window.location.href;
      logger.i("[AuthCallbackScreen] Full URL: $fullUrl");

      final Uri? currentUri = Uri.tryParse(fullUrl);
      if (currentUri == null) {
        logger.i(
          "[AuthCallbackScreen] Could not parse URI. Navigating to /login.",
        );
        if (mounted) {
          Navigator.of(
            context,
          ).pushNamedAndRemoveUntil('/login', (route) => false);
        }
        return;
      }
      logger.i("[AuthCallbackScreen] Parsed URI: $currentUri");
      logger.i("[AuthCallbackScreen] URI Fragment: ${currentUri.fragment}");

      String? token;
      if (currentUri.fragment.isNotEmpty) {
        final Uri fragmentUri = Uri.parse(
          'dummy://dummy${currentUri.fragment.startsWith('/') ? currentUri.fragment : '/${currentUri.fragment}'}',
        );
        logger.i("[AuthCallbackScreen] Parsed Fragment URI: $fragmentUri");
        if (fragmentUri.pathSegments.contains('auth-callback') &&
            fragmentUri.queryParameters.containsKey('token')) {
          token = fragmentUri.queryParameters['token'];
        }
      }

      if (token == null && currentUri.queryParameters.containsKey('token')) {
        logger.i(
          "[AuthCallbackScreen] Token found in main query parameters (not fragment).",
        );
        token = currentUri.queryParameters['token'];
      }
      logger.i("[AuthCallbackScreen] Extracted Token: $token");

      if (token != null && token.isNotEmpty) {
        logger.i(
          "[AuthCallbackScreen] Valid token found. Calling loginWithToken...",
        );
        final bool loginSuccess = await ref
            .read(authNotifierProvider.notifier)
            .loginWithToken(token);

        logger.i(
          "[AuthCallbackScreen] loginWithToken returned: $loginSuccess, mounted: $mounted",
        ); // ADDED THIS LOG

        if (!mounted) {
          logger.i(
            "[AuthCallbackScreen] Widget unmounted after loginWithToken. No navigation.",
          );
          return;
        }

        if (loginSuccess) {
          logger.i(
            "[AuthCallbackScreen] loginWithToken succeeded. Navigating to /home.",
          );
          Navigator.of(
            context,
          ).pushNamedAndRemoveUntil('/home', (route) => false);
        } else {
          logger.i(
            "[AuthCallbackScreen] loginWithToken failed. Navigating to /login.",
          );
          Navigator.of(
            context,
          ).pushNamedAndRemoveUntil('/login', (route) => false);
        }
      } else {
        logger.i(
          "[AuthCallbackScreen] Token not extracted or is empty. Navigating to /login.",
        );
        if (mounted) {
          Navigator.of(
            context,
          ).pushNamedAndRemoveUntil('/login', (route) => false);
        }
      }
    } else {
      logger.i("[AuthCallbackScreen] Not running on web. Navigating to /login.");
      if (mounted) {
        Navigator.of(
          context,
        ).pushNamedAndRemoveUntil('/login', (route) => false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    // REMOVED ref.listen from build method. Navigation is handled by _handleAuthCallback.
    // MyApp in main.dart will ensure the correct screen is shown based on global AuthState.

    // Show a loading indicator while processing the token
    return const Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 20),
            Text('Processing authentication...'),
          ],
        ),
      ),
    );
  }
}
