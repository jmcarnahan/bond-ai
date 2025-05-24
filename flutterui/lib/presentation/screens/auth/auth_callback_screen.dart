import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/providers/auth_provider.dart';
import 'package:flutter/foundation.dart' show kIsWeb; // Import kIsWeb
// Import 'dart:html' to access window.location.href, only for web.
// Use conditional import to avoid errors on non-web platforms.
import 'dart:html' if (dart.library.io) 'dart:io' as html_stub;

class AuthCallbackScreen extends ConsumerStatefulWidget {
  const AuthCallbackScreen({super.key});

  @override
  ConsumerState<AuthCallbackScreen> createState() => _AuthCallbackScreenState();
}

class _AuthCallbackScreenState extends ConsumerState<AuthCallbackScreen> {
  @override
  void initState() {
    super.initState();
    // Use WidgetsBinding.instance.addPostFrameCallback to ensure context is available
    // and to process after the first frame has been built.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _handleAuthCallback();
    });
  }

  void _handleAuthCallback() async {
    // Made async
    print("[AuthCallbackScreen] _handleAuthCallback triggered.");
    if (kIsWeb) {
      // Use kIsWeb for a more robust check
      print("[AuthCallbackScreen] Running on web.");
      final String fullUrl = html_stub.window.location.href;
      print("[AuthCallbackScreen] Full URL: $fullUrl");

      final Uri? currentUri = Uri.tryParse(fullUrl);
      if (currentUri == null) {
        print(
          "[AuthCallbackScreen] Could not parse URI. Navigating to /login.",
        );
        if (mounted)
          Navigator.of(
            context,
          ).pushNamedAndRemoveUntil('/login', (route) => false);
        return;
      }
      print("[AuthCallbackScreen] Parsed URI: $currentUri");
      print("[AuthCallbackScreen] URI Fragment: ${currentUri.fragment}");

      String? token;
      if (currentUri.fragment.isNotEmpty) {
        final Uri fragmentUri = Uri.parse(
          'dummy://dummy${currentUri.fragment.startsWith('/') ? currentUri.fragment : '/${currentUri.fragment}'}',
        );
        print("[AuthCallbackScreen] Parsed Fragment URI: $fragmentUri");
        if (fragmentUri.pathSegments.contains('auth-callback') &&
            fragmentUri.queryParameters.containsKey('token')) {
          token = fragmentUri.queryParameters['token'];
        }
      }

      if (token == null && currentUri.queryParameters.containsKey('token')) {
        print(
          "[AuthCallbackScreen] Token found in main query parameters (not fragment).",
        );
        token = currentUri.queryParameters['token'];
      }
      print("[AuthCallbackScreen] Extracted Token: $token");

      if (token != null && token.isNotEmpty) {
        print(
          "[AuthCallbackScreen] Valid token found. Calling loginWithToken...",
        );
        final bool loginSuccess = await ref
            .read(authNotifierProvider.notifier)
            .loginWithToken(token);

        print(
          "[AuthCallbackScreen] loginWithToken returned: $loginSuccess, mounted: $mounted",
        ); // ADDED THIS LOG

        if (!mounted) {
          print(
            "[AuthCallbackScreen] Widget unmounted after loginWithToken. No navigation.",
          );
          return;
        }

        if (loginSuccess) {
          print(
            "[AuthCallbackScreen] loginWithToken succeeded. Navigating to /home.",
          );
          Navigator.of(
            context,
          ).pushNamedAndRemoveUntil('/home', (route) => false);
        } else {
          print(
            "[AuthCallbackScreen] loginWithToken failed. Navigating to /login.",
          );
          Navigator.of(
            context,
          ).pushNamedAndRemoveUntil('/login', (route) => false);
        }
      } else {
        print(
          "[AuthCallbackScreen] Token not extracted or is empty. Navigating to /login.",
        );
        if (mounted)
          Navigator.of(
            context,
          ).pushNamedAndRemoveUntil('/login', (route) => false);
      }
    } else {
      print("[AuthCallbackScreen] Not running on web. Navigating to /login.");
      if (mounted)
        Navigator.of(
          context,
        ).pushNamedAndRemoveUntil('/login', (route) => false);
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
