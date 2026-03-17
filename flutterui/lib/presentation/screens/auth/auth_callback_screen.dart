import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/providers/auth_provider.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:universal_html/html.dart' as html;
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
    logger.i("[AuthCallbackScreen] _handleAuthCallback triggered.");
    logger.i("[AuthCallbackScreen] Current route: ${ModalRoute.of(context)?.settings.name}");

    if (kIsWeb) {
      logger.i("[AuthCallbackScreen] Running on web.");
      final String fullUrl = html.window.location.href;
      logger.i("[AuthCallbackScreen] Full URL: $fullUrl");

      final Uri? currentUri = Uri.tryParse(fullUrl);
      if (currentUri == null) {
        logger.e(
          "[AuthCallbackScreen] Could not parse URI. Navigating to login.",
        );
        if (mounted) {
          _navigateTo('/login');
        }
        return;
      }
      logger.i("[AuthCallbackScreen] Parsed URI: $currentUri");
      logger.i("[AuthCallbackScreen] URI Query: ${currentUri.queryParameters}");
      logger.i("[AuthCallbackScreen] URI Fragment: ${currentUri.fragment}");

      // Extract code or token from URL parameters
      String? code;
      String? token;

      // Check fragment first (hash-based routing)
      if (currentUri.fragment.isNotEmpty) {
        final Uri fragmentUri = Uri.parse(
          'dummy://dummy${currentUri.fragment.startsWith('/') ? currentUri.fragment : '/${currentUri.fragment}'}',
        );
        logger.i("[AuthCallbackScreen] Parsed Fragment URI: $fragmentUri");
        if (fragmentUri.pathSegments.contains('auth-callback')) {
          code = fragmentUri.queryParameters['code'];
          token = fragmentUri.queryParameters['token'];
        }
      }

      // Fallback to main query parameters
      if (code == null && currentUri.queryParameters.containsKey('code')) {
        code = currentUri.queryParameters['code'];
      }
      if (token == null && currentUri.queryParameters.containsKey('token')) {
        token = currentUri.queryParameters['token'];
      }

      logger.i("[AuthCallbackScreen] Extracted code: ${code != null ? '(present)' : 'null'}, token: ${token != null ? '(present)' : 'null'}");

      if (code != null && code.isNotEmpty) {
        // New flow: exchange authorization code for token/session
        logger.i("[AuthCallbackScreen] Auth code found. Calling loginWithCode...");
        final bool loginSuccess = await ref
            .read(authNotifierProvider.notifier)
            .loginWithCode(code);

        // Clean the URL to prevent stale ?code= from triggering re-exchange on refresh.
        // With hash routing the fragment is replaced by navigation, but this is defensive
        // for non-hash routing paths (dev, mobile web).
        _cleanUrlQueryParams();

        logger.i("[AuthCallbackScreen] loginWithCode returned: $loginSuccess, mounted: $mounted");

        if (!mounted) return;
        _navigateTo(loginSuccess ? '/home' : '/login');
      } else if (token != null && token.isNotEmpty) {
        // Legacy flow: direct token (backward compatibility during rollout)
        logger.i("[AuthCallbackScreen] Legacy token found. Calling loginWithToken...");
        final bool loginSuccess = await ref
            .read(authNotifierProvider.notifier)
            .loginWithToken(token);

        // Clean legacy token from URL too
        _cleanUrlQueryParams();

        logger.i("[AuthCallbackScreen] loginWithToken returned: $loginSuccess, mounted: $mounted");

        if (!mounted) return;
        _navigateTo(loginSuccess ? '/home' : '/login');
      } else {
        logger.i("[AuthCallbackScreen] No code or token found. Navigating to login.");
        if (mounted) {
          _navigateTo('/login');
        }
      }
    } else {
      logger.i("[AuthCallbackScreen] Not running on web. Navigating to login.");
      if (mounted) {
        _navigateTo('/login');
      }
    }
  }

  void _cleanUrlQueryParams() {
    // Reset the browser URL to the origin root, stripping both the /auth-callback
    // pathname and any ?code= or ?token= query params. This prevents:
    // 1. Stale ?code= triggering re-exchange on refresh
    // 2. /auth-callback pathname persisting in the URL bar (e.g., /auth-callback#/home)
    // See: sbel-crm cookie-auth-migration.md Issue 1
    if (kIsWeb) {
      try {
        final cleanUrl = '${html.window.location.origin}/';
        html.window.history.replaceState(null, '', cleanUrl);
        logger.i("[AuthCallbackScreen] Cleaned URL to $cleanUrl");
      } catch (e) {
        // Best-effort — hash routing cleans the fragment anyway
        logger.w("[AuthCallbackScreen] Could not clean URL: $e");
      }
    }
  }

  void _navigateTo(String route) {
    try {
      Navigator.of(context).pushNamedAndRemoveUntil(route, (route) => false);
    } catch (e) {
      logger.e("[AuthCallbackScreen] Error navigating to $route: $e");
      Navigator.of(context).pushNamedAndRemoveUntil('/', (route) => false);
    }
  }

  @override
  Widget build(BuildContext context) {
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
