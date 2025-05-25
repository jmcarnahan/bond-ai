import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/core/utils/logger.dart';

// Provider to control the visibility of the thread banner
final showThreadBannerProvider = StateProvider<bool>((ref) => true);

class RouteObserverForBanner extends NavigatorObserver {
  final WidgetRef _ref;

  RouteObserverForBanner(this._ref);

  void _updateBannerVisibility(RouteSettings settings) {
    String? routeName = settings.name;
    bool shouldShowBanner = true; // Default to true

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
      
      // Use null-aware operator and default to false if routeName is null
      if (routeName?.startsWith('/chat') ?? false) {
        shouldShowBanner = false;
      }
    } else {
      // If route name is null (e.g., initial unnamed route), typically show banner.
      // This case might need refinement if initial route shouldn't show banner.
      // For now, default to true.
      shouldShowBanner = true;
    }
    
    // Only update if the state changes to avoid unnecessary rebuilds
    if (_ref.read(showThreadBannerProvider) != shouldShowBanner) {
      _ref.read(showThreadBannerProvider.notifier).state = shouldShowBanner;
    }
    logger.i("[RouteObserverForBanner] Route: ${settings.name}, Path: $routeName, Show Banner: $shouldShowBanner");
  }

  @override
  void didPush(Route<dynamic> route, Route<dynamic>? previousRoute) {
    super.didPush(route, previousRoute);
    _updateBannerVisibility(route.settings);
  }

  @override
  void didPop(Route<dynamic> route, Route<dynamic>? previousRoute) {
    super.didPop(route, previousRoute);
    // When a route is popped, the previousRoute becomes the current one.
    if (previousRoute != null) {
      _updateBannerVisibility(previousRoute.settings);
    } else {
      // Popped to the very first route (no previousRoute), assume it's home-like.
      if (_ref.read(showThreadBannerProvider) != true) {
        _ref.read(showThreadBannerProvider.notifier).state = true;
      }
      logger.i("[RouteObserverForBanner] Popped to initial route. Show Banner: true");
    }
  }

  @override
  void didReplace({Route<dynamic>? newRoute, Route<dynamic>? oldRoute}) {
    super.didReplace(newRoute: newRoute, oldRoute: oldRoute);
    if (newRoute != null) {
      _updateBannerVisibility(newRoute.settings);
    }
  }
}
