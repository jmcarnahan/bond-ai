import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/core/utils/logger.dart';
import 'package:flutterui/providers/auth_provider.dart';

final showThreadBannerProvider = StateProvider<bool>((ref) => false);

class RouteObserverForBanner extends NavigatorObserver {
  final WidgetRef _ref;

  RouteObserverForBanner(this._ref);

  void _updateBannerVisibility(RouteSettings settings) {
    // Delay the state update to avoid modifying providers during build
    WidgetsBinding.instance.addPostFrameCallback((_) {
      String? routeName = settings.name;
      bool shouldShowBanner = false;

      if (routeName != null) {
        if (routeName.startsWith('/#/')) {
          routeName = routeName.substring(2);
        }
        if (!routeName.startsWith('/')) {
          routeName = '/$routeName';
        }
        try {
          final Uri uri = Uri.parse(routeName);
          routeName = uri.path;
        } catch (e) {
          logger.w("[RouteObserverForBanner] Error parsing routeName '$routeName' for banner visibility: $e");
        }
      } else {
        routeName = '/';
      }

      if (routeName == '/home') {
        shouldShowBanner = true;
      } else if (routeName == '/') {
        final authState = _ref.read(authNotifierProvider);
        if (authState is Authenticated) {
          shouldShowBanner = true;
        }
      }

      if (_ref.read(showThreadBannerProvider) != shouldShowBanner) {
        _ref.read(showThreadBannerProvider.notifier).state = shouldShowBanner;
      }
    });
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
    if (previousRoute is PageRoute) {
      _updateBannerVisibility(previousRoute.settings);
    } else if (previousRoute == null && route is PageRoute) {
      if (_ref.read(showThreadBannerProvider)) {
        _ref.read(showThreadBannerProvider.notifier).state = false;
      }
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
