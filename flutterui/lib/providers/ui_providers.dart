import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/core/utils/logger.dart';
import 'package:flutterui/providers/auth_provider.dart'; // Added for auth state

// Provider to control the visibility of the thread banner
final showThreadBannerProvider = StateProvider<bool>((ref) => false); // Default to false

class RouteObserverForBanner extends NavigatorObserver {
  final WidgetRef _ref;

  RouteObserverForBanner(this._ref);

  void _updateBannerVisibility(RouteSettings settings) {
    String? routeName = settings.name;
    bool shouldShowBanner = false; // Default to false

    if (routeName != null) {
      // Normalize routeName (mirroring logic from main.dart's onGenerateRoute)
      if (routeName.startsWith('/#/')) {
        routeName = routeName.substring(2);
      }
      if (!routeName.startsWith('/')) {
        routeName = '/$routeName';
      }
      try {
        final Uri uri = Uri.parse(routeName);
        routeName = uri.path; // Get the path part
      } catch (e) {
        logger.w("[RouteObserverForBanner] Error parsing routeName '$routeName' for banner visibility: $e");
        // Keep original routeName if parsing fails, might still work for simple cases
      }
    } else {
      // If settings.name is null, Flutter's default initial route name is '/'.
      routeName = '/';
    }
      
    // Show banner ONLY on the HomeScreen
    // HomeScreen is active if route is '/home' or if initial route '/' and authenticated.
    if (routeName == '/home') {
      shouldShowBanner = true;
    } else if (routeName == '/') {
      final authState = _ref.read(authNotifierProvider);
      if (authState is Authenticated) {
        shouldShowBanner = true; // Initial route is HomeScreen when authenticated
      }
    }
    // For all other routes, shouldShowBanner remains false.
    
    // Only update if the state changes to avoid unnecessary rebuilds
    if (_ref.read(showThreadBannerProvider) != shouldShowBanner) {
      _ref.read(showThreadBannerProvider.notifier).state = shouldShowBanner;
    }
    logger.i("[RouteObserverForBanner] Route: ${settings.name}, Path: $routeName, Show Banner: $shouldShowBanner");
  }

  @override
  void didPush(Route<dynamic> route, Route<dynamic>? previousRoute) {
    super.didPush(route, previousRoute);
    if (route is PageRoute) {
      _updateBannerVisibility(route.settings);
    }
  }

  @override
  void didPop(Route<dynamic> route, Route<dynamic>? previousRoute) {
    super.didPop(route, previousRoute);
    // When a PageRoute is popped, the previousRoute (if also a PageRoute) becomes the current one.
    if (previousRoute is PageRoute) {
      _updateBannerVisibility(previousRoute.settings);
    } else if (previousRoute == null && route is PageRoute) {
      // This case implies we popped the last PageRoute.
      // If there's no previous route at all, or if it's not a PageRoute,
      // it means we are likely at the root or a non-page route context.
      // Banner should not be shown if the stack is effectively empty of PageRoutes.
      if (_ref.read(showThreadBannerProvider)) {
        _ref.read(showThreadBannerProvider.notifier).state = false;
      }
      logger.i("[RouteObserverForBanner] Popped last PageRoute or to a non-PageRoute. Show Banner: false");
    }
  }

  @override
  void didReplace({Route<dynamic>? newRoute, Route<dynamic>? oldRoute}) {
    super.didReplace(newRoute: newRoute, oldRoute: oldRoute);
    if (newRoute is PageRoute) {
      _updateBannerVisibility(newRoute.settings);
    }
  }
}
