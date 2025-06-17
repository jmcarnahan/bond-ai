import 'dart:async';
import 'package:app_links/app_links.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../providers/auth_provider.dart';
import '../utils/logger.dart';

class DeepLinkService {
  final AppLinks _appLinks = AppLinks();
  StreamSubscription<Uri>? _linkSubscription;
  
  void initDeepLinks(BuildContext context, WidgetRef ref) {
    logger.i('[DeepLinkService] Initializing deep links');
    
    // Handle initial link if app was launched from a deep link
    _handleInitialLink(context, ref);
    
    // Handle links when app is already running
    _linkSubscription = _appLinks.uriLinkStream.listen((uri) {
      logger.i('[DeepLinkService] Received link from stream: $uri');
      _handleDeepLink(uri, context, ref);
    }, onError: (error) {
      logger.e('[DeepLinkService] Error in link stream: $error');
    });
  }
  
  Future<void> _handleInitialLink(BuildContext context, WidgetRef ref) async {
    try {
      logger.i('[DeepLinkService] Checking for initial deep link');
      final initialUri = await _appLinks.getInitialLink();
      if (initialUri != null) {
        logger.i('[DeepLinkService] Found initial deep link: $initialUri');
        await _handleDeepLink(initialUri, context, ref);
      } else {
        logger.i('[DeepLinkService] No initial deep link found');
      }
    } catch (e) {
      logger.e('[DeepLinkService] Error handling initial link: $e');
    }
  }
  
  Future<void> _handleDeepLink(Uri uri, BuildContext context, WidgetRef ref) async {
    logger.i('[DeepLinkService] Received deep link: $uri');
    logger.i('[DeepLinkService] Scheme: ${uri.scheme}, Host: ${uri.host}');
    logger.i('[DeepLinkService] Query parameters: ${uri.queryParameters}');
    
    // Handle auth callback: bondai://auth-callback?token=xxx
    if (uri.scheme == 'bondai' && uri.host == 'auth-callback') {
      final token = uri.queryParameters['token'];
      logger.i('[DeepLinkService] Token extracted: ${token != null ? "Yes (${token.substring(0, 10)}...)" : "No"}');
      
      if (token != null && token.isNotEmpty) {
        logger.i('[DeepLinkService] Processing auth token from deep link');
        
        // Use the auth provider to login with the token
        final success = await ref.read(authNotifierProvider.notifier).loginWithToken(token);
        logger.i('[DeepLinkService] Login with token result: $success');
        
        if (success) {
          logger.i('[DeepLinkService] Authentication successful, handling navigation');
          
          // Give the auth state time to update
          await Future.delayed(const Duration(milliseconds: 100));
          
          // Navigate to home/main screen
          if (context.mounted) {
            try {
              // First try to pop any overlaying screens (like Safari view)
              if (Navigator.canPop(context)) {
                logger.i('[DeepLinkService] Popping current route');
                Navigator.of(context).popUntil((route) => route.isFirst);
              }
              
              // The auth state change should trigger navigation to MobileNavigationShell
              // automatically via MobileAuthWrapper
              logger.i('[DeepLinkService] Navigation handled by auth state change');
            } catch (e) {
              logger.e('[DeepLinkService] Navigation error: $e');
            }
          }
        } else {
          logger.e('[DeepLinkService] Login with token failed');
        }
      } else {
        logger.e('[DeepLinkService] No token found in auth callback');
      }
    } else {
      logger.w('[DeepLinkService] Unhandled deep link: $uri');
    }
  }
  
  void dispose() {
    _linkSubscription?.cancel();
  }
}